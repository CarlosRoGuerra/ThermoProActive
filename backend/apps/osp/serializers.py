from rest_framework import serializers

from .models import OrdemServico


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
            # Conteúdo técnico (Seção D)
            "grau_risco", "grau_risco_display", "grau_risco_descricao", "prazo_dias",
            "acompanhamento", "acompanhamento_display",
            "anomalia", "recomendacao", "observacao", "componente",
            "amplitude_velocidade", "amplitude_aceleracao",
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
        read_only_fields = ["numero", "gerada_automaticamente", "criticidade_origem", "finalizada_em"]

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
