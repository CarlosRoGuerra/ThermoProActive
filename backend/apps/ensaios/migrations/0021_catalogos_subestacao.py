"""
Catálogos dos ensaios elétricos de subestação — TC, TP, DJ, CS e RP (docs/25).

Não há ficha do cliente para estes equipamentos: o conjunto de ensaios é o de
comissionamento e manutenção usual (referências em cada `nota_tecnica`). Nenhum limite
numérico é cadastrado aqui: o critério é informativo, salvo o erro de relação de TC e TP,
que sai da classe de exatidão da placa (IEC 61869-2 e -3, em `calculos_subestacao.py`).
Parâmetros "calculado" são os que o sistema deriva de outros valores. Tudo continua
editável no admin. A migração é idempotente (update_or_create por módulo e sigla).
"""
from django.db import migrations

INFO, QUAL = "INFORMATIVO", "QUALITATIVO"
ROTULOS = ("Observações", "Instrumentação Utilizada", "Data da Próxima Análise")

# modulo, sigla, nome, título da ficha, forma, ordem, nota técnica
ENSAIOS = [
    ("ENSAIO_ELETRICO_TC", "RELA", "Relação de transformação e polaridade", "RELAÇÃO DE TRANSFORMAÇÃO E POLARIDADE — TC",
     "MEDICAO", 1,
     "Erro de relação admitido pela classe de exatidão da placa (IEC 61869-2): medição 0,1 a 5 = ± a classe; "
     "proteção 5P = ±1 %, 10P = ±3 %. Classe fora da tabela: sem critério definido.\n"
     "Ensaio de relação por injeção de corrente no primário e leitura no secundário; polaridade por método "
     "de corrente contínua ou de ensaio de polaridade (ANSI/NETA ATS, ensaios de TC)."),
    ("ENSAIO_ELETRICO_TC", "EXC", "Saturação (curva de excitação)", "CURVA DE EXCITAÇÃO — TC", "CURVA", 2,
     "Curva tensão × corrente de excitação por núcleo (IEEE C57.13). Tensão de joelho pelo critério do IEEE "
     "C57.13 (10 % a mais de tensão exige 50 % a mais de corrente). Sem critério de aceitação definido."),
    ("ENSAIO_ELETRICO_TC", "ISO", "Resistência de isolação", "RESISTÊNCIA DE ISOLAÇÃO — TC", "MEDICAO", 3,
     "Leitura informativa em megôhmetro (tensão contínua). Sem limite universal: critério do fabricante ou do "
     "cliente."),
    ("ENSAIO_ELETRICO_TC", "OHM", "Resistência ôhmica do enrolamento", "RESISTÊNCIA ÔHMICA — TC", "MEDICAO", 4,
     "Resistência em corrente contínua do enrolamento secundário (leitura informativa, para comparação entre "
     "campanhas). Sem limite universal."),
    ("ENSAIO_ELETRICO_TP", "RELA", "Relação de transformação e polaridade", "RELAÇÃO DE TRANSFORMAÇÃO E POLARIDADE — TP",
     "MEDICAO", 1,
     "Erro de relação admitido pela classe de exatidão da placa (IEC 61869-3): medição 0,1 a 3 = ± a classe; "
     "proteção 3P = ±3 %, 6P = ±6 %. Classe fora da tabela: sem critério definido."),
    ("ENSAIO_ELETRICO_TP", "ISO", "Resistência de isolação", "RESISTÊNCIA DE ISOLAÇÃO — TP", "MEDICAO", 2,
     "Leitura informativa em megôhmetro. Sem limite universal: critério do fabricante ou do cliente."),
    ("ENSAIO_ELETRICO_TP", "OHM", "Resistência ôhmica do enrolamento", "RESISTÊNCIA ÔHMICA — TP", "MEDICAO", 3,
     "Resistência em corrente contínua do enrolamento (leitura informativa). Sem limite universal."),
    ("ENSAIO_ELETRICO_DJ", "RCON", "Resistência de contatos", "RESISTÊNCIA DE CONTATOS — DISJUNTOR", "MEDICAO", 1,
     "Resistência entre terminais de cada polo, em microohm, com corrente contínua (ANSI/NETA ATS). "
     "Critério do fabricante: sem limite universal."),
    ("ENSAIO_ELETRICO_DJ", "ISO", "Resistência de isolação", "RESISTÊNCIA DE ISOLAÇÃO — DISJUNTOR", "MEDICAO", 2,
     "Isolação entre polos, de cada polo para a massa e com o disjuntor fechado/aberto (ANSI/NETA ATS). "
     "Leitura informativa."),
    ("ENSAIO_ELETRICO_DJ", "TEMP", "Tempos de abertura e fechamento", "TEMPOS DE OPERAÇÃO — DISJUNTOR", "MEDICAO", 3,
     "Tempos de operação por polo (ms), com a simultaneidade = maior menos menor tempo entre os polos. "
     "Método de ensaio: IEC 62271-100 e ANSI C37.09. Critério do fabricante: sem limite universal."),
    ("ENSAIO_ELETRICO_CS", "RCON", "Resistência de contatos", "RESISTÊNCIA DE CONTATOS — CHAVE SECCIONADORA",
     "MEDICAO", 1,
     "Resistência de contato de cada fase, em microohm (ANSI/NETA ATS). Critério do fabricante: sem limite "
     "universal."),
    ("ENSAIO_ELETRICO_CS", "ISO", "Resistência de isolação", "RESISTÊNCIA DE ISOLAÇÃO — CHAVE SECCIONADORA",
     "MEDICAO", 2,
     "Isolação de cada fase para a massa e entre fases (ANSI/NETA ATS). Leitura informativa."),
    ("ENSAIO_ELETRICO_RP", "PICK", "Corrente de pickup das funções", "PICKUP DAS FUNÇÕES DE PROTEÇÃO — RELÉ",
     "MEDICAO", 1,
     "Corrente de atuação de cada função (ANSI 50, 51, 50N, 51N…) comparada com o valor esperado. A tolerância "
     "é informada em cada linha, conforme o ajuste e a norma de método (IEC 60255-151). Erro = (medido − "
     "esperado) ÷ esperado."),
    ("ENSAIO_ELETRICO_RP", "TEMP", "Tempo de atuação das funções", "TEMPO DE ATUAÇÃO — RELÉ", "MEDICAO", 2,
     "Tempo de atuação de cada função, comparado com o tempo esperado pela curva ajustada. A tolerância é "
     "informada em cada linha (IEC 60255-151). Erro = (medido − esperado) ÷ esperado."),
]

