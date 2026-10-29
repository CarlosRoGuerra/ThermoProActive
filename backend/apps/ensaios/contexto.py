"""Congela critérios de novos lançamentos; não atribui critérios retroativos ao legado."""
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import FileField
from django.utils import timezone

from .models import ParametroEnsaio, ReferenciaParametro


def serializavel(dados):
    return json.loads(json.dumps(dados, cls=DjangoJSONEncoder))


def campos(obj):
    return {f.attname: (str(f.value_from_object(obj)) if isinstance(f, FileField)
                       else f.value_from_object(obj)) for f in obj._meta.concrete_fields}


def restaurar(modelo, dados):
    # Instâncias só em memória: preservam Decimal/date e rótulos de choices do modelo.
    return modelo(**{f.attname: f.to_python(dados[f.attname]) for f in modelo._meta.concrete_fields
                     if f.attname in dados})


def parametros_registrados(resultado, padrao):
    contexto = getattr(resultado, "contexto_tecnico", {}) or {}
    if "parametros" not in contexto:
        return padrao
    return [restaurar(ParametroEnsaio, p) for p in contexto["parametros"]]


class ReferenciasRegistradas:
    def __init__(self, dados):
        self.dados = dados

    def para(self, parametro_id, **escopo):
        dados = self.dados.get(str(parametro_id))
        return restaurar(ReferenciaParametro, dados) if dados else None


def registrar_contexto(resultado, autor=None, origem="API"):
    from apps.cadastros.models import ModuloTecnico
    from .relatorio import _Campanha
    from .relatorio_fluidos import (ResolvedorReferencias, _contexto_referencia, _oleo_novo,
                                    _oleo_novo_rotulos, contexto_comparacao_fluido)

    parametros = list(resultado.ensaio.parametros.filter(ativo=True))
    resultado.contexto_tecnico = {}
    campanha = _Campanha(resultado)
    contexto = {"versao": 1, "origem": origem, "registrado_em": timezone.now(),
                "registrado_por": getattr(autor, "pk", None), "data_campanha": campanha.data,
                "parametros": [campos(p) for p in parametros]}
    from .relatorio import _um
    registro = _um(resultado.item, "registro_eletrico")
    trafo = _um(resultado.item.equipamento, "dados_transformador")
    contexto["registro_eletrico"] = campos(registro) if registro else None
    contexto["dados_transformador"] = campos(trafo) if trafo else None
    if resultado.ensaio.modulo == ModuloTecnico.FLUIDO_LUBRIFICANTE:
        # O contexto anterior já foi arquivado na revisão pelo serializer.
        escopo = _contexto_referencia(campanha, resultado.item.equipamento)
        resolvedor = ResolvedorReferencias(p.pk for p in parametros)
        contexto["referencias"] = {}
        for p in parametros:
            referencia = resolvedor.para(p.pk, **escopo)
            contexto["referencias"][str(p.pk)] = campos(referencia) if referencia else None
        contexto["oleo_novo"] = _oleo_novo(campanha)
        contexto["oleo_novo_rotulos"] = _oleo_novo_rotulos(campanha)
        contexto["comparacao_fluido"] = contexto_comparacao_fluido(campanha)
        contexto["motor_comparacao"] = "comparacao_fluido_v1"
    contexto = serializavel(contexto)
    type(resultado).objects.filter(pk=resultado.pk).update(contexto_tecnico=contexto)
    resultado.contexto_tecnico = contexto


def registrar_revisao(resultado, autor=None):
    from .models import RevisaoResultadoEnsaio

    dados = campos(resultado)
    dados["valores"] = [campos(v) for v in resultado.valores.all()]
    RevisaoResultadoEnsaio.objects.create(
        resultado=resultado, autor=autor, dados=serializavel(dados),
    )
