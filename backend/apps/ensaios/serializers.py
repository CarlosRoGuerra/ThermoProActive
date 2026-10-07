from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import serializers

from apps.coletas.models import ItemInspecao

from apps.cadastros.models import ModuloTecnico

from .models import (
    ColetaFluido,
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    OrigemReferencia,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    SolicitacaoPadraoEnsaio,
    TipoFluido,
    TipoReferencia,
    ValorParametro,
)
from .relatorio import avaliar_resultado
from .relatorio_fluidos import avaliar_resultado_fluido, ensaios_padrao

FLUIDO = ModuloTecnico.FLUIDO_LUBRIFICANTE

# Situações que encerram um ensaio solicitado (o resto ainda espera laudo).
SITUACOES_FINAIS = ("REALIZADO", "NAO_COLETADO", "NAO_REALIZADO")


# ------------------------------- Catálogos ----------------------------------
class ParametroEnsaioSerializer(serializers.ModelSerializer):
    # "EF — Ferro (Fe)": rótulo para escolher o parâmetro (vários ensaios têm nomes iguais).
    identificacao = serializers.SerializerMethodField()

    class Meta:
        model = ParametroEnsaio
        exclude = ["ativo"]

    def get_identificacao(self, obj) -> str:
        simbolo = f" ({obj.simbolo})" if obj.simbolo else ""
        return f"{obj.ensaio.sigla} — {obj.nome}{simbolo}"


class EnsaioSerializer(serializers.ModelSerializer):
    parametros = ParametroEnsaioSerializer(many=True, read_only=True)
    modulo_display = serializers.CharField(source="get_modulo_display", read_only=True)
    # Fluidos: aplicações em que o ensaio vem marcado por padrão na coleta.
    padrao_em = serializers.SerializerMethodField()

    class Meta:
        model = Ensaio
        exclude = ["ativo"]

    def get_padrao_em(self, obj) -> list:
        return sorted({s.aplicacao for s in obj.solicitacoes_padrao.all() if s.ativo})


class ProdutoFluidoSerializer(serializers.ModelSerializer):
    aplicacao_display = serializers.CharField(source="get_aplicacao_display", read_only=True)

    class Meta:
        model = ProdutoFluido
        exclude = ["ativo"]


class SolicitacaoPadraoEnsaioSerializer(serializers.ModelSerializer):
    ensaio_sigla = serializers.CharField(source="ensaio.sigla", read_only=True)
    aplicacao_display = serializers.CharField(source="get_aplicacao_display", read_only=True)

    class Meta:
        model = SolicitacaoPadraoEnsaio
        exclude = ["ativo"]

    def validate_ensaio(self, ensaio):
        if ensaio.modulo != FLUIDO:
            raise serializers.ValidationError("Só ensaios de fluidos lubrificantes e hidráulicos.")
        return ensaio


