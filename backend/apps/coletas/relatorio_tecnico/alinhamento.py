"""Módulos de relatório do alinhamento a laser entre eixos e polias (Anexo I 2.3.2.8.1.1–2) — inspeção por rota.

A OSP mostra o último serviço de alinhamento do equipamento até a data de término do relatório: antes
e depois da correção, nos dois planos (vertical e horizontal), rpm, correções nos pés, redução do
desalinhamento e condição (só com tolerância cadastrada e validada).
"""
from .generico import CONSIDERACOES_GENERICAS, GLOSSARIO_GENERICO
from .inspecao import ModuloInspecaoRota

GLOSSARIO_ALINHAMENTO = GLOSSARIO_GENERICO + (
    ("6.8", "PAR", "Desalinhamento paralelo (mm): deslocamento lateral entre as linhas de centro dos eixos ou polias."),
    ("6.9", "ANG", "Desalinhamento angular (mm/100 mm): inclinação entre as linhas de centro, por 100 mm de distância."),
    ("6.10", "VERT", "Plano vertical do alinhamento a laser."),
    ("6.11", "HOR", "Plano horizontal do alinhamento a laser."),
    ("6.12", "RPM", "Rotação em que o alinhamento foi executado."),
)

CONSIDERACOES_ALINHAMENTO = (
    CONSIDERACOES_GENERICAS[0],
    "A tolerância de alinhamento depende do fabricante e da rotação. A condição só é classificada com "
    "tolerância cadastrada e validada para o equipamento; sem ela, permanece pendente.",
    "Os calços e deslocamentos nos pés são os registrados na execução. O relatório não calcula correções.",
    *CONSIDERACOES_GENERICAS[1:],
)

MODULO_ALINHAMENTO_EIXOS = ModuloInspecaoRota(
    chave="ALINHAMENTO_EIXOS",
    carta_glossario=GLOSSARIO_ALINHAMENTO,
    carta_consideracoes=CONSIDERACOES_ALINHAMENTO,
    # 12 termos não cabem numa A4 (medido no PDF): os do alinhamento (6.8–6.12) abrem a segunda folha.
    carta_quebras_glossario=("6.8",),
)

MODULO_ALINHAMENTO_POLIAS = ModuloInspecaoRota(
    chave="ALINHAMENTO_POLIAS",
    carta_glossario=GLOSSARIO_ALINHAMENTO,
    carta_consideracoes=CONSIDERACOES_ALINHAMENTO,
    # 12 termos não cabem numa A4 (medido no PDF): os do alinhamento (6.8–6.12) abrem a segunda folha.
    carta_quebras_glossario=("6.8",),
)

SUBTIPO_POR_CHAVE = {"ALINHAMENTO_EIXOS": "ALINHAMENTO_EIXOS", "ALINHAMENTO_POLIAS": "ALINHAMENTO_POLIAS"}


def ultimo_alinhamento(cliente_id, equipamento_id, ate, chave):
    """Último serviço de alinhamento (eixos ou polias) do equipamento até `ate`, ou None. Não grava nada."""
    from apps.coletas.alinhamento import analise_par
    from apps.coletas.models import MedicaoTecnica

    subtipo = SUBTIPO_POR_CHAVE[chave]
    qs = MedicaoTecnica.objects.filter(
        subtipo=subtipo, equipamento_id=equipamento_id, inspecao__cliente_id=cliente_id,
    ).select_related("inspecao", "equipamento", "componente", "instrumento")
    if ate is not None:
        qs = qs.filter(inspecao__data__lte=ate)
    medicao = qs.order_by("-data_hora", "-pk").first()
    if medicao is None:
        return None
    analise = analise_par(medicao)
    faltando = [nome for nome, ok in (
        ("tolerância de desalinhamento angular (mm/100 mm)", analise["criterio_angular_validado"]),
        ("tolerância de desalinhamento paralelo (mm)", analise["criterio_paralelo_validado"]),
    ) if not ok]
    return {
        "data": medicao.inspecao.data.isoformat(),
        "ponto": medicao.ponto_medicao,
        "antes": analise["antes"],
        "depois": analise["depois"],
        "reducao_angular_pct": analise["reducao_angular_pct"],
        "reducao_paralelo_pct": analise["reducao_paralelo_pct"],
        "condicao": analise["condicao"],
        "condicao_angular": analise["condicao_angular"],
        "condicao_paralelo": analise["condicao_paralelo"],
        "criterio_validado": analise["criterio_angular_validado"] or analise["criterio_paralelo_validado"],
        # Origem do critério que classificou (o angular é o da condição; o paralelo complementa).
        "criterio": {"angular": analise["criterio_angular"], "paralelo": analise["criterio_paralelo"]},
        "limites": {"angular": analise["limites_angular"], "paralelo": analise["limites_paralelo"]},
        "pendencias": [f"Cadastrar e validar a {nome} para este equipamento." for nome in faltando],
    }
