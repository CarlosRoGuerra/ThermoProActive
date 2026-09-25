from django.db import migrations, models


def modulo_pelo_nome(nome: str) -> str:
    """
    Mesma dedução que o front fazia pelo nome (`tecnologiaTipo` em lib/inspecoes.ts)
    — usada só para preencher o que já existe, para nenhum relatório mudar de cara
    na virada. Daqui em diante o módulo é escolhido no cadastro da tecnologia.
    """
    n = (nome or "").lower()
    if "vibra" in n:
        return "VIBRACAO"
    if "termo" in n or "infraverm" in n:
        return "TERMOGRAFIA"
    return ""


def preencher_modulo(apps, schema_editor):
    TecnologiaAnalise = apps.get_model("cadastros", "TecnologiaAnalise")
    for tecnologia in TecnologiaAnalise.objects.all():
        modulo = modulo_pelo_nome(tecnologia.nome)
        if modulo:
            TecnologiaAnalise.objects.filter(pk=tecnologia.pk).update(modulo_tecnico=modulo)


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0025_tipoequipamento_categoria_tecnica_dadostecnicosmotor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tecnologiaanalise",
            name="modulo_tecnico",
            field=models.CharField(
                blank=True,
                choices=[("VIBRACAO", "Vibração"), ("TERMOGRAFIA", "Termografia")],
                default="",
                help_text="Medições, imagens e norma que o relatório técnico desta tecnologia mostra. "
                          "Vazio = layout padrão da inspeção por rota.",
                max_length=20,
                verbose_name="Módulo técnico do relatório",
            ),
        ),
        migrations.RunPython(preencher_modulo, migrations.RunPython.noop),
    ]
