"""Resistência de isolação de motores — Anexo I 2.3.2.5.1.1 (ficha, índices e critério).

Ficha, por leitura (`MedicaoTecnica`, subtipo `MOTOR_RI`, unidade de resistência):
- `tempo_leitura_s`: 30, 60 ou 600 (R30, R60, R600);
- `tensao_ensaio_v`: tensão aplicada no ensaio (V, maior que zero);
- `temperatura_c`: temperatura do enrolamento na leitura (°C);
- `ligacao` (opcional): ex.: fase-terra, enrolamento-enrolamento;
- `umidade_pct` (opcional).

Índices (aritmética, sem limite embutido):
- DAR (índice de absorção) = R60 ÷ R30;
- IP (índice de polarização) = R600 ÷ R60.

Um grupo de leituras = mesma inspeção, equipamento, ponto, componente, instrumento,
tensão, temperatura e ligação. Motor não herda ficha nem critério de transformador.

Critério: `preditiva.LimiteAlarmeSerie` por grandeza (`DAR`, `IP`, `R60`), só VALIDADO.
Sem critério validado, o índice fica PENDENTE. Nenhum valor mínimo é assumido.
"""
from decimal import Decimal, InvalidOperation

TEMPOS_VALIDOS = (30, 60, 600)


def _decimal(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None
    return numero if numero.is_finite() else None


def validar_ficha(parametros: dict) -> dict:
    """Erros da ficha de resistência de isolação (vazio = válida)."""
    erros = {}
    tempo = parametros.get("tempo_leitura_s")
    if tempo not in TEMPOS_VALIDOS and str(tempo) not in {str(t) for t in TEMPOS_VALIDOS}:
        erros["tempo_leitura_s"] = "Informe o tempo de leitura: 30, 60 ou 600 segundos."
    tensao = _decimal(parametros.get("tensao_ensaio_v"))
    if tensao is None or tensao <= 0:
        erros["tensao_ensaio_v"] = "Informe a tensão de ensaio em volts, maior que zero."
    if _decimal(parametros.get("temperatura_c")) is None:
        erros["temperatura_c"] = "Informe a temperatura do enrolamento na leitura (°C)."
    umidade = parametros.get("umidade_pct")
    if umidade not in (None, "") and (_decimal(umidade) is None or not 0 <= _decimal(umidade) <= 100):
        erros["umidade_pct"] = "A umidade relativa deve estar entre 0 e 100 %."
    return erros


def indices(r30, r60, r600):
    """(DAR, IP) a partir das leituras de 30, 60 e 600 s. Ausente ou divisor não positivo → None."""
    r30, r60, r600 = _decimal(r30), _decimal(r60), _decimal(r600)
    dar = (r60 / r30).quantize(Decimal("0.01")) if r30 and r60 is not None and r30 > 0 else None
    ip = (r600 / r60).quantize(Decimal("0.01")) if r60 and r600 is not None and r60 > 0 else None
    return dar, ip


def classificar_indice(valor, limites: dict):
    """Condição de um índice. `limites` = {"ALERTA": x, "CRITICO": y} (sentido INFERIOR).

    Sem critério validado (ou valor ausente) → PENDENTE.
    """
    valor = _decimal(valor)
    alerta, critico = _decimal(limites.get("ALERTA")), _decimal(limites.get("CRITICO"))
    if valor is None or (alerta is None and critico is None):
        return "PENDENTE"
    if critico is not None and valor <= critico:
        return "CRITICO"
    if alerta is not None and valor <= alerta:
        return "ALERTA"
    return "NORMAL"


PIOR = {"NORMAL": 0, "ALERTA": 1, "CRITICO": 2}


def pior_condicao(condicoes):
    """Pior condição entre os índices; PENDENTE se algum índice não tem critério."""
    if not condicoes or any(c == "PENDENTE" for c in condicoes):
        return "PENDENTE"
    return max(condicoes, key=PIOR.get)


def grupo_de(medicao):
    """Leituras do mesmo grupo, por tempo: {30: medição, 60: ..., 600: ...}. A mais recente vence."""
    from .models import MedicaoTecnica

    parametros = medicao.parametros or {}
    qs = MedicaoTecnica.objects.filter(
        inspecao_id=medicao.inspecao_id, equipamento_id=medicao.equipamento_id,
        ponto_medicao=medicao.ponto_medicao, componente_id=medicao.componente_id,
        instrumento_id=medicao.instrumento_id, subtipo="MOTOR_RI",
    ).order_by("-data_hora", "-pk")
    grupo = {}
    for m in qs:
        p = m.parametros or {}
        if str(p.get("tensao_ensaio_v")) != str(parametros.get("tensao_ensaio_v")):
            continue
        if str(p.get("temperatura_c")) != str(parametros.get("temperatura_c")):
            continue
        if str(p.get("ligacao", "")) != str(parametros.get("ligacao", "")):
            continue
        tempo = p.get("tempo_leitura_s")
        try:
            tempo = int(tempo)
        except (TypeError, ValueError):
            continue
        grupo.setdefault(tempo, m)
    return grupo


def criterio_validado(grandeza, unidade, cliente_id, equipamento_id, data):
    """{"ALERTA": x, "CRITICO": y} do `LimiteAlarmeSerie` VALIDADO mais específico, ou {}."""
    from django.db.models import Q
    from django.utils import timezone

    from apps.preditiva.models import LimiteAlarmeSerie, Validacao

    data = data or timezone.localdate()
    qs = LimiteAlarmeSerie.objects.filter(
        ativo=True, modalidade="ENSAIO_ELETRICO", grandeza=grandeza, unidade=unidade,
        validacao=Validacao.VALIDADA, sentido="INFERIOR",
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
        return {}
    c = escolhido[0]
    limites = {}
    if c.valor_alerta is not None:
        limites["ALERTA"] = c.valor_alerta
    if c.valor_critico is not None:
        limites["CRITICO"] = c.valor_critico
    return limites


def analise_grupo(medicao):
    """Análise completa do grupo da leitura: leituras, DAR, IP, critérios e condição. Não grava nada."""
    grupo = grupo_de(medicao)
    parametros = medicao.parametros or {}
    cliente_id = medicao.inspecao.cliente_id
    data = medicao.inspecao.data
    valores = {t: (grupo[t].valor if t in grupo else None) for t in TEMPOS_VALIDOS}
    dar, ip = indices(valores[30], valores[60], valores[600])
    dar_lim = criterio_validado("DAR", "", cliente_id, medicao.equipamento_id, data)
    ip_lim = criterio_validado("IP", "", cliente_id, medicao.equipamento_id, data)
    cond = {
        "DAR": classificar_indice(dar, dar_lim),
        "IP": classificar_indice(ip, ip_lim),
    }
    return {
        "tensao_ensaio_v": str(parametros.get("tensao_ensaio_v")),
        "temperatura_c": str(parametros.get("temperatura_c")),
        "ligacao": parametros.get("ligacao", ""),
        "leituras": {str(t): (str(v) if v is not None else None) for t, v in valores.items()},
        "medicoes": {str(t): (grupo[t].pk if t in grupo else None) for t in TEMPOS_VALIDOS},
        "DAR": str(dar) if dar is not None else None,
        "IP": str(ip) if ip is not None else None,
        "condicao_DAR": cond["DAR"],
        "condicao_IP": cond["IP"],
        "condicao": pior_condicao(list(cond.values())),
        "criterios": {"DAR": {k: str(v) for k, v in dar_lim.items()}, "IP": {k: str(v) for k, v in ip_lim.items()}},
    }
