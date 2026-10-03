"""
Catálogo da análise de fluidos lubrificantes e hidráulicos (FQ, EF e CP).

- Parâmetros com unidade e a norma de referência do método quando o pedido do
  cliente a cita (ASTM D445, D664, D6304, D5185; ISO 4406). Todos INFORMATIVOS:
  não existe limite universal — alerta e crítico entram em "Referências de
  parâmetros", por equipamento, fluido, cliente ou aplicação, com origem e vigência.
- Solicitação padrão acordada com o cliente: lubrificante → FQ + EF;
  hidráulico → FQ + EF + CP.
- Pontos de coleta do óleo isolante existentes passam a ser só dessa tecnologia;
  os de fluidos entram como sugestão (editáveis).
- Definição da Técnica da tecnologia AFLH, só se estiver vazia (proposta, editável
  em Cadastros → Tecnologias de análise).
"""
from django.db import migrations

FLUIDO, OLEO = "FLUIDO_LUBRIFICANTE", "OLEO_ISOLANTE"
INFO, QUAL = "INFORMATIVO", "QUALITATIVO"
DESGASTE, CONTAMINANTES, ADITIVOS = "Metais de desgaste", "Contaminantes", "Aditivos"

ENSAIOS = [
    # sigla, nome, título da ficha, ordem, nota técnica
    ("FQ", "Físico-Química", "RESULTADOS DO ENSAIO FQ - FÍSICO-QUÍMICA", 1, ""),
    ("EF", "Espectrofotometria", "RESULTADOS DO ENSAIO EF - ESPECTROFOTOMETRIA", 2,
     "Elementos em ppm (mg/kg). A espectrometria quantifica o material dissolvido e as partículas muito finas; "
     "partículas maiores aparecem na Contagem de Partículas."),
    ("CP", "Contagem de Partículas", "RESULTADOS DO ENSAIO CP - CONTAGEM DE PARTÍCULAS", 3,
     "Contagens por mL. Código de limpeza conforme ISO 4406 (> 4, > 6 e > 14 µm(c)); a meta de limpeza vem das "
     "referências cadastradas para o equipamento, o fabricante ou o contrato."),
]

PARAMETROS = {
    # codigo, nome, símbolo, grupo, unidade, norma, tipo, casas, calculado, no gráfico
    "FQ": [
        ("VISC40", "Viscosidade cinemática a 40 °C", "", "", "cSt", "ASTM D445", INFO, 2, False, True),
        ("VISC100", "Viscosidade cinemática a 100 °C", "", "", "cSt", "ASTM D445", INFO, 2, False, True),
        ("IV", "Índice de viscosidade", "", "", "", "", INFO, 0, False, False),
        ("AGUA", "Teor de água", "", "", "ppm", "ASTM D6304", INFO, 0, False, True),
        ("TAN", "Número de acidez (TAN)", "", "", "mgKOH/g", "ASTM D664", INFO, 2, False, True),
        ("DENSIDADE", "Densidade", "", "", "g/cm³", "", INFO, 4, False, False),
        ("OXIDACAO", "Oxidação", "", "", "Abs/cm", "", INFO, 1, False, True),
        ("INSOLUVEIS", "Insolúveis em pentano", "", "", "% m/m", "", INFO, 2, False, False),
        ("COR", "Cor", "", "", "", "ASTM D1500", INFO, 1, False, False),
        ("APARENCIA", "Aparência", "", "", "", "Visual", QUAL, 0, False, False),
    ],
    "EF": [
        ("FE", "Ferro", "Fe", DESGASTE), ("CU", "Cobre", "Cu", DESGASTE), ("CR", "Cromo", "Cr", DESGASTE),
        ("AL", "Alumínio", "Al", DESGASTE), ("PB", "Chumbo", "Pb", DESGASTE), ("SN", "Estanho", "Sn", DESGASTE),
        ("NI", "Níquel", "Ni", DESGASTE), ("AG", "Prata", "Ag", DESGASTE), ("MN", "Manganês", "Mn", DESGASTE),
        ("TI", "Titânio", "Ti", DESGASTE), ("V", "Vanádio", "V", DESGASTE),
        ("SI", "Silício", "Si", CONTAMINANTES), ("NA", "Sódio", "Na", CONTAMINANTES),
        ("K", "Potássio", "K", CONTAMINANTES),
        ("CA", "Cálcio", "Ca", ADITIVOS), ("MG", "Magnésio", "Mg", ADITIVOS), ("P", "Fósforo", "P", ADITIVOS),
        ("ZN", "Zinco", "Zn", ADITIVOS), ("B", "Boro", "B", ADITIVOS), ("MO", "Molibdênio", "Mo", ADITIVOS),
        ("BA", "Bário", "Ba", ADITIVOS),
    ],
    "CP": [
        ("P4", "Partículas > 4 µm(c)", "", "Contagem", "part./mL", "ISO 4406", INFO, 0, False, True),
        ("P6", "Partículas > 6 µm(c)", "", "Contagem", "part./mL", "ISO 4406", INFO, 0, False, True),
        ("P14", "Partículas > 14 µm(c)", "", "Contagem", "part./mL", "ISO 4406", INFO, 0, False, True),
        ("P21", "Partículas > 21 µm(c)", "", "Contagem", "part./mL", "", INFO, 0, False, False),
        ("P38", "Partículas > 38 µm(c)", "", "Contagem", "part./mL", "", INFO, 0, False, False),
        ("P70", "Partículas > 70 µm(c)", "", "Contagem", "part./mL", "", INFO, 0, False, False),
        ("NAS1638", "Classe NAS 1638 (informada pelo laboratório)", "", "Classe", "", "NAS 1638", INFO, 0, False,
         False),
        ("ISO4406", "Código ISO 4406", "", "Código", "", "ISO 4406", INFO, 0, True, False),
    ],
}

