from django.utils import timezone
from rest_framework import serializers

from .models import (
    Achado,
    AchadoImagem,
    Carregamento,
    Inspecao,
    ItemInspecao,
    MedicaoTecnica,
    MedicaoTermografia,
    MedicaoVibracao,
    Relatorio,
)


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


# =============================================================================
# Fluxo de inspeção campo → escritório (Carregamento → Item → Achado → Imagens)
# =============================================================================


class AchadoImagemSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = AchadoImagem
        fields = ["id", "achado", "tipo", "tipo_display", "arquivo", "legenda", "criado_em"]


class AchadoSerializer(serializers.ModelSerializer):
    # Rastreabilidade (somente leitura — vem do item/carregamento/equipamento).
    equipamento_tag = serializers.CharField(source="item.equipamento.tag", read_only=True)
    equipamento_nome = serializers.CharField(source="item.equipamento.nome", read_only=True)
    equipamento_id = serializers.IntegerField(source="item.equipamento_id", read_only=True)
    area_nome = serializers.CharField(source="item.equipamento.setor.area.nome", read_only=True)
    setor_nome = serializers.CharField(source="item.equipamento.setor.nome", read_only=True)
    tipo_equipamento_nome = serializers.CharField(
        source="item.equipamento.tipo_equipamento.nome", read_only=True, default=None
    )
    tecnologia = serializers.IntegerField(source="item.carregamento.tecnologia_id", read_only=True)
    tecnologia_nome = serializers.CharField(
        source="item.carregamento.tecnologia.nome", read_only=True
    )
    analista_nome = serializers.CharField(source="item.carregamento.analista.nome", read_only=True)
    # "data" para o escritório/auditoria = data de término do relatório.
    data = serializers.DateField(source="item.carregamento.relatorio.data_termino", read_only=True, default=None)
    numero_relatorio = serializers.CharField(source="item.carregamento.relatorio.numero", read_only=True, default=None)
    # Nomes legíveis dos catálogos selecionados.
    tipo_componente_nome = serializers.CharField(source="tipo_componente.nome", read_only=True, default=None)
    tipo_anomalia_nome = serializers.CharField(source="tipo_anomalia.nome", read_only=True, default=None)
    recomendacao_nome = serializers.CharField(source="recomendacao.nome", read_only=True, default=None)
    condicao_nome = serializers.CharField(source="condicao.nome", read_only=True, default=None)
    condicao_sigla = serializers.CharField(source="condicao.sigla", read_only=True, default=None)
    imagens = AchadoImagemSerializer(many=True, read_only=True)

    class Meta:
        model = Achado
        exclude = ["ativo"]


class ItemInspecaoSerializer(serializers.ModelSerializer):
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    equipamento_nome = serializers.CharField(source="equipamento.nome", read_only=True)
    area_nome = serializers.CharField(source="equipamento.setor.area.nome", read_only=True)
    setor_nome = serializers.CharField(source="equipamento.setor.nome", read_only=True)
    tipo_equipamento_nome = serializers.CharField(
        source="equipamento.tipo_equipamento.nome", read_only=True, default=None
    )
    condicao_nome = serializers.CharField(source="condicao.nome", read_only=True, default=None)
    condicao_gera_acao = serializers.BooleanField(source="condicao.gera_acao", read_only=True, default=None)
    data = serializers.DateField(source="carregamento.data_coleta", read_only=True)
    achados = AchadoSerializer(many=True, read_only=True)
    qtd_achados = serializers.IntegerField(source="achados.count", read_only=True)

    class Meta:
        model = ItemInspecao
        exclude = ["ativo"]


class RelatorioSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnologia_nome = serializers.CharField(source="tecnologia.nome", read_only=True)
    qtd_rotas = serializers.IntegerField(source="carregamentos.count", read_only=True)

    class Meta:
        model = Relatorio
        exclude = ["ativo"]
        # Número gerado no back; início derivado das rotas.
        read_only_fields = ["numero", "data_inicio"]


