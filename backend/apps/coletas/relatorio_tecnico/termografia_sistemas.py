"""Módulos de relatório da termografia de sistemas mecânicos e de processos (Anexo I 2.3.2.2.2–4).

Mesma família da termografia elétrica (medições térmicas, ΔT, imagem térmica), mas com glossário
próprio: sem grandezas elétricas, sem Grau de Risco por faixa de ΔT e sem carga/IC, que são do
sistema elétrico (`docs/12`). A faixa de ΔT que separa normal, alerta e crítico não é fixa aqui:
vem do `LimiteAlarmeSerie` validado do sistema e do equipamento (ver `docs/26`).

- `TERMOGRAFIA_MECANICA`: sistemas mecânicos dinâmicos e estáticos (`sistema` MEC_DINAMICO ou MEC_ESTATICO);
- `TERMO_PROCESSOS`: processos industriais (`sistema` PROCESSO).

A ΔT é aritmética. Sem critério validado a condição sai PENDENTE, e o relatório diz o que falta.
"""
from apps.coletas.alinhamento import texto_limite
from apps.coletas.relatorio_tecnico.inspecao import ModuloInspecaoRota, MEDIA_TEMPERATURA
from apps.coletas.relatorio_tecnico.termografia import CONSIDERACOES_TERMOGRAFIA

GLOSSARIO_TERMOGRAFIA_SISTEMAS = (
    ("6.1", "Temperaturas", ""),
    ("6.1.1", "T.M.", "Temperatura Monitorada: temperatura mensurada do componente foco da medição, que apresenta diferencial em relação à temperatura de referência."),
    ("6.1.2", "T.R.", "Temperatura de Referência: temperatura mensurada de componente similar, sem anomalia, submetido às mesmas condições de operação do componente foco da medição."),
    ("6.1.3", "ΔT", "Delta de Temperatura: diferença matemática entre a temperatura monitorada e a temperatura de referência."),
    ("6.2", "Critério de condição", ""),
    ("6.2.1", "Critério", "A condição (normal, alerta ou crítico) é classificada pela faixa de ΔT cadastrada e validada para o sistema e o equipamento. O relatório mostra a origem e a fonte desse critério."),
    ("6.2.2", "Pendente", "Sem critério validado para o sistema e o equipamento, o ΔT é apresentado sem classificação. O diferencial térmico não determina sozinho a condição do equipamento."),
    ("6.3", "O.S.P.", "Ordem de Serviço Preditivo: ordem de serviço gerada para correção de cada anomalia detectada."),
    ("6.4", "PDM", "Parado Devido à Manutenção: equipamento parado devido a alguma intervenção da equipe de manutenção."),
    ("6.5", "PDP", "Parado Devido ao Processo: equipamento parado devido ao processo produtivo."),
    ("6.6", "MP", "Monitoramento Prejudicado: existe obstrução parcial, física ou não, ao componente foco da medição."),
    ("6.7", "NM", "Não Monitorado: existe obstrução total, física ou não, ao componente foco da medição, e/ou condição que coloque em risco a integridade física dos trabalhadores."),
)

MODULO_TERMOGRAFIA_MECANICA = ModuloInspecaoRota(
    chave="TERMOGRAFIA_MECANICA",
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA_SISTEMAS,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
)

MODULO_TERMO_PROCESSOS = ModuloInspecaoRota(
    chave="TERMO_PROCESSOS",
    medias=(MEDIA_TEMPERATURA,),
    carta_glossario=GLOSSARIO_TERMOGRAFIA_SISTEMAS,
    carta_consideracoes=CONSIDERACOES_TERMOGRAFIA,
)

#: Sistemas do `LimiteAlarmeSerie` que cada módulo mecânico aceita (além do cadastro sem sistema).
SISTEMAS_POR_MODULO = {
    "TERMOGRAFIA_MECANICA": ("MEC_DINAMICO", "MEC_ESTATICO"),
    "TERMO_PROCESSOS": ("PROCESSO",),
}

PENDENCIA_DELTA = (
    "Cadastrar e validar o critério de ΔT para este equipamento em Cadastros → Limites de alarme "
    "(termografia, sistema mecânico ou de processo). Sem ele, a condição não é classificada."
)


def criterio_delta_t(cliente_id, equipamento_id, data, chave, delta):
    """Condição do ΔT pelo critério VALIDADO do sistema (ou PENDENTE, com o que falta). Não grava nada.

    `chave` é o módulo (TERMOGRAFIA_MECANICA ou TERMO_PROCESSOS). Critério mais específico primeiro:
    equipamento, depois sistema, depois cliente, depois vigência mais recente. Sem nenhum VALIDADO,
    o ΔT sai sem classificação.
    """
    from django.db.models import Q
    from django.utils import timezone

    from apps.coletas.ultrassom import classificar_superior
    from apps.preditiva.models import LimiteAlarmeSerie, Validacao

    data = data or timezone.localdate()
    qs = LimiteAlarmeSerie.objects.filter(
        ativo=True, modalidade="TERMOGRAFIA", grandeza="delta_t", unidade="°C", sentido="SUPERIOR",
        validacao=Validacao.VALIDADA,
    ).filter(
        Q(cliente__isnull=True) | Q(cliente_id=cliente_id),
        Q(equipamento__isnull=True) | Q(equipamento_id=equipamento_id),
        Q(sistema="") | Q(sistema__in=SISTEMAS_POR_MODULO[chave]),
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    escolhidos = sorted(qs, key=lambda c: (
        0 if c.equipamento_id else 1, 0 if c.sistema else 1, 0 if c.cliente_id else 1,
        -(c.vigencia_inicio.toordinal() if c.vigencia_inicio else 0), -c.pk,
    ))
    if not escolhidos:
        return {"condicao": "PENDENTE", "limites": {}, "criterio": None, "pendencia": PENDENCIA_DELTA}
    c = escolhidos[0]
    limites = {}
    if c.valor_alerta is not None:
        limites["ALERTA"] = texto_limite(c.valor_alerta)
    if c.valor_critico is not None:
        limites["CRITICO"] = texto_limite(c.valor_critico)
    criterio = {"id": c.pk, "origem": c.origem, "origem_display": c.get_origem_display(), "fonte": c.fonte,
                "validacao": c.validacao}
    if delta is None:
        return {"condicao": "PENDENTE", "limites": limites, "criterio": criterio,
                "pendencia": "Temperatura medida ou de referência não registrada: o ΔT não foi calculado."}
    limites_dec = {"ALERTA": c.valor_alerta, "CRITICO": c.valor_critico}
    condicao = classificar_superior(delta, limites_dec)
    return {"condicao": condicao, "limites": limites, "criterio": criterio, "pendencia": ""}
