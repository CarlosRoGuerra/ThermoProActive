from django.db import transaction
from rest_framework import serializers

from .models import (
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    ParametroEnsaio,
    PontoColeta,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    TipoFluido,
    ValorParametro,
)


# ------------------------------- Catálogos ----------------------------------
class ParametroEnsaioSerializer(serializers.ModelSerializer):
    class Meta:
        model = ParametroEnsaio
        exclude = ["ativo"]


class EnsaioSerializer(serializers.ModelSerializer):
    parametros = ParametroEnsaioSerializer(many=True, read_only=True)
    modulo_display = serializers.CharField(source="get_modulo_display", read_only=True)

    class Meta:
        model = Ensaio
        exclude = ["ativo"]


class TipoFluidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoFluido
        exclude = ["ativo"]


class PontoColetaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PontoColeta
        exclude = ["ativo"]


class ItemChecklistVisualSerializer(serializers.ModelSerializer):
    grupo_display = serializers.CharField(source="get_grupo_display", read_only=True)

    class Meta:
        model = ItemChecklistVisual
        exclude = ["ativo"]


# ------------------------- Coleta e registro de campo -------------------------
def _checar_modulo(item, modulo):
    """O item precisa ser de uma rota cuja tecnologia usa este módulo técnico."""
    if item.carregamento.tecnologia.modulo_tecnico != modulo:
        raise serializers.ValidationError(
            {"item": "Este equipamento está numa rota de outra tecnologia (módulo técnico diferente)."}
        )


class InspecaoVisualItemSerializer(serializers.ModelSerializer):
    item_checklist_nome = serializers.CharField(source="item_checklist.nome", read_only=True)
    grupo = serializers.CharField(source="item_checklist.grupo", read_only=True)

    class Meta:
        model = InspecaoVisualColeta
        fields = ["id", "item_checklist", "item_checklist_nome", "grupo", "estado", "observacao", "foto"]


class ColetaOleoSerializer(serializers.ModelSerializer):
    """Coleta da amostra; `inspecao_visual`, quando enviada, substitui o checklist inteiro."""

    inspecao_visual = InspecaoVisualItemSerializer(many=True, required=False)

    class Meta:
        model = ColetaOleo
        exclude = ["ativo"]

    def validate(self, attrs):
        item = attrs.get("item") or getattr(self.instance, "item", None)
        _checar_modulo(item, "OLEO_ISOLANTE")
        for ensaio in attrs.get("ensaios", []):
            if ensaio.modulo != "OLEO_ISOLANTE":
                raise serializers.ValidationError({"ensaios": f"{ensaio.sigla} não é um ensaio de óleo."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        checklist = validated_data.pop("inspecao_visual", None)
        coleta = super().create(validated_data)
        self._gravar_checklist(coleta, checklist)
        return coleta

    @transaction.atomic
    def update(self, instance, validated_data):
        checklist = validated_data.pop("inspecao_visual", None)
        coleta = super().update(instance, validated_data)
        self._gravar_checklist(coleta, checklist)
        return coleta

    @staticmethod
    def _gravar_checklist(coleta, checklist):
        if checklist is None:
            return
        coleta.inspecao_visual.all().delete()
        InspecaoVisualColeta.objects.bulk_create([InspecaoVisualColeta(coleta=coleta, **i) for i in checklist])


class RegistroEnsaioEletricoSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroEnsaioEletrico
        exclude = ["ativo"]

    def validate(self, attrs):
        item = attrs.get("item") or getattr(self.instance, "item", None)
        _checar_modulo(item, "ENSAIO_ELETRICO")
        for ensaio in attrs.get("ensaios", []):
            if ensaio.modulo != "ENSAIO_ELETRICO":
                raise serializers.ValidationError({"ensaios": f"{ensaio.sigla} não é um ensaio elétrico."})
        return attrs


# -------------------------------- Resultados --------------------------------
class ValorParametroSerializer(serializers.ModelSerializer):
    parametro_codigo = serializers.CharField(source="parametro.codigo", read_only=True)

    class Meta:
        model = ValorParametro
        fields = ["id", "parametro", "parametro_codigo", "serie", "posicao", "valor", "valor_texto", "estado",
                  "limite_deteccao"]


class ResultadoEnsaioSerializer(serializers.ModelSerializer):
    """
    Resultado de um ensaio com os valores. `valores`, quando enviados, substituem
    todos os do resultado (mesmo contrato para digitação, planilha ou integração).
    """

    valores = ValorParametroSerializer(many=True, required=False)
    ensaio_sigla = serializers.CharField(source="ensaio.sigla", read_only=True)
    situacao_display = serializers.CharField(source="get_situacao_display", read_only=True)

    class Meta:
        model = ResultadoEnsaio
        exclude = ["ativo"]

    def validate(self, attrs):
        item = attrs.get("item") or getattr(self.instance, "item", None)
        ensaio = attrs.get("ensaio") or getattr(self.instance, "ensaio", None)
        _checar_modulo(item, ensaio.modulo)
        for v in attrs.get("valores", []):
            parametro = v["parametro"]
            if parametro.ensaio_id != ensaio.id:
                raise serializers.ValidationError({"valores": f"{parametro.codigo} não é parâmetro do ensaio {ensaio.sigla}."})
            if parametro.calculado:
                raise serializers.ValidationError({"valores": f"{parametro.codigo} é calculado pelo sistema."})
        if attrs.get("data_analise") and attrs.get("data_proxima") and attrs["data_proxima"] < attrs["data_analise"]:
            raise serializers.ValidationError({"data_proxima": "A próxima data não pode ser anterior à análise."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        valores = validated_data.pop("valores", None)
        resultado = super().create(validated_data)
        self._gravar_valores(resultado, valores)
        return resultado

    @transaction.atomic
    def update(self, instance, validated_data):
        valores = validated_data.pop("valores", None)
        resultado = super().update(instance, validated_data)
        self._gravar_valores(resultado, valores)
        return resultado

    @staticmethod
    def _gravar_valores(resultado, valores):
        if valores is None:
            return
        resultado.valores.all().delete()
        ValorParametro.objects.bulk_create([ValorParametro(resultado=resultado, **v) for v in valores])
