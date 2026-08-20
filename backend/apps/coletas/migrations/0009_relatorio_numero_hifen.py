from django.db import migrations


def pontos_para_hifen(apps, schema_editor):
    """
    Normaliza o número dos relatórios existentes para o gabarito definitivo:
    RT-{SIGLA}-{AAAA.MM.DD}.{SEQ}  ->  RT-{SIGLA}-{AAAA-MM-DD}-{SEQ}
    (troca os separadores de ponto por hífen). Transformação determinística e
    bijetiva — não gera colisão na unicidade (cliente, numero).
    """
    Relatorio = apps.get_model("coletas", "Relatorio")
    for rel in Relatorio.objects.filter(numero__contains=".").iterator():
        novo = rel.numero.replace(".", "-")
        if novo != rel.numero:
            rel.numero = novo
            rel.save(update_fields=["numero"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("coletas", "0008_relatorio_consideracoes_finais_and_more"),
    ]

    operations = [
        migrations.RunPython(pontos_para_hifen, noop),
    ]
