"""
Ajustes do catálogo de fluidos pedidos pelo responsável técnico (08 e 09/10/2026):

- A variação da viscosidade a 40 °C usa a viscosidade do ÓLEO NOVO da ficha técnica do
  fluido (ASTM D445, cSt = mm²/s) — vale para qualquer classificação (ISO VG, SAE, AGMA…).
  A referência geral passa a dizer isso.
- Densidade com o método mais comum (ASTM D4052); a temperatura e o método do óleo novo
  ficam no cadastro do fluido (cada fabricante usa um: 15 °C/D4052, 20 °C/D1298…).
- Índice de viscosidade e TBN com o método da ficha técnica (ASTM D2270 e D2896).
- Viscosidade a 100 °C sai da análise (informação de ficha técnica, sem uso no laudo):
  o parâmetro é desativado — valores já gravados ficam no banco.
- Metas de limpeza ISO 4406 recomendadas por máquina/componente (tabela enviada pelo
  responsável técnico) como catálogo de consulta — a meta aplicada continua sendo a
  cadastrada em "Referências dos parâmetros".
"""
from django.db import migrations

FLUIDO = "FLUIDO_LUBRIFICANTE"
OBS_ANTIGA = "±20% do grau ISO VG do fluido da amostra (ex.: ISO VG 68 → 68 cSt ± 20%)."
OBS_NOVA = ("±20% da viscosidade a 40 °C do óleo novo (ficha técnica do fluido, ASTM D445; "
            "ex.: 46 cSt → 36,8 a 55,2 cSt).")
PARAMETROS = [
    # código, campo, (antes, depois)
    ("DENSIDADE", "norma", ("", "ASTM D4052")),
    ("IV", "norma", ("", "ASTM D2270")),
    ("TBN", "norma", ("", "ASTM D2896")),
    ("VISC100", "ativo", (True, False)),
]
FONTE_METAS = "Tabela de níveis ISO 4406 recomendados enviada pelo responsável técnico em 09/10/2026"
METAS = [
    ("Mancais de Rolamentos", "16/14/12"), ("Mancais de Bucha", "20/17/14"), ("Redutores", "19/16/13"),
    ("Transmissões", "18/16/13"), ("Motores Diesel", "19/17/14"), ("Turbinas", "16/14/12"),
    ("Máquinas de Papel", "18/15/13"), ("Servo-válvulas", "14/12/10"), ("Válvulas Proporcionais", "15/13/11"),
    ("Bomba de Pistões", "16/14/12"), ("Bomba de Palhetas", "18/16/13"), ("Bomba de Engrenagens", "19/17/14"),
    ("Rolamentos em geral", "16/14/12"),
]


def _aplicar(apps, indice):
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    for codigo, campo, valores in PARAMETROS:
        Parametro.objects.filter(ensaio__modulo=FLUIDO, ensaio__sigla="FQ", codigo=codigo,
                                 **{campo: valores[1 - indice]}).update(**{campo: valores[indice]})
    de, para = (OBS_ANTIGA, OBS_NOVA) if indice == 1 else (OBS_NOVA, OBS_ANTIGA)
    Referencia.objects.filter(parametro__codigo="VISC40", origem="RESPONSAVEL_TECNICO", observacao=de) \
        .update(observacao=para)


def carregar(apps, schema_editor):
    _aplicar(apps, 1)
    Meta = apps.get_model("ensaios", "MetaLimpezaRecomendada")
    for nome, codigo in METAS:
        Meta.objects.get_or_create(nome=nome, defaults={"codigo": codigo, "fonte": FONTE_METAS})


def desfazer(apps, schema_editor):
    _aplicar(apps, 0)
    apps.get_model("ensaios", "MetaLimpezaRecomendada").objects.filter(fonte=FONTE_METAS).delete()


class Migration(migrations.Migration):
    dependencies = [("ensaios", "0012_ficha_tecnica_e_metas_iso")]

    operations = [migrations.RunPython(carregar, desfazer)]
