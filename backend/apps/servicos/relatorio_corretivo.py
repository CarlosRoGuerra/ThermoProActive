"""
Montagem do payload do relatório de manutenção corretiva — UMA regra de verdade.

Os números do balanceamento já são calculados no banco (`BalanceamentoPonto.save`,
`EconomiaEnergetica.save`, `rules.py`). Este módulo só os empacota, acrescentando
o que depende do conjunto (a escala do mostrador polar) — nada é recalculado, e
nada é preenchido por omissão: grandeza ausente sai `None` e a apresentação mostra
o estado de ausência, nunca um zero plausível.

A mesma função serve `ServicoCampoViewSet.relatorio()` (tela do serviço) e
`RelatorioViewSet.dossie()` (folha da OSP no relatório técnico), sem chamada HTTP
interna entre views.

Extensão: `MONTADORES` despacha por tipo de serviço; sem um montador específico,
cai em `montar_relatorio_corretivo` (a base) — que já é honesta para qualquer tipo,
porque pontos/planos vazios são o estado REAL de um serviço sem essas medições, não
um campo inventado. O alinhamento a laser tem particularidades ainda não definidas
com o cliente (tolerância, offset, calços…) — quando forem, ganha o seu
`montar_relatorio_alinhamento` aqui, sem tocar no balanceamento nem na base comum.
"""
from . import rules
from .choices import TipoServico


def _f(valor):
    """Decimal → float para o JSON; `None` continua `None` (ausência ≠ zero)."""
    return float(valor) if valor is not None else None


def _velocidade_referencia(servico, pontos):
    """
    Velocidade inicial oficial do balanceamento — a condição ANTES da correção.

    Fonte: o Reference Run do ponto de foco (a medição que baseou a decisão de
    balancear). Sem foco definido, cai no primeiro ponto medido, na mesma ordenação
    técnica já usada em todo o resto do relatório (`BalanceamentoPonto.Meta.ordering`
    — `reference_mms` é campo obrigatório do modelo, então qualquer ponto que exista
    já tem essa medição). Sem nenhum ponto, não há velocidade a mostrar.

    Nunca usa Trial (o ensaio) nem Trim (o resultado) — e não é a mesma fonte do
    `Achado.velocidade_global` da análise genérica, que não é coletado neste fluxo.
    """
    if not pontos:
        return None
    foco = next((p for p in pontos if p.id == servico.ponto_foco_id), None)
    ponto = foco if foco is not None else pontos[0]
    return _f(ponto.reference_mms)


def _corrida(mms, fase):
    """
    Uma corrida (reference/trial/trim) do ponto.

    Amplitude sem fase é dado real — a fase deixou de ser coletada no Reference Run
    (pedido do cliente, 2026-09-16) e nem todo trim tem fase medida. Nesses casos a
    corrida sai com `fase: null` em vez de sumir: o gráfico antes/depois continua
    usando a amplitude, e só o mostrador polar deixa de desenhar a agulha.
    """
    if mms is None:
        return None
    return {"mms": _f(mms), "fase": _f(fase)}


