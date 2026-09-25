"""
Catálogos dos ensaios de transformador, transcritos dos relatórios de referência
2025-12_TRF-001_Óleo.pdf e 2025-12_TRF-001_ENDe.pdf (unidades, normas,
referências e tipo de limite como estão nas fichas). Parâmetros "calculados" são
os que o sistema deriva de outros valores (TG/TGC, erro do R×T, IP/IA); o critério
do IP (> 1,0) é do ANSI/NETA ATS, adotado por pesquisa — ver docs/10.
Tudo continua editável no admin.
"""
from decimal import Decimal

from django.db import migrations

D = Decimal

ENSAIOS = [
    # sigla, nome, modulo, titulo da ficha, ordem, rótulo conclusão, rótulo informações, rótulo próxima data, nota técnica
    ("FQ", "Físico-Químico", "OLEO_ISOLANTE", "RESULTADOS DO ENSAIO FQ - FÍSICO-QUÍMICO", 1,
     "Conclusão", "Informações Adicionais", "Data da Próxima Coleta", ""),
    ("CR", "Cromatográfico", "OLEO_ISOLANTE", "RESULTADOS DO ENSAIO CR - CROMATOGRÁFICO", 2,
     "Conclusão", "Informações Adicionais", "Data da Próxima Coleta", ""),
    ("PCB", "Teor PCB", "OLEO_ISOLANTE", "RESULTADOS DO ENSAIO PCB - TEOR DE PCB", 3,
     "Conclusão", "Informações Adicionais", "Data da Próxima Coleta", ""),
    ("2FAL", "2-FAL", "OLEO_ISOLANTE", "RESULTADOS DO ENSAIO 2-FAL", 4,
     "Conclusão", "Informações Adicionais", "Data da Próxima Coleta",
     "1. Análise realizada conforme a Norma NBR-15349:2006;\n"
     "2. O limite de Quantificação [LQ] referente à metodologia do ensaio para cada composto é de 0,010mg/kg;\n"
     "3. Com o envelhecimento do papel isolante do transformador, são produzidos compostos solúveis em óleo, "
     "denominados compostos furânicos. Altas concentrações de 2-furfural, o composto de maior predominância no "
     "óleo é uma indicação clara da degradação da celulose. A determinação do Grau de Polimerização em função da "
     "concentração de 2-furfural no óleo isolante foi obitida impiricamente de acordo com a equação De Pablo, e "
     "permite assim estimar o tempo de vida remanescente do transformador;\n"
     "4. Segundo a NBR-5356-7:2017, são informados na tabela G.3 os seguintes valores para o ensaio de Grau de "
     "Polimerização [GP] em papel isolante: Fim de vida útil, menor que 200 monômeros. Após secagem em fábrica, "
     "maior que 800 monômeros. No recebimento em fábrica, maior que 1.000 monômeros. Equipamentos que tiveram o "
     "óleo isolante regenerado ou substituído apresentam resultados de teor de 2-Furfural e seus derivados que "
     "impossibilitam um diagnóstico preciso da real situação da isolação celulósica;"),
    ("RXT", "Relação de Transformação", "ENSAIO_ELETRICO", "R x T - RELAÇÃO DE TRANSFORMAÇÃO", 1,
     "Observações", "Instrumentação Utilizada", "Data da Próxima Análise", ""),
    ("RXI", "Resistência de Isolação", "ENSAIO_ELETRICO", "R x I - RESISTÊNCIA DE ISOLAÇÃO", 2,
     "Observações", "Instrumentação Utilizada", "Data da Próxima Coleta", ""),
    ("RXO", "Resistência Ôhmica", "ENSAIO_ELETRICO", "R x O - RESISTÊNCIA ÔHMICA", 3,
     "Observações", "Instrumentação Utilizada", "Data da Próxima Análise", ""),
]

MAX, MIN, FAIXA, QUAL, INFO = "MAXIMO", "MINIMO", "FAIXA", "QUALITATIVO", "INFORMATIVO"
NORMA_CR = "NBR-7070 | NBR-7274"
NORMA_2FAL = "NBR-5356:7"

