"""Registro técnico sem atribuir limites não homologados às modalidades do contrato.

O Anexo I 2.3 lista tipos de coleta, mas não define critérios de classificação.
Os antigos limiares genéricos misturavam grandezas, aplicações e unidades. Novas
leituras aguardam critério específico; os resultados anteriores ficam preservados
no modelo. A inspeção sensitiva admite avaliação explícita do responsável.
"""
from dataclasses import dataclass


@dataclass
class ResultadoTecnico:
    criticidade: str
    diagnostico: str


def classificar_tecnica(tipo: str, grandeza: str, valor, valor_referencia=None, parametros=None) -> ResultadoTecnico:
    parametros = parametros if isinstance(parametros, dict) else {}
    if tipo == "SENSITIVA":
        criticidade = str(parametros.get("criticidade") or "").upper()
        if criticidade in ("NORMAL", "ALERTA", "CRITICO"):
            return ResultadoTecnico(
                criticidade, parametros.get("observacao") or "Avaliação sensitiva informada pelo técnico.",
            )
    return ResultadoTecnico(
        "", "Leitura registrada. Classificação pendente de critério específico validado para a modalidade, "
        "grandeza, unidade e aplicação; o valor registrado não comprova condição normal.",
    )