def montar_relatorio_corretivo(servico):
    """Base comum a qualquer manutenção corretiva (cabeçalho, planos, pontos, economia)."""
    from .serializers import EconomiaEnergeticaSerializer, ServicoCampoSerializer

    pontos = list(servico.pontos.all())

    # Escala do mostrador: a maior vibração do serviço vira raio 1.
    amplitudes = []
    for p in pontos:
        amplitudes.append(p.reference_mms)
        amplitudes.extend(v for v in (p.trial_mms, p.trim_mms) if v is not None)
    amplitude_maxima = max(amplitudes) if amplitudes else None

    def vetor(fase, amplitude):
        if fase is None or amplitude is None:
            return None
        x, y = rules.vetor_polar(fase, amplitude=amplitude, amplitude_maxima=amplitude_maxima)
        return {"x": float(x), "y": float(y), "fase": float(fase), "amplitude": float(amplitude)}

    dados_pontos = []
    for p in pontos:
        dados_pontos.append({
            "id": p.id,
            "codigo_ponto": p.codigo_ponto,
            "numero_mancal": p.numero_mancal,
            "direcao": p.direcao,
            "identificacao": p.identificacao,
            "plano": p.plano_id,
            "reference": _corrida(p.reference_mms, p.reference_fase),
            "trial": _corrida(p.trial_mms, p.trial_fase),
            # O resultado só existe depois do trim run. `trim_fase` pode ser nulo
            # mesmo com o trim medido — e continua nulo aqui: o ângulo do Trial
            # NUNCA substitui o do Trim (seriam duas correções diferentes).
            "trim": _corrida(p.trim_mms, p.trim_fase) if p.completo else None,
            "completo": p.completo,
            "residual_pct": _f(p.residual_pct),
            "reducao_pct": _f(p.reducao_pct),
            "zona_iso": p.zona_iso,
            "criticidade": p.criticidade,
            "criticidade_display": p.get_criticidade_display() if p.criticidade else "",
            "eficaz": p.eficaz,
            "diagnostico": p.diagnostico,
            "mostrador": {
                "reference": vetor(p.reference_fase, p.reference_mms),
                "trial": vetor(p.trial_fase, p.trial_mms),
                "trim": vetor(p.trim_fase, p.trim_mms),
            },
        })

    # Planos: o relatório final mostra a correção que FICOU na máquina
    # (massa_final_g / angulo_final). Massa e ângulo de teste pertencem ao Trial
    # Run e vão junto só como registro do ensaio.
    dados_planos = [
        {
            "id": pl.id,
            "numero": pl.numero,
            "descricao": pl.descricao,
            "massa_teste_g": _f(pl.massa_teste_g),
            "angulo_teste": _f(pl.angulo_teste),
            "massa_final_g": _f(pl.massa_final_g),
            "angulo_final": _f(pl.angulo_final),
        }
        for pl in servico.planos.all()
    ]

    economia = getattr(servico, "economia", None)
    dados_economia = None
    if economia is not None:
        dados_economia = {
            **EconomiaEnergeticaSerializer(economia).data,
            "premissas": economia.premissas,
        }

    completos = [p for p in pontos if p.completo]
    return {
        "servico_id": servico.pk,
        "tipo": servico.tipo,
        "servico": ServicoCampoSerializer(servico).data,
        "rotacao_hz": _f(servico.rotacao_hz),
        "rotacao_rpm": servico.rotacao_rpm,
        "classe_iso": servico.equipamento.classe_iso,
        "ponto_foco": servico.ponto_foco_id,
        "velocidade_referencia": _velocidade_referencia(servico, pontos),
        "planos": dados_planos,
        "pontos": dados_pontos,
        "mostrador": {
            "setores": rules.SETORES_MOSTRADOR,
            "graus_por_setor": rules.GRAUS_POR_SETOR,
            "amplitude_maxima": float(amplitude_maxima) if amplitude_maxima else None,
        },
        "resultado": {
            "pontos_completos": len(completos),
            "reducao_media_pct": _f(servico.reducao_media_pct),
            # Sem nenhum ponto medido não há veredito: `criticidade_final` cairia
            # em "NORMAL" por falta de dados, que num laudo seria uma afirmação.
            "criticidade_final": servico.criticidade_final if completos else None,
        },
        "economia": dados_economia,
    }


def montar_relatorio_balanceamento(servico):
    """Balanceamento dinâmico — hoje é a base; o ponto de extensão fica explícito."""
    return montar_relatorio_corretivo(servico)


#: Tipos de corretiva com apresentação de relatório já definida com o cliente.
MONTADORES = {TipoServico.BALANCEAMENTO: montar_relatorio_balanceamento}


def payload_corretivo(servico):
    """Payload do endpoint do serviço — vale para qualquer tipo (base + específicos)."""
    return MONTADORES.get(servico.tipo, montar_relatorio_corretivo)(servico)


def payload_corretivo_do_dossie(servico):
    """
    Payload da folha da OSP no relatório técnico — SEMPRE reconhecida como
    manutenção corretiva (nunca cai de volta no layout preditivo por falta de
    montador específico).

    Usa a mesma regra de `payload_corretivo`: com montador específico (hoje, só
    balanceamento), o layout definido com o cliente; sem ele, a base comum, que já
    é honesta para qualquer tipo (pontos/planos vazios refletem um serviço real sem
    essas medições — nunca um campo técnico inventado). O alinhamento a laser fica
    assim com identificação, foto e a Economia energética (modelo comum aos dois
    tipos) até que suas particularidades sejam definidas com o cliente; o frontend
    decide, a partir de `tipo`, se usa o layout específico ou o genérico.
    """
    dados = MONTADORES.get(servico.tipo, montar_relatorio_corretivo)(servico)
    # `servico` é o serializer completo — e ele aninha planos, pontos e economia de
    # novo. Na folha isso duplicaria o bloco técnico em cada uma das dezenas de OSPs
    # do relatório, sem acrescentar nada: cabeçalho (empresa, TAG, analista, data)
    # a folha já tem do achado. Mesma montagem, só sem a repetição.
    dados.pop("servico", None)
    return dados