PARAMETROS = {
    # codigo, nome, unidade, norma, tipo, limite, limite superior, referência texto, casas, calculado, no gráfico
    "FQ": [
        ("VISCOSIDADE", "Viscosidade a 40ºC", "cSt", "NBR-10441", MAX, D("50.00"), None, "", 2, False, True),
        ("DENSIDADE", "Densidade", "", "NBR-7148", MAX, D("0.90"), None, "", 2, False, True),
        ("FATOR_POTENCIA", "Fator de Potência a 100ºC", "%", "NBR-12133", MAX, D("3.00"), None, "", 2, False, True),
        ("NEUTRALIZACAO", "Índice de Neutralização", "mgKOH/g", "NBR-14248", MAX, D("0.30"), None, "", 2, False, True),
        ("TEOR_AGUA", "Teor de Água", "ppm", "NBR-10710", MAX, D("40.00"), None, "", 2, False, True),
        ("RIGIDEZ", "Rigidez Dielétrica", "kV/2,5mm", "NBR-60156", MIN, D("40.00"), None, "", 2, False, True),
        ("TENSAO_INTERFACIAL", "Tensão Interfacial a 25ºC", "dina/cm", "NBR-6234", MIN, D("20.00"), None, "", 2, False, True),
        ("COR", "Cor", "", "NBR-14483", INFO, None, None, "", 2, False, False),
        ("APARENCIA", "Aparência", "", "Visual", QUAL, None, None, "Límpido", 0, False, False),
    ],
    "CR": [
        ("H2", "Hidrogênio (H2)", "ppm", NORMA_CR, MAX, D("200.0"), None, "", 1, False, True),
        ("O2", "Oxigênio (O2)", "ppm", NORMA_CR, MAX, D("20000.0"), None, "", 1, False, True),
        ("N2", "Nitrogênio (N2)", "ppm", NORMA_CR, MAX, D("80000.0"), None, "", 1, False, True),
        ("CH4", "Metano (CH4)", "ppm", NORMA_CR, MAX, D("100.0"), None, "", 1, False, True),
        ("CO", "Monóxido de Carbono (CO)", "ppm", NORMA_CR, MAX, D("500.0"), None, "", 1, False, True),
        ("CO2", "Dióxido de Carbono (CO2)", "ppm", NORMA_CR, MAX, D("5000.0"), None, "", 1, False, True),
        ("C2H4", "Etileno (C2H4)", "ppm", NORMA_CR, MAX, D("60.0"), None, "", 1, False, True),
        ("C2H6", "Etano (C2H6)", "ppm", NORMA_CR, MAX, D("115.0"), None, "", 1, False, True),
        ("C2H2", "Acetileno (C2H2)", "ppm", NORMA_CR, MAX, D("0.0"), None, "", 1, False, True),
        ("TG", "TG — Total de Gases", "ppm", "", INFO, None, None, "", 0, True, False),
        ("TGC", "TGC — Total de Gases Combustíveis", "ppm", "IEEE C57.104", INFO, None, None, "", 0, True, False),
    ],
    "PCB": [
        ("PCB", "Teor PCB (cromatog.)", "mg/kg", "NBR-13882", MAX, D("50.0"), None, "", 1, False, True),
    ],
    "2FAL": [
        ("2FOL", "2-Furfurilalcool", "mg/kg", NORMA_2FAL, MAX, D("0.010"), None, "", 3, False, True),
        ("5HMF", "5-Hidroximetil 2-FUR", "mg/kg", NORMA_2FAL, MAX, D("0.010"), None, "", 3, False, True),
        ("2FAL", "2-Furfural", "mg/kg", NORMA_2FAL, MAX, D("0.010"), None, "", 3, False, True),
        ("2ACF", "2-Acetilfurano", "mg/kg", NORMA_2FAL, MAX, D("0.010"), None, "", 3, False, True),
        ("5MEF", "5-Metil 2-Furfural", "mg/kg", NORMA_2FAL, MAX, D("0.010"), None, "", 3, False, True),
        ("GP", "Grau de Polimerização", "GP", NORMA_2FAL, MIN, D("800.00"), None, "", 2, False, True),
    ],
    "RXT": [
        ("NOMINAL", "Relação Nominal", "", "", INFO, None, None, "", 3, False, False),
        ("MEDIDA", "Relação medida", "", "", INFO, None, None, "", 3, False, False),
        ("ERRO", "Erro", "%", "ANSI NETA ATS 2009", FAIXA, D("-0.5"), D("0.5"), "", 2, True, False),
    ],
    "RXI": [
        ("RESISTENCIA", "Resistência de isolação", "MΩ", "", INFO, None, None, "", 0, False, True),
        ("TENSAO", "Tensão de ensaio", "V", "", INFO, None, None, "", 0, False, False),
        ("IP", "Índice de Polarização (600 s / 60 s)", "", "ANSI/NETA ATS", MIN, D("1.0"), None, "", 2, True, False),
        ("IA", "Índice de Absorção (60 s / 30 s)", "", "", INFO, None, None, "", 2, True, False),
    ],
    "RXO": [
        ("H1H2", "H1 | H2", "Ω", "", INFO, None, None, "", 2, False, False),
        ("H1H3", "H1 | H3", "Ω", "", INFO, None, None, "", 2, False, False),
        ("H2H3", "H2 | H3", "Ω", "", INFO, None, None, "", 2, False, False),
        ("X0X1", "X0 | X1", "mΩ", "", INFO, None, None, "", 2, False, False),
        ("X0X2", "X0 | X2", "mΩ", "", INFO, None, None, "", 2, False, False),
        ("X0X3", "X0 | X3", "mΩ", "", INFO, None, None, "", 2, False, False),
    ],
}

