from rest_framework import serializers

from .models import (
    Area,
    ClassificacaoInspecao,
    Cliente,
    Componente,
    Empresa,
    Equipamento,
    FalhaRecorrente,
    GrupoAcesso,
    Instrumento,
    Norma,
    Rota,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoCriticidade,
    TipoEquipamento,
    TipoInspecao,
    TipoRecomendacao,
)


class TecnologiasVinculoMixin(serializers.ModelSerializer):
    """
    Reuso para catálogos vinculados a tecnologias de análise (Norma, Instrumento,
    Tipo de componente/anomalia/recomendação): grava por lista de IDs e devolve
    uma versão legível (tecnologias_display) para exibir e pré-selecionar na tela.
    """

    tecnologias = serializers.PrimaryKeyRelatedField(
        many=True, required=False, queryset=TecnologiaAnalise.objects.ativos()
    )
    tecnologias_display = serializers.SerializerMethodField()

    def get_tecnologias_display(self, obj):
        return [
            {"id": t.id, "nome": t.nome, "sigla": t.sigla}
            for t in obj.tecnologias.all()
        ]


class EmpresaSerializer(serializers.ModelSerializer):
    endereco_formatado = serializers.CharField(read_only=True)

    class Meta:
        model = Empresa
        exclude = ["ativo"]


class ClienteSerializer(serializers.ModelSerializer):
    endereco_formatado = serializers.CharField(read_only=True)
    cidade_uf = serializers.CharField(read_only=True)

    class Meta:
        model = Cliente
        exclude = ["ativo"]


class AreaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    identificacao = serializers.CharField(read_only=True)

    class Meta:
        model = Area
        fields = [
            "id", "cliente", "cliente_nome", "codigo", "nome", "complemento",
            "identificacao", "criado_em",
        ]


class SetorSerializer(serializers.ModelSerializer):
    area_nome = serializers.CharField(source="area.nome", read_only=True)
    identificacao = serializers.CharField(read_only=True)

    class Meta:
        model = Setor
        fields = [
            "id", "area", "area_nome", "codigo", "nome", "complemento",
            "identificacao", "criado_em",
        ]


class ComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Componente
        fields = ["id", "equipamento", "nome", "criado_em"]


class EquipamentoSerializer(serializers.ModelSerializer):
    componentes = ComponenteSerializer(many=True, read_only=True)
    setor_nome = serializers.CharField(source="setor.nome", read_only=True)
    area_id = serializers.IntegerField(source="setor.area_id", read_only=True)
    area_nome = serializers.CharField(source="setor.area.nome", read_only=True)
    classe_iso_display = serializers.CharField(source="get_classe_iso_display", read_only=True)
    cliente_id = serializers.IntegerField(source="setor.area.cliente_id", read_only=True)
    # Hierarquia Equipamento → Sub-item (o sub-item é um equipamento filho).
    equipamento_pai_tag = serializers.CharField(source="equipamento_pai.tag", read_only=True, default=None)
    is_subitem = serializers.BooleanField(read_only=True)
    nivel = serializers.IntegerField(read_only=True)
    caminho = serializers.CharField(read_only=True)
    qtd_subitens = serializers.IntegerField(source="subitens.count", read_only=True)

    class Meta:
        model = Equipamento
        fields = [
            "id", "setor", "setor_nome", "area_id", "area_nome", "cliente_id",
            "equipamento_pai", "equipamento_pai_tag", "is_subitem", "nivel",
            "caminho", "qtd_subitens",
            "tag", "nome", "tipo",
            "fabricante", "modelo", "numero_serie", "potencia_kw",
            "rotacao_nominal_rpm", "classe_iso", "classe_iso_display",
            "componentes", "criado_em",
        ]

    def validate(self, attrs):
        """Roda a checagem de ciclo do modelo também na API."""
        instancia = Equipamento(**{**{f: getattr(self.instance, f, None) for f in ()}, **attrs})
        instancia.pk = self.instance.pk if self.instance else None
        instancia.clean()
        return attrs


class InstrumentoSerializer(TecnologiasVinculoMixin):
    periodicidade_display = serializers.CharField(
        source="get_periodicidade_calibracao_display", read_only=True
    )
    proxima_calibracao = serializers.DateField(read_only=True)
    calibracao_vencida = serializers.BooleanField(read_only=True)

    class Meta:
        model = Instrumento
        exclude = ["ativo"]


# --- Catálogos / tabelas de referência (Anexo I 2.2.1.5–2.2.1.14, 2.2.1.18) ---


class NormaSerializer(TecnologiasVinculoMixin):
    class Meta:
        model = Norma
        exclude = ["ativo"]


class TecnologiaAnaliseSerializer(serializers.ModelSerializer):
    class Meta:
        model = TecnologiaAnalise
        exclude = ["ativo"]


class TipoEquipamentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoEquipamento
        exclude = ["ativo"]


class ClassificacaoInspecaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassificacaoInspecao
        exclude = ["ativo"]


class TipoInspecaoSerializer(serializers.ModelSerializer):
    classificacao_nome = serializers.CharField(source="classificacao.nome", read_only=True, default=None)

    class Meta:
        model = TipoInspecao
        exclude = ["ativo"]


class FalhaRecorrenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FalhaRecorrente
        exclude = ["ativo"]


class TipoComponenteSerializer(TecnologiasVinculoMixin):
    class Meta:
        model = TipoComponente
        exclude = ["ativo"]


class TipoAnomaliaSerializer(TecnologiasVinculoMixin):
    class Meta:
        model = TipoAnomalia
        exclude = ["ativo"]


class TipoRecomendacaoSerializer(TecnologiasVinculoMixin):
    class Meta:
        model = TipoRecomendacao
        exclude = ["ativo"]


class TipoCriticidadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoCriticidade
        exclude = ["ativo"]


class GrupoAcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrupoAcesso
        exclude = ["ativo"]


class RotaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    qtd_equipamentos = serializers.IntegerField(source="equipamentos.count", read_only=True)

    class Meta:
        model = Rota
        exclude = ["ativo"]
