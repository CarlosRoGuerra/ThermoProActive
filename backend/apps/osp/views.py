import base64
import binascii

from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import mixins
from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteResponde, InternoEditaClienteVisualiza
from apps.accounts.security import ip_do_cliente
from apps.coletas.views import escopo_cliente
from apps.core.escopo import restringe_setor

from . import execucao, services
from .models import (
    ApontamentoExecucao,
    AssinaturaOSP,
    EvidenciaOSP,
    ItemModeloChecklist,
    ModeloChecklist,
    OrdemServico,
    PecaOSP,
)
from .serializers import (
    ApontamentoExecucaoSerializer,
    AssinaturaOSPSerializer,
    EvidenciaOSPSerializer,
    HistoricoOSPSerializer,
    ItemModeloChecklistSerializer,
    ModeloChecklistSerializer,
    OrdemServicoSerializer,
    PecaOSPSerializer,
    StatusUpdateSerializer,
)


#: Valores de `OrdemServico.criticidade_origem` (ver `services.CRITICIDADE_PARA_PRIORIDADE`).
CRITICIDADES_ORIGEM = ("CRITICO", "ALERTA", "NORMAL")


class OrdemServicoViewSet(viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    # Único recurso em que o Portal escreve: o cliente devolve as informações
    # da execução (PATCH), mas não abre nem apaga OSP (decisão de 2026-09-21).
    # QUAIS campos ele pode tocar está em
    # `OrdemServicoSerializer.CAMPOS_RETORNO_CLIENTE`.
    permission_classes = [InternoEditaClienteResponde]
    filterset_fields = ["status", "prioridade", "cliente", "equipamento", "gerada_automaticamente"]
    search_fields = ["numero", "titulo", "descricao"]
    ordering_fields = ["criado_em", "sla_data", "prioridade"]

    def get_queryset(self):
        qs = OrdemServico.objects.select_related(
            "cliente", "equipamento", "responsavel", "aprovado_por",
            "achado__item__carregamento__relatorio",
        ).prefetch_related("achado__imagens")
        # `?sla_vencido=true`: só as abertas fora do prazo (o painel e o filtro
        # usam a mesma definição de `OrdemServico.sla_vencido`).
        if str(self.request.query_params.get("sla_vencido", "")).lower() in ("1", "true", "sim"):
            qs = qs.com_sla_vencido()
        # `?criticidade_origem=CRITICO`: drill-down do painel (Visão geral → "Crítico").
        # Valor fora da lista é 400 (não "lista vazia", que esconderia o erro de digitação).
        criticidade = self.request.query_params.get("criticidade_origem")
        if criticidade:
            if criticidade not in CRITICIDADES_ORIGEM:
                raise ValidationError({"criticidade_origem": "Use CRITICO, ALERTA ou NORMAL."})
            qs = qs.filter(criticidade_origem=criticidade)
        # 2.1.1.6: restrição de setor do usuário de cliente (sem restrição = cliente inteiro).
        return restringe_setor(escopo_cliente(qs, self.request.user), self.request.user, "equipamento__setor")

    def handle_exception(self, exc):
        # Violação de regra do fluxo (transição inválida, sem permissão, ...)
        # vira resposta estruturada com `codigo`, venha da view ou do serializer.
        if isinstance(exc, services.ErroOSP):
            return Response({"detail": exc.mensagem, "codigo": exc.codigo}, status=exc.http)
        return super().handle_exception(exc)

    def _impedir_cruzar_cliente(self, validated_data):
        """
        Segunda tranca de `cliente`/`equipamento`.

        Hoje ela não tem por onde disparar: o cliente não cria OSP, e os dois
        campos saem somente-leitura para ele em `OrdemServicoSerializer`. Fica
        de propósito — é a guarda que impede reatribuir uma OSP para outra
        empresa (e vazar o TAG alheio na resposta) se a regra de escrita voltar
        a afrouxar, como já afrouxou uma vez.
        """
        user = self.request.user
        if not (user.is_cliente and user.cliente_id):
            return
        cliente = validated_data.get("cliente")
        if cliente is not None and cliente.pk != user.cliente_id:
            raise ValidationError({"cliente": "Isso não pertence à sua empresa."})
        equipamento = validated_data.get("equipamento")
        if equipamento is not None and not equipamento.__class__.objects.filter(
            pk=equipamento.pk, setor__area__cliente_id=user.cliente_id
        ).exists():
            raise ValidationError({"equipamento": "Isso não pertence à sua empresa."})

    def perform_create(self, serializer):
        self._impedir_cruzar_cliente(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._impedir_cruzar_cliente(serializer.validated_data)
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        # A OSP é registro de auditoria (histórico, SLA, custos): não se apaga,
        # se CANCELA — o histórico permanece.
        self.get_object()
        return Response(
            {"detail": "OSP não é excluída: use o cancelamento (o histórico é preservado).",
             "codigo": "exclusao_nao_permitida"},
            status=http.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated])
    def status(self, request, pk=None):
        """
        Move a OSP de status — fluxo do item 2.6.3.

        Corpo: `{"status": "...", "motivo": "..."}` (motivo obrigatório para
        cancelar, reabrir e rejeitar a aprovação). A regra e a permissão por
        perfil moram em `services.transicionar`; aqui só se traduz a resposta:
        409 transição inválida · 403 sem permissão · 400 sem motivo.
        """
        osp = self.get_object()  # já escopado por cliente (404 fora do escopo)
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        osp, alterou = services.transicionar(
            osp.pk, serializer.validated_data["status"], request.user,
            serializer.validated_data.get("motivo", ""),
        )
        dados = OrdemServicoSerializer(
            self.get_queryset().get(pk=osp.pk), context=self.get_serializer_context()
        ).data
        return Response({**dados, "alterado": alterou})

    @action(detail=True, methods=["get", "post"], url_path="checklist")
    def checklist(self, request, pk=None):
        """
        2.6.2.2 — GET: modelos aplicáveis com itens e respostas. POST (equipe técnica):
        `{"respostas": [{"item": id, "situacao": "CONFORME|NAO_CONFORME|NAO_SE_APLICA",
        "observacao": "..."}]}`. Cliente só lê; não responde o checklist técnico.
        """
        osp = self.get_object()
        if request.method == "GET":
            return Response({"modelos": execucao.checklist_da_osp(osp),
                             "pendencias": execucao.pendencias_checklist(osp)})
        if request.user.perfil not in services.INTERNOS_OPERAM:
            return Response({"detail": "Seu perfil não responde o checklist.", "codigo": "sem_permissao"},
                            status=http.HTTP_403_FORBIDDEN)
        respostas = request.data.get("respostas")
        if not isinstance(respostas, list):
            return Response({"detail": "Envie a lista `respostas`.", "codigo": "dados_invalidos"},
                            status=http.HTTP_400_BAD_REQUEST)
        try:
            with transaction.atomic():
                gravadas = execucao.responder_checklist(osp, respostas, request.user)
        except execucao.ErroExecucao as exc:
            return Response({"detail": exc.mensagem, "codigo": exc.codigo}, status=exc.http)
        return Response({"gravadas": gravadas, "modelos": execucao.checklist_da_osp(osp),
                         "pendencias": execucao.pendencias_checklist(osp)})

    @action(detail=True, methods=["get"])
    def historico(self, request, pk=None):
        """Trilha completa da OSP, do mais antigo ao mais recente (2.6.2.3)."""
        osp = self.get_object()
        return Response(HistoricoOSPSerializer(osp.historico.all(), many=True).data)


# --- 2.6.2.2 a 2.6.2.8 -------------------------------------------------------

class SomenteMasterGerencia(BasePermission):
    """Catálogo de checklist: leitura para a equipe interna; escrita só Master."""

    message = "Somente o Master gerencia os modelos de checklist."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated and user.is_interno):
            return False
        return request.method in ("GET", "HEAD", "OPTIONS") or user.is_master


