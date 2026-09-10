"""Serializers de Manutenção corretiva — balanceamento e economia energética."""
from decimal import Decimal

from rest_framework import serializers

from .models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
)
from .analise_balanceamento import validar_servico_balanceamento


class VinculoBalanceamentoMixin:
    def validate(self, attrs):
        attrs = super().validate(attrs)
        servico = attrs.get("servico", getattr(self.instance, "servico", None))
        if self.instance and servico != self.instance.servico:
            raise serializers.ValidationError({"servico": "Não é possível mover medições entre serviços."})
        validar_servico_balanceamento(servico)
        plano = attrs.get("plano", getattr(self.instance, "plano", None))
        if plano and (not plano.ativo or plano.servico_id != servico.pk):
            raise serializers.ValidationError({"plano": "O plano deve pertencer ao mesmo serviço de balanceamento."})
        return attrs


class BalanceamentoPlanoSerializer(VinculoBalanceamentoMixin, serializers.ModelSerializer):
    class Meta:
        model = BalanceamentoPlano
        fields = [
            "id", "servico", "numero", "descricao",
            "massa_teste_g", "angulo_teste", "massa_final_g", "angulo_final",
        ]

    def validate_numero(self, value):
        # Quantidade de planos é uma escolha fixa (1 ou 2) — nunca uma lista arbitrária.
        if value not in (1, 2):
            raise serializers.ValidationError("O plano deve ser 1 ou 2 — nunca existe plano 3.")
        return value


class BalanceamentoPontoSerializer(VinculoBalanceamentoMixin, serializers.ModelSerializer):
    direcao_display = serializers.CharField(source="get_direcao_display", read_only=True)
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)
    codigo_ponto = serializers.CharField(read_only=True)
    completo = serializers.BooleanField(read_only=True)

    class Meta:
        model = BalanceamentoPonto
        fields = [
            "id", "servico", "plano", "numero_mancal", "direcao", "direcao_display",
            "identificacao", "codigo_ponto", "completo",
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
        attrs = super().validate(attrs)
        # A curva de redução divide pelo reference run — zero quebraria o cálculo.
        reference = attrs.get("reference_mms", getattr(self.instance, "reference_mms", None))
        if reference is not None and reference <= 0:
            raise serializers.ValidationError(
                {"reference_mms": "A vibração do reference run deve ser maior que zero."}
            )
        # Trial Run só no ponto de foco escolhido no serviço (os demais pontos não
        # precisam — e não devem — ter Trial Run). Não se aplica ao Trim Run, que é
        # livre em qualquer ponto.
        trial_mms = attrs.get("trial_mms", getattr(self.instance, "trial_mms", None) if self.instance else None)
        trial_fase = attrs.get("trial_fase", getattr(self.instance, "trial_fase", None) if self.instance else None)
        if trial_mms is not None or trial_fase is not None:
            servico = attrs.get("servico", getattr(self.instance, "servico", None))
            foco_id = servico.ponto_foco_id if servico else None
            instancia_id = self.instance.id if self.instance else None
            if foco_id is None or foco_id != instancia_id:
                raise serializers.ValidationError({
                    "trial_mms": "Só o ponto de foco selecionado no serviço pode registrar Trial Run.",
                })
        return attrs


class EconomiaEnergeticaSerializer(serializers.ModelSerializer):
    premissas = serializers.ListField(child=serializers.CharField(), read_only=True)
    # Nulo só no banco (registros anteriores a este campo existir) — na API é sempre
    # obrigatório, como as demais entradas da economia.
    investimento = serializers.DecimalField(
        max_digits=12, decimal_places=2, min_value=Decimal("0")
    )

    class Meta:
        model = EconomiaEnergetica
        fields = [
            "id", "servico",
            # entradas — todas obrigatórias, todas coletadas na hora:
            "tensao_v", "corrente_antes_a", "corrente_apos_a", "fator_potencia",
            "horas_dia", "dias_ano", "custo_kwh", "investimento",
            # calculados:
            "reducao_corrente_a", "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
            "payback_meses", "payback_dias", "retorno_ano", "premissas",
        ]
        read_only_fields = [
            "reducao_corrente_a", "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
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
            if self.instance.tipo == "BALANCEAMENTO":
                validar_servico_balanceamento(self.instance)
            for campo in ("cliente", "equipamento", "tipo", "analista", "instrumento", "relatorio", "data_execucao", "achado"):
                if campo in attrs and attrs[campo] != getattr(self.instance, campo):
                    raise serializers.ValidationError({campo: "Este vínculo é definido pela atividade corretiva."})
        return attrs

    def validate_ponto_foco(self, value):
        if value is not None:
            servico_id = self.instance.pk if self.instance else None
            if value.servico_id != servico_id:
                raise serializers.ValidationError("O ponto de foco deve pertencer a este serviço.")
        return value

    item = serializers.IntegerField(source="item_id", read_only=True)
    atividade = serializers.IntegerField(source="item.carregamento_id", read_only=True, default=None)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    equipamento_nome = serializers.CharField(source="equipamento.nome", read_only=True)
    classe_iso = serializers.CharField(source="equipamento.classe_iso", read_only=True)
    # Placa do motor (cadastro do equipamento) — pré-preenche a Economia energética sem
    # redigitar; ausentes, o front mostra aviso em vez de assumir um valor.
    equipamento_tensao_nominal = serializers.DecimalField(
        source="equipamento.tensao_nominal", max_digits=8, decimal_places=2,
        read_only=True, default=None,
    )
    equipamento_fator_potencia_nominal = serializers.DecimalField(
        source="equipamento.fator_potencia_nominal", max_digits=4, decimal_places=3,
        read_only=True, default=None,
    )
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
            "equipamento_nome", "classe_iso", "equipamento_tensao_nominal",
            "equipamento_fator_potencia_nominal", "tipo", "tipo_display", "item", "atividade",
            "osp", "achado", "relatorio", "analise_tecnica",
            "analista", "analista_nome", "instrumento",
            "data_execucao", "rotacao_hz", "rotacao_rpm", "custo_servico", "observacoes",
            "planos", "pontos", "ponto_foco", "economia",
            "numero_planos", "reducao_media_pct", "criticidade_final",
        ]
        read_only_fields = ["rotacao_rpm", "analise_tecnica"]
