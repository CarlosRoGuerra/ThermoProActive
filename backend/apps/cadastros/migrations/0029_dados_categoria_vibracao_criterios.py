"""
Dados do cadastro técnico por tipo de equipamento e do perfil normativo da vibração.

1. Categoria técnica dos tipos que ainda estão sem ela (só preenche o vazio):
   a) evidência: tipo cujos equipamentos já têm datasheet de UMA só categoria
      (todos com dados de transformador → TRANSFORMADOR; de motor → MOTOR_ELETRICO);
   b) associação explícita, por nome EXATO, dos tipos que o catálogo usa para essas
      máquinas (lista abaixo). É a mesma decisão que o Master tomaria em
      Dados de sistema → Tipos de equipamento, registrada uma vez aqui — o sistema
      continua sem deduzir nada pelo nome em tempo de execução.
2. `analise_vibracao` = verdadeiro só com evidência: categoria motor elétrico, ou
   equipamento do tipo já analisado numa rota de vibração, num serviço de
   balanceamento ou numa medição de vibração do fluxo antigo. Transformador nunca.
   Os demais tipos ficam desmarcados e o Master marca os que forem máquina rotativa.
3. Critérios de severidade — os mesmos números de `apps.coletas.rules.FAIXAS_ISO_VRMS`,
   agora com a origem de cada um: as quatro classes da ISO 10816-1:1995 (Anexo B)
   como NORMA e o limite B/C de 4,49 mm/s da Classe II como ACORDO COM O CLIENTE.
   O acordo prevalece sobre a norma, então a classificação não muda.

Nenhum registro é apagado. Reverter desfaz só o que esta migração criou/marcou.
"""
from decimal import Decimal

from django.db import migrations

TRANSFORMADOR, MOTOR = "TRANSFORMADOR", "MOTOR_ELETRICO"

# Nomes exatos (sem diferenciar maiúsculas e espaços nas pontas).
NOMES_CATEGORIA = {
    "transformador": TRANSFORMADOR,
    "transformadores": TRANSFORMADOR,
    "transformador a óleo": TRANSFORMADOR,
    "transformador a oleo": TRANSFORMADOR,
    "transformador seco": TRANSFORMADOR,
    "transformador trifásico": TRANSFORMADOR,
    "transformador trifasico": TRANSFORMADOR,
    "transformador de potência": TRANSFORMADOR,
    "transformador de potencia": TRANSFORMADOR,
    "motor elétrico": MOTOR,
    "motor eletrico": MOTOR,
    "motores elétricos": MOTOR,
    "motores eletricos": MOTOR,
}

D = Decimal
NORMA = "ISO 10816-1"
EDICAO = "1995"
FONTE_NORMA = "ISO 10816-1:1995, Anexo B (classes de máquina I a IV). Norma substituída pela ISO 20816-1:2016."
CRITERIOS = [
    # classe, descrição, A/B, B/C, C/D, origem, fonte
    ("I", "Máquinas pequenas, até 15 kW", D("0.71"), D("1.80"), D("4.50"), "NORMA", FONTE_NORMA),
    ("II", "Máquinas médias, de 15 a 75 kW", D("1.12"), D("2.80"), D("7.10"), "NORMA", FONTE_NORMA),
    ("III", "Máquinas grandes em base rígida", D("1.80"), D("4.50"), D("11.20"), "NORMA", FONTE_NORMA),
    ("IV", "Máquinas grandes em base flexível", D("2.80"), D("7.10"), D("18.00"), "NORMA", FONTE_NORMA),
    ("II", "Máquinas médias, de 15 a 75 kW", D("1.12"), D("4.49"), D("7.10"), "ACORDO_CLIENTE",
     "Limite B/C de 4,49 mm/s confirmado com o cliente em 16/09/2026 (a ISO 10816-1 publica 2,80 mm/s); "
     "A/B e C/D seguem a norma."),
]