class ClienteAprovadorAssina(BasePermission):
    """Assinatura do cliente (2.6.2.6): só perfis que aprovam a execução, do próprio cliente."""

    message = "Seu perfil não pode assinar a OSP."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and user.is_cliente
            and user.perfil in services.CLIENTE_APROVADORES
        )


class _ErroHTTP(Exception):
    """Carrega um ErroExecucao até o handle_exception da view."""

    def __init__(self, erro):
        super().__init__(erro.mensagem)
        self.erro = erro


def _erro_execucao(exc):
    return Response({"detail": exc.mensagem, "codigo": exc.codigo}, status=exc.http)


class _TraduzErroExecucaoMixin:
    def handle_exception(self, exc):
        if isinstance(exc, _ErroHTTP):
            return _erro_execucao(exc.erro)
        return super().handle_exception(exc)


class ModeloChecklistViewSet(viewsets.ModelViewSet):
    """Modelos de checklist (2.6.2.2) — cadastrados pelo Master, por tecnologia/tipo."""

    serializer_class = ModeloChecklistSerializer
    permission_classes = [SomenteMasterGerencia]
    filterset_fields = ["ativo", "tecnologia", "tipo_equipamento"]

    def get_queryset(self):
        return ModeloChecklist.objects.prefetch_related("itens").select_related("tecnologia", "tipo_equipamento")

    def destroy(self, request, *args, **kwargs):
        # Modelo já usado em alguma OSP não some: desativa (o histórico das OSPs permanece).
        modelo = self.get_object()
        if modelo.itens.filter(respostas__isnull=False).exists():
            modelo.ativo = False
            modelo.save(update_fields=["ativo"])
            return Response(status=http.HTTP_204_NO_CONTENT)
        return super().destroy(request, *args, **kwargs)


