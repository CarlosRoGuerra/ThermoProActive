from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza, IsInterno
from apps.coletas.models import Inspecao
from apps.coletas.views import escopo_cliente

from .models import Laudo, StatusLaudo
from .serializers import GerarLaudoSerializer, LaudoSerializer
from .services import gerar_laudo_de_inspecao


class LaudoViewSet(viewsets.ModelViewSet):
    serializer_class = LaudoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["status", "criticidade_geral", "inspecao", "inspecao__cliente"]
    search_fields = ["numero", "titulo"]

    def get_queryset(self):
        qs = Laudo.objects.select_related("inspecao__cliente", "responsavel")
        # Cliente só vê laudos emitidos da própria empresa (Portal — item 2.7).
        if self.request.user.is_cliente:
            qs = qs.filter(status=StatusLaudo.EMITIDO)
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")

    @action(detail=False, methods=["post"], permission_classes=[IsInterno])
    def gerar(self, request):
        """Gera automaticamente um laudo a partir de uma inspeção (item 2.5.1.1)."""
        serializer = GerarLaudoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        inspecao = get_object_or_404(Inspecao, pk=serializer.validated_data["inspecao"])
        laudo = gerar_laudo_de_inspecao(inspecao, responsavel=request.user)
        return Response(LaudoSerializer(laudo).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[IsInterno])
    def emitir(self, request, pk=None):
        """Emite o laudo (assinatura/responsável técnico) — item 2.5.1.3."""
        laudo = self.get_object()
        if not request.user.conselho_classe:
            return Response(
                {"detail": "Responsável sem Conselho de Classe cadastrado para assinar o laudo."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        laudo.emitir()

        # Notifica o cliente (Anexo I 2.10.2.3 — Laudo concluído).
        from apps.notificacoes.models import EventoNotificacao, Nivel
        from apps.notificacoes.services import clientes_do_cliente, notificar

        notificar(
            EventoNotificacao.LAUDO_CONCLUIDO,
            clientes_do_cliente(laudo.inspecao.cliente),
            titulo=f"Laudo {laudo.numero} disponível",
            mensagem=f"O laudo '{laudo.titulo}' foi emitido e está disponível para consulta.",
            url=f"/laudos/{laudo.id}",
            nivel=Nivel.INFO,
        )
        return Response(LaudoSerializer(laudo).data)