class CarregamentoListSerializer(serializers.ModelSerializer):
    """Versão enxuta para a listagem (sem itens aninhados)."""

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnologia_nome = serializers.CharField(source="tecnologia.nome", read_only=True)
    rota_nome = serializers.CharField(source="rota.nome", read_only=True, default="")
    analista_nome = serializers.CharField(source="analista.nome", read_only=True)
    instrumento_nome = serializers.CharField(source="instrumento.tipo", read_only=True, default="")
    numero = serializers.CharField(source="relatorio.numero", read_only=True, default=None)
    data_inicio = serializers.DateField(source="relatorio.data_inicio", read_only=True, default=None)
    data_termino = serializers.DateField(source="relatorio.data_termino", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    qtd_itens = serializers.IntegerField(source="itens.count", read_only=True)
    pode_transferir = serializers.BooleanField(read_only=True)

    class Meta:
        model = Carregamento
        fields = [
            "id", "cliente", "cliente_nome", "tecnologia", "tecnologia_nome",
            "relatorio", "numero", "data_inicio", "data_termino", "data_coleta",
            "rota", "rota_nome", "instrumento", "instrumento_nome",
            "analista", "analista_nome",
            "status", "status_display", "qtd_itens",
            "pode_transferir", "transferido_em", "criado_em",
        ]


class CarregamentoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnologia_nome = serializers.CharField(source="tecnologia.nome", read_only=True)
    rota_nome = serializers.CharField(source="rota.nome", read_only=True, default="")
    instrumento_nome = serializers.CharField(source="instrumento.tipo", read_only=True, default="")
    analista_nome = serializers.CharField(source="analista.nome", read_only=True)
    numero = serializers.CharField(source="relatorio.numero", read_only=True, default=None)
    data_inicio = serializers.DateField(source="relatorio.data_inicio", read_only=True, default=None)
    data_termino = serializers.DateField(source="relatorio.data_termino", read_only=True, default=None)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    itens = ItemInspecaoSerializer(many=True, read_only=True)
    qtd_itens = serializers.IntegerField(source="itens.count", read_only=True)
    qtd_pendentes = serializers.IntegerField(source="itens_pendentes.count", read_only=True)
    pode_transferir = serializers.BooleanField(read_only=True)
    # Entrada da Ação 1 ("Gerar novo número"): a data de término do novo relatório.
    data_termino_novo = serializers.DateField(write_only=True, required=False)

    class Meta:
        model = Carregamento
        exclude = ["ativo"]
        extra_kwargs = {
            # analista assume o usuário logado; cliente/tecnologia vêm do relatório
            # na Ação 2 (reaproveitar) e são exigidos na Ação 1 (ver validate).
            "analista": {"required": False},
            "cliente": {"required": False},
            "tecnologia": {"required": False},
            "relatorio": {"required": False},
        }

    def validate(self, attrs):
        if not attrs.get("relatorio"):
            # Ação 1: precisa de cliente, tecnologia e a data de término.
            faltando = [c for c in ("cliente", "tecnologia") if not attrs.get(c)]
            if not attrs.get("data_termino_novo"):
                faltando.append("data_termino_novo")
            if faltando:
                raise serializers.ValidationError(
                    {c: "Obrigatório ao gerar um novo número." for c in faltando}
                )
        return attrs

    def create(self, validated_data):
        request = self.context.get("request")
        if request and not validated_data.get("analista"):
            validated_data["analista"] = request.user

        data_coleta = validated_data.get("data_coleta") or timezone.localdate()
        validated_data["data_coleta"] = data_coleta
        data_termino_novo = validated_data.pop("data_termino_novo", None)
        relatorio = validated_data.get("relatorio")

        if relatorio is None:
            # Ação 1 — "Gerar novo número": cria o relatório (fonte do número/datas).
            cliente = validated_data["cliente"]
            tecnologia = validated_data["tecnologia"]
            data_termino = data_termino_novo or data_coleta
            relatorio = Relatorio.objects.create(
                cliente=cliente, tecnologia=tecnologia,
                numero=Relatorio.proximo_numero(tecnologia, data_termino),
                data_inicio=data_coleta, data_termino=data_termino,
            )
            validated_data["relatorio"] = relatorio
        else:
            # Ação 2 — "Utilizar outro número": herda cliente/tecnologia do relatório
            # e recua a data de início se esta coleta for anterior.
            validated_data["cliente"] = relatorio.cliente
            validated_data["tecnologia"] = relatorio.tecnologia
            if relatorio.data_inicio is None or data_coleta < relatorio.data_inicio:
                relatorio.data_inicio = data_coleta
                relatorio.save(update_fields=["data_inicio"])

        carregamento = super().create(validated_data)
        if carregamento.rota_id:
            # Ordem natural de inspeção: área → setor → tag (não a ordem de cadastro).
            equipamentos = carregamento.rota.equipamentos.order_by(
                "setor__area__nome", "setor__nome", "tag"
            )
            ItemInspecao.objects.bulk_create([
                ItemInspecao(carregamento=carregamento, equipamento=eq, ordem=i)
                for i, eq in enumerate(equipamentos, start=1)
            ])
        return carregamento
