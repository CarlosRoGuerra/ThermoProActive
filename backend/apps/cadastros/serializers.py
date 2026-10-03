from rest_framework import serializers

from . import criterios
from .models import (
    Area,
    CategoriaTecnica,
    ClassificacaoInspecao,
    Cliente,
    Componente,
    Condicao,
    CriterioSeveridadeVibracao,
    DadosTecnicosMotor,
    DadosTecnicosTransformador,
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


class _DatasheetSerializer(serializers.ModelSerializer):
    """
    O datasheet só existe para equipamento cujo tipo tem a categoria técnica
    correspondente (vínculo explícito do catálogo). Sem isso, um transformador
    podia ganhar dados de motor — e o motor sincroniza potência/rotação/Classe
    ISO para o equipamento.
    """

    categoria = ""
    rotulo = ""

    def validate(self, attrs):
        equipamento = attrs.get("equipamento") or getattr(self.instance, "equipamento", None)
        tipo = equipamento.tipo_equipamento if equipamento else None
        if tipo is None or tipo.categoria_tecnica != self.categoria:
            nome_tipo = f"do tipo «{tipo.nome}»" if tipo else "sem tipo definido"
            raise serializers.ValidationError({
                "equipamento": (
                    f"Dados técnicos de {self.rotulo} só valem para equipamentos cujo tipo tem a categoria "
                    f"técnica «{CategoriaTecnica(self.categoria).label}». Este equipamento está {nome_tipo}."
                )
            })
        return attrs


class DadosTecnicosMotorSerializer(_DatasheetSerializer):
    categoria = CategoriaTecnica.MOTOR_ELETRICO
    rotulo = "motor"

    class Meta:
        model = DadosTecnicosMotor
        exclude = ["ativo"]


class DadosTecnicosTransformadorSerializer(_DatasheetSerializer):
    categoria = CategoriaTecnica.TRANSFORMADOR
    rotulo = "transformador"

    class Meta:
        model = DadosTecnicosTransformador
        exclude = ["ativo"]


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
    # Tipo vindo do catálogo (Dados de sistema): grava por id, lê o nome.
    tipo_equipamento_nome = serializers.CharField(
        source="tipo_equipamento.nome", read_only=True, default=None
    )
    # Qual datasheet técnico específico mostrar na tela (vínculo do catálogo, não
    # inferido pelo nome do tipo — ver TipoEquipamento.categoria_tecnica).
    categoria_tecnica = serializers.CharField(
        source="tipo_equipamento.categoria_tecnica", read_only=True, default=""
    )
    # A classe de vibração só existe quando o tipo é avaliado por vibração; o
    # critério (limites, norma, origem) vem do perfil normativo, não do equipamento.
    analise_vibracao = serializers.BooleanField(
        source="tipo_equipamento.analise_vibracao", read_only=True, default=False
    )
    criterio_vibracao = serializers.SerializerMethodField()
    # "TAG — nome", para listas de escolha (vários equipamentos têm o mesmo nome).
    identificacao = serializers.SerializerMethodField()
    criticidade_display = serializers.CharField(source="get_criticidade_display", read_only=True)
    # Acesso estruturado pela entidade de equipamento (nested, só leitura — escrita é
    # pelos endpoints próprios /dados-tecnicos-motor/ e /dados-tecnicos-transformador/,
    # mesmo padrão de ServicoCampoSerializer.planos/pontos).
    dados_motor = DadosTecnicosMotorSerializer(read_only=True)
    dados_transformador = DadosTecnicosTransformadorSerializer(read_only=True)

    class Meta:
        model = Equipamento
        fields = [
            "id", "setor", "setor_nome", "area_id", "area_nome", "cliente_id",
            "equipamento_pai", "equipamento_pai_tag", "is_subitem", "nivel",
            "caminho", "qtd_subitens",
            "tag", "nome", "tipo_equipamento", "tipo_equipamento_nome",
            "categoria_tecnica", "tipo",
            "fabricante", "modelo", "numero_serie", "numero_patrimonio", "ano_fabricacao", "potencia_kw",
            "rotacao_nominal_rpm", "classe_iso", "classe_iso_display",
            "analise_vibracao", "criterio_vibracao", "identificacao",
            "criticidade", "criticidade_display",
            "tensao_nominal", "fator_potencia_nominal",
            "dados_motor", "dados_transformador",
            "componentes", "criado_em",
        ]
        read_only_fields = ["tipo"]

    def get_identificacao(self, obj) -> str:
        return " — ".join(x for x in (obj.tag, obj.nome) if x)

    def get_criterio_vibracao(self, obj):
        tipo = obj.tipo_equipamento
        if not (tipo and tipo.analise_vibracao and obj.classe_iso):
            return None
        cliente_id = obj.setor.area.cliente_id if obj.setor_id else None
        # Uma consulta por (classe, cliente) na listagem inteira, não por equipamento.
        cache = self.context.setdefault("_criterios_vibracao", {})
        chave = (obj.classe_iso, cliente_id)
        if chave not in cache:
            cache[chave] = criterios.resumo_criterio(criterios.criterio_vigente(obj.classe_iso, cliente_id=cliente_id))
        return cache[chave]

    def validate(self, attrs):
        """Roda a checagem de ciclo do modelo também na API."""
        instancia = Equipamento(**{**{f: getattr(self.instance, f, None) for f in ()}, **attrs})
        instancia.pk = self.instance.pk if self.instance else None
        instancia.clean()
        # Tipo que não é avaliado por vibração não carrega classe de vibração
        # (ex.: transformador) — o "II" padrão do model não vira dado.
        if "tipo_equipamento" in attrs:
            tipo = attrs["tipo_equipamento"]
        else:
            tipo = getattr(self.instance, "tipo_equipamento", None)
        if tipo is not None and not tipo.analise_vibracao:
            attrs["classe_iso"] = ""
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
    categoria_tecnica_display = serializers.CharField(source="get_categoria_tecnica_display", read_only=True)

    class Meta:
        model = TipoEquipamento
        exclude = ["ativo"]

    def validate(self, attrs):
        def valor(campo, padrao):
            return attrs.get(campo, getattr(self.instance, campo, padrao))

        categoria = valor("categoria_tecnica", "")
        if categoria == CategoriaTecnica.TRANSFORMADOR and valor("analise_vibracao", False):
            raise serializers.ValidationError({
                "analise_vibracao": "Transformador não é avaliado por severidade de vibração (máquina estática).",
            })
        # Trocar a categoria de um tipo que já tem datasheets deixaria esses
        # equipamentos com dados técnicos de outra categoria.
        antiga = getattr(self.instance, "categoria_tecnica", "")
        relacao = {
            CategoriaTecnica.MOTOR_ELETRICO: "dados_motor",
            CategoriaTecnica.TRANSFORMADOR: "dados_transformador",
        }.get(antiga)
        if self.instance and relacao and categoria != antiga and Equipamento.objects.filter(
            tipo_equipamento=self.instance, **{f"{relacao}__isnull": False}
        ).exists():
            raise serializers.ValidationError({
                "categoria_tecnica": (
                    f"Há equipamentos deste tipo com dados técnicos de «{CategoriaTecnica(antiga).label}». "
                    "Mude o tipo desses equipamentos antes de trocar a categoria."
                ),
            })
        return attrs


class CriterioSeveridadeVibracaoSerializer(serializers.ModelSerializer):
    origem_display = serializers.CharField(source="get_origem_display", read_only=True)
    classe_display = serializers.CharField(source="get_classe_display", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True, default=None)

    class Meta:
        model = CriterioSeveridadeVibracao
        exclude = ["ativo"]

    def validate(self, attrs):
        def valor(campo):
            return attrs.get(campo, getattr(self.instance, campo, None))

        ab, bc, cd = valor("limite_ab"), valor("limite_bc"), valor("limite_cd")
        if None not in (ab, bc, cd) and not (ab <= bc <= cd):
            raise serializers.ValidationError("Os limites precisam ser crescentes: A/B ≤ B/C ≤ C/D.")
        inicio, fim = valor("vigencia_inicio"), valor("vigencia_fim")
        if inicio and fim and fim < inicio:
            raise serializers.ValidationError({"vigencia_fim": "O fim da vigência não pode ser anterior ao início."})
        if valor("origem") not in (None, "NORMA") and not (valor("fonte") or "").strip():
            raise serializers.ValidationError({
                "fonte": "Critério fora da norma precisa da fonte (ata, contrato, e-mail) que o sustenta.",
            })
        return attrs


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


class CondicaoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Condicao
        exclude = ["ativo"]


class GrupoAcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = GrupoAcesso
        exclude = ["ativo"]


class RotaSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    tecnologia_nome = serializers.CharField(source="tecnologia.nome", read_only=True, default=None)
    qtd_equipamentos = serializers.IntegerField(source="equipamentos.count", read_only=True)

    class Meta:
        model = Rota
        exclude = ["ativo"]
