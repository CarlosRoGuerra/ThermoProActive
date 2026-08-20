from django.db import migrations, models


def backfill_sequencial_global(apps, schema_editor):
    """
    Carimba o sequencial global das OSPs já existentes, na ordem em que foram
    incluídas no banco (criação). É a soma acumulada de todas as OSPs — antes
    da barra fica o sequencial do cliente; depois, este número global.
    """
    OrdemServico = apps.get_model("osp", "OrdemServico")
    seq = 0
    for osp in OrdemServico.objects.order_by("criado_em", "id").iterator():
        seq += 1
        osp.sequencial_global = seq
        osp.save(update_fields=["sequencial_global"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("osp", "0006_ordemservico_achado_ordemservico_sequencial_cliente"),
    ]

    operations = [
        migrations.AddField(
            model_name="ordemservico",
            name="sequencial_global",
            field=models.PositiveIntegerField(
                blank=True,
                editable=False,
                null=True,
                verbose_name="Sequencial global da OSP (todo o BD)",
            ),
        ),
        migrations.RunPython(backfill_sequencial_global, noop),
    ]
