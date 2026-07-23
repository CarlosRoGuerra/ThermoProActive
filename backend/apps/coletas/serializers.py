from rest_framework import serializers

from .models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao


class MedicaoVibracaoSerializer(serializers.ModelSerializer):
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    componente_nome = serializers.CharField(source="componente.nome", read_only=True, default=None)
    direcao_display = serializers.CharField(source="get_direcao_display", read_only=True)
    parametro_display = serializers.CharField(source="get_parametro_display", read_only=True)
    # Nomenclatura do relatório: mancal + direção + parâmetro (ex.: "1HA").
    codigo_ponto = serializers.CharField(read_only=True)
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)

    class Meta:
        model = MedicaoVibracao
        fields = [
            "id", "inspecao", "equipamento", "equipamento_tag", "componente",
            "componente_nome", "instrumento", "ponto_medicao", "numero_mancal",
            "parametro", "parametro_display", "codigo_ponto", "direcao",
            "direcao_display", "rotacao_rpm", "velocidade_rms", "aceleracao_rms",
            "deslocamento_pp", "fator_crista", "temperatura",
            # calculados (somente leitura):
            "zona_iso", "criticidade", "criticidade_display", "diagnostico_sugerido",
            "data_hora",
        ]
        read_only_fields = ["zona_iso", "criticidade", "diagnostico_sugerido", "data_hora"]


class MedicaoTermografiaSerializer(serializers.ModelSerializer):
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    componente_nome = serializers.CharField(source="componente.nome", read_only=True, default=None)
    sistema_display = serializers.CharField(source="get_sistema_display", read_only=True)
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)

    class Meta:
        model = MedicaoTermografia
        fields = [
            "id", "inspecao", "equipamento", "equipamento_tag", "componente",
            "componente_nome", "instrumento", "ponto_medicao", "sistema",
            "sistema_display", "temperatura_ponto", "temperatura_referencia",
            "temperatura_ambiente", "emissividade", "carga_percentual",
            # calculados (somente leitura):
            "delta_t", "criticidade", "criticidade_display", "diagnostico_sugerido",
            "data_hora",
        ]
        read_only_fields = ["delta_t", "criticidade", "diagnostico_sugerido", "data_hora"]


class MedicaoTecnicaSerializer(serializers.ModelSerializer):
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    componente_nome = serializers.CharField(source="componente.nome", read_only=True, default=None)
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)

    class Meta:
        model = MedicaoTecnica
        fields = [
            "id", "inspecao", "equipamento", "equipamento_tag", "componente",
            "componente_nome", "instrumento", "tipo", "tipo_display", "ponto_medicao",
            "grandeza", "valor", "unidade", "valor_referencia", "parametros",
            # calculados (somente leitura):
            "criticidade", "criticidade_display", "diagnostico_sugerido", "data_hora",
        ]
        read_only_fields = ["criticidade", "diagnostico_sugerido", "data_hora"]

    def validate(self, attrs):
        # O tipo da medição segue o tipo da inspeção, garantindo coerência.
        inspecao = attrs.get("inspecao")
        if inspecao and not attrs.get("tipo"):
            attrs["tipo"] = inspecao.tipo_analise
        return attrs


class InspecaoSerializer(serializers.ModelSerializer):
    medicoes_vibracao = MedicaoVibracaoSerializer(many=True, read_only=True)
    medicoes_termografia = MedicaoTermografiaSerializer(many=True, read_only=True)
    medicoes_tecnicas = MedicaoTecnicaSerializer(many=True, read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnico_nome = serializers.CharField(source="tecnico.nome", read_only=True)
    tipo_analise_display = serializers.CharField(source="get_tipo_analise_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    criticidade_maxima = serializers.CharField(read_only=True)
    qtd_medicoes = serializers.IntegerField(source="total_medicoes", read_only=True)

    class Meta:
        model = Inspecao
        fields = [
            "id", "cliente", "cliente_nome", "tipo_analise", "tipo_analise_display",
            "tecnico", "tecnico_nome", "data", "status", "status_display",
            "observacoes", "latitude", "longitude", "criticidade_maxima",
            "qtd_medicoes", "medicoes_vibracao", "medicoes_termografia",
            "medicoes_tecnicas", "criado_em",
        ]
        # O técnico é opcional no POST: assume o usuário autenticado (ver create()).
        extra_kwargs = {"tecnico": {"required": False}}

    def create(self, validated_data):
        # O técnico responsável padrão é o usuário autenticado (perfil interno).
        request = self.context.get("request")
        if request and not validated_data.get("tecnico"):
            validated_data["tecnico"] = request.user
        return super().create(validated_data)


class InspecaoListSerializer(serializers.ModelSerializer):
    """Versão enxuta para listagens (sem medições aninhadas)."""

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnico_nome = serializers.CharField(source="tecnico.nome", read_only=True)
    tipo_analise_display = serializers.CharField(source="get_tipo_analise_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    criticidade_maxima = serializers.CharField(read_only=True)
    qtd_medicoes = serializers.IntegerField(source="total_medicoes", read_only=True)

    class Meta:
        model = Inspecao
        fields = [
            "id", "cliente", "cliente_nome", "tipo_analise", "tipo_analise_display",
            "tecnico_nome", "data", "status", "status_display",
            "criticidade_maxima", "qtd_medicoes", "criado_em",
        ]
