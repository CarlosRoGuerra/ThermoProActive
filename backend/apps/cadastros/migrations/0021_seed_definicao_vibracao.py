"""
Semeia a "Definição da Técnica" (item 7 da carta) nas tecnologias de VIBRAÇÃO,
para que o conteúdo venha do banco na hora de formar o relatório/carta.

Só preenche campos VAZIOS (não sobrescreve nada que já tenha sido cadastrado).
Alvo: tecnologias cujo nome contém "vibra" (ex.: "Análise Vibracional …").
"""
from django.db import migrations

INTRO = (
    "Uma máquina ideal não produz “qualquer” vibração, pois toda a energia é canalizada para a "
    "execução do trabalho a ser realizado. Na prática, entretanto, os elementos que compõem as "
    "máquinas, em geral, interagem entre si e, devido à presença de atrito, ação de forças cíclicas "
    "etc., dissipa energia na forma de calor, ruído e vibrações.\n"
    "Um bom projeto deve apresentar bom rendimento, ou seja, baixo nível de dissipação de calor, "
    "baixo nível de ruído e baixo nível de vibração. De uma forma geral, as máquinas novas, quando "
    "bem projetadas, satisfazem a esses requisitos. Entretanto, com o desgaste, acomodação de "
    "fundações, má utilização, falta de manutenção, etc., as máquinas têm suas propriedades "
    "dinâmicas alteradas.\n"
    "Todos esses fatores são refletidos na diminuição de rendimento e, consequentemente, no aumento "
    "do nível de vibração."
)

FLUXO = (
    "O fluxo de trabalho consiste em 03 etapas distintas:\n"
    "1ª etapa (contratada): coleta de dados, análise de dados, emissão de laudos.\n"
    "2ª etapa (contratante): planejamento e execução das correções, retorno das informações.\n"
    "3ª etapa (contratada): análise das informações retornadas, avaliação de resultados."
)

LEGENDA = "Abaixo observaremos a disposição dos pontos de medição:"


def seed(apps, schema_editor):
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")
    for t in Tecnologia.objects.filter(nome__icontains="vibra"):
        campos = []
        if not (t.definicao_tecnica or "").strip():
            t.definicao_tecnica = INTRO
            campos.append("definicao_tecnica")
        if not (t.definicao_fluxo_trabalho or "").strip():
            t.definicao_fluxo_trabalho = FLUXO
            campos.append("definicao_fluxo_trabalho")
        if not (t.definicao_legenda_imagem or "").strip():
            t.definicao_legenda_imagem = LEGENDA
            campos.append("definicao_legenda_imagem")
        if campos:
            t.save(update_fields=campos)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("cadastros", "0020_tecnologiaanalise_definicao_fluxo_trabalho_and_more"),
    ]

    operations = [
        migrations.RunPython(seed, noop),
    ]
