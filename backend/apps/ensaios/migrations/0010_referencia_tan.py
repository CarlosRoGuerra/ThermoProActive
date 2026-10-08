"""
TAN dos fluidos lubrificantes e hidráulicos — resposta do responsável técnico em 08/10/2026:
"até 2,0 mgKOH/g (acima disso pode indicar problema)".

Referência geral (todos os clientes e aplicações): máximo de 2,0 mgKOH/g como limite de
ALERTA ("pode indicar problema" = intensificar o monitoramento). Sem limite crítico — não
foi definido. Uma referência mais específica (equipamento, fluido, cliente) prevalece.
"""
from decimal import Decimal as D

from django.db import migrations

FONTE = "Definido pelo responsável técnico em 08/10/2026"


def carregar(apps, schema_editor):
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    p = Parametro.objects.filter(ensaio__modulo="FLUIDO_LUBRIFICANTE", codigo="TAN").first()
    if p is None or Referencia.objects.filter(parametro=p, origem="RESPONSAVEL_TECNICO", cliente__isnull=True,
                                              equipamento__isnull=True, produto__isnull=True, aplicacao="").exists():
        return
    Referencia.objects.create(
        parametro=p, tipo="MAXIMO", limite_alerta=D("2.0"), origem="RESPONSAVEL_TECNICO", fonte=FONTE,
        observacao="Até 2,0 mgKOH/g; acima disso pode indicar problema (oxidação/contaminação).",
    )


def desfazer(apps, schema_editor):
    apps.get_model("ensaios", "ReferenciaParametro").objects.filter(
        parametro__codigo="TAN", origem="RESPONSAVEL_TECNICO", fonte=FONTE).delete()


class Migration(migrations.Migration):
    dependencies = [("ensaios", "0009_criterios_responsavel_tecnico")]

    operations = [migrations.RunPython(carregar, desfazer)]
