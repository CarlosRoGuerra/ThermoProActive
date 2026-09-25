from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import serializers

from apps.coletas.models import ItemInspecao

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
from .relatorio import avaliar_resultado

# Situações que encerram um ensaio solicitado (o resto ainda espera laudo).
SITUACOES_FINAIS = ("REALIZADO", "NAO_COLETADO", "NAO_REALIZADO")


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
    `avaliacao` devolve a parte calculada da ficha (erro, IP, TG/TGC, conformidade),
    com as mesmas regras do relatório.
    """

    valores = ValorParametroSerializer(many=True, required=False)
    ensaio_sigla = serializers.CharField(source="ensaio.sigla", read_only=True)
    situacao_display = serializers.CharField(source="get_situacao_display", read_only=True)
    avaliacao = serializers.SerializerMethodField()

    class Meta:
        model = ResultadoEnsaio
        exclude = ["ativo"]

    def get_avaliacao(self, obj) -> dict:
        return avaliar_resultado(obj)

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


# ------------------------- Fila de lançamento (leitura) -------------------------
class TransformadorInspecaoSerializer(serializers.ModelSerializer):
    """
    Um transformador numa rota de óleo isolante ou de ensaios elétricos, com o que
    o lançamento precisa: rota, relatório, registro de campo e a situação de cada
    ensaio do módulo (`pendentes` = solicitados ainda sem laudo).
    """

    carregamento_status = serializers.CharField(source="carregamento.status", read_only=True)
    relatorio = serializers.IntegerField(source="carregamento.relatorio_id", read_only=True)
    numero = serializers.CharField(source="carregamento.relatorio.numero", read_only=True, default=None)
    cliente = serializers.IntegerField(source="carregamento.cliente_id", read_only=True)
    cliente_nome = serializers.CharField(source="carregamento.cliente.nome", read_only=True)
    tecnologia = serializers.IntegerField(source="carregamento.tecnologia_id", read_only=True)
    tecnologia_nome = serializers.CharField(source="carregamento.tecnologia.nome", read_only=True)
    modulo = serializers.CharField(source="carregamento.tecnologia.modulo_tecnico", read_only=True)
    data_coleta = serializers.DateField(source="carregamento.data_coleta", read_only=True)
    analista_nome = serializers.CharField(source="carregamento.analista.nome", read_only=True)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    equipamento_nome = serializers.CharField(source="equipamento.nome", read_only=True)
    area_nome = serializers.CharField(source="equipamento.setor.area.nome", read_only=True)
    setor_nome = serializers.CharField(source="equipamento.setor.nome", read_only=True)
    condicao_sigla = serializers.CharField(source="condicao.sigla", read_only=True, default=None)
    condicao_nome = serializers.CharField(source="condicao.nome", read_only=True, default=None)
    possui_tanque_expansao = serializers.BooleanField(
        source="equipamento.dados_transformador.possui_tanque_expansao", read_only=True, default=None
    )
    registro = serializers.SerializerMethodField()
    ensaios = serializers.SerializerMethodField()
    pendentes = serializers.SerializerMethodField()

    class Meta:
        model = ItemInspecao
        fields = [
            "id", "carregamento", "carregamento_status", "relatorio", "numero", "cliente", "cliente_nome",
            "tecnologia", "tecnologia_nome", "modulo", "data_coleta", "analista_nome", "equipamento",
            "equipamento_tag", "equipamento_nome", "area_nome", "setor_nome", "condicao", "condicao_sigla",
            "condicao_nome", "possui_tanque_expansao", "registro", "ensaios", "pendentes",
        ]

    @staticmethod
    def _registro(obj):
        for campo in ("coleta_oleo", "registro_eletrico"):
            try:
                return getattr(obj, campo)
            except ObjectDoesNotExist:
                continue
        return None

    def _catalogo(self, modulo):
        # Uma consulta por módulo na página inteira, não por transformador.
        cache = self.context.setdefault("_ensaios_por_modulo", {})
        if modulo not in cache:
            cache[modulo] = list(Ensaio.objects.ativos().filter(modulo=modulo).order_by("ordem"))
        return cache[modulo]

    def get_registro(self, obj):
        r = self._registro(obj)
        if r is None:
            return None
        return {"id": r.id, "data": getattr(r, "data_coleta", None) or getattr(r, "data_ensaio", None)}

    def get_ensaios(self, obj) -> list:
        registro = self._registro(obj)
        solicitados = {e.id for e in registro.ensaios.all()} if registro else set()
        resultados = {r.ensaio_id: r for r in obj.resultados_ensaio.all() if r.ativo}
        return [
            {"sigla": e.sigla, "nome": e.nome, "solicitado": e.id in solicitados,
             "situacao": resultados[e.id].situacao if e.id in resultados else None}
            for e in self._catalogo(obj.carregamento.tecnologia.modulo_tecnico)
        ]

    def get_pendentes(self, obj) -> int:
        return sum(1 for e in self.get_ensaios(obj) if e["solicitado"] and e["situacao"] not in SITUACOES_FINAIS)
