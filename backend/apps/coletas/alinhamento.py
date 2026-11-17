"""Alinhamento a laser entre eixos e polias — Anexo I 2.3.2.8.1.1 e 2.3.2.8.1.2 (ficha e comparação).

Um registro por fase (`MedicaoTecnica`, tipo CORRETIVA, subtipo ALINHAMENTO_EIXOS ou ALINHAMENTO_POLIAS):
- `fase`: "antes" ou "depois" da correção;
- desalinhamento nos dois planos: `vertical_paralelo_mm`, `vertical_angular_mm_100mm`,
  `horizontal_paralelo_mm`, `horizontal_angular_mm_100mm` (valores com sinal);
- `rpm` (obrigatório, > 0): rotação em que o alinhamento foi feito;
- `correcao_pe_vertical_mm` e `correcao_pe_horizontal_mm` (opcionais): calços e deslocamentos aplicados
  nos pés, registrados como informados (não são calculados aqui);
- `distancia_pes_mm` (opcional): distância do acoplamento aos pés, quando medida.

`valor` = maior desalinhamento angular dos dois planos (mm/100 mm), e a ficha exige que bata com os
campos. Tolerância: `preditiva.LimiteAlarmeSerie` VALIDADO para "Desalinhamento angular" (mm/100 mm) e
"Desalinhamento paralelo" (mm), sentido superior, com a faixa de rpm informada na fonte do critério.
Sem critério validado, PENDENTE. Não há tolerância universal aqui.

A redução entre antes e depois é aritmética: (antes − depois) ÷ antes × 100, só com antes > 0.
"""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

SUBTIPOS = ("ALINHAMENTO_EIXOS", "ALINHAMENTO_POLIAS")
FASES = ("antes", "depois")
GRANDEZA_ANGULAR = "Desalinhamento angular"
UNIDADE_ANGULAR = "mm/100mm"
GRANDEZA_PARALELO = "Desalinhamento paralelo"
UNIDADE_PARALELO = "mm"
CAMPOS_MEDIDOS = ("vertical_paralelo_mm", "vertical_angular_mm_100mm", "horizontal_paralelo_mm",
                  "horizontal_angular_mm_100mm")


def texto_limite(valor) -> str:
    """Limite do cadastro sem zeros à direita: o banco devolve 4 casas (0.0500 → "0.05", 10.0000 → "10")."""
    return format(Decimal(valor).quantize(Decimal("0.0001")).normalize(), "f")


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() else None


def maior_angular(parametros: dict):
    """Maior |angular| entre os dois planos, ou None se algum estiver ausente."""
    v = _decimal(parametros.get("vertical_angular_mm_100mm"))
    h = _decimal(parametros.get("horizontal_angular_mm_100mm"))
    if v is None or h is None:
        return None
    return max(abs(v), abs(h))


def maior_paralelo(parametros: dict):
    """Maior |paralelo| entre os dois planos, ou None se algum estiver ausente."""
    v = _decimal(parametros.get("vertical_paralelo_mm"))
    h = _decimal(parametros.get("horizontal_paralelo_mm"))
    if v is None or h is None:
        return None
    return max(abs(v), abs(h))


def validar_ficha(parametros: dict, valor) -> dict:
    """Erros da ficha de alinhamento por campo (vazio = válida). `valor` é o campo valor da medição."""
    erros = {}
    if parametros.get("fase") not in FASES:
        erros["fase"] = "Informe a fase: antes ou depois da correção."
    for campo in CAMPOS_MEDIDOS:
        if _decimal(parametros.get(campo)) is None:
            erros[campo] = "Informe o desalinhamento neste plano (número, com sinal)."
    rpm = _decimal(parametros.get("rpm"))
    if rpm is None or rpm <= 0:
        erros["rpm"] = "Informe a rotação em rpm, maior que zero."
    for campo in ("correcao_pe_vertical_mm", "correcao_pe_horizontal_mm", "distancia_pes_mm"):
        if parametros.get(campo) not in (None, "") and _decimal(parametros.get(campo)) is None:
            erros[campo] = "Valor numérico, quando informado."
    if not erros:
        esperado = maior_angular(parametros)
        atual = _decimal(valor)
        if atual is None or esperado is None or abs(atual - esperado) > Decimal("0.001"):
            erros["valor"] = "O valor deve ser o maior desalinhamento angular dos dois planos."
        distancia = _decimal(parametros.get("distancia_pes_mm"))
        if distancia is not None and distancia <= 0:
            erros["distancia_pes_mm"] = "A distância aos pés deve ser maior que zero."
    return erros


