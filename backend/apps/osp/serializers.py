from rest_framework import serializers

from . import services
from .models import HistoricoOSP, OrdemServico


class OrdemServicoSerializer(serializers.ModelSerializer):
    """
    A OSP é o único recurso em que o Portal escreve — e só nos campos de
    RETORNO DE INFORMAÇÃO (`CAMPOS_RETORNO_CLIENTE`): quando a corretiva foi
    planejada e executada, por quem, o que foi feito, se a abertura da máquina
    confirmou o diagnóstico, e quanto custou de fato.

    Todo o resto (título, grau de risco, anomalia, recomendação, amplitudes,
    status, acompanhamento, responsável, SLA) é diagnóstico técnico da
    CONTRATADA e fica somente-leitura para o cliente. A trava é aplicada em
    `__init__`, ou seja, vale para qualquer caminho de escrita — não depende de
    o formulário do front esconder o campo.
    """

    #: Campos que o cliente devolve preenchidos. Espelha os dois blocos
    #: marcados no modelo: "Etapas alimentadas pelo cliente" e
    #: "Avaliação de Resultados" (a base do ROI da Seção D).
    CAMPOS_RETORNO_CLIENTE = frozenset({
        # Etapas da execução
        "planejado_em", "planejado_por",
        "executado_em", "executado_por",
        "finalizado_por", "descricao_corretiva", "resultado_confirmacao",
        # Avaliação de Resultados — custo real, que só o cliente conhece
        "pred_mao_obra_h", "pred_mao_obra_valor",
        "pred_terceirizado_h", "pred_terceirizado_valor",
        "pred_material_valor", "pred_producao_h", "pred_producao_valor",
        "pred_outros_valor",
        "emerg_mao_obra_h", "emerg_mao_obra_valor",
        "emerg_terceirizado_h", "emerg_terceirizado_valor",
        "emerg_material_valor", "emerg_producao_h", "emerg_producao_valor",
        "emerg_outros_valor",
        "custo_real",
    })

    aprovado_por_nome = serializers.CharField(source="aprovado_por.nome", read_only=True, default=None)
    sla_cumprido = serializers.BooleanField(read_only=True, allow_null=True)
    tempo_ciclo_horas = serializers.FloatField(read_only=True, allow_null=True)
    # O que ESTE usuário pode fazer agora (botões do front e prova das permissões).
    transicoes_permitidas = serializers.SerializerMethodField()
    # Evidências fotográficas (2.6.2.4): as da análise que originou a OSP.
    evidencias = serializers.SerializerMethodField()

    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    responsavel_nome = serializers.CharField(source="responsavel.nome", read_only=True, default=None)
    prioridade_display = serializers.CharField(source="get_prioridade_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    sla_vencido = serializers.BooleanField(read_only=True)
    # Seção D do relatório: grau de risco e a Avaliação de Resultados.
    grau_risco_display = serializers.CharField(source="get_grau_risco_display", read_only=True)
    acompanhamento_display = serializers.CharField(source="get_acompanhamento_display", read_only=True)
    grau_risco_descricao = serializers.CharField(read_only=True)
    resultado_confirmacao_display = serializers.CharField(source="get_resultado_confirmacao_display", read_only=True)
    prazo_dias = serializers.IntegerField(read_only=True)
    total_preditiva = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_emergencial = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    retorno_investimento = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    planejado_por_nome = serializers.CharField(source="planejado_por.nome", read_only=True, default=None)
    executado_por_nome = serializers.CharField(source="executado_por.nome", read_only=True, default=None)
    finalizado_por_nome = serializers.CharField(source="finalizado_por.nome", read_only=True, default=None)
    # Fluxo novo: OSP gerada de uma análise. "OSP | Código" = sequencial_cliente | id.
    # A data de referência/auditoria vem do relatório (data de término).
    data_auditoria = serializers.DateField(
        source="achado.item.carregamento.relatorio.data_termino", read_only=True, default=None
    )
    numero_relatorio = serializers.CharField(
        source="achado.item.carregamento.relatorio.numero", read_only=True, default=None
    )

    class Meta:
        model = OrdemServico
        fields = [
            "id", "numero", "sequencial_cliente", "sequencial_global", "achado",
            "data_auditoria", "numero_relatorio",
            "cliente", "cliente_nome", "equipamento", "equipamento_tag",
            "inspecao", "titulo", "descricao", "prioridade", "prioridade_display",
            "status", "status_display", "criticidade_origem", "gerada_automaticamente",
            "responsavel", "responsavel_nome", "sla_data", "sla_vencido",
            "sla_origem", "sla_cumprido", "tempo_ciclo_horas",
            "aprovado_por", "aprovado_por_nome", "aprovado_em",
            "transicoes_permitidas", "evidencias",
            # Conteúdo técnico (Seção D)
            "grau_risco", "grau_risco_display", "grau_risco_descricao", "prazo_dias",
            "acompanhamento", "acompanhamento_display",
            "anomalia", "recomendacao", "observacao", "componente",
            "amplitude_velocidade", "amplitude_aceleracao", "amplitude_deslocamento",
            # Etapas alimentadas pelo cliente
            "planejado_em", "planejado_por", "planejado_por_nome",
            "executado_em", "executado_por", "executado_por_nome",
            "finalizado_por", "finalizado_por_nome", "descricao_corretiva",
            "resultado_confirmacao", "resultado_confirmacao_display",
            # Avaliação de Resultados
            "pred_mao_obra_h", "pred_mao_obra_valor",
            "pred_terceirizado_h", "pred_terceirizado_valor",
            "pred_material_valor", "pred_producao_h", "pred_producao_valor", "pred_outros_valor",
            "emerg_mao_obra_h", "emerg_mao_obra_valor",
            "emerg_terceirizado_h", "emerg_terceirizado_valor",
            "emerg_material_valor", "emerg_producao_h", "emerg_producao_valor", "emerg_outros_valor",
            "total_preditiva", "total_emergencial", "retorno_investimento",
            "custo_estimado", "custo_real", "finalizada_em", "criado_em",
        ]
        # `status` só muda por `/status/` (máquina de estados + permissão + histórico).
        read_only_fields = [
            "numero", "gerada_automaticamente", "criticidade_origem", "finalizada_em",
            "status", "sla_origem", "aprovado_por", "aprovado_em",
        ]

    def get_transicoes_permitidas(self, obj):
        usuario = getattr(self.context.get("request"), "user", None)
        return services.transicoes_permitidas(usuario, obj) if usuario else []

    def get_evidencias(self, obj):
        if not obj.achado_id:
            return []
        return [
            {"id": img.id, "tipo": img.tipo, "legenda": img.legenda,
             "arquivo": img.arquivo.url if img.arquivo else None}
            for img in obj.achado.imagens.all()
        ]

    def validate_responsavel(self, valor):
        # A OSP é atendida pela CONTRATADA: apontar um usuário do cliente
        # exporia a OSP a quem não a opera (e mostraria o nome na resposta).
        if valor is not None and not (valor.is_interno and valor.is_active):
            raise serializers.ValidationError("O responsável deve ser um técnico ativo da equipe interna.")
        return valor

    def create(self, validated_data):
        osp = OrdemServico(**validated_data)
        osp._ator = getattr(self.context.get("request"), "user", None)
        osp.save()
        return osp

    def update(self, instance, validated_data):
        ator = getattr(self.context.get("request"), "user", None)
        return services.aplicar_edicao(instance.pk, validated_data, ator)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        usuario = getattr(self.context.get("request"), "user", None)
        if not getattr(usuario, "is_cliente", False):
            return
        # Portal: tudo que não é campo de retorno vira leitura. Um PATCH que
        # mande `grau_risco` não levanta erro — o DRF simplesmente descarta o
        # campo somente-leitura, então o diagnóstico da CONTRATADA não é
        # sobrescrito nem por engano nem de propósito.
        for nome, campo in self.fields.items():
            if nome not in self.CAMPOS_RETORNO_CLIENTE:
                campo.read_only = True

        # "Quem planejou/executou/finalizou" é escolhido numa lista de pessoas.
        # Sem recortar o queryset, o Portal poderia apontar um usuário de outra
        # empresa e receber o nome dele de volta em `*_por_nome` — um vazamento
        # entre inquilinos pela porta dos fundos. Só a própria equipe entra.
        equipe = type(usuario).objects.filter(
            cliente_id=usuario.cliente_id, is_active=True
        ) if usuario.cliente_id else type(usuario).objects.none()
        for nome in ("planejado_por", "executado_por", "finalizado_por"):
            self.fields[nome].queryset = equipe


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrdemServico._meta.get_field("status").choices)
    motivo = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class HistoricoOSPSerializer(serializers.ModelSerializer):
    tipo_display = serializers.CharField(source="get_tipo_display", read_only=True)

    class Meta:
        model = HistoricoOSP
        fields = [
            "id", "tipo", "tipo_display", "ator", "ator_nome", "ator_perfil",
            "status_anterior", "status_novo", "alteracoes", "motivo", "criado_em",
        ]
        read_only_fields = fields
