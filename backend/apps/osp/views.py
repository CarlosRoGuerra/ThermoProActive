from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteResponde, IsInterno
from apps.coletas.views import escopo_cliente

from .models import OrdemServico
from .serializers import OrdemServicoSerializer, StatusUpdateSerializer


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
            "cliente", "equipamento", "responsavel",
            "achado__item__carregamento__relatorio",
        )
        return escopo_cliente(qs, self.request.user)

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

    @action(detail=True, methods=["patch"], permission_classes=[IsInterno])
    def status(self, request, pk=None):
        """
        Atualiza o status da OSP — fluxo do item 2.6.3.

        Restrito à equipe interna: o status é a leitura que a CONTRATADA faz do
        andamento. O cliente informa as DATAS e o que foi feito (campos de
        retorno); quem move a OSP de coluna, a partir disso, é a equipe.
        """
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
