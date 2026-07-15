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


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        exclude = ["ativo"]


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        exclude = ["ativo"]


class AreaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)

    class Meta:
        model = Area
        fields = ["id", "cliente", "cliente_nome", "nome", "criado_em"]


class SetorSerializer(serializers.ModelSerializer):
    area_nome = serializers.CharField(source="area.nome", read_only=True)

    class Meta:
        model = Setor
        fields = ["id", "area", "area_nome", "nome", "criado_em"]


class ComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Componente
        fields = ["id", "equipamento", "nome", "criado_em"]


class EquipamentoSerializer(serializers.ModelSerializer):
    componentes = ComponenteSerializer(many=True, read_only=True)
    setor_nome = serializers.CharField(source="setor.nome", read_only=True)
    classe_iso_display = serializers.CharField(source="get_classe_iso_display", read_only=True)
    cliente_id = serializers.IntegerField(source="setor.area.cliente_id", read_only=True)

    class Meta:
        model = Equipamento
        fields = [
            "id", "setor", "setor_nome", "cliente_id", "tag", "nome", "tipo",
            "fabricante", "modelo", "numero_serie", "potencia_kw",
            "rotacao_nominal_rpm", "classe_iso", "classe_iso_display",
            "componentes", "criado_em",
        ]


class InstrumentoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Instrumento
        exclude = ["ativo"]


# --- Catálogos / tabelas de referência (Anexo I 2.2.1.5–2.2.1.14, 2.2.1.18) ---


class NormaSerializer(serializers.ModelSerializer):
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


class TipoComponenteSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoComponente
        exclude = ["ativo"]


class TipoAnomaliaSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoAnomalia
        exclude = ["ativo"]


class TipoRecomendacaoSerializer(serializers.ModelSerializer):
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
