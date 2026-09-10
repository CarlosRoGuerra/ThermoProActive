"""API de Manutenção corretiva — balanceamento dinâmico e economia energética."""
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza

from . import rules
from .analise_balanceamento import validar_servico_balanceamento
from .models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
)
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
        """
        servico = self.get_object()
        pontos = list(servico.pontos.all())

        # Escala do mostrador: a maior vibração do serviço vira raio 1.
        amplitudes = []
        for p in pontos:
            amplitudes.append(p.reference_mms)
            amplitudes.extend(v for v in (p.trial_mms, p.trim_mms) if v is not None)
        amplitude_maxima = max(amplitudes) if amplitudes else None

        def vetor(fase, amplitude):
            if fase is None or amplitude is None:
                return None
            x, y = rules.vetor_polar(fase, amplitude=amplitude, amplitude_maxima=amplitude_maxima)
            return {"x": float(x), "y": float(y), "fase": float(fase), "amplitude": float(amplitude)}

        dados_pontos = []
        for p in pontos:
            dados_pontos.append({
                "id": p.id,
                "codigo_ponto": p.codigo_ponto,
                "numero_mancal": p.numero_mancal,
                "direcao": p.direcao,
                "plano": p.plano_id,
                "reference": {"mms": float(p.reference_mms), "fase": float(p.reference_fase)},
                "trial": (
                    {"mms": float(p.trial_mms), "fase": float(p.trial_fase)}
                    if p.trial_mms is not None and p.trial_fase is not None else None
                ),
                "trim": (
                    {"mms": float(p.trim_mms), "fase": float(p.trim_fase)}
                    if p.completo else None
                ),
                "completo": p.completo,
                "residual_pct": float(p.residual_pct) if p.residual_pct is not None else None,
                "reducao_pct": float(p.reducao_pct) if p.reducao_pct is not None else None,
                "zona_iso": p.zona_iso,
                "criticidade": p.criticidade,
                "eficaz": p.eficaz,
                "diagnostico": p.diagnostico,
                "mostrador": {
                    "reference": vetor(p.reference_fase, p.reference_mms),
                    "trial": vetor(p.trial_fase, p.trial_mms),
                    "trim": vetor(p.trim_fase, p.trim_mms),
                },
            })

        economia = getattr(servico, "economia", None)
        dados_economia = None
        if economia is not None:
            dados_economia = {
                **EconomiaEnergeticaSerializer(economia).data,
                "premissas": economia.premissas,
            }

        return Response({
            "servico": ServicoCampoSerializer(servico).data,
            "mostrador": {
                "setores": rules.SETORES_MOSTRADOR,
                "graus_por_setor": rules.GRAUS_POR_SETOR,
                "amplitude_maxima": float(amplitude_maxima) if amplitude_maxima else None,
            },
            "pontos": dados_pontos,
            "economia": dados_economia,
        })


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
