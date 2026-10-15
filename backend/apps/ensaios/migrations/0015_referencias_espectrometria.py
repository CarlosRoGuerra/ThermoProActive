"""
Referências gerais da espectrometria (EF) — responsável técnico, 13/10/2026 (2ª mensagem,
"análise comparativa entre o óleo usado e o óleo novo"). Método do óleo em uso: ASTM D5185
(a D4951 é de controle de qualidade do óleo novo, só aditivos).

Metais de desgaste (máximo, ppm):        alerta > / crítico >
  Hidráulicos      Fe 15/30 · Cu 10/20 · Al 5/15 · Cr 3/8 · Pb 5/10 · Sn 5/10
  Redutores e engrenagens (aplicação "Lubrificante")
                   Fe 80/150 · Cu 25/50 · Al 15/30 · Cr 5/15 · Pb 10/25 · Sn 10/25
                   (Fe crítico informado como "150 a 200": vale o 150, o mais rigoroso)
Contaminação:     Si — aumento > 15 ppm sobre o óleo novo = crítico (o antiespumante de
                  silicone do óleo novo fica na linha de base); Na > 15 ppm = alerta
Metais traço:     Mn, Ti, Ni, Ag, V > 5 ppm = alerta (investigação)
Aditivos:         Zn, P, B, Mo, Ba — queda > 15% do óleo novo = alerta; > 25% = crítico
                  Ca, Mg — aumento > 20 ppm sobre o óleo novo = alerta (mistura com óleo de motor)

Aditivos e silício comparam com o BOLETIM DO ÓLEO NOVO cadastrado para o fluido; sem
boletim, a queda fica sem classificação e o aumento conta a partir de zero.
Uma referência mais específica (equipamento, tipo, fluido, cliente) continua prevalecendo.
"""
from decimal import Decimal as D

from django.db import migrations

FONTE = "Definido pelo responsável técnico em 13/10/2026"
DESGASTE = {
    "HIDRAULICO": {"FE": (15, 30), "CU": (10, 20), "AL": (5, 15), "CR": (3, 8), "PB": (5, 10), "SN": (5, 10)},
    "LUBRIFICANTE": {"FE": (80, 150), "CU": (25, 50), "AL": (15, 30), "CR": (5, 15), "PB": (10, 25), "SN": (10, 25)},
}
REFERENCIAS = (
    [("SI", dict(tipo="AUMENTO", base_oleo_novo=True, limite_critico=D("15"),
                 observacao="Aumento sobre o óleo novo: poeira/quartzo do ambiente."))]
    + [("NA", dict(tipo="MAXIMO", limite_alerta=D("15"), observacao="Água externa (lavagem, torre de resfriamento)."))]
    + [(c, dict(tipo="MAXIMO", limite_alerta=D("5"), observacao="Metal traço: acima de 5 ppm, investigar."))
       for c in ("MN", "TI", "NI", "AG", "V")]
    + [(c, dict(tipo="QUEDA", base_oleo_novo=True, limite_alerta=D("15"), limite_critico=D("25"),
                observacao="Consumo do aditivo em relação ao óleo novo."))
       for c in ("ZN", "P", "B", "MO", "BA")]
    + [(c, dict(tipo="AUMENTO", base_oleo_novo=True, limite_alerta=D("20"),
                observacao="Aparecimento no óleo usado: mistura com óleo de motor."))
       for c in ("CA", "MG")]
)


def carregar(apps, schema_editor):
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Referencia = apps.get_model("ensaios", "ReferenciaParametro")
    params = {p.codigo: p for p in Parametro.objects.filter(ensaio__modulo="FLUIDO_LUBRIFICANTE", ensaio__sigla="EF")}

    def criar(codigo, aplicacao="", **campos):
        p = params.get(codigo)
        if p is None or Referencia.objects.filter(parametro=p, origem="RESPONSAVEL_TECNICO", aplicacao=aplicacao,
                                                  cliente__isnull=True, equipamento__isnull=True,
                                                  tipo_equipamento__isnull=True, produto__isnull=True).exists():
            return
        Referencia.objects.create(parametro=p, aplicacao=aplicacao, origem="RESPONSAVEL_TECNICO", fonte=FONTE, **campos)

    for aplicacao, limites in DESGASTE.items():
        for codigo, (alerta, critico) in limites.items():
            criar(codigo, aplicacao, tipo="MAXIMO", limite_alerta=D(alerta), limite_critico=D(critico),
                  observacao="Metal de desgaste (óleo em uso, ASTM D5185).")
    for codigo, campos in REFERENCIAS:
        criar(codigo, **campos)


def desfazer(apps, schema_editor):
    apps.get_model("ensaios", "ReferenciaParametro").objects.filter(origem="RESPONSAVEL_TECNICO", fonte=FONTE).delete()


class Migration(migrations.Migration):
    dependencies = [("ensaios", "0014_boletim_oleo_novo")]

    operations = [migrations.RunPython(carregar, desfazer)]
