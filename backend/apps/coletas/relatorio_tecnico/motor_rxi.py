"""Módulo de relatório da resistência de isolação de motores (Anexo I 2.3.2.5.1.1) — inspeção por rota.

A OSP mostra o último grupo de leituras do motor (mesmo equipamento e cliente) até a data
de término do relatório: tensão e temperatura de ensaio, R30, R60, R600, DAR, IP e condição
(só com critério cadastrado e validado).
"""
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import ModuloInspecaoRota

GLOSSARIO_MOTOR_RXI = GLOSSARIO_GENERICO + (
    ("6.8", "R30", "Resistência de isolação lida em 30 s após a aplicação da tensão de ensaio (MΩ)."),
    ("6.9", "R60", "Resistência de isolação lida em 60 s após a aplicação da tensão de ensaio (MΩ)."),
    ("6.10", "R600", "Resistência de isolação lida em 600 s (10 min) após a aplicação da tensão de ensaio (MΩ)."),
    ("6.11", "DAR", "Índice de absorção dielétrica: R60 ÷ R30."),
    ("6.12", "IP", "Índice de polarização: R600 ÷ R60."),
)

CONSIDERACOES_MOTOR_RXI = (
    CONSIDERACOES_GENERICAS[0],
    "Os índices são razões entre leituras do mesmo ensaio (mesma tensão, temperatura e ligação). A condição "
    "só é classificada com critério cadastrado e validado para o motor; sem ele, permanece pendente.",
    "O resultado do ensaio de isolação depende da temperatura e da umidade do enrolamento na leitura. "
    "Não é um diagnóstico de falha.",
    *CONSIDERACOES_GENERICAS[1:],
)

MODULO_MOTOR_RXI = ModuloInspecaoRota(
    chave="MOTOR_RXI",
    carta_glossario=GLOSSARIO_MOTOR_RXI,
    carta_consideracoes=CONSIDERACOES_MOTOR_RXI,
)


def ultimo_motor_rxi(cliente_id, equipamento_id, ate):
    """Último grupo de leituras de isolação do equipamento até `ate` (data), ou None. Não grava nada."""
    from apps.coletas.models import MedicaoTecnica
    from apps.coletas.motor_rxi import analise_grupo

    qs = MedicaoTecnica.objects.filter(
        subtipo="MOTOR_RI", equipamento_id=equipamento_id, inspecao__cliente_id=cliente_id,
    ).select_related("inspecao", "equipamento", "componente", "instrumento")
    if ate is not None:
        qs = qs.filter(inspecao__data__lte=ate)
    medicao = qs.order_by("-data_hora", "-pk").first()
    if medicao is None:
        return None
    analise = analise_grupo(medicao)
    return {
        "data": medicao.inspecao.data.isoformat(),
        "ponto": medicao.ponto_medicao,
        "tensao_ensaio_v": analise["tensao_ensaio_v"],
        "temperatura_c": analise["temperatura_c"],
        "ligacao": analise["ligacao"],
        "R30": analise["leituras"]["30"],
        "R60": analise["leituras"]["60"],
        "R600": analise["leituras"]["600"],
        "DAR": analise["DAR"],
        "IP": analise["IP"],
        "condicao": analise["condicao"],
        "criterio_validado": bool(analise["criterios"]["DAR"] or analise["criterios"]["IP"]),
    }
