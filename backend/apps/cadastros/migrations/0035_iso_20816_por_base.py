"""
ISO 20816-3:2022 por tipo de base — tabelas A.1 (Grupo 1) e A.2 (Grupo 2) enviadas pelo
responsável técnico em 08/10/2026, com o deslocamento:

  "o critério de vibração vale também para base rígida = Não" — cada base tem a sua coluna.

                    velocidade (mm/s RMS)       deslocamento (µm RMS)
                    A/B    B/C    C/D            A/B   B/C   C/D
  Grupo 1 rígida    2,3    4,5    7,1            29    57    90
  Grupo 1 flexível  3,5    7,1    11,0           45    90    140
  Grupo 2 rígida    1,4    2,8    4,5            22    45    71
  Grupo 2 flexível  2,3    4,5    7,1            37    71    113

São os valores publicados pela norma (origem NORMA), com vigência a partir de 08/10/2026.
Os critérios de 07/10/2026 (coluna flexível para qualquer base) ficam com vigência só nesse
dia — nada é apagado. O tipo de base das máquinas vem do datasheet do motor, quando há;
sem ele, a análise usa a base rígida (a mais rigorosa) e avisa no diagnóstico.
"""
from datetime import date
from decimal import Decimal as D

from django.db import migrations

INICIO = date(2026, 10, 8)
FIM_ANTERIOR = date(2026, 10, 7)
NOMES = {"G1": "Máquinas acima de 300 kW", "G2": "Máquinas de 15 a 300 kW"}
TABELAS = {"G1": "Tabela A.1", "G2": "Tabela A.2"}
CRITERIOS = [
    # classe, suporte, (A/B, B/C, C/D) velocidade, (A/B, B/C, C/D) deslocamento
    ("G1", "RIGIDO", (D("2.30"), D("4.50"), D("7.10")), (D("29"), D("57"), D("90"))),
    ("G1", "FLEXIVEL", (D("3.50"), D("7.10"), D("11.00")), (D("45"), D("90"), D("140"))),
    ("G2", "RIGIDO", (D("1.40"), D("2.80"), D("4.50")), (D("22"), D("45"), D("71"))),
    ("G2", "FLEXIVEL", (D("2.30"), D("4.50"), D("7.10")), (D("37"), D("71"), D("113"))),
]


def _fonte(classe, suporte):
    base = "fundação rígida" if suporte == "RIGIDO" else "fundação flexível"
    return f"ISO 20816-3:2022, {TABELAS[classe]} — {base} (enviada pelo responsável técnico em 08/10/2026)"


def carregar(apps, schema_editor):
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")
    Equipamento = apps.get_model("cadastros", "Equipamento")
    DadosMotor = apps.get_model("cadastros", "DadosTecnicosMotor")

    Criterio.objects.filter(classe__in=["G1", "G2"], cliente__isnull=True, origem="RESPONSAVEL_TECNICO",
                            vigencia_inicio=FIM_ANTERIOR, vigencia_fim__isnull=True).update(vigencia_fim=FIM_ANTERIOR)
    for classe, suporte, (ab, bc, cd), (dab, dbc, dcd) in CRITERIOS:
        if Criterio.objects.filter(classe=classe, suporte=suporte, cliente__isnull=True, vigencia_inicio=INICIO).exists():
            continue
        Criterio.objects.create(
            norma_codigo="ISO 20816-3", norma_edicao="2022", classe=classe, suporte=suporte,
            descricao_grupo=NOMES[classe], limite_ab=ab, limite_bc=bc, limite_cd=cd,
            desloc_ab=dab, desloc_bc=dbc, desloc_cd=dcd, origem="NORMA", fonte=_fonte(classe, suporte),
            vigencia_inicio=INICIO,
        )
    for eq_id, base in DadosMotor.objects.exclude(tipo_base="").values_list("equipamento_id", "tipo_base"):
        Equipamento.objects.filter(pk=eq_id, tipo_base="").update(tipo_base=base)


def desfazer(apps, schema_editor):
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")
    for classe, suporte, _, _ in CRITERIOS:
        Criterio.objects.filter(classe=classe, suporte=suporte, cliente__isnull=True, vigencia_inicio=INICIO,
                                fonte=_fonte(classe, suporte)).delete()
    Criterio.objects.filter(classe__in=["G1", "G2"], cliente__isnull=True, origem="RESPONSAVEL_TECNICO",
                            vigencia_inicio=FIM_ANTERIOR, vigencia_fim=FIM_ANTERIOR).update(vigencia_fim=None)
    # `Equipamento.tipo_base` some com o campo ao reverter a 0034.


class Migration(migrations.Migration):
    dependencies = [("cadastros", "0034_base_e_deslocamento")]

    operations = [migrations.RunPython(carregar, desfazer)]