CHECKLIST = {
    "GERAL": [
        "Aterramento conectado", "Buchas do Primário", "Buchas do Secundário", "Comutador",
        "Janela de inspeção", "Nível de Óleo", "Pintura", "Radiadores de resfriamento",
        "Registro do dreno", "Registro superior [alívio de pressão]", "Tampa superior", "Vedação",
    ],
    "TANQUE_EXPANSAO": [
        "Desumidificador de Ar [Sílica Gel]", "Desumidificador de Ar [Nível de Óleo]",
        "Rele de gás - Buchholz", "Rele de pressão súbita", "Tanque de Expansão", "Termômetro",
        "Tubo de explosão", "Válvula de alívio de pressão",
    ],
}


def carregar(apps, schema_editor):
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Item = apps.get_model("ensaios", "ItemChecklistVisual")
    PontoColeta = apps.get_model("ensaios", "PontoColeta")
    TipoFluido = apps.get_model("ensaios", "TipoFluido")

    for sigla, nome, modulo, titulo, ordem, r_conc, r_info, r_prox, nota in ENSAIOS:
        ensaio, _ = Ensaio.objects.update_or_create(sigla=sigla, defaults=dict(
            nome=nome, modulo=modulo, titulo_ficha=titulo, ordem=ordem, rotulo_conclusao=r_conc,
            rotulo_informacoes=r_info, rotulo_proxima=r_prox, nota_tecnica=nota,
        ))
        for i, (codigo, pnome, unidade, norma, tipo, lim, lim_sup, ref, casas, calc, graf) in enumerate(
            PARAMETROS[sigla], start=1
        ):
            Parametro.objects.update_or_create(ensaio=ensaio, codigo=codigo, defaults=dict(
                nome=pnome, unidade=unidade, norma=norma, tipo_limite=tipo, limite=lim, limite_superior=lim_sup,
                referencia_texto=ref, casas_decimais=casas, calculado=calc, no_grafico=graf, ordem=i,
            ))
    for grupo, nomes in CHECKLIST.items():
        for i, nome in enumerate(nomes, start=1):
            Item.objects.update_or_create(nome=nome, grupo=grupo, defaults={"ordem": i})
    PontoColeta.objects.get_or_create(nome="Dreno Inferior Lado AT")
    TipoFluido.objects.get_or_create(nome="Óleo Mineral B [Parafínico]")


class Migration(migrations.Migration):

    dependencies = [("ensaios", "0001_initial")]

    operations = [migrations.RunPython(carregar, migrations.RunPython.noop)]