class ReferenciaParametroSerializer(serializers.ModelSerializer):
    """
    Referência de um parâmetro de fluido, com escopo, origem e vigência. As regras
    abaixo impedem referência que o classificador não saberia aplicar.
    """

    parametro_codigo = serializers.CharField(source="parametro.codigo", read_only=True)
    parametro_nome = serializers.CharField(source="parametro.nome", read_only=True)
    parametro_unidade = serializers.CharField(source="parametro.unidade", read_only=True)
    ensaio_sigla = serializers.CharField(source="parametro.ensaio.sigla", read_only=True)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    origem_display = serializers.CharField(source="get_origem_display", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True, default=None)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True, default=None)
    produto_nome = serializers.CharField(source="produto.nome", read_only=True, default=None)

    class Meta:
        model = ReferenciaParametro
        exclude = ["ativo"]

    def validate(self, attrs):
        def valor(campo):
            return attrs.get(campo, getattr(self.instance, campo, None))

        parametro, tipo = valor("parametro"), valor("tipo")
        alerta, critico, base = valor("limite_alerta"), valor("limite_critico"), valor("valor_base")
        texto = (valor("referencia_texto") or "").strip()
        if parametro is not None and parametro.ensaio.modulo != FLUIDO:
            raise serializers.ValidationError({"parametro": "Referências por escopo valem para os ensaios de fluidos."})
        if tipo == TipoReferencia.CODIGO_ISO:
            from .calculos_fluidos import ler_codigo
            from .relatorio_fluidos import CODIGO_ISO4406

            if parametro is not None and parametro.codigo != CODIGO_ISO4406:
                raise serializers.ValidationError({"tipo": "Meta ISO 4406 só no parâmetro do código ISO da CP."})
            if ler_codigo(texto) is None:
                raise serializers.ValidationError({"referencia_texto": "Informe a meta no formato X/Y/Z (ex.: 17/15/12)."})
        elif tipo == TipoReferencia.QUALITATIVO:
            if not texto:
                raise serializers.ValidationError({"referencia_texto": "Informe o resultado esperado."})
        else:
            if alerta is None and critico is None:
                raise serializers.ValidationError("Informe o limite de alerta, o crítico ou os dois.")
            if tipo == TipoReferencia.VARIACAO and not base and not valor("base_grau_iso"):
                raise serializers.ValidationError({"valor_base": "A variação precisa do valor de base (óleo novo/nominal)."})
            if valor("base_grau_iso") and (tipo != TipoReferencia.VARIACAO or getattr(parametro, "codigo", "") != "VISC40"):
                raise serializers.ValidationError({
                    "base_grau_iso": "A base pelo grau ISO VG vale só para a variação da viscosidade a 40 °C.",
                })
            if alerta is not None and critico is not None:
                fora_de_ordem = critico < alerta if tipo in (TipoReferencia.MAXIMO, TipoReferencia.VARIACAO) else critico > alerta
                if fora_de_ordem:
                    raise serializers.ValidationError({"limite_critico": "O limite crítico precisa ser mais severo que o de alerta."})
        inicio, fim = valor("vigencia_inicio"), valor("vigencia_fim")
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError({"vigencia_fim": "O fim da vigência não pode ser anterior ao início."})
        equipamento, cliente = valor("equipamento"), valor("cliente")
        if equipamento is not None and cliente is not None and equipamento.setor.area.cliente_id != cliente.id:
            raise serializers.ValidationError({"equipamento": "O equipamento é de outro cliente."})
        if valor("origem") != OrigemReferencia.NORMA and not (valor("fonte") or "").strip():
            raise serializers.ValidationError({"fonte": "Informe a fonte (manual, laudo, contrato, acordo) da referência."})
        return attrs


class TipoFluidoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoFluido
        exclude = ["ativo"]


class PontoColetaSerializer(serializers.ModelSerializer):
    modulo_display = serializers.CharField(source="get_modulo_display", read_only=True)

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