# modulo, sigla, codigo, nome, símbolo, unidade, norma, tipo, referência texto, casas, calculado, no gráfico
PARAMETROS = [
    ("ENSAIO_ELETRICO_TC", "RELA", "RELACAO_MEDIDA", "Relação medida", "", "", "IEC 61869-2", INFO, "", 4, False, False),
    ("ENSAIO_ELETRICO_TC", "RELA", "ERRO_RELACAO", "Erro de relação", "", "%", "IEC 61869-2", INFO, "", 2, True, True),
    ("ENSAIO_ELETRICO_TC", "RELA", "POLARIDADE", "Polaridade", "", "", "ANSI/NETA ATS", QUAL, "", 0, False, False),
    ("ENSAIO_ELETRICO_TC", "EXC", "CORRENTE_EXCITACAO", "Corrente de excitação", "", "mA", "IEEE C57.13", INFO, "", 2, False, False),
    ("ENSAIO_ELETRICO_TC", "ISO", "TENSAO_ENSAIO", "Tensão de ensaio", "", "V", "Informativo", INFO, "", 0, False, False),
    ("ENSAIO_ELETRICO_TC", "ISO", "RESISTENCIA", "Resistência de isolação", "", "MΩ", "Informativo", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_TC", "OHM", "RESISTENCIA", "Resistência ôhmica", "", "Ω", "Informativo", INFO, "", 4, False, True),
    ("ENSAIO_ELETRICO_TP", "RELA", "RELACAO_MEDIDA", "Relação medida", "", "", "IEC 61869-3", INFO, "", 4, False, False),
    ("ENSAIO_ELETRICO_TP", "RELA", "ERRO_RELACAO", "Erro de relação", "", "%", "IEC 61869-3", INFO, "", 2, True, True),
    ("ENSAIO_ELETRICO_TP", "RELA", "POLARIDADE", "Polaridade", "", "", "ANSI/NETA ATS", QUAL, "", 0, False, False),
    ("ENSAIO_ELETRICO_TP", "ISO", "TENSAO_ENSAIO", "Tensão de ensaio", "", "V", "Informativo", INFO, "", 0, False, False),
    ("ENSAIO_ELETRICO_TP", "ISO", "RESISTENCIA", "Resistência de isolação", "", "MΩ", "Informativo", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_TP", "OHM", "RESISTENCIA", "Resistência ôhmica", "", "Ω", "Informativo", INFO, "", 4, False, True),
    ("ENSAIO_ELETRICO_DJ", "RCON", "RESISTENCIA", "Resistência de contato", "", "µΩ", "Fabricante", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_DJ", "ISO", "TENSAO_ENSAIO", "Tensão de ensaio", "", "V", "Informativo", INFO, "", 0, False, False),
    ("ENSAIO_ELETRICO_DJ", "ISO", "RESISTENCIA", "Resistência de isolação", "", "MΩ", "Informativo", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_DJ", "TEMP", "TEMPO_ABERTURA", "Tempo de abertura", "", "ms", "Fabricante", INFO, "", 1, False, True),
    ("ENSAIO_ELETRICO_DJ", "TEMP", "TEMPO_FECHAMENTO", "Tempo de fechamento", "", "ms", "Fabricante", INFO, "", 1, False, True),
    ("ENSAIO_ELETRICO_CS", "RCON", "RESISTENCIA", "Resistência de contato", "", "µΩ", "Fabricante", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_CS", "ISO", "TENSAO_ENSAIO", "Tensão de ensaio", "", "V", "Informativo", INFO, "", 0, False, False),
    ("ENSAIO_ELETRICO_CS", "ISO", "RESISTENCIA", "Resistência de isolação", "", "MΩ", "Informativo", INFO, "", 0, False, True),
    ("ENSAIO_ELETRICO_RP", "PICK", "AJUSTE", "Ajuste de pickup", "", "A", "Ajuste do relé", INFO, "", 2, False, False),
    ("ENSAIO_ELETRICO_RP", "PICK", "ESPERADO", "Valor esperado", "", "A", "Ajuste do relé", INFO, "", 2, False, False),
    ("ENSAIO_ELETRICO_RP", "PICK", "MEDIDO", "Valor medido", "", "A", "Medição", INFO, "", 2, False, True),
    ("ENSAIO_ELETRICO_RP", "PICK", "TOLERANCIA", "Tolerância informada", "", "%", "Informada no lançamento", INFO, "", 1, False, False),
    ("ENSAIO_ELETRICO_RP", "PICK", "ERRO", "Erro", "", "%", "IEC 60255-151", INFO, "", 2, True, True),
    ("ENSAIO_ELETRICO_RP", "TEMP", "ESPERADO", "Tempo esperado", "", "s", "Curva ajustada", INFO, "", 3, False, False),
    ("ENSAIO_ELETRICO_RP", "TEMP", "MEDIDO", "Tempo medido", "", "s", "Medição", INFO, "", 3, False, True),
    ("ENSAIO_ELETRICO_RP", "TEMP", "TOLERANCIA", "Tolerância informada", "", "%", "Informada no lançamento", INFO, "", 1, False, False),
    ("ENSAIO_ELETRICO_RP", "TEMP", "ERRO", "Erro", "", "%", "IEC 60255-151", INFO, "", 2, True, True),
]


def carregar(apps, schema_editor):
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    ensaios = {}
    for modulo, sigla, nome, titulo, forma, ordem, nota in ENSAIOS:
        ensaio, _ = Ensaio.objects.update_or_create(
            modulo=modulo, sigla=sigla,
            defaults={
                "nome": nome, "titulo_ficha": titulo, "forma": forma, "ordem": ordem,
                "rotulo_conclusao": ROTULOS[0], "rotulo_informacoes": ROTULOS[1],
                "rotulo_proxima": ROTULOS[2], "nota_tecnica": nota, "ativo": True,
            },
        )
        ensaios[(modulo, sigla)] = ensaio
    for ordem, (modulo, sigla, codigo, nome, simbolo, unidade, norma, tipo, ref, casas, calc, grafico) in enumerate(
        PARAMETROS, start=1
    ):
        Parametro.objects.update_or_create(
            ensaio=ensaios[(modulo, sigla)], codigo=codigo,
            defaults={
                "nome": nome, "simbolo": simbolo, "unidade": unidade, "norma": norma, "tipo_limite": tipo,
                "referencia_texto": ref, "casas_decimais": casas, "calculado": calc, "no_grafico": grafico,
                "ordem": ordem, "ativo": True,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("ensaios", "0020_subestacao_schema"),
    ]

    operations = [
        migrations.RunPython(carregar, migrations.RunPython.noop),
    ]
