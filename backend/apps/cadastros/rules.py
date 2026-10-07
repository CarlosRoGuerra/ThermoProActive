"""
Regras de cadastro técnico — hoje só a classificação do motor para a severidade de vibração.

Função pura, sem Django e sem I/O (mesmo padrão de `apps.coletas.rules` e
`apps.servicos.rules`): o `save()` do model chama daqui, e a regra é testável
isoladamente. Constante e limiares declarados aqui, nada escondido (Cláusula 12.4).
"""
from decimal import Decimal

from .models import ClasseISO

#: Até aqui a máquina é "pequena" (Classe I) — a ISO 20816-3 só cobre acima de 15 kW.
POTENCIA_LIMITE_CLASSE_I_KW = Decimal("15")
#: Limite entre o Grupo 2 e o Grupo 1 da ISO 20816-3:2022.
POTENCIA_LIMITE_GRUPO_2_KW = Decimal("300")


def classificar_classe_iso(potencia_kw, tipo_base: str | None = None) -> str | None:
    """
    Grupo da máquina pela potência nominal (definição do responsável técnico em
    07/10/2026, com base na ISO 20816-3:2022):

        potência ≤ 15 kW          → Classe I
        15 kW < potência ≤ 300 kW → Grupo 2
        potência > 300 kW         → Grupo 1

    O tipo de base não decide mais o grupo: o critério de cada grupo vale para
    qualquer suporte (o parâmetro fica por compatibilidade). Sem potência não há
    como decidir — devolve `None` em vez de chutar.
    """
    if potencia_kw is None:
        return None
    p = Decimal(potencia_kw)
    if p <= POTENCIA_LIMITE_CLASSE_I_KW:
        return ClasseISO.I
    if p <= POTENCIA_LIMITE_GRUPO_2_KW:
        return ClasseISO.G2
    return ClasseISO.G1
