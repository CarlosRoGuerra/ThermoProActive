"""Serializers de Manutenção corretiva — balanceamento e economia energética."""
from rest_framework import serializers

from .models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
)


class BalanceamentoPlanoSerializer(serializers.ModelSerializer):
    class Meta:
        model = BalanceamentoPlano
        fields = [
            "id", "servico", "numero", "descricao",
            "massa_teste_g", "angulo_teste", "massa_final_g", "angulo_final",
        ]


class BalanceamentoPontoSerializer(serializers.ModelSerializer):
    direcao_display = serializers.CharField(source="get_direcao_display", read_only=True)
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)
    codigo_ponto = serializers.CharField(read_only=True)
    completo = serializers.BooleanField(read_only=True)

    class Meta:
        model = BalanceamentoPonto
        fields = [
            "id", "servico", "plano", "numero_mancal", "direcao", "direcao_display",
            "codigo_ponto", "completo",
            "reference_mms", "reference_fase",
            "trial_mms", "trial_fase",
            "trim_mms", "trim_fase",
            # calculados (somente leitura):
            "residual_pct", "reducao_pct", "zona_iso", "criticidade",
            "criticidade_display", "eficaz", "diagnostico",
        ]
        read_only_fields = [
            "residual_pct", "reducao_pct", "zona_iso", "criticidade", "eficaz", "diagnostico",
        ]

    def validate(self, attrs):
        # A curva de redução divide pelo reference run — zero quebraria o cálculo.
        reference = attrs.get("reference_mms", getattr(self.instance, "reference_mms", None))
        if reference is not None and reference <= 0:
            raise serializers.ValidationError(
                {"reference_mms": "A vibração do reference run deve ser maior que zero."}
            )
        return attrs


class EconomiaEnergeticaSerializer(serializers.ModelSerializer):
    premissas = serializers.ListField(child=serializers.CharField(), read_only=True)

    class Meta:
        model = EconomiaEnergetica
        fields = [
            "id", "servico",
            # entradas — todas obrigatórias, todas coletadas na hora:
            "tensao_v", "corrente_antes_a", "corrente_apos_a", "fator_potencia",
            "horas_dia", "dias_ano", "custo_kwh",
            # calculados:
            "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
            "payback_meses", "payback_dias", "retorno_ano", "premissas",
        ]
        read_only_fields = [
            "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
            "payback_meses", "payback_dias", "retorno_ano",
        ]


class ServicoCampoListSerializer(serializers.ModelSerializer):
    item = serializers.IntegerField(source="item_id", read_only=True)
    atividade = serializers.IntegerField(source="item.carregamento_id", read_only=True, default=None)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    numero_planos = serializers.IntegerField(read_only=True)
    reducao_media_pct = serializers.DecimalField(
        max_digits=8, decimal_places=3, read_only=True
    )
    criticidade_final = serializers.CharField(read_only=True)

    class Meta:
        model = ServicoCampo
        fields = [
            "id", "cliente", "cliente_nome", "equipamento", "equipamento_tag",
            "tipo", "tipo_display", "data_execucao", "rotacao_hz", "rotacao_rpm",
            "numero_planos", "reducao_media_pct", "criticidade_final", "custo_servico", "item", "atividade",
        ]


class ServicoCampoSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        if self.instance and self.instance.item_id:
            for campo in ("cliente", "equipamento", "tipo", "analista", "instrumento", "relatorio", "data_execucao"):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError({campo: "Este vínculo é definido pela atividade corretiva."})
        return attrs

    item = serializers.IntegerField(source="item_id", read_only=True)
    atividade = serializers.IntegerField(source="item.carregamento_id", read_only=True, default=None)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    equipamento_nome = serializers.CharField(source="equipamento.nome", read_only=True)
    classe_iso = serializers.CharField(source="equipamento.classe_iso", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    analista_nome = serializers.CharField(source="analista.get_full_name", read_only=True)

    planos = BalanceamentoPlanoSerializer(many=True, read_only=True)
    pontos = BalanceamentoPontoSerializer(many=True, read_only=True)
    economia = EconomiaEnergeticaSerializer(read_only=True)

    numero_planos = serializers.IntegerField(read_only=True)
    reducao_media_pct = serializers.DecimalField(
        max_digits=8, decimal_places=3, read_only=True
    )
    criticidade_final = serializers.CharField(read_only=True)

    class Meta:
        model = ServicoCampo
        fields = [
            "id", "cliente", "cliente_nome", "equipamento", "equipamento_tag",
            "equipamento_nome", "classe_iso", "tipo", "tipo_display", "item", "atividade",
            "osp", "achado", "relatorio",
            "analista", "analista_nome", "instrumento",
            "data_execucao", "rotacao_hz", "rotacao_rpm", "custo_servico", "observacoes",
            "planos", "pontos", "economia",
            "numero_planos", "reducao_media_pct", "criticidade_final",
        ]
        read_only_fields = ["rotacao_rpm"]
