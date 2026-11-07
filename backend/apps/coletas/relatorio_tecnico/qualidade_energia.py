"""Módulo de relatório da qualidade de energia (Anexo I 2.3.2.10) — inspeção por rota.

A OSP mostra, para cada grandeza (THD de tensão, THD de corrente e desequilíbrio de tensão), a
última leitura do equipamento até a data de término do relatório, com a janela de agregação e a
condição (só com critério cadastrado e validado, sentido superior).
"""
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import ModuloInspecaoRota

GLOSSARIO_QUALIDADE_ENERGIA = GLOSSARIO_GENERICO + (
    ("6.8", "THD-V", "Distorção harmônica total de tensão (%): razão entre os harmônicos e a componente fundamental."),
    ("6.9", "THD-I", "Distorção harmônica total de corrente (%): razão entre os harmônicos e a componente fundamental."),
    ("6.10", "DESEQ", "Desequilíbrio de tensão (%) entre as fases, pelo método adotado pelo analisador."),
    ("6.11", "AGR", "Janela de agregação: intervalo e critério estatístico com que o analisador resume a leitura."),
)

CONSIDERACOES_QUALIDADE_ENERGIA = (
    CONSIDERACOES_GENERICAS[0],
    "A condição de cada grandeza só é classificada com critério cadastrado e validado para a instalação; "
    "não há limiar universal de distorção harmônica nem de desequilíbrio neste relatório.",
    "A leitura apresentada é uma amostra da janela de agregação registrada. Não constitui, sozinha, um "
    "estudo completo de qualidade de energia.",
    *CONSIDERACOES_GENERICAS[1:],
)

MODULO_QUALIDADE_ENERGIA = ModuloInspecaoRota(
    chave="QUALIDADE_ENERGIA",
    carta_glossario=GLOSSARIO_QUALIDADE_ENERGIA,
    carta_consideracoes=CONSIDERACOES_QUALIDADE_ENERGIA,
)


def ultimo_qualidade_energia(cliente_id, equipamento_id, ate):
    """Última leitura de cada grandeza até `ate`, com a condição, ou None. Não grava nada."""
    from apps.coletas.qualidade_energia import GRANDEZAS, classificar_superior, ultimas_leituras
    from apps.preditiva.tendencia import limites_medicao

    ultimas = ultimas_leituras(cliente_id, equipamento_id, ate)
    if not ultimas:
        return None
    saida = {}
    for grandeza in GRANDEZAS:
        medicao = ultimas.get(grandeza)
        if medicao is None:
            saida[grandeza] = None
            continue
        limite = limites_medicao(medicao)
        valores = {v["nivel"]: v["valor"] for v in limite["limites"]}
        superior = all(v["sentido"] == "SUPERIOR" for v in limite["limites"]) if limite["limites"] else False
        saida[grandeza] = {
            "data": medicao.inspecao.data.isoformat(),
            "valor": str(medicao.valor),
            "janela_agregacao": (medicao.parametros or {}).get("janela_agregacao", ""),
            "condicao": classificar_superior(medicao.valor, valores) if (limite["validado"] and superior) else "PENDENTE",
            "criterio_validado": bool(limite["validado"]),
        }
    return saida
