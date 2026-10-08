from decimal import Decimal

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Base da variação = valor do óleo novo do cadastro do fluido (ficha técnica), não o
    texto do grau ISO VG — responsável técnico, 08/10/2026. Renomeia o campo (sem perda
    de dado). Os campos novos da ficha técnica e as metas de limpeza vêm na 0012.
    """

    dependencies = [("ensaios", "0010_referencia_tan")]

    operations = [
        migrations.RenameField("referenciaparametro", "base_grau_iso", "base_oleo_novo"),
        migrations.AlterField(
            model_name="referenciaparametro",
            name="base_oleo_novo",
            field=models.BooleanField(
                default=False, verbose_name="Base = valor do óleo novo (cadastro do fluido)",
                help_text="Na Variação: a base é o valor do óleo novo do fluido da coleta (viscosidade a 40 °C, "
                          "densidade, índice de viscosidade ou TBN, da ficha técnica), em vez de um valor fixo.",
            ),
        ),
        migrations.AlterField(
            model_name="produtofluido",
            name="grau_viscosidade",
            field=models.CharField(blank=True, max_length=20, verbose_name="Grau / classificação de viscosidade",
                                   help_text="Só informativo, em qualquer classificação: ISO VG 46, SAE 40, AGMA 4…"),
        ),
        migrations.AlterField(
            model_name="produtofluido",
            name="viscosidade_40c_cst",
            field=models.DecimalField(
                blank=True, decimal_places=2, max_digits=8, null=True,
                verbose_name="Viscosidade cinemática a 40 °C do óleo novo (cSt = mm²/s) — ASTM D445",
                help_text="Da ficha técnica do fabricante. É a base da variação da viscosidade.",
            ),
        ),
        migrations.AlterField(
            model_name="produtofluido",
            name="indice_viscosidade",
            field=models.DecimalField(blank=True, decimal_places=1, max_digits=6, null=True,
                                      verbose_name="Índice de viscosidade do óleo novo — ASTM D2270",
                                      help_text="Número adimensional (ex.: 100). Não é a viscosidade."),
        ),
    ]
