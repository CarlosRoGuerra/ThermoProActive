"""
Conteúdo da Carta ao Cliente dos relatórios de ensaios elétricos de subestação (TC, TP,
DJ, CS e RP).

Não há relatório de referência do cliente para estes equipamentos: os textos são a
PROPOSTA de docs/25, escrita a partir das normas citadas nas fichas (IEC 61869-2 e -3,
IEEE C57.13, ANSI/NETA ATS, IEC 62271-100, IEC 60255-151) — validar com o responsável
técnico do cliente (docs/25, seção 6).
"""

_CRITICIDADE = ("Criticidade", "Prioridade do laudo de cada ensaio: Rotina, Alerta ou Crítica. Não se confunde com o Grau de Risco das inspeções.")

CONSIDERACOES_SUBESTACAO = (
    "Os ensaios foram realizados com instrumentos identificados na ficha de cada ensaio. Os valores são "
    "apresentados como medidos: quando a norma ou o fabricante não define um limite universal, o resultado "
    "sai como informativo, sem critério de aceitação definido.",
    "Os erros de relação de TC e TP são avaliados pela classe de exatidão da placa, na tabela da norma do "
    "equipamento. Os erros de pickup e de tempo dos relés são avaliados pela tolerância informada em cada "
    "lançamento, que deve estar de acordo com o ajuste e com a norma de método adotada.",
)


def _conteudo(equipamento_plural: str) -> tuple:
    return (
        "Seção A – Carta ao Cliente",
        "Seção B – KPI’s Dashboard",
        "Seção C – Relação de Equipamentos Contemplados",
        f"Seção D – Fichas dos Ensaios Elétricos de {equipamento_plural} [registro e resultados dos ensaios]",
    )


def _glossario(termos_especificos: tuple) -> tuple:
    return (
        ("6.1", "Ensaios", ""),
        *termos_especificos,
        ("6.2", "Termos", ""),
        ("6.2.1", "Medido", "Valor lido no ensaio, no mesmo tipo de grandeza da coluna."),
        ("6.2.2", "Esperado / nominal", "Valor de referência do ensaio: relação nominal da placa, valor esperado do ajuste ou tempo da curva."),
        ("6.2.3", "Erro (%)", "Diferença percentual entre o medido e o esperado: (medido − esperado) ÷ esperado × 100."),
        ("6.2.4", "Classe de exatidão", "Classe da placa do TC ou TP; define o erro de relação admissível pela norma do equipamento."),
        ("6.2.5", "Simultaneidade", "Diferença entre o maior e o menor tempo de operação entre os polos do disjuntor (ms)."),
        ("6.3",) + _CRITICIDADE,
    )


GLOSSARIO_TC = _glossario((
    ("6.1.1", "RELA", "Relação de transformação e polaridade: relação entre a corrente primária e a secundária, comparada com a relação nominal da placa, e sentido relativo dos terminais."),
    ("6.1.2", "EXC", "Saturação: curva de corrente de excitação em função da tensão aplicada ao secundário, por núcleo."),
    ("6.1.3", "ISO", "Resistência de isolação: resistência entre enrolamentos e destes para a massa, em tensão contínua."),
    ("6.1.4", "OHM", "Resistência ôhmica: resistência em corrente contínua do enrolamento secundário."),
))

GLOSSARIO_TP = _glossario((
    ("6.1.1", "RELA", "Relação de transformação e polaridade: relação entre a tensão primária e a secundária, comparada com a relação nominal da placa."),
    ("6.1.2", "ISO", "Resistência de isolação: resistência entre enrolamentos e destes para a massa, em tensão contínua."),
    ("6.1.3", "OHM", "Resistência ôhmica: resistência em corrente contínua do enrolamento."),
))

GLOSSARIO_DJ = _glossario((
    ("6.1.1", "RCON", "Resistência de contatos: resistência de cada polo fechado, medida com corrente contínua."),
    ("6.1.2", "ISO", "Resistência de isolação: isolação entre polos e para a massa."),
    ("6.1.3", "TEMP", "Tempos de operação: tempo de abertura e de fechamento de cada polo, medidos durante a manobra."),
))

GLOSSARIO_CS = _glossario((
    ("6.1.1", "RCON", "Resistência de contatos: resistência de cada fase com a chave fechada, medida com corrente contínua."),
    ("6.1.2", "ISO", "Resistência de isolação: isolação de cada fase para a massa e entre fases."),
))

GLOSSARIO_RP = _glossario((
    ("6.1.1", "PICK", "Pickup das funções: corrente de atuação de cada função de proteção (ANSI 50, 51, 50N, 51N e outras), comparada com o valor esperado."),
    ("6.1.2", "TEMP", "Tempo de atuação: tempo entre a injeção da grandeza e o comando de disparo, comparado com o tempo esperado pela curva ajustada."),
    ("6.1.3", "Tolerância", "Tolerância informada no lançamento, conforme o ajuste e a norma de método (IEC 60255-151)."),
))

CONTEUDO_TC = _conteudo("Transformadores de Corrente")
CONTEUDO_TP = _conteudo("Transformadores de Potencial")
CONTEUDO_DJ = _conteudo("Disjuntores")
CONTEUDO_CS = _conteudo("Chaves Seccionadoras")
CONTEUDO_RP = _conteudo("Relés de Proteção")
