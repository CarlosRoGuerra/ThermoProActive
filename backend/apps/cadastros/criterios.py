"""
Critério de severidade de vibração vigente — o perfil normativo que a análise usa.

O equipamento só informa o grupo (`Equipamento.classe_iso`); os limites vêm de
`CriterioSeveridadeVibracao`, com norma, edição, origem e vigência. Ordem de
escolha, entre os registros ativos do grupo e em vigor na data:

  1. do próprio cliente antes dos que valem para todos;
  2. acordo com o cliente antes da norma, e a norma antes do legado;
  3. a vigência mais recente.

Sem nenhum registro (banco sem a carga inicial, testes de função pura), vale
`apps.coletas.rules.FAIXAS_ISO_VRMS` — os mesmos números da carga inicial.
"""
from datetime import date

from django.db.models import Q

from .models import ClasseISO, CriterioSeveridadeVibracao, OrigemCriterio

PRIORIDADE_ORIGEM = {OrigemCriterio.ACORDO_CLIENTE: 0, OrigemCriterio.NORMA: 1, OrigemCriterio.LEGADO: 2}


def _vigentes(classe, data, cliente_id):
    data = data or date.today()
    qs = CriterioSeveridadeVibracao.objects.ativos().filter(classe=classe).filter(
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    return qs.filter(Q(cliente__isnull=True) | Q(cliente_id=cliente_id)) if cliente_id else qs.filter(cliente__isnull=True)


def _ordenar(criterios, cliente_id):
    return sorted(
        criterios,
        key=lambda c: (
            0 if cliente_id and c.cliente_id == cliente_id else 1,
            PRIORIDADE_ORIGEM.get(c.origem, 9),
            -(c.vigencia_inicio.toordinal() if c.vigencia_inicio else 0),
            -c.id,
        ),
    )


def criterio_vigente(classe, data=None, cliente_id=None):
    """O critério que a análise aplica a uma máquina do grupo `classe` (ou None)."""
    if not classe:
        return None
    candidatos = _ordenar(_vigentes(classe, data, cliente_id), cliente_id)
    return candidatos[0] if candidatos else None


def referencia_da_norma(classe, data=None):
    """O valor publicado pela norma para o grupo (para mostrar a diferença de um acordo)."""
    candidatos = [c for c in _vigentes(classe, data, None) if c.origem == OrigemCriterio.NORMA]
    return _ordenar(candidatos, None)[0] if candidatos else None


def faixas_vigentes(classe, data=None, cliente_id=None):
    """Limites {A, B, C} (mm/s) do critério vigente, no formato de `FAIXAS_ISO_VRMS`; None sem registro."""
    c = criterio_vigente(classe, data, cliente_id)
    if c is None:
        return None
    return {"A": c.limite_ab, "B": c.limite_bc, "C": c.limite_cd}


def descricao_curta(c) -> str:
    """'ISO 10816-1:1995, classe II — limite por acordo com o cliente' (vazio sem critério)."""
    if c is None:
        return ""
    norma = f"{c.norma_codigo}:{c.norma_edicao}" if c.norma_edicao else c.norma_codigo
    texto = f"{norma}, classe {c.classe}"
    if c.origem == OrigemCriterio.ACORDO_CLIENTE:
        texto += " — limites por acordo com o cliente"
    elif c.origem == OrigemCriterio.LEGADO:
        texto += " — limites legados, origem não documentada"
    return texto


def resumo_criterio(c):
    """O critério como o cadastro e a carta mostram: norma, grupo, limites e origem."""
    if c is None:
        return None
    return {
        "id": c.id,
        "norma": c.norma_codigo,
        "edicao": c.norma_edicao,
        "classe": c.classe,
        "descricao_grupo": c.descricao_grupo,
        "limites": {"ab": c.limite_ab, "bc": c.limite_bc, "cd": c.limite_cd},
        "origem": c.origem,
        "origem_display": c.get_origem_display(),
        "fonte": c.fonte,
        "cliente": c.cliente_id,
    }


def tabela_severidade(data=None, cliente_id=None):
    """
    Critérios aplicados às quatro classes, para a tabela da carta. Quando o
    aplicado não é o da norma, `norma` traz o valor publicado — a carta imprime
    a diferença em nota, em vez de apresentar o acordo como se fosse a ISO.
    """
    linhas = []
    for classe in ClasseISO.values:
        aplicado = criterio_vigente(classe, data, cliente_id)
        if aplicado is None:
            continue
        norma = None if aplicado.origem == OrigemCriterio.NORMA else referencia_da_norma(classe, data)
        linhas.append({**resumo_criterio(aplicado), "referencia_norma": resumo_criterio(norma)})
    return linhas or _tabela_de_reserva()


def _tabela_de_reserva():
    """Sem critério cadastrado: a tabela de reserva do motor de vibração, marcada como legado."""
    from apps.coletas.rules import FAIXAS_ISO_VRMS

    return [
        {
            "id": None, "norma": "ISO 10816-1", "edicao": "", "classe": classe, "descricao_grupo": "",
            "limites": {"ab": f["A"], "bc": f["B"], "cd": f["C"]},
            "origem": OrigemCriterio.LEGADO, "origem_display": OrigemCriterio.LEGADO.label,
            "fonte": "Tabela de reserva do sistema — critérios não cadastrados.", "cliente": None,
            "referencia_norma": None,
        }
        for classe, f in FAIXAS_ISO_VRMS.items()
    ]


def _br(valor) -> str:
    return f"{valor:.2f}".replace(".", ",")


def notas_tabela_severidade(linhas) -> list[str]:
    """
    Notas da tabela da carta para todo limite que não é o publicado pela norma:
    a diferença aparece escrita — o acordo nunca passa por valor da ISO. A fonte
    completa (ata, e-mail, contrato) fica no cadastro do critério.
    """
    notas = []
    nomes = {"ab": "Bom/Satisfatório", "bc": "Satisfatório/Alerta", "cd": "Alerta/Perigo"}
    for c in linhas:
        if c["origem"] == OrigemCriterio.NORMA:
            continue
        if c["origem"] == OrigemCriterio.LEGADO:
            notas.append(f"Classe {c['classe']}: limites legados do sistema, sem fonte documentada.")
            continue
        ref = c.get("referencia_norma")
        norma = f"{ref['norma']}:{ref['edicao']}" if ref and ref["edicao"] else (ref or c)["norma"]
        diferencas = [
            f"limite {nomes[k]} de {_br(c['limites'][k])} mm/s"
            + (f" (a {norma} publica {_br(ref['limites'][k])} mm/s)" if ref else "")
            for k in ("ab", "bc", "cd")
            if ref is None or c["limites"][k] != ref["limites"][k]
        ]
        notas.append(f"Classe {c['classe']}: " + "; ".join(diferencas) + " — por acordo com o cliente.")
    return notas