class ItemModeloChecklistViewSet(viewsets.ModelViewSet):
    serializer_class = ItemModeloChecklistSerializer
    permission_classes = [SomenteMasterGerencia]
    filterset_fields = ["modelo"]
    queryset = ItemModeloChecklist.objects.all()

    def destroy(self, request, *args, **kwargs):
        if self.get_object().respostas.exists():
            raise ValidationError({"detail": "Item já respondido em alguma OSP: desative o modelo em vez de apagar o item."})
        return super().destroy(request, *args, **kwargs)


class PecaOSPViewSet(_TraduzErroExecucaoMixin, viewsets.ModelViewSet):
    """Peças e materiais aplicados (2.6.2.7). Interno lança; cliente só lê as da própria OSP."""

    serializer_class = PecaOSPSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["osp"]

    def get_queryset(self):
        return restringe_setor(escopo_cliente(PecaOSP.objects.select_related("osp"), self.request.user, campo_cliente="osp__cliente"), self.request.user, "osp__equipamento__setor")

    def perform_create(self, serializer):
        dados = {k: v for k, v in serializer.validated_data.items() if k != "osp"}
        try:
            serializer.instance = execucao.registrar_peca(serializer.validated_data["osp"], dados, self.request.user)
        except execucao.ErroExecucao as exc:
            raise _ErroHTTP(exc)

    def perform_update(self, serializer):
        raise ValidationError({"detail": "Remova e lance a peça de novo: a alteração fica no histórico."})

    def perform_destroy(self, instance):
        try:
            execucao.remover_peca(instance, self.request.user)
        except execucao.ErroExecucao as exc:
            raise _ErroHTTP(exc)


