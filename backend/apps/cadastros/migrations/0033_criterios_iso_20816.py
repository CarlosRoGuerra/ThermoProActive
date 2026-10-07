"""
Severidade de vibração pela ISO 20816-3:2022 — definição do responsável técnico em 07/10/2026:

  - até 15 kW: Classe I (a ISO 20816-3 não cobre) — crítico acima de 4,5 mm/s, como no
    critério já cadastrado (ISO 10816-1:1995, Classe I), que continua valendo;
  - 15 a 300 kW: Grupo 2 — crítico acima de 7,1 mm/s;
  - acima de 300 kW: Grupo 1 — crítico acima de 11,0 mm/s.

O responsável técnico informou o limite crítico (C/D). Os limites A/B e B/C são os da
MESMA coluna da tabela da norma (fundação flexível), que é a coluna desses valores
críticos; ficam registrados como "critério do responsável técnico", com a fonte escrita
— a carta diz isso em nota. Para máquina em base rígida a norma é mais rigorosa.

O que esta migração faz (nada é apagado):
1. Cria os critérios do Grupo 2 e do Grupo 1 com vigência a partir de 07/10/2026.
2. Encerra em 06/10/2026 a vigência dos critérios globais das Classes II, III e IV
   (ISO 10816-1). Os relatórios até essa data continuam com a tabela da época.
3. Reclassifica as máquinas avaliadas por vibração: pela potência quando conhecida
   (≤ 15 kW → I; ≤ 300 kW → Grupo 2; > 300 kW → Grupo 1); sem potência, Classe II
   vira Grupo 2 (15–75 kW cabe nos 15–300 kW). Classe III/IV sem potência fica como
   está — acima de 75 kW pode ser Grupo 2 ou 1 — e o cadastro pede a revisão.
   Medições e serviços já gravados guardam a zona calculada na época: não mudam.
"""
from datetime import date
from decimal import Decimal as D

from django.db import migrations

INICIO = date(2026, 10, 7)
FIM_ANTERIOR = date(2026, 10, 6)
FONTE = ("ISO 20816-3:2022, Anexo A — zonas da fundação flexível aplicadas a todo o grupo; limite crítico "
         "definido pelo responsável técnico em 07/10/2026")
CRITERIOS = [
    # classe, descrição, A/B, B/C, C/D
    ("G2", "Máquinas de 15 a 300 kW", D("2.30"), D("4.50"), D("7.10")),
    ("G1", "Máquinas acima de 300 kW", D("3.50"), D("7.10"), D("11.00")),
]
LIMITE_I, LIMITE_G2 = D("15"), D("300")


def carregar(apps, schema_editor):
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")
    Equipamento = apps.get_model("cadastros", "Equipamento")
    DadosMotor = apps.get_model("cadastros", "DadosTecnicosMotor")

    for classe, descricao, ab, bc, cd in CRITERIOS:
        if not Criterio.objects.filter(classe=classe, cliente__isnull=True, vigencia_inicio=INICIO).exists():
            Criterio.objects.create(
                norma_codigo="ISO 20816-3", norma_edicao="2022", classe=classe, descricao_grupo=descricao,
                limite_ab=ab, limite_bc=bc, limite_cd=cd, origem="RESPONSAVEL_TECNICO", fonte=FONTE,
                vigencia_inicio=INICIO,
            )
    Criterio.objects.filter(classe__in=["II", "III", "IV"], cliente__isnull=True, vigencia_fim__isnull=True) \
        .update(vigencia_fim=FIM_ANTERIOR)

    potencia_motor = dict(DadosMotor.objects.exclude(potencia_kw__isnull=True).values_list("equipamento_id", "potencia_kw"))
    for eq in Equipamento.objects.filter(tipo_equipamento__analise_vibracao=True).exclude(classe_iso__in=["", "G1", "G2"]):
        p = potencia_motor.get(eq.id) or eq.potencia_kw
        if p is not None:
            nova = "I" if p <= LIMITE_I else ("G2" if p <= LIMITE_G2 else "G1")
        else:
            nova = {"II": "G2"}.get(eq.classe_iso, eq.classe_iso)
        if nova != eq.classe_iso:
            Equipamento.objects.filter(pk=eq.pk).update(classe_iso=nova)


def desfazer(apps, schema_editor):
    """Volta ao critério da ISO 10816-1: grupos pela regra antiga (potência e base)."""
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")
    Equipamento = apps.get_model("cadastros", "Equipamento")
    DadosMotor = apps.get_model("cadastros", "DadosTecnicosMotor")

    Criterio.objects.filter(classe__in=["II", "III", "IV"], cliente__isnull=True, vigencia_fim=FIM_ANTERIOR) \
        .update(vigencia_fim=None)
    Criterio.objects.filter(classe__in=["G1", "G2"], cliente__isnull=True, vigencia_inicio=INICIO,
                            origem="RESPONSAVEL_TECNICO", fonte=FONTE).delete()
    motores = {m.equipamento_id: m for m in DadosMotor.objects.all()}
    for eq in Equipamento.objects.filter(classe_iso__in=["G1", "G2"]):
        m = motores.get(eq.id)
        p = (m.potencia_kw if m and m.potencia_kw is not None else None) or eq.potencia_kw
        base = m.tipo_base if m else ""
        if p is not None and p <= D("75"):
            antiga = "II"
        elif base == "FLEXIVEL":
            antiga = "IV"
        elif base == "RIGIDA" or (p is not None and p > D("75")):
            antiga = "III"
        else:
            antiga = "II"
        Equipamento.objects.filter(pk=eq.pk).update(classe_iso=antiga)


class Migration(migrations.Migration):
    dependencies = [("cadastros", "0032_grupos_iso_20816")]

    operations = [migrations.RunPython(carregar, desfazer)]
