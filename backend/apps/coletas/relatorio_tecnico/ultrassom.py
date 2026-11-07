"""Módulo de relatório do ultrassom elétrico e mecânico (Anexo I 2.3.2.6) — inspeção por rota.

A OSP mostra a última leitura de ultrassom do equipamento até a data de término do relatório:
subtipo, nível em dB, ganho, distância, frequência quando registrada e condição (só com critério
cadastrado e validado, sentido superior).
"""
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import ModuloInspecaoRota

GLOSSARIO_ULTRASSOM = GLOSSARIO_GENERICO + (
    ("6.8", "dB", "Nível de ultrassom em decibéis, na escala do instrumento usado na leitura."),
    ("6.9", "GANHO", "Ganho do instrumento durante a leitura (dB). Níveis só são comparados com o mesmo ganho."),
    ("6.10", "DIST", "Distância entre o sensor e a fonte de ultrassom na leitura (cm)."),
    ("6.11", "UE", "Ultrassom elétrico: detecção de descargas e ruídos de origem elétrica."),
    ("6.12", "UM", "Ultrassom mecânico: detecção de atrito e impacto em componentes girantes."),
)

CONSIDERACOES_ULTRASSOM = (
    CONSIDERACOES_GENERICAS[0],
    "O nível em dB depende do instrumento, do ganho, da distância e da frequência. Leituras com condições "
    "diferentes não são comparadas. A condição só é classificada com critério cadastrado e validado para a "
    "modalidade e a aplicação; sem ele, permanece pendente.",
    "A leitura de ultrassom é um indício que orienta a inspeção. Não identifica, sozinha, a causa da condição "
    "observada.",
    *CONSIDERACOES_GENERICAS[1:],
)

MODULO_ULTRASSOM = ModuloInspecaoRota(
    chave="ULTRASSOM",
    carta_glossario=GLOSSARIO_ULTRASSOM,
    carta_consideracoes=CONSIDERACOES_ULTRASSOM,
)


def ultimo_ultrassom(cliente_id, equipamento_id, ate):
    """Última leitura de ultrassom do equipamento até `ate` com a condição, ou None. Não grava nada."""
    from apps.coletas.ultrassom import classificar_superior, ultima_leitura
    from apps.preditiva.tendencia import limites_medicao

    medicao = ultima_leitura(cliente_id, equipamento_id, ate)
    if medicao is None:
        return None
    limite = limites_medicao(medicao)
    valores = {v["nivel"]: v["valor"] for v in limite["limites"]}
    superior = all(v["sentido"] == "SUPERIOR" for v in limite["limites"]) if limite["limites"] else False
    condicao = classificar_superior(medicao.valor, valores) if (limite["validado"] and superior) else "PENDENTE"
    parametros = medicao.parametros or {}
    return {
        "data": medicao.inspecao.data.isoformat(),
        "subtipo": medicao.subtipo or "",
        "grandeza": medicao.grandeza,
        "nivel_db": str(medicao.valor),
        "ganho_db": str(parametros.get("ganho_db", "")),
        "distancia_cm": str(parametros.get("distancia_cm", "")),
        "frequencia_khz": str(parametros["frequencia_khz"]) if parametros.get("frequencia_khz") not in (None, "") else None,
        "condicao": condicao,
        "criterio_validado": bool(limite["validado"]),
    }