def reducao_percentual(antes, depois):
    """Redução em % do desalinhamento. None se 'antes' não for positivo ou faltar valor."""
    antes, depois = _decimal(antes), _decimal(depois)
    if antes is None or depois is None or antes <= 0:
        return None
    return ((antes - depois) / antes * 100).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def criterio_superior(grandeza, unidade, cliente_id, equipamento_id, data):
    """(limites, origem) do `LimiteAlarmeSerie` VALIDADO (sentido superior) mais específico.

    `limites` = {"ALERTA": x, "CRITICO": y}; `origem` = {id, origem, origem_display, fonte, validacao}
    para o relatório dizer de onde vem o critério. Sem critério validado: ({}, None).
    """
    from django.db.models import Q
    from django.utils import timezone

    from apps.preditiva.models import LimiteAlarmeSerie, Validacao

    data = data or timezone.localdate()
    qs = LimiteAlarmeSerie.objects.filter(
        ativo=True, modalidade="CORRETIVA", grandeza=grandeza, unidade=unidade,
        validacao=Validacao.VALIDADA, sentido="SUPERIOR",
    ).filter(
        Q(cliente__isnull=True) | Q(cliente_id=cliente_id),
        Q(equipamento__isnull=True) | Q(equipamento_id=equipamento_id),
        Q(vigencia_inicio__isnull=True) | Q(vigencia_inicio__lte=data),
        Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=data),
    )
    escolhido = sorted(qs, key=lambda c: (
        0 if c.equipamento_id else 1, 0 if c.cliente_id else 1,
        -(c.vigencia_inicio.toordinal() if c.vigencia_inicio else 0), -c.pk,
    ))
    if not escolhido:
        return {}, None
    c = escolhido[0]
    limites = {}
    if c.valor_alerta is not None:
        limites["ALERTA"] = c.valor_alerta
    if c.valor_critico is not None:
        limites["CRITICO"] = c.valor_critico
    origem = {"id": c.pk, "origem": c.origem, "origem_display": c.get_origem_display(), "fonte": c.fonte,
              "validacao": c.validacao}
    return limites, origem


def par_de(medicao):
    """Registro de fase oposta do mesmo serviço (mesma inspeção, equipamento, ponto e subtipo), ou None."""
    from .models import MedicaoTecnica

    fase = (medicao.parametros or {}).get("fase")
    oposta = "depois" if fase == "antes" else "antes"
    candidatos = MedicaoTecnica.objects.filter(
        inspecao_id=medicao.inspecao_id, equipamento_id=medicao.equipamento_id,
        ponto_medicao=medicao.ponto_medicao, subtipo=medicao.subtipo,
    ).exclude(pk=medicao.pk).order_by("-data_hora", "-pk")
    for m in candidatos:
        if (m.parametros or {}).get("fase") == oposta:
            return m
    return None


def analise_par(medicao):
    """Antes e depois do mesmo serviço, reduções e condição (pela tolerância cadastrada). Não grava nada."""
    from apps.coletas.ultrassom import classificar_superior

    par = par_de(medicao)
    antes = medicao if (medicao.parametros or {}).get("fase") == "antes" else par
    depois = medicao if (medicao.parametros or {}).get("fase") == "depois" else par
    cliente_id = medicao.inspecao.cliente_id
    data = medicao.inspecao.data
    eq = medicao.equipamento_id
    lim_ang, crit_ang = criterio_superior(GRANDEZA_ANGULAR, UNIDADE_ANGULAR, cliente_id, eq, data)
    lim_par, crit_par = criterio_superior(GRANDEZA_PARALELO, UNIDADE_PARALELO, cliente_id, eq, data)

    def trio(m):
        if m is None:
            return None
        p = m.parametros or {}
        return {"medicao_id": m.pk, "data": m.inspecao.data.isoformat(), "rpm": str(p.get("rpm")),
                "angular_mm_100mm": str(maior_angular(p)) if maior_angular(p) is not None else None,
                "paralelo_mm": str(maior_paralelo(p)) if maior_paralelo(p) is not None else None,
                "correcao_pe_vertical_mm": p.get("correcao_pe_vertical_mm"),
                "correcao_pe_horizontal_mm": p.get("correcao_pe_horizontal_mm")}

    depois_p = (depois.parametros or {}) if depois is not None else {}
    ang_depois = maior_angular(depois_p) if depois is not None else None
    par_depois = maior_paralelo(depois_p) if depois is not None else None
    cond_ang = classificar_superior(ang_depois, lim_ang) if ang_depois is not None else "PENDENTE"
    cond_par = classificar_superior(par_depois, lim_par) if par_depois is not None else "PENDENTE"
    if "PENDENTE" in (cond_ang, cond_par) or depois is None:
        condicao = "PENDENTE"
    else:
        condicao = max((cond_ang, cond_par), key=lambda c: {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}[c])
    ang_antes = maior_angular(antes.parametros or {}) if antes is not None else None
    par_antes = maior_paralelo(antes.parametros or {}) if antes is not None else None
    return {
        "antes": trio(antes),
        "depois": trio(depois),
        "reducao_angular_pct": str(reducao_percentual(abs(ang_antes) if ang_antes is not None else None,
                                                     abs(ang_depois) if ang_depois is not None else None))
        if ang_antes is not None and ang_depois is not None else None,
        "reducao_paralelo_pct": str(reducao_percentual(par_antes, par_depois))
        if par_antes is not None and par_depois is not None else None,
        "condicao_angular": cond_ang,
        "condicao_paralelo": cond_par,
        "condicao": condicao,
        "criterio_angular_validado": bool(lim_ang),
        "criterio_paralelo_validado": bool(lim_par),
        "criterio_angular": crit_ang,
        "criterio_paralelo": crit_par,
        "limites_angular": {k: texto_limite(v) for k, v in lim_ang.items()},
        "limites_paralelo": {k: texto_limite(v) for k, v in lim_par.items()},
    }
