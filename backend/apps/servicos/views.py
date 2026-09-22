"""API de Manutenção corretiva — balanceamento dinâmico e economia energética."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza

from .analise_balanceamento import validar_servico_balanceamento
from .models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
)
from .relatorio_corretivo import payload_corretivo
from .serializers import (
    BalanceamentoPlanoSerializer,
    BalanceamentoPontoSerializer,
    EconomiaEnergeticaSerializer,
    ServicoCampoListSerializer,
    ServicoCampoSerializer,
)


def escopo_cliente(qs, user, campo_cliente="cliente"):
    """Perfis cliente só enxergam os próprios serviços (Portal — item 2.7)."""
    if user.is_cliente:
        return qs.filter(**{campo_cliente: user.cliente_id})
    return qs


class ServicoCampoViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        if instance.item_id:
            raise ValidationError("A análise vinculada à rota deve ser preservada.")
        super().perform_destroy(instance)

    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["cliente", "equipamento", "tipo", "analista", "relatorio", "osp"]
    search_fields = ["equipamento__tag", "equipamento__nome", "observacoes"]
    ordering_fields = ["data_execucao", "criado_em"]

    def get_queryset(self):
        qs = (
            ServicoCampo.objects.ativos()
            .select_related("cliente", "equipamento", "analista", "instrumento", "economia")
            .prefetch_related("planos", "pontos")
        )
        return escopo_cliente(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return ServicoCampoListSerializer
        return ServicoCampoSerializer

    @action(detail=True, methods=["get"])
    def relatorio(self, request, pk=None):
        """
        Payload pronto do relatório: os mesmos números da planilha, mais o que ela não
        dava — veredito ISO por ponto e as coordenadas do mostrador polar já calculadas
        (o front desenha o SVG, não refaz trigonometria).

        A montagem vive em `relatorio_corretivo` porque a folha da OSP no relatório
        técnico (`RelatorioViewSet.dossie`) consome exatamente os mesmos números.
        """
        return Response(payload_corretivo(self.get_object()))


class BalanceamentoPlanoViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        validar_servico_balanceamento(instance.servico)
        super().perform_destroy(instance)

    serializer_class = BalanceamentoPlanoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["servico"]

    def get_queryset(self):
        qs = BalanceamentoPlano.objects.ativos().select_related("servico")
        return escopo_cliente(qs, self.request.user, "servico__cliente")


class BalanceamentoPontoViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        validar_servico_balanceamento(instance.servico)
        super().perform_destroy(instance)

    serializer_class = BalanceamentoPontoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["servico", "plano", "direcao"]

    def get_queryset(self):
        qs = BalanceamentoPonto.objects.ativos().select_related(
            "servico", "servico__equipamento", "plano"
        )
        return escopo_cliente(qs, self.request.user, "servico__cliente")


class EconomiaEnergeticaViewSet(viewsets.ModelViewSet):
    serializer_class = EconomiaEnergeticaSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["servico"]

    def get_queryset(self):
        qs = EconomiaEnergetica.objects.ativos().select_related("servico")
        return escopo_cliente(qs, self.request.user, "servico__cliente")