def _evidencia_vibracao(apps):
    """IDs de tipos com equipamento já analisado por vibração (rota, balanceamento ou legado)."""
    ItemInspecao = apps.get_model("coletas", "ItemInspecao")
    MedicaoVibracao = apps.get_model("coletas", "MedicaoVibracao")
    ServicoCampo = apps.get_model("servicos", "ServicoCampo")
    tipos = set(
        ItemInspecao.objects.filter(carregamento__tecnologia__modulo_tecnico="VIBRACAO")
        .exclude(equipamento__tipo_equipamento__isnull=True)
        .values_list("equipamento__tipo_equipamento_id", flat=True)
    )
    tipos |= set(
        ServicoCampo.objects.filter(tipo="BALANCEAMENTO")
        .exclude(equipamento__tipo_equipamento__isnull=True)
        .values_list("equipamento__tipo_equipamento_id", flat=True)
    )
    tipos |= set(
        MedicaoVibracao.objects.exclude(equipamento__tipo_equipamento__isnull=True)
        .values_list("equipamento__tipo_equipamento_id", flat=True)
    )
    return tipos


def carregar(apps, schema_editor):
    TipoEquipamento = apps.get_model("cadastros", "TipoEquipamento")
    Equipamento = apps.get_model("cadastros", "Equipamento")
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")

    # 1. Categoria técnica (só onde está vazia).
    for tipo in TipoEquipamento.objects.filter(categoria_tecnica=""):
        equipamentos = Equipamento.objects.filter(tipo_equipamento=tipo)
        com_trafo = equipamentos.filter(dados_transformador__isnull=False).exists()
        com_motor = equipamentos.filter(dados_motor__isnull=False).exists()
        categoria = ""
        if com_trafo != com_motor:
            categoria = TRANSFORMADOR if com_trafo else MOTOR
        elif not com_trafo:
            categoria = NOMES_CATEGORIA.get(tipo.nome.strip().casefold(), "")
        if categoria:
            TipoEquipamento.objects.filter(pk=tipo.pk).update(categoria_tecnica=categoria)

    # 2. Avaliado por vibração (só com evidência; transformador nunca).
    evidencia = _evidencia_vibracao(apps)
    (TipoEquipamento.objects.filter(categoria_tecnica=MOTOR) | TipoEquipamento.objects.filter(id__in=evidencia)) \
        .exclude(categoria_tecnica=TRANSFORMADOR).update(analise_vibracao=True)

    # 3. Perfil normativo da vibração.
    if not Criterio.objects.exists():
        for classe, descricao, ab, bc, cd, origem, fonte in CRITERIOS:
            Criterio.objects.create(
                norma_codigo=NORMA, norma_edicao=EDICAO, classe=classe, descricao_grupo=descricao,
                limite_ab=ab, limite_bc=bc, limite_cd=cd, origem=origem, fonte=fonte,
            )


def desfazer(apps, schema_editor):
    Criterio = apps.get_model("cadastros", "CriterioSeveridadeVibracao")
    for classe, _descricao, ab, bc, cd, origem, fonte in CRITERIOS:
        Criterio.objects.filter(
            norma_codigo=NORMA, norma_edicao=EDICAO, classe=classe, cliente__isnull=True,
            limite_ab=ab, limite_bc=bc, limite_cd=cd, origem=origem, fonte=fonte,
        ).delete()
    # analise_vibracao some com o campo ao reverter a 0028; a categoria preenchida
    # fica (o Master pode tê-la confirmado depois — apagar seria perder decisão).


class Migration(migrations.Migration):
    dependencies = [
        ("cadastros", "0028_perfil_normativo_vibracao"),
        ("coletas", "0010_carregamento_tipo_corretiva"),
        ("servicos", "0008_alter_balanceamentoponto_reference_fase"),
    ]

    operations = [migrations.RunPython(carregar, desfazer)]
