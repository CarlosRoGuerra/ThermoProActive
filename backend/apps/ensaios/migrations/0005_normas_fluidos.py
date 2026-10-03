"""
Normas dos métodos citados nas fichas de fluidos (catálogo "Normas", item 5 da
carta), vinculadas às tecnologias do módulo FLUIDO_LUBRIFICANTE.

Mesmo critério das normas do óleo isolante: o código como sai na ficha e a
descrição do uso no relatório (não o título oficial). São as referências de
MÉTODO de ensaio — nenhuma traz limite de aceitação; os limites ficam em
"Referências dos parâmetros". Não duplica: reaproveita a norma de mesmo código.
"""
from django.db import migrations

NORMAS = [
    ("ASTM D445", "Viscosidade cinemática de líquidos transparentes e opacos", "ASTM"),
    ("ASTM D664", "Número de acidez de produtos de petróleo por titulação potenciométrica", "ASTM"),
    ("ASTM D6304", "Teor de água em produtos de petróleo e óleos lubrificantes por titulação Karl Fischer coulométrica", "ASTM"),
    ("ASTM D5185", "Determinação multielementar em óleos lubrificantes usados e novos por ICP-AES", "ASTM"),
    ("ISO 4406", "Código do nível de contaminação de fluidos hidráulicos por partículas sólidas", "ISO"),
]


def carregar(apps, schema_editor):
    Norma = apps.get_model("cadastros", "Norma")
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")
    tecnologias = list(Tecnologia.objects.filter(modulo_tecnico="FLUIDO_LUBRIFICANTE"))
    for codigo, nome, orgao in NORMAS:
        norma = Norma.objects.filter(codigo=codigo).first() or Norma.objects.create(codigo=codigo, nome=nome, orgao=orgao)
        norma.tecnologias.add(*tecnologias)


def desfazer(apps, schema_editor):
    Norma = apps.get_model("cadastros", "Norma")
    for codigo, nome, _ in NORMAS:
        Norma.objects.filter(codigo=codigo, nome=nome).delete()


class Migration(migrations.Migration):
    dependencies = [("ensaios", "0004_catalogos_fluidos")]

    operations = [migrations.RunPython(carregar, desfazer)]