SOLICITACAO_PADRAO = {"LUBRIFICANTE": ("FQ", "EF"), "HIDRAULICO": ("FQ", "EF", "CP")}

PONTOS_FLUIDO = [
    "Válvula de amostragem do reservatório",
    "Linha de retorno, antes do filtro",
    "Linha de pressão, após a bomba",
    "Bujão de dreno",
]

DEFINICAO_AFLH = (
    "A análise de fluidos lubrificantes e hidráulicos avalia, por amostragem periódica, a condição do fluido e do "
    "equipamento que ele lubrifica: o estado do próprio fluido (Físico-Química), o desgaste e a contaminação "
    "(Espectrofotometria) e o grau de limpeza (Contagem de Partículas, nos sistemas hidráulicos)."
)
FLUXO_AFLH = "\n".join([
    "1ª etapa (contratada): coleta da amostra em campo, com o registro do ponto de coleta, da condição operacional "
    "e do histórico do fluido;",
    "2ª etapa (laboratório): ensaios solicitados — FQ e EF nos lubrificantes; FQ, EF e CP nos hidráulicos;",
    "3ª etapa (contratada): análise dos resultados frente às referências cadastradas e à tendência das coletas "
    "anteriores, com conclusão e recomendação por ensaio;",
    "4ª etapa (contratante): execução das recomendações e retorno das informações para o próximo ciclo.",
])


def carregar(apps, schema_editor):
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Solicitacao = apps.get_model("ensaios", "SolicitacaoPadraoEnsaio")
    PontoColeta = apps.get_model("ensaios", "PontoColeta")
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")

    ensaios = {}
    for sigla, nome, titulo, ordem, nota in ENSAIOS:
        ensaios[sigla], _ = Ensaio.objects.update_or_create(modulo=FLUIDO, sigla=sigla, defaults=dict(
            nome=nome, titulo_ficha=titulo, ordem=ordem, nota_tecnica=nota, rotulo_conclusao="Conclusão",
            rotulo_informacoes="Informações Adicionais", rotulo_proxima="Data da Próxima Coleta",
        ))
    for sigla, linhas in PARAMETROS.items():
        for i, linha in enumerate(linhas, start=1):
            if sigla == "EF":
                codigo, nome, simbolo, grupo = linha
                unidade, norma, tipo, casas, calc, graf = "ppm", "ASTM D5185", INFO, 1, False, True
            else:
                codigo, nome, simbolo, grupo, unidade, norma, tipo, casas, calc, graf = linha
            Parametro.objects.update_or_create(ensaio=ensaios[sigla], codigo=codigo, defaults=dict(
                nome=nome, simbolo=simbolo, grupo=grupo, unidade=unidade, norma=norma, tipo_limite=tipo,
                casas_decimais=casas, calculado=calc, no_grafico=graf, ordem=i,
            ))
    for aplicacao, siglas in SOLICITACAO_PADRAO.items():
        for sigla in siglas:
            Solicitacao.objects.get_or_create(aplicacao=aplicacao, ensaio=ensaios[sigla])

    PontoColeta.objects.filter(modulo="").update(modulo=OLEO)
    for nome in PONTOS_FLUIDO:
        PontoColeta.objects.get_or_create(nome=nome, modulo=FLUIDO)

    for tec in Tecnologia.objects.filter(modulo_tecnico=FLUIDO):
        mudou = {}
        if not tec.definicao_tecnica.strip():
            mudou["definicao_tecnica"] = DEFINICAO_AFLH
        if not tec.definicao_fluxo_trabalho.strip():
            mudou["definicao_fluxo_trabalho"] = FLUXO_AFLH
        if mudou:
            Tecnologia.objects.filter(pk=tec.pk).update(**mudou)


def desfazer(apps, schema_editor):
    apps.get_model("ensaios", "PontoColeta").objects.filter(modulo=FLUIDO, nome__in=PONTOS_FLUIDO).delete()
    apps.get_model("ensaios", "SolicitacaoPadraoEnsaio").objects.filter(ensaio__modulo=FLUIDO).delete()
    # Ensaios só saem se ninguém lançou resultado — o histórico de laudos nunca é
    # apagado. Ordem explícita (vínculos → referências → parâmetros → ensaios) com
    # exclusão direta: o coletor de cascata do Django falha com modelos históricos
    # de apps diferentes ("Must be ParametroEnsaio instance").
    alias = schema_editor.connection.alias
    Ensaio = apps.get_model("ensaios", "Ensaio")
    sem_resultado = list(Ensaio.objects.filter(modulo=FLUIDO, resultados__isnull=True).values_list("id", flat=True))
    for nome in ("ColetaOleo", "RegistroEnsaioEletrico", "ColetaFluido"):
        vinculo = apps.get_model("ensaios", nome)._meta.get_field("ensaios").remote_field.through
        vinculo.objects.filter(ensaio_id__in=sem_resultado)._raw_delete(alias)
    apps.get_model("ensaios", "ReferenciaParametro").objects.filter(
        parametro__ensaio_id__in=sem_resultado)._raw_delete(alias)
    apps.get_model("ensaios", "ParametroEnsaio").objects.filter(ensaio_id__in=sem_resultado)._raw_delete(alias)
    Ensaio.objects.filter(id__in=sem_resultado)._raw_delete(alias)


class Migration(migrations.Migration):
    dependencies = [
        ("ensaios", "0003_fluidos_lubrificantes_hidraulicos"),
        ("cadastros", "0031_dados_modulo_das_tecnologias"),
    ]

    operations = [migrations.RunPython(carregar, desfazer)]
