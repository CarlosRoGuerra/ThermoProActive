"""
Potássio (K) na espectrometria — responsável técnico, 21/10/2026: "acima de 25 ppm nível
crítico, o limite é até 50 ppm". Referência geral: alerta acima de 25 ppm (início da faixa
crítica) e crítico acima de 50 ppm (limite). Contaminante: vale para qualquer aplicação.

Na mesma resposta: compressores usam óleo hidráulico (aplicação "Hidráulico" na coleta) e
mancais usam graxa (fora da análise de óleo).
"""
from decimal import Decimal as D

from django.db import migrations

FONTE = "Definido pelo responsável técnico em 21/10/2026"


def carregar(apps, schema_editor):
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    k = Parametro.objects.filter(ensaio__modulo="FLUIDO_LUBRIFICANTE", ensaio__sigla="EF", codigo="K").first()
    if k is None or Referencia.objects.filter(parametro=k, origem="RESPONSAVEL_TECNICO", aplicacao="",
                                              cliente__isnull=True, equipamento__isnull=True,
                                              tipo_equipamento__isnull=True, produto__isnull=True).exists():
        return
    Referencia.objects.create(parametro=k, tipo="MAXIMO", limite_alerta=D("25"), limite_critico=D("50"),
                              origem="RESPONSAVEL_TECNICO", fonte=FONTE,
                              observacao="Contaminante (água de refrigeração/aditivos de arrefecimento).")


def desfazer(apps, schema_editor):
    apps.get_model("ensaios", "ReferenciaParametro").objects.filter(
        parametro__codigo="K", origem="RESPONSAVEL_TECNICO", fonte=FONTE).delete()


class Migration(migrations.Migration):
    dependencies = [("ensaios", "0015_referencias_espectrometria")]

    operations = [migrations.RunPython(carregar, desfazer)]
