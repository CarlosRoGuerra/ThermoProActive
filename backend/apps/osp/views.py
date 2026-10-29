from rest_framework import status as http
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteResponde
from apps.coletas.views import escopo_cliente

from . import services
from .models import OrdemServico
from .serializers import HistoricoOSPSerializer, OrdemServicoSerializer, StatusUpdateSerializer


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
        return escopo_cliente(qs, self.request.user)

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

    @action(detail=True, methods=["get"])
    def historico(self, request, pk=None):
        """Trilha completa da OSP, do mais antigo ao mais recente (2.6.2.3)."""
        osp = self.get_object()
        return Response(HistoricoOSPSerializer(osp.historico.all(), many=True).data)
