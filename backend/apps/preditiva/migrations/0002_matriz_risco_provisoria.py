from django.db import migrations


def criar_matriz_provisoria(apps, schema_editor):
    """Matriz padrão PROVISÓRIA, global, para o Master revisar. Valores espelham risco.MATRIZ_RESERVA."""
    MatrizRisco = apps.get_model("preditiva", "MatrizRisco")
    if MatrizRisco.objects.filter(cliente__isnull=True).exists():
        return
    MatrizRisco.objects.create(
        nome="Matriz provisória do sistema",
        peso_severidade="0.60",
        peso_tendencia="0.40",
        consequencia={"A": 3, "B": 2, "C": 1},
        faixas=[
            {"ate": 25, "rotulo": "BAIXO"},
            {"ate": 50, "rotulo": "MODERADO"},
            {"ate": 75, "rotulo": "ALTO"},
            {"ate": 100, "rotulo": "MUITO ALTO"},
        ],
        validacao="PROVISORIA",
        fonte="Padrão provisório — a confirmar pelo cliente.",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("preditiva", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(criar_matriz_provisoria, migrations.RunPython.noop),
    ]
