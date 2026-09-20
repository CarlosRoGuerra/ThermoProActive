from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import InternoOuClienteMasterEdita
from apps.coletas.views import escopo_cliente

from .models import OrdemServico
from .serializers import OrdemServicoSerializer, StatusUpdateSerializer


class OrdemServicoViewSet(viewsets.ModelViewSet):
    serializer_class = OrdemServicoSerializer
    # Master do cliente também cria/edita/exclui e muda status (decisão de
    # 2026-09-18) — antes só a equipe interna escrevia aqui.
    permission_classes = [InternoOuClienteMasterEdita]
    filterset_fields = ["status", "prioridade", "cliente", "equipamento", "gerada_automaticamente"]
    search_fields = ["numero", "titulo", "descricao"]
    ordering_fields = ["criado_em", "sla_data", "prioridade"]

    def get_queryset(self):
        qs = OrdemServico.objects.select_related(
            "cliente", "equipamento", "responsavel",
            "achado__item__carregamento__relatorio",
        )
        return escopo_cliente(qs, self.request.user)

    def _impedir_cruzar_cliente(self, validated_data):
        """
        `get_queryset()` só protege OSP que já existe. Sem isto, o Master de um
        cliente poderia criar (ou reatribuir) uma OSP com `cliente` de outra
        empresa, ou com `equipamento` de outra empresa — inclusive vazando o TAG
        do equipamento alheio de volta na resposta.
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