class EvidenciaOSPViewSet(_TraduzErroExecucaoMixin, viewsets.ModelViewSet):
    """Fotos antes/durante/depois direto na OSP (2.6.2.4)."""

    serializer_class = EvidenciaOSPSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["osp", "fase"]

    def get_queryset(self):
        return restringe_setor(escopo_cliente(EvidenciaOSP.objects.select_related("osp"), self.request.user,
                              campo_cliente="osp__cliente"), self.request.user, "osp__equipamento__setor")

    def perform_create(self, serializer):
        if serializer.validated_data["osp"].status in execucao.ESTADOS_ENCERRADOS:
            raise _ErroHTTP(execucao.ErroExecucao("OSP encerrada: reabra-a para anexar fotos.",
                                                   codigo="osp_encerrada", http=409))
        serializer.save(enviado_por=self.request.user)

    def perform_update(self, serializer):
        # Só fase e legenda mudam; a foto é trocada apagando e enviando outra.
        if "arquivo" in serializer.validated_data:
            raise ValidationError({"arquivo": "Apague esta foto e envie outra."})
        serializer.save()

    def perform_destroy(self, instance):
        armazenamento, nome = instance.arquivo.storage, instance.arquivo.name
        instance.delete()
        transaction.on_commit(lambda: armazenamento.delete(nome) if nome else None)


class ApontamentoExecucaoViewSet(_TraduzErroExecucaoMixin, mixins.CreateModelMixin,
                                 mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Tempo de execução (2.6.2.8): leitura para quem enxerga a OSP; apontamento manual pela equipe."""

    serializer_class = ApontamentoExecucaoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["osp", "origem"]

    def get_queryset(self):
        return restringe_setor(escopo_cliente(ApontamentoExecucao.objects.select_related("osp"), self.request.user,
                              campo_cliente="osp__cliente"), self.request.user, "osp__equipamento__setor")

    def perform_create(self, serializer):
        dados = serializer.validated_data
        try:
            serializer.instance = execucao.apontar_tempo(
                dados["osp"], dados["inicio"], dados["fim"], dados.get("observacao", ""), self.request.user,
            )
        except execucao.ErroExecucao as exc:
            raise _ErroHTTP(exc)


class AssinaturaOSPViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Assinatura do cliente (2.6.2.6). Criação: POST com `osp`, `nome`, `cargo` e
    `assinatura_png` (PNG em base64, desenhado no canvas do Portal). Imutável.
    """

    serializer_class = AssinaturaOSPSerializer
    filterset_fields = ["osp"]

    def get_permissions(self):
        if self.action == "create":
            return [ClienteAprovadorAssina()]
        return [InternoEditaClienteVisualiza()]

    def get_queryset(self):
        return restringe_setor(escopo_cliente(AssinaturaOSP.objects.select_related("osp").order_by("-assinado_em", "id"), self.request.user,
                              campo_cliente="osp__cliente"), self.request.user, "osp__equipamento__setor")

    def create(self, request, *args, **kwargs):
        osp_id = request.data.get("osp")
        nome = (request.data.get("nome") or "").strip()
        cargo = (request.data.get("cargo") or "").strip()
        bruto = request.data.get("assinatura_png") or ""
        if not (osp_id and nome and cargo and bruto):
            return Response({"detail": "Informe OSP, nome, cargo e a assinatura.", "codigo": "dados_incompletos"},
                            status=http.HTTP_400_BAD_REQUEST)
        if bruto.lstrip().startswith("data:") and "," in bruto:
            bruto = bruto.split(",", 1)[1]
        try:
            png = base64.b64decode(bruto, validate=True)
            execucao.validar_assinatura_png(png)
        except (binascii.Error, ValueError) as erro:
            return Response({"detail": str(erro) or "Assinatura inválida.", "codigo": "assinatura_invalida"},
                            status=http.HTTP_400_BAD_REQUEST)
        # OSP de outro cliente = 404, sem confirmar que existe.
        osp = get_object_or_404(
            restringe_setor(escopo_cliente(OrdemServico.objects.all(), request.user, campo_cliente="cliente"),
                            request.user, "equipamento__setor"),
            pk=osp_id,
        )
        try:
            with transaction.atomic():
                bloqueada = OrdemServico.objects.select_for_update().get(pk=osp.pk)
                assinatura = execucao.registrar_assinatura(
                    bloqueada, request.user, nome=nome, cargo=cargo, ip=ip_do_cliente(request), png=png,
                )
        except execucao.ErroExecucao as exc:
            return _erro_execucao(exc)
        return Response(AssinaturaOSPSerializer(assinatura).data, status=http.HTTP_201_CREATED)
