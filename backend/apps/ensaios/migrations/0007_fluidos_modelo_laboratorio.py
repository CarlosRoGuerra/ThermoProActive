"""
Complementos da análise de fluidos a partir do relatório-modelo do laboratório
(2016-11-0882, AO Midori):

- TBN (número de base, mgKOH/g) na Físico-Química — está no glossário do modelo;
  entra logo depois do TAN, deslocando a ordem dos demais (reversível).
- Boro entre os metais CONTAMINANTES do EF (no modelo: silício, sódio, boro e
  potássio); a ordem dos elementos acompanha o grupo.
- Norma do método dos insolúveis em pentano (ASTM D4055), como no modelo.
- Normas citadas no modelo e ainda não cadastradas (item 5 da carta), ligadas às
  tecnologias do módulo. Não duplica: reaproveita a norma de mesmo código. O Master
  desliga, em Normas (NBRs), as que o seu laboratório não usa.
- Instrumentação padrão da análise de fluidos (item 4 da carta), só pelo TIPO do
  instrumento, como no modelo: marca, modelo, série e calibração são do laboratório
  e ficam para o Master preencher em Instrumentação. Só cria se a tecnologia ainda
  não tiver nenhum instrumento vinculado.

Nenhum limite é criado aqui: TBN e insolúveis entram como informativos.
"""
from django.db import migrations

FLUIDO = "FLUIDO_LUBRIFICANTE"
NORMAS = [
    ("ASTM D6595", "Espectrometria de Emissão Óptica", "ASTM"),
    ("ASTM E2412", "Espectrometria de Infravermelho – IR", "ASTM"),
    ("ASTM D2270", "Viscosidade de Dupla Temperatura (40 °C / 100 °C)", "ASTM"),
    ("ISO 11171", "Calibração para contador de partículas automático", "ISO"),
    ("ASTM D4951", "Determinação de elementos aditivos em óleos lubrificantes por ICP-AES", "ASTM"),
    ("ASTM D974", "Número de acidez e de base por titulação com indicador de cor", "ASTM"),
    ("ASTM D4377", "Teor de água por titulação Karl Fischer potenciométrica", "ASTM"),
    ("ASTM D4055", "Insolúveis em pentano por filtração em membrana", "ASTM"),
]
INSTRUMENTOS = [
    "Espectrômetro de Emissão Óptica",
    "Espectrômetro de Infravermelho – IR",
    "Viscosímetro de Dupla Temperatura (40°/100°)",
    "Contador de Partículas",
    "Microscópio",
    "Softwares de Análises",
]
POSICAO_TBN = 6  # logo depois do TAN (ordem 5)
EF_ANTES = ["FE", "CU", "CR", "AL", "PB", "SN", "NI", "AG", "MN", "TI", "V", "SI", "NA", "K", "CA", "MG", "P", "ZN",
            "B", "MO", "BA"]
EF_DEPOIS = ["FE", "CU", "CR", "AL", "PB", "SN", "NI", "AG", "MN", "TI", "V", "SI", "NA", "B", "K", "CA", "MG", "P",
             "ZN", "MO", "BA"]


def _ordenar_ef(Parametro, Ensaio, ordem, grupo_boro):
    ef = Ensaio.objects.filter(modulo=FLUIDO, sigla="EF").first()
    if ef is None:
        return
    for i, codigo in enumerate(ordem, start=1):
        Parametro.objects.filter(ensaio=ef, codigo=codigo).update(ordem=i)
    Parametro.objects.filter(ensaio=ef, codigo="B").update(grupo=grupo_boro)


def carregar(apps, schema_editor):
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Norma = apps.get_model("cadastros", "Norma")
    Tecnologia = apps.get_model("cadastros", "TecnologiaAnalise")
    Instrumento = apps.get_model("cadastros", "Instrumento")

    fq = Ensaio.objects.filter(modulo=FLUIDO, sigla="FQ").first()
    if fq is not None:
        if not Parametro.objects.filter(ensaio=fq, codigo="TBN").exists():
            for p in Parametro.objects.filter(ensaio=fq, ordem__gte=POSICAO_TBN).order_by("-ordem"):
                Parametro.objects.filter(pk=p.pk).update(ordem=p.ordem + 1)
            Parametro.objects.create(
                ensaio=fq, codigo="TBN", nome="Número de base (TBN)", unidade="mgKOH/g", norma="",
                tipo_limite="INFORMATIVO", casas_decimais=2, calculado=False, no_grafico=True, ordem=POSICAO_TBN,
            )
        Parametro.objects.filter(ensaio=fq, codigo="INSOLUVEIS", norma="").update(norma="ASTM D4055")

    _ordenar_ef(Parametro, Ensaio, EF_DEPOIS, "Contaminantes")

    tecnologias = list(Tecnologia.objects.filter(modulo_tecnico=FLUIDO))
    for codigo, nome, orgao in NORMAS:
        norma = Norma.objects.filter(codigo=codigo).first() or Norma.objects.create(codigo=codigo, nome=nome, orgao=orgao)
        norma.tecnologias.add(*tecnologias)

    for tec in tecnologias:
        if tec.instrumentos.exists():
            continue
        for tipo in INSTRUMENTOS:
            instrumento = Instrumento.objects.filter(tipo=tipo, marca="", modelo="", numero_serie="").first() \
                or Instrumento.objects.create(tipo=tipo)
            instrumento.tecnologias.add(tec)


def desfazer(apps, schema_editor):
    Ensaio = apps.get_model("ensaios", "Ensaio")
    Parametro = apps.get_model("ensaios", "ParametroEnsaio")
    Norma = apps.get_model("cadastros", "Norma")
    Instrumento = apps.get_model("cadastros", "Instrumento")

    fq = Ensaio.objects.filter(modulo=FLUIDO, sigla="FQ").first()
    if fq is not None:
        Parametro.objects.filter(ensaio=fq, codigo="INSOLUVEIS", norma="ASTM D4055").update(norma="")
        tbn = Parametro.objects.filter(ensaio=fq, codigo="TBN", valores__isnull=True).first()
        if tbn is not None:
            ordem = tbn.ordem
            alias = schema_editor.connection.alias
            Parametro.objects.filter(pk=tbn.pk)._raw_delete(alias)
            for p in Parametro.objects.filter(ensaio=fq, ordem__gt=ordem).order_by("ordem"):
                Parametro.objects.filter(pk=p.pk).update(ordem=p.ordem - 1)
    _ordenar_ef(Parametro, Ensaio, EF_ANTES, "Aditivos")
    for codigo, nome, _ in NORMAS:
        Norma.objects.filter(codigo=codigo, nome=nome).delete()
    # Só os instrumentos criados aqui (sem marca/modelo/série) e ainda sem uso em campo.
    Instrumento.objects.filter(
        tipo__in=INSTRUMENTOS, marca="", modelo="", numero_serie="", data_ultima_calibracao__isnull=True,
        carregamentos__isnull=True, resultados_ensaio__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("ensaios", "0006_volume_reservatorio_fluido"),
        ("cadastros", "0031_dados_modulo_das_tecnologias"),
    ]

    operations = [migrations.RunPython(carregar, desfazer)]
