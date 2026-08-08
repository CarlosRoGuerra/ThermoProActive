from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza
from apps.coletas.views import escopo_cliente

from .models import OrdemServico
from .serializers import OrdemServicoSerializer, StatusUpdateSerializer


class OrdemServicoViewSet(viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["status", "prioridade", "cliente", "equipamento", "gerada_automaticamente"]
    search_fields = ["numero", "titulo", "descricao"]
    ordering_fields = ["criado_em", "sla_data", "prioridade"]

    def get_queryset(self):
        qs = OrdemServico.objects.select_related(
            "cliente", "equipamento", "responsavel",
            "achado__item__carregamento__relatorio",
        )
        return escopo_cliente(qs, self.request.user)

    @action(detail=True, methods=["patch"])
    def status(self, request, pk=None):
        """Atualiza o status da OSP — fluxo do item 2.6.3."""
        osp = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        novo_status = serializer.validated_data["status"]
        osp.status = novo_status
        osp.save()

        # Notifica aprovadores quando entra em aprovação (Anexo I 2.10.2.5).
        if novo_status == "AGUARDANDO_APROVACAO":
            from apps.notificacoes.models import EventoNotificacao, Nivel
            from apps.notificacoes.services import aprovadores_do_cliente, notificar

            notificar(
                EventoNotificacao.APROVACAO_PENDENTE,
                aprovadores_do_cliente(osp.cliente),
                titulo=f"Aprovação pendente: OSP {osp.numero}",
                mensagem=f"A OSP {osp.numero} ({osp.equipamento.tag}) aguarda sua aprovação.",
                url="/osps",
                nivel=Nivel.ALERTA,
            )
        return Response(OrdemServicoSerializer(osp).data)
