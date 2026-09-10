"""
Cenário de teste do módulo de Serviços de Campo (balanceamento + economia).

Reproduz os DOIS casos das planilhas do Fabrício, com os números originais, para
conferir na tela contra o Excel:

  · `Bal-1P` — Ventilador Espargidor, 1 plano, mancal 2H
                12,31 → 1,70 mm/s  = 86,2% de redução
  · `Bal-2P` — Exaustor, 2 planos, mancais 3H e 4H
                20,00 → 0,90 mm/s  = 95,5%   |   12,31 → 1,70 mm/s = 86,2%
  · Economia  — 380 V, 71,0 → 66,2 A, FP 0,93, 20 h, R$ 0,35/kWh, serviço R$ 1.606
                = 2,938 kW · R$ 7.506/ano · payback de 2,6 meses

Cria também um terceiro serviço com um ponto EM ANDAMENTO (sem trim run), para ver
o estado intermediário — o técnico salvou o reference e o trial e ainda não aplicou
a massa final.

Uso:  python manage.py seed_balanceamento
Idempotente: apaga e recria só os dados deste CNPJ.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import (
    Area,
    Cliente,
    Empresa,
    Equipamento,
    Instrumento,
    PeriodicidadeCalibracao,
    Setor,
)
from apps.servicos.models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
    TipoServico,
)

User = get_user_model()

CNPJ_DEMO = "45.678.901/0001-23"
EMAIL_ANALISTA = "analista@thermoproactive.com.br"
SENHA_ANALISTA = "thermo123"


class Command(BaseCommand):
    help = "Cria serviços de balanceamento com os números das planilhas do Fabrício."

    @transaction.atomic
    def handle(self, *args, **options):
        hoje = date.today()

        # --- Limpa execução anterior -------------------------------------
        antigo = Cliente.objects.filter(cnpj=CNPJ_DEMO).first()
        if antigo:
            ServicoCampo.objects.filter(cliente=antigo).delete()
            Equipamento.objects.filter(setor__area__cliente=antigo).delete()
            Area.objects.filter(cliente=antigo).delete()
            antigo.delete()
            self.stdout.write("Cenário anterior removido.")

        Empresa.objects.get_or_create(
            cnpj="39.923.567/0001-75",
            defaults={"nome": "ThermoProActive Serviços Ltda", "contato_gestor": "Fabrício Papa"},
        )

        cliente = Cliente.objects.create(
            nome="Metalúrgica Bandeirantes S.A.",
            nome_fantasia="Bandeirantes",
            cnpj=CNPJ_DEMO,
            unidade_negocio="Planta Sorocaba",
            cidade="Sorocaba",
            uf="SP",
            contato_gestor="Sra. Marina Toledo",
            departamento="Engenharia de Manutenção",
        )
        area = Area.objects.create(cliente=cliente, codigo="002", nome="Utilidades")
        setor = Setor.objects.create(area=area, codigo="6301", nome="Casa de Ventiladores")

        instrumento, _ = Instrumento.objects.get_or_create(
            numero_serie="BAL-2201",
            defaults={
                "tipo": "Balanceador de campo",
                "marca": "PRÜFTECHNIK",
                "modelo": "VIBXPERT II Balancer",
                "entidade_calibracao": "PRÜFTECHNIK",
            },
        )
        instrumento.data_ultima_calibracao = date(hoje.year - 1, 3, 20)
        instrumento.periodicidade_calibracao = PeriodicidadeCalibracao.BIENAL
        instrumento.save()

        analista = User.objects.filter(email=EMAIL_ANALISTA).first()
        if not analista:
            analista = User.objects.create_user(
                email=EMAIL_ANALISTA,
                nome="Fabrício Papa",
                password=SENHA_ANALISTA,
                perfil="TECNICO",
                cargo="Analista de Vibração N-III",
            )
            analista.is_staff = True
            analista.save()

        # =================================================================
        # 1) Aba Bal-1P — Ventilador Espargidor, 1 plano
        # =================================================================
        ventilador = Equipamento.objects.create(
            setor=setor, tag="VEN-101", nome="Ventilador Espargidor",
            tipo="Ventilador centrífugo", fabricante="OTAM",
            potencia_kw=Decimal("45"), rotacao_nominal_rpm=1784, classe_iso="II",
        )
        servico_1p = ServicoCampo.objects.create(
            cliente=cliente, equipamento=ventilador, tipo=TipoServico.BALANCEAMENTO,
            analista=analista, instrumento=instrumento,
            data_execucao=hoje - timedelta(days=12),
            rotacao_hz=Decimal("29.74"), custo_servico=Decimal("1606"),
            observacoes="Balanceamento em 1 plano, rotor do ventilador espargidor.",
        )
        plano_1 = BalanceamentoPlano.objects.create(
            servico=servico_1p, numero=1, descricao="Rotor — lado acoplamento",
            massa_teste_g=Decimal("30"), angulo_teste=Decimal("0"),
            massa_final_g=Decimal("100"), angulo_final=Decimal("136"),
        )
        ponto_1p = BalanceamentoPonto.objects.create(
            servico=servico_1p, plano=plano_1, numero_mancal=2, direcao="H",
            identificacao="Rotor — lado acoplamento",
            reference_mms=Decimal("12.31"), reference_fase=Decimal("110"),
            trial_mms=Decimal("23.95"), trial_fase=Decimal("133"),
            trim_mms=Decimal("1.70"), trim_fase=Decimal("136"),
        )
        # Único ponto medido: é naturalmente o ponto de foco (maior/única amplitude).
        servico_1p.ponto_foco = ponto_1p
        servico_1p.save(update_fields=["ponto_foco"])
        EconomiaEnergetica.objects.create(
            servico=servico_1p,
            tensao_v=Decimal("380"),
            corrente_antes_a=Decimal("71.0"),
            corrente_apos_a=Decimal("66.2"),
            fator_potencia=Decimal("0.93"),
            horas_dia=Decimal("20"),
            dias_ano=365,
            custo_kwh=Decimal("0.35"),
        )

        # =================================================================
        # 2) Aba Bal-2P — Exaustor, 2 planos
        # =================================================================
        exaustor = Equipamento.objects.create(
            setor=setor, tag="EXA-205", nome="Exaustor de Cabine de Pintura",
            tipo="Exaustor centrífugo", fabricante="Berlim",
            potencia_kw=Decimal("75"), rotacao_nominal_rpm=1784, classe_iso="III",
        )
        servico_2p = ServicoCampo.objects.create(
            cliente=cliente, equipamento=exaustor, tipo=TipoServico.BALANCEAMENTO,
            analista=analista, instrumento=instrumento,
            data_execucao=hoje - timedelta(days=5),
            rotacao_hz=Decimal("29.74"), custo_servico=Decimal("2480"),
            observacoes="Balanceamento em 2 planos, rotor de dupla sucção.",
        )
        p1 = BalanceamentoPlano.objects.create(
            servico=servico_2p, numero=1, descricao="Plano 1 — lado motor",
            massa_teste_g=Decimal("30"), angulo_teste=Decimal("0"),
            massa_final_g=Decimal("100"), angulo_final=Decimal("240"),
        )
        p2 = BalanceamentoPlano.objects.create(
            servico=servico_2p, numero=2, descricao="Plano 2 — lado livre",
            massa_teste_g=Decimal("30"), angulo_teste=Decimal("0"),
            massa_final_g=Decimal("110"), angulo_final=Decimal("75"),
        )
        ponto_2p_foco = BalanceamentoPonto.objects.create(
            servico=servico_2p, plano=p1, numero_mancal=3, direcao="H",
            identificacao="Mancal lado motor",
            reference_mms=Decimal("20.00"), reference_fase=Decimal("210"),
            trial_mms=Decimal("50.00"), trial_fase=Decimal("235"),
            trim_mms=Decimal("0.90"), trim_fase=Decimal("240"),
        )
        BalanceamentoPonto.objects.create(
            servico=servico_2p, plano=p2, numero_mancal=4, direcao="H",
            identificacao="Mancal lado livre",
            reference_mms=Decimal("12.31"), reference_fase=Decimal("60"),
            trial_mms=Decimal("23.95"), trial_fase=Decimal("80"),
            trim_mms=Decimal("1.70"), trim_fase=Decimal("75"),
        )
        # Ponto de foco = maior amplitude de reference (mancal 3H, 20,00 mm/s). O
        # mancal 4H manteve o trial run já lançado no cenário original da planilha —
        # dado histórico preservado, só deixou de ser "o foco" daqui pra frente.
        servico_2p.ponto_foco = ponto_2p_foco
        servico_2p.save(update_fields=["ponto_foco"])
        EconomiaEnergetica.objects.create(
            servico=servico_2p,
            tensao_v=Decimal("440"),
            corrente_antes_a=Decimal("118.4"),
            corrente_apos_a=Decimal("109.7"),
            fator_potencia=Decimal("0.91"),
            horas_dia=Decimal("16"),
            dias_ano=330,
            custo_kwh=Decimal("0.38"),
        )

        # =================================================================
        # 3) Serviço EM ANDAMENTO — reference e trial medidos, sem trim
        # =================================================================
        bomba = Equipamento.objects.create(
            setor=setor, tag="BBA-310", nome="Bomba de Recirculação",
            tipo="Bomba centrífuga", fabricante="KSB",
            potencia_kw=Decimal("30"), rotacao_nominal_rpm=3560, classe_iso="II",
        )
        servico_wip = ServicoCampo.objects.create(
            cliente=cliente, equipamento=bomba, tipo=TipoServico.BALANCEAMENTO,
            analista=analista, instrumento=instrumento, data_execucao=hoje,
            rotacao_hz=Decimal("59.33"), custo_servico=Decimal("1390"),
            observacoes="Em execução — massa final ainda não aplicada.",
        )
        plano_wip = BalanceamentoPlano.objects.create(
            servico=servico_wip, numero=1, descricao="Rotor",
            massa_teste_g=Decimal("15"), angulo_teste=Decimal("0"),
        )
        ponto_wip = BalanceamentoPonto.objects.create(
            servico=servico_wip, plano=plano_wip, numero_mancal=1, direcao="H",
            identificacao="Rotor",
            reference_mms=Decimal("8.64"), reference_fase=Decimal("47"),
            trial_mms=Decimal("14.20"), trial_fase=Decimal("72"),
            # sem trim: o ponto fica "Em andamento" na tela
        )
        servico_wip.ponto_foco = ponto_wip
        servico_wip.save(update_fields=["ponto_foco"])

        # --- Resumo ---------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("\nCenário criado.\n"))
        self.stdout.write(f"  Cliente:  {cliente.nome} ({cliente.cnpj})")
        self.stdout.write(f"  Login:    {EMAIL_ANALISTA} / {SENHA_ANALISTA}\n")
        for s in (servico_1p, servico_2p, servico_wip):
            self.stdout.write(f"  /servicos/{s.id}  {s.equipamento.tag} — {s.equipamento.nome}")
            for p in s.pontos.all():
                if p.completo:
                    self.stdout.write(
                        f"      {p.codigo_ponto}: {p.reference_mms} → {p.trim_mms} mm/s"
                        f"  = {p.reducao_pct:.1f}% · zona {p.zona_iso}"
                    )
                else:
                    self.stdout.write(f"      {p.codigo_ponto}: em andamento (sem trim run)")
            eco = getattr(s, "economia", None)
            if eco:
                self.stdout.write(
                    f"      economia: {eco.reducao_kw:.3f} kW · "
                    f"R$ {eco.economia_rs_ano:,.2f}/ano · payback {eco.payback_meses:.1f} meses"
                )
        self.stdout.write("")
