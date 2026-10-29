"""Comparação histórica determinística; estatística descritiva não é diagnóstico.

Não consulta critérios mutáveis no replay. O snapshot registra contexto, leituras,
sequência temporal e fórmulas da versão aplicada no momento da classificação.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

VERSAO = "historico_descritivo_v1"


def numero_finito(valor):
    if valor is None or isinstance(valor, bool):
        return None
    try:
        numero = Decimal(str(valor))
        return numero if numero.is_finite() else None
    except (ValueError, TypeError, InvalidOperation):
        return None


def serializavel(valor):
    return json.loads(json.dumps(valor, cls=DjangoJSONEncoder))


def contexto_medicao(medicao):
    campos = ["equipamento_id", "componente_id", "instrumento_id", "ponto_medicao"]
    nome = type(medicao).__name__
    if nome == "MedicaoVibracao":
        campos += ["subtipo", "direcao", "parametro", "numero_mancal", "rotacao_rpm", "parametros"]
    elif nome == "MedicaoTermografia":
        campos += ["sistema", "temperatura_referencia", "temperatura_ambiente", "emissividade", "carga_percentual"]
    else:
        campos += ["tipo", "subtipo", "grandeza", "unidade", "valor_referencia", "parametros"]
    contexto = {}
    for campo in campos:
        definicao = medicao._meta.get_field(campo)
        valor = getattr(medicao, campo)
        # Objetos ainda não recarregados podem trazer int/str num DecimalField.
        # Canonicaliza a precisão persistida para a comparação não depender disso.
        if valor is not None and definicao.get_internal_type() == "DecimalField":
            valor = definicao.to_python(valor).quantize(Decimal(1).scaleb(-definicao.decimal_places))
        elif valor is not None and not definicao.is_relation:
            valor = definicao.to_python(valor)
        contexto[campo] = valor
    return serializavel(contexto)


def campo_valor(medicao):
    return {"MedicaoVibracao": "velocidade_rms", "MedicaoTermografia": "delta_t"}.get(
        type(medicao).__name__, "valor",
    )


def analisar_historico(medicao, limite=3):
    """Seleciona até `limite` leituras anteriores, no mesmo contexto exato.

    Sem instrumento e contexto operacional registrado não se afirma
    comparabilidade. Regressão OLS usa dias reais e precisa de 2 pontos.
    A janela 3 é legada/documentada, não um requisito normativo.
    """
    if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= 1000:
        raise ValueError("A janela histórica deve ser um inteiro entre 1 e 1000.")
    contexto = contexto_medicao(medicao)
    instante = medicao.data_hora or timezone.now()
    campo = campo_valor(medicao)
    atual = numero_finito(getattr(medicao, campo))
    base = {
        "versao": VERSAO, "contexto": contexto, "grandeza": campo,
        "unidade": {"velocidade_rms": "mm/s", "delta_t": "°C"}.get(campo, getattr(medicao, "unidade", "")),
        "janela": limite, "instante": instante.isoformat(),
        "atual": str(atual) if atual is not None else None,
        "entradas": [], "status": "INCONCLUSIVA", "motivo": "sem_historico_comparavel",
        "estatisticas": {}, "diagnostico": False,
    }
    valido = atual is not None and (campo != "velocidade_rms" or atual >= 0)
    nome = type(medicao).__name__
    parametros = getattr(medicao, "parametros", {})
    contexto_informado = isinstance(parametros, dict) and bool(parametros.get("contexto_operacional"))
    operacional = (
        bool(medicao.rotacao_rpm is not None or contexto_informado) if nome == "MedicaoVibracao"
        else medicao.carga_percentual is not None and medicao.temperatura_ambiente is not None
        if nome == "MedicaoTermografia" else contexto_informado
    )
    if not valido:
        base["motivo"] = "leitura_ausente_ou_invalida"
    elif medicao.instrumento_id is None or not operacional:
        base["motivo"] = "instrumento_ou_contexto_operacional_ausente"
    else:
        filtros_contexto = {chave: valor for chave, valor in contexto.items()
                           if medicao._meta.get_field(chave).get_internal_type() != "JSONField"}
        candidatos = type(medicao).objects.filter(
            **filtros_contexto, data_hora__lt=instante,
            inspecao__data__lte=medicao.inspecao.data,
        ).exclude(pk=medicao.pk).select_related("inspecao").order_by("-data_hora", "-pk")
        for anterior in candidatos.iterator():
            valor = numero_finito(getattr(anterior, campo))
            if contexto_medicao(anterior) != contexto or valor is None or (campo == "velocidade_rms" and valor < 0):
                continue
            base["entradas"].append({"id": anterior.pk, "data_hora": anterior.data_hora.isoformat(),
                                      "data_inspecao": anterior.inspecao.data.isoformat(), "valor": str(valor)})
            if len(base["entradas"]) >= limite:
                break
        base["entradas"].reverse()
        if base["entradas"]:
            valores = [Decimal(p["valor"]) for p in base["entradas"]]
            media = sum(valores) / len(valores)
            anterior = valores[-1]
            estat = {"media_historica": str(media), "minimo_historico": str(min(valores)),
                     "maximo_historico": str(max(valores)), "diferenca_anterior": str(atual - anterior),
                     "diferenca_media": str(atual - media),
                     "variacao_percentual_media": str((atual - media) / abs(media) * 100) if media != 0 else None}
            # Inclinação usa histórico + atual e tempo, não a ordem de inserção.
            origem = datetime.fromisoformat(base["entradas"][0]["data_hora"])
            def dias(delta):
                return (Decimal(delta.days * 86400 + delta.seconds) + Decimal(delta.microseconds) / 1000000) / 86400
            xs = [dias(datetime.fromisoformat(p["data_hora"]) - origem) for p in base["entradas"]] + [dias(instante - origem)]
            ys = valores + [atual]
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            denominador = sum((x - mx) ** 2 for x in xs)
            estat["inclinacao_por_dia"] = str(sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / denominador) if denominador else None
            estat["unidade_inclinacao"] = f"{base['unidade']}/dia"
            base.update(status="COMPARAVEL", motivo="estatistica_descritiva_sem_diagnostico", estatisticas=estat)
    base["fingerprint"] = hashlib.sha256(json.dumps(base, sort_keys=True).encode()).hexdigest()
    return base


def replay_vibracao(snapshot):
    """Reproduz somente a regra v2 com os dados congelados, sem ler o banco."""
    from .rules import classificar_vibracao

    if snapshot.get("motor") != "vibracao_v2" or not snapshot.get("entradas"):
        raise ValueError("Snapshot sem entradas da versão vibracao_v2; replay indisponível.")
    entrada = snapshot["entradas"]
    faixas = {k: Decimal(v) for k, v in snapshot["faixas"].items() if k in "ABC"}
    resultado = classificar_vibracao(
        snapshot["classe_iso"], Decimal(entrada["velocidade_rms"]), faixas=faixas,
        historico_vrms=[Decimal(v) for v in snapshot["historico_vrms"]],
        fator_evolucao=Decimal(snapshot["fator_evolucao"]) if snapshot.get("evolucao_aplicavel") else None,
        avisos=tuple(snapshot.get("avisos", [])),
    )
    return {"zona_iso": resultado.zona_iso, "criticidade": resultado.criticidade,
            "diagnostico_sugerido": resultado.diagnostico}


MOTORES_REPLAY = {"vibracao_v2", "termografia_delta_v2", "sensitiva_manual_v2", "tecnica_pendente_v2"}


def replay_medicao(snapshot):
    """Reexecuta apenas versões reconhecidas, a partir das entradas congeladas."""
    motor = snapshot.get("motor")
    if motor == "vibracao_v2":
        return replay_vibracao(snapshot)
    entrada = snapshot.get("entradas")
    if motor not in MOTORES_REPLAY or not entrada:
        raise ValueError("Snapshot sem entradas/versão compatível; replay indisponível.")
    if motor == "termografia_delta_v2":
        delta = Decimal(entrada["temperatura_ponto"]) - Decimal(entrada["temperatura_referencia"])
        return {"zona_iso": "", "criticidade": "", "diagnostico_sugerido": (
            f"ΔT = {delta:.1f} °C. Critério específico do sistema ainda não validado; "
            "o diferencial térmico não determina sozinho a condição do equipamento."
        )}
    from .rules_tecnicas import classificar_tecnica
    resultado = classificar_tecnica(entrada["tipo"], entrada["grandeza"], entrada.get("valor"),
                                    entrada.get("valor_referencia"), entrada.get("parametros"))
    return {"zona_iso": "", "criticidade": resultado.criticidade, "diagnostico_sugerido": resultado.diagnostico}
