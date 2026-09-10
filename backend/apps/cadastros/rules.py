"""
Regras de cadastro técnico — hoje só a classificação ISO do motor elétrico.

Função pura, sem Django e sem I/O (mesmo padrão de `apps.coletas.rules` e
`apps.servicos.rules`): o `save()` do model chama daqui, e a regra é testável
isoladamente. Constante e limiares declarados aqui, nada escondido (Cláusula 12.4).
"""
from decimal import Decimal

from .models import ClasseISO, TipoBase

#: Acima disso a máquina já não é "pequena/média" — decide entre III e IV pela base.
POTENCIA_LIMITE_CLASSE_II_KW = Decimal("75")
#: Machine médias vão de >15 até este limite.
POTENCIA_LIMITE_CLASSE_I_KW = Decimal("15")


def classificar_classe_iso(potencia_kw, tipo_base: str | None) -> str | None:
    """
    Classe ISO 10816-3 pela potência e rigidez da base de montagem:

        potência ≤ 15 kW              → Classe I
        15 kW < potência ≤ 75 kW      → Classe II
        potência > 75 kW, base rígida → Classe III
        potência > 75 kW, base flexível → Classe IV

    Sem potência não há como decidir. Acima de 75 kW sem o tipo de base informado
    também não — devolve `None` em vez de chutar III ou IV (não assume valor).
    """
    if potencia_kw is None:
        return None
    p = Decimal(potencia_kw)
    if p <= POTENCIA_LIMITE_CLASSE_I_KW:
        return ClasseISO.I
    if p <= POTENCIA_LIMITE_CLASSE_II_KW:
        return ClasseISO.II
    if tipo_base == TipoBase.RIGIDA:
        return ClasseISO.III
    if tipo_base == TipoBase.FLEXIVEL:
        return ClasseISO.IV
    return None