class ColetaFluidoSerializer(serializers.ModelSerializer):
    """
    Coleta da amostra de fluido lubrificante/hidráulico. Na criação sem `ensaios`,
    marca os ensaios padrão da aplicação (lubrificante: FQ + EF; hidráulico: FQ +
    EF + CP) — o técnico pode marcar ou desmarcar depois.
    """

    aplicacao_display = serializers.CharField(source="get_aplicacao_display", read_only=True)
    produto_nome = serializers.CharField(source="produto.nome", read_only=True, default=None)

    class Meta:
        model = ColetaFluido
        exclude = ["ativo"]
        extra_kwargs = {"ensaios": {"required": False}}

    def validate(self, attrs):
        item = attrs.get("item") or getattr(self.instance, "item", None)
        _checar_modulo(item, FLUIDO)
        for ensaio in attrs.get("ensaios", []):
            if ensaio.modulo != FLUIDO:
                raise serializers.ValidationError({"ensaios": f"{ensaio.sigla} não é um ensaio de fluidos."})
        ponto = attrs.get("ponto_coleta")
        if ponto is not None and ponto.modulo not in ("", FLUIDO):
            raise serializers.ValidationError({"ponto_coleta": "Ponto de coleta de outra tecnologia."})
        aplicacao = attrs.get("aplicacao", getattr(self.instance, "aplicacao", ""))
        produto = attrs.get("produto", getattr(self.instance, "produto", None))
        if produto is not None and produto.aplicacao and produto.aplicacao != aplicacao:
            raise serializers.ValidationError({
                "produto": f"O fluido «{produto.nome}» está cadastrado como {produto.get_aplicacao_display().lower()}.",
            })
        coleta = attrs.get("data_coleta", getattr(self.instance, "data_coleta", None))
        troca_ = attrs.get("data_ultima_troca", getattr(self.instance, "data_ultima_troca", None))
        if coleta and troca_ and troca_ > coleta:
            raise serializers.ValidationError({"data_ultima_troca": "A última troca não pode ser depois da coleta."})
        return attrs

    def create(self, validated_data):
        if "ensaios" not in validated_data:
            validated_data["ensaios"] = ensaios_padrao(validated_data.get("aplicacao"))
        return super().create(validated_data)


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
        if obj.ensaio.modulo == FLUIDO:
            return avaliar_resultado_fluido(obj)
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
class ItemEnsaioSerializer(serializers.ModelSerializer):
    """
    Um equipamento numa rota de ensaios (transformador ou fluidos), com o que o
    lançamento precisa: rota, relatório, registro de campo e a situação de cada
    ensaio do módulo (`pendentes` = solicitados ainda sem laudo).
    """

    REGISTROS = ("coleta_oleo", "registro_eletrico", "coleta_fluido")

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
    registro = serializers.SerializerMethodField()
    ensaios = serializers.SerializerMethodField()
    pendentes = serializers.SerializerMethodField()

    class Meta:
        model = ItemInspecao
        fields = [
            "id", "carregamento", "carregamento_status", "relatorio", "numero", "cliente", "cliente_nome",
            "tecnologia", "tecnologia_nome", "modulo", "data_coleta", "analista_nome", "equipamento",
            "equipamento_tag", "equipamento_nome", "area_nome", "setor_nome", "condicao", "condicao_sigla",
            "condicao_nome", "registro", "ensaios", "pendentes",
        ]

    @classmethod
    def _registro(cls, obj):
        for campo in cls.REGISTROS:
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


class TransformadorInspecaoSerializer(ItemEnsaioSerializer):
    """Transformador numa rota de óleo isolante ou de ensaios elétricos."""

    possui_tanque_expansao = serializers.BooleanField(
        source="equipamento.dados_transformador.possui_tanque_expansao", read_only=True, default=None
    )

    class Meta(ItemEnsaioSerializer.Meta):
        fields = ItemEnsaioSerializer.Meta.fields + ["possui_tanque_expansao"]


class FluidoInspecaoSerializer(ItemEnsaioSerializer):
    """Equipamento numa rota de fluidos lubrificantes e hidráulicos, com o fluido da coleta."""

    aplicacao = serializers.SerializerMethodField()
    fluido = serializers.SerializerMethodField()
    tipo_equipamento_nome = serializers.CharField(source="equipamento.tipo_equipamento.nome", read_only=True,
                                                  default=None)

    class Meta(ItemEnsaioSerializer.Meta):
        fields = ItemEnsaioSerializer.Meta.fields + ["aplicacao", "fluido", "tipo_equipamento_nome"]

    def _coleta(self, obj):
        try:
            return obj.coleta_fluido
        except ObjectDoesNotExist:
            return None

    def get_aplicacao(self, obj):
        c = self._coleta(obj)
        return c.aplicacao if c else None

    def get_fluido(self, obj):
        c = self._coleta(obj)
        return c.nome_fluido if c else None
