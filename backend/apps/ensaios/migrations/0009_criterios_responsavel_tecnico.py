"""
Respostas do responsável técnico (07/10/2026) para a análise de fluidos e o óleo isolante:

1. Referências gerais dos fluidos lubrificantes e hidráulicos (valem para todos os
   clientes e aplicações; uma referência mais específica — do equipamento, do fluido,
   do cliente — continua prevalecendo):
     - viscosidade a 40 °C: ±20% do grau ISO VG do fluido da amostra (ISO VG 68 →
       68 cSt ± 20%). Passou disso = crítico ("intervir", como no relatório-modelo);
     - teor de água: máximo de 2% (20.000 ppm). Passou disso = crítico.
   O limite de alerta não foi definido: fica vazio (o sistema não inventa).
2. Instrumentação: o laboratório é parceiro e já está cadastrado em Instrumentação
   ("LFxx - Laboratório de Fluídos"). Os 6 instrumentos genéricos criados pela 0007
   (só o tipo, sem uso) saem; os laboratórios passam a ficar disponíveis nas
   tecnologias de fluidos lubrificantes e de óleo isolante, para o analista escolher
   no laudo — e a carta lista o laboratório escolhido.
3. PCB (óleo isolante): faixas da NBR 13882 na nota técnica da ficha. O limite
   (50 mg/kg) já era o do catálogo.
"""
from decimal import Decimal as D

from django.db import migrations

FLUIDO, OLEO = "FLUIDO_LUBRIFICANTE", "OLEO_ISOLANTE"
FONTE = "Definido pelo responsável técnico em 07/10/2026"
REFERENCIAS = [
    # código do parâmetro, campos
    ("VISC40", dict(tipo="VARIACAO", base_grau_iso=True, limite_critico=D("20"),
                    observacao="±20% do grau ISO VG do fluido da amostra (ex.: ISO VG 68 → 68 cSt ± 20%).")),
    ("AGUA", dict(tipo="MAXIMO", limite_critico=D("20000"), observacao="Máximo de 2% de água (20.000 ppm).")),
]
GENERICOS = [
    "Espectrômetro de Emissão Óptica",
    "Espectrômetro de Infravermelho – IR",
    "Viscosímetro de Dupla Temperatura (40°/100°)",
    "Contador de Partículas",
    "Microscópio",
    "Softwares de Análises",
]
LABORATORIOS = ("Laboratório de Fluídos", "Laboratorio de Fluidos", "Laboratório de Fluidos")
NOTA_PCB = (
    "Teor de PCB conforme NBR 13882: acima de 50 mg/kg, amostra contaminada; de 2 a 50 mg/kg, presença de PCB "
    "sob controle; abaixo de 2 mg/kg, não detectado pelo método do laboratório."
)


def _laboratorios(Instrumento):
    ids = set()
    for nome in LABORATORIOS:
        ids |= set(Instrumento.objects.filter(tipo__icontains=nome, ativo=True).values_list("id", flat=True))
    return Instrumento.objects.filter(id__in=ids)


def carregar(apps, schema_editor):
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Instrumento = apps.get_model("cadastros", "Instrumento")
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")

    for codigo, campos in REFERENCIAS:
        p = Parametro.objects.filter(ensaio__modulo=FLUIDO, codigo=codigo).first()
        if p is None or Referencia.objects.filter(parametro=p, origem="RESPONSAVEL_TECNICO", cliente__isnull=True,
                                                  equipamento__isnull=True, produto__isnull=True, aplicacao="").exists():
            continue
        Referencia.objects.create(parametro=p, origem="RESPONSAVEL_TECNICO", fonte=FONTE, **campos)

    Instrumento.objects.filter(
        tipo__in=GENERICOS, marca="", modelo="", numero_serie="", data_ultima_calibracao__isnull=True,
        carregamentos__isnull=True, resultados_ensaio__isnull=True,
    ).delete()
    tecnologias = list(Tecnologia.objects.filter(modulo_tecnico__in=[FLUIDO, OLEO]))
    for lab in _laboratorios(Instrumento):
        lab.tecnologias.add(*tecnologias)

    Ensaio.objects.filter(modulo=OLEO, sigla="PCB", nota_tecnica="").update(nota_tecnica=NOTA_PCB)


def desfazer(apps, schema_editor):
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Instrumento = apps.get_model("cadastros", "Instrumento")
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")

    Referencia.objects.filter(origem="RESPONSAVEL_TECNICO", fonte=FONTE).delete()
    Ensaio.objects.filter(modulo=OLEO, sigla="PCB", nota_tecnica=NOTA_PCB).update(nota_tecnica="")
    tecnologias = list(Tecnologia.objects.filter(modulo_tecnico__in=[FLUIDO, OLEO]))
    for lab in _laboratorios(Instrumento):
        lab.tecnologias.remove(*tecnologias)
    # Os instrumentos genéricos não voltam: eram só o tipo, sem dado do laboratório.


class Migration(migrations.Migration):
    dependencies = [
        ("ensaios", "0008_referencia_base_grau_iso"),
        ("cadastros", "0033_criterios_iso_20816"),
    ]

    operations = [migrations.RunPython(carregar, desfazer)]
