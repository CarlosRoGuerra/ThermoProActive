from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza, IsInterno, IsMaster
from apps.coletas.models import Inspecao, Relatorio
from apps.coletas.views import escopo_cliente

from .models import Laudo, StatusLaudo, TemplateLaudo, EventoLaudo
from .relatorio import montar_relatorio_tecnico
from .serializers import GerarLaudoSerializer, LaudoSerializer, MotivoLaudoSerializer, TemplateLaudoSerializer, EventoLaudoSerializer, AnexoLaudoSerializer
from .services import gerar_laudo_de_inspecao, emitir_laudo, revisar_laudo, cancelar_laudo


class LaudoViewSet(viewsets.ModelViewSet):
    serializer_class = LaudoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["status", "criticidade_geral", "inspecao", "inspecao__cliente"]
    search_fields = ["numero", "titulo"]

    def get_queryset(self):
        qs = Laudo.objects.select_related("cliente_documento", "inspecao__cliente", "relatorio_origem__cliente", "relatorio_origem__tecnologia", "responsavel", "template")
        # Cliente só vê laudos emitidos da própria empresa (Portal — item 2.7).
        if self.request.user.is_cliente:
            if not self.request.user.cliente_id:
                return qs.none()
            qs = qs.filter(Q(status=StatusLaudo.EMITIDO) | Q(status=StatusLaudo.CANCELADO, data_emissao__isnull=False)).filter(
                Q(cliente_documento_id=self.request.user.cliente_id) | (Q(cliente_documento__isnull=True) & (
                    Q(inspecao__cliente_id=self.request.user.cliente_id) | Q(relatorio_origem__cliente_id=self.request.user.cliente_id))))
        return qs

    @transaction.atomic
    def perform_create(self, serializer):
        laudo = serializer.save()
        EventoLaudo.objects.create(laudo=laudo, acao="CRIADO", autor=self.request.user)

    @transaction.atomic
    def perform_update(self, serializer):
        anterior = Laudo.objects.select_for_update().get(pk=serializer.instance.pk)
        if anterior.status != StatusLaudo.RASCUNHO:
            raise ValidationError("Documento emitido/cancelado é imutável. Crie uma revisão.")
        dados = {campo: str(getattr(anterior, campo)) for campo in serializer.validated_data}
        laudo = serializer.save()
        EventoLaudo.objects.create(laudo=laudo, acao="EDITADO", autor=self.request.user, dados={"antes": dados})

    def perform_destroy(self, instance):
        raise ValidationError("Preserve o histórico documental. Use o cancelamento com motivo.")

    @action(detail=False, methods=["post"], permission_classes=[IsInterno])
    def gerar(self, request):
        """Gera automaticamente um laudo a partir de uma inspeção (item 2.5.1.1)."""
        serializer = GerarLaudoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if "inspecao" in serializer.validated_data:
            inspecao = get_object_or_404(Inspecao, pk=serializer.validated_data["inspecao"])
            laudo = gerar_laudo_de_inspecao(inspecao, responsavel=request.user)
        else:
            relatorio = get_object_or_404(Relatorio.objects.ativos(), pk=serializer.validated_data["relatorio_origem"])
            from apps.coletas.relatorio_tecnico import modulo_da_tecnologia, ModuloIndisponivel
            try:
                modulo_da_tecnologia(relatorio.tecnologia)
            except ModuloIndisponivel as erro:
                raise ValidationError(erro.mensagem)
            with transaction.atomic():
                laudo = Laudo.objects.create(relatorio_origem=relatorio, responsavel=request.user,
                    titulo=f"Laudo de {relatorio.tecnologia.nome} — {relatorio.cliente.nome}",
                    conclusao="Rascunho gerado do relatório de rotas. A conclusão exige revisão técnica.")
                EventoLaudo.objects.create(laudo=laudo, acao="GERADO", autor=request.user)
        return Response(LaudoSerializer(laudo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="relatorio-tecnico")
    def relatorio_tecnico(self, request, pk=None):
        """
        Payload completo do Relatório Técnico (capa + seções A, C e D).
        O front renderiza em HTML paginado e o usuário imprime em PDF.
        """
        laudo = self.get_object()
        if laudo.status != StatusLaudo.RASCUNHO and not laudo.snapshot_emissao:
            raise ValidationError("Documento legado sem snapshot. O original precisa ser preservado e saneado; não será reconstruído com dados atuais.")
        if laudo.status == StatusLaudo.RASCUNHO:
            from .snapshots import montar_snapshot
            return Response(montar_snapshot(laudo, request)["relatorio"])
        return Response(montar_relatorio_tecnico(laudo, request))

    @action(detail=True, methods=["get"])
    def documento(self, request, pk=None):
        """Prévia declarativa em rascunho; envelope emitido permanece congelado."""
        from .snapshots import montar_snapshot, hash_snapshot
        laudo = self.get_object()
        if laudo.snapshot_emissao:
            if hash_snapshot(laudo.snapshot_emissao) != laudo.snapshot_hash:
                raise ValidationError("A integridade do snapshot não confere. Acione o responsável pelo acervo.")
            return Response(laudo.snapshot_emissao)
        if laudo.status != StatusLaudo.RASCUNHO:
            raise ValidationError("Documento legado sem snapshot; o original exige saneamento.")
        return Response(montar_snapshot(laudo, request))

    @action(detail=True, methods=["get"])
    def previa(self, request, pk=None):
        return self.documento(request, pk)

    @action(detail=True, methods=["post"], permission_classes=[IsInterno])
    def emitir(self, request, pk=None):
        """Emite o laudo (assinatura/responsável técnico) — item 2.5.1.3."""
        laudo, _ = emitir_laudo(self.get_object(), request.user, request)
        return Response(LaudoSerializer(laudo).data)

    @action(detail=True, methods=["post"], permission_classes=[IsInterno])
    def revisar(self, request, pk=None):
        dados = MotivoLaudoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        laudo, criado = revisar_laudo(self.get_object(), request.user, dados.validated_data["motivo"])
        return Response(LaudoSerializer(laudo).data, status=status.HTTP_201_CREATED if criado else status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[IsInterno])
    def cancelar(self, request, pk=None):
        dados = MotivoLaudoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        laudo = cancelar_laudo(self.get_object(), request.user, dados.validated_data["motivo"])
        return Response(LaudoSerializer(laudo).data)

    @action(detail=True, methods=["get"])
    def versoes(self, request, pk=None):
        laudo = self.get_object()
        raiz_id = laudo.documento_raiz_id or laudo.pk
        versoes = self.get_queryset().filter(Q(pk=raiz_id) | Q(documento_raiz_id=raiz_id)).order_by("versao")
        return Response(LaudoSerializer(versoes, many=True).data)

    @action(detail=True, methods=["get"])
    def eventos(self, request, pk=None):
        laudo = self.get_object()
        return Response(EventoLaudoSerializer(laudo.eventos.select_related("autor"), many=True).data)

    @action(detail=True, methods=["get"])
    def historico(self, request, pk=None):
        return self.eventos(request, pk)

    @action(detail=True, methods=["get", "post"])
    def anexos(self, request, pk=None):
        from django.conf import settings
        from django.db.models import Sum
        laudo = self.get_object()
        if request.method == "GET":
            return Response(AnexoLaudoSerializer(laudo.anexos.all(), many=True).data)
        dados = AnexoLaudoSerializer(data=request.data)
        dados.is_valid(raise_exception=True)
        with transaction.atomic():
            laudo = Laudo.objects.select_for_update().get(pk=laudo.pk)
            if laudo.status != StatusLaudo.RASCUNHO:
                raise ValidationError("Somente rascunhos podem receber novas evidências. Crie uma revisão.")
            total = laudo.anexos.aggregate(total=Sum("tamanho"))["total"] or 0
            if total + dados.validated_data["imagem"].size > int(getattr(settings, "LAUDOS_MAX_IMAGENS_BYTES", 40 * 1024 * 1024)):
                raise ValidationError("O conjunto de imagens excede o limite operacional configurado.")
            anexo = dados.save(laudo=laudo, criado_por=request.user)
            EventoLaudo.objects.create(laudo=laudo, acao="ANEXO_ADICIONADO", autor=request.user,
                                       dados={"anexo_id": anexo.pk, "sha256": anexo.sha256, "legenda": anexo.legenda})
        return Response(AnexoLaudoSerializer(anexo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"anexos/(?P<anexo_id>[^/.]+)")
    def remover_anexo(self, request, pk=None, anexo_id=None):
        laudo = self.get_object()
        with transaction.atomic():
            laudo = Laudo.objects.select_for_update().get(pk=laudo.pk)
            if laudo.status != StatusLaudo.RASCUNHO:
                raise ValidationError("Evidências de documento emitido/cancelado são imutáveis.")
            anexo = get_object_or_404(laudo.anexos.all(), pk=anexo_id)
            EventoLaudo.objects.create(laudo=laudo, acao="ANEXO_REMOVIDO", autor=request.user,
                                       dados={"anexo_id": anexo.pk, "sha256": anexo.sha256, "legenda": anexo.legenda})
            anexo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"])
    def pdf(self, request, pk=None):
        import hashlib
        laudo = self.get_object()
        if laudo.status == StatusLaudo.RASCUNHO or not laudo.pdf_disponivel:
            raise ValidationError("PDF emitido indisponível. Emita o rascunho ou saneie o documento legado.")
        conteudo = bytes(laudo.pdf_conteudo)
        if hashlib.sha256(conteudo).hexdigest() != laudo.pdf_hash:
            raise ValidationError("A integridade do PDF não confere. Acione o responsável pelo acervo.")
        resposta = HttpResponse(conteudo, content_type="application/pdf")
        resposta["Content-Disposition"] = f'attachment; filename="{laudo.numero}.pdf"'
        resposta["Cache-Control"] = "private, no-store"
        resposta["X-Content-SHA256"] = laudo.pdf_hash
        if laudo.status == StatusLaudo.CANCELADO:
            resposta["X-Documento-Status"] = "CANCELADO"
        return resposta


class TemplateLaudoViewSet(viewsets.ModelViewSet):
    queryset = TemplateLaudo.objects.select_related("cliente")
    serializer_class = TemplateLaudoSerializer
    permission_classes = [IsInterno]
    filterset_fields = ["cliente", "tipo_analise", "ativo"]

    def get_permissions(self):
        return [IsInterno()] if self.request.method in ("GET", "HEAD", "OPTIONS") else [IsMaster()]

    def perform_destroy(self, instance):
        raise ValidationError("Desative o template para preservar as referências documentais.")
