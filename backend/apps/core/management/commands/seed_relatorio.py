"""
Cenário completo e fictício para visualizar o Relatório Técnico.

Cria um cliente industrial com hierarquia real (Área → Setor → Equipamento →
Sub-item), 6 meses de inspeções, medições com valores plausíveis e OSPs
classificadas — o suficiente para todos os gráficos da Seção B terem conteúdo.

Uso:  python manage.py seed_relatorio
Idempotente: recria o cenário do zero a cada execução (só os dados deste CNPJ).
"""
import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.cadastros.models import (
    Area,
    Cliente,
    Componente,
    Empresa,
    Equipamento,
    Instrumento,
    PeriodicidadeCalibracao,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
)
from apps.coletas.models import (
    Direcao,
    Inspecao,
    MedicaoVibracao,
    ParametroMedicao,
    TipoAnalise,
)
from apps.laudos.models import Laudo
from apps.osp.models import Acompanhamento, GrauRisco, OrdemServico

User = get_user_model()

CNPJ_DEMO = "12.345.678/0001-90"

#: Estrutura da planta: (código área, nome área, complemento, setores)
PLANTA = [
    ("001", "SP1930", "Matriz", [
        ("6201", "Vácuo", "Piso Inferior"),
        ("6202", "Aparas", "Piso Inferior"),
        ("6203", "Acabamento", "Piso Superior"),
    ]),
    ("004", "SP2001", "Filial", [
        ("6401", "Sala dos Compressores", ""),
    ]),
]

#: (tag, nome, classe ISO, potência, rotação, sub-itens)
MAQUINAS = [
    ("BVC-101", "Bomba de Vácuo Nº.01", "II", 45, 1780, ["Motor Elétrico", "Mancais da Bomba"]),
    ("BVC-102", "Bomba de Vácuo Nº.02", "II", 45, 1780, ["Motor Elétrico"]),
    ("EXA-201", "Champion — Puxador de Aparas", "III", 90, 1750, ["Motor Elétrico", "Mancais do Exaustor"]),
    ("EXA-202", "WD102 — Puxador de Aparas", "II", 55, 1760, ["Motor Elétrico"]),
    ("CPR-301", "Compressor Chicago CPC-50", "III", 110, 1780, ["Motor Elétrico", "Unidade Compressora"]),
    ("CPR-401", "Compressor Kaeser CSD-75", "IV", 132, 1785, ["Motor Elétrico", "Unidade Compressora"]),
]

ANOMALIAS_RECOMENDACOES = [
    ("Desalinhamento", "Realinhar o conjunto motor/bomba a laser."),
    ("Desbalanceamento", "Balancear o rotor em campo."),
    ("Freq. Pista Ext. Rol.", "Substituir rolamento(s) do mancal indicado."),
    ("Folga Mecânica", "Reapertar a fixação da base e verificar chumbadores."),
    ("Lubrificação", "Relubrificar conforme plano; verificar tipo de graxa."),
    ("Cavitação", "Avaliar NPSH disponível e condição da sucção."),
    ("Ressonância", "Avaliar rigidez da base; considerar reforço estrutural."),
]


class Command(BaseCommand):
    help = "Popula um cenário fictício completo para visualizar o Relatório Técnico."

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(42)  # cenário reproduzível
        hoje = date.today()

        # --- Limpa execução anterior -------------------------------------
        antigo = Cliente.objects.filter(cnpj=CNPJ_DEMO).first()
        if antigo:
            OrdemServico.objects.filter(cliente=antigo).delete()
            Laudo.objects.filter(inspecao__cliente=antigo).delete()
            MedicaoVibracao.objects.filter(inspecao__cliente=antigo).delete()
            Inspecao.objects.filter(cliente=antigo).delete()
            Equipamento.objects.filter(setor__area__cliente=antigo).delete()
            Area.objects.filter(cliente=antigo).delete()
            antigo.delete()
            self.stdout.write("Cenário anterior removido.")

        # --- Contratada (sai no cabeçalho do relatório) -------------------
        empresa, _ = Empresa.objects.get_or_create(
            cnpj="39.923.567/0001-75",
            defaults={"nome": "ThermoProActive Serviços Ltda"},
        )
        empresa.logradouro = "Rua Benedicto de Souza"
        empresa.numero = "87"
        empresa.bairro = "São Luiz"
        empresa.cep = "13.145-076"
        empresa.cidade, empresa.uf = "Paulínia", "SP"
        empresa.contato_gestor = "Fabrício Papa"
        empresa.save()

        # --- Contratante ---------------------------------------------------
        cliente = Cliente.objects.create(
            nome="Papelex Indústria de Papéis S.A.",
            nome_fantasia="Papelex",
            cnpj=CNPJ_DEMO,
            unidade_negocio="Planta São Paulo",
            logradouro="Rua Henry Ford",
            numero="1930",
            bairro="Parque da Mooca",
            cep="03.109-001",
            cidade="São Paulo",
            uf="SP",
            contato_gestor="Sr. Claudemir Gonçalves",
            departamento="Coordenação de Manutenção",
            email="manutencao@papelex.com.br",
            telefone="(11) 3456-7890",
        )

        # --- Instrumentação -------------------------------------------------
        instrumento, _ = Instrumento.objects.get_or_create(
            numero_serie="031101",
            defaults={
                "tipo": "Coletor/Analisador de Vibrações",
                "marca": "PRÜFTECHNIK",
                "modelo": "VIBXPERT II",
                "entidade_calibracao": "PRÜFTECHNIK",
                "software_analise": "OMNITREND",
            },
        )
        instrumento.data_ultima_calibracao = date(hoje.year - 1, 5, 12)
        instrumento.periodicidade_calibracao = PeriodicidadeCalibracao.BIENAL
        instrumento.save()

        # --- Catálogos usados na classificação ------------------------------
        vib, _ = TecnologiaAnalise.objects.get_or_create(
            nome="Análise de Vibração", defaults={"sigla": "VIB"}
        )
        cat_anomalias = {}
        for nome, _rec in ANOMALIAS_RECOMENDACOES:
            obj, _ = TipoAnomalia.objects.get_or_create(nome=nome)
            obj.tecnologias.add(vib)
            cat_anomalias[nome] = obj
        cat_componentes = {}
        for nome in ["Motor Elétrico", "Mancal", "Rolamento", "Rotor", "Unidade Compressora", "Acoplamento"]:
            obj, _ = TipoComponente.objects.get_or_create(nome=nome)
            obj.tecnologias.add(vib)
            cat_componentes[nome] = obj

        # --- Hierarquia da planta -------------------------------------------
        setores = []
        for cod_a, nome_a, compl_a, lista_setores in PLANTA:
            area = Area.objects.create(
                cliente=cliente, codigo=cod_a, nome=nome_a, complemento=compl_a
            )
            for cod_s, nome_s, compl_s in lista_setores:
                setores.append(
                    Setor.objects.create(area=area, codigo=cod_s, nome=nome_s, complemento=compl_s)
                )

        equipamentos = []
        for i, (tag, nome, classe, pot, rpm, subitens) in enumerate(MAQUINAS):
            setor = setores[i % len(setores)]
            principal = Equipamento.objects.create(
                setor=setor, tag=tag, nome=nome, classe_iso=classe,
                tipo="Máquina rotativa", fabricante=random.choice(["KSB", "WEG", "Kaeser", "Atlas Copco"]),
                potencia_kw=Decimal(pot), rotacao_nominal_rpm=rpm,
            )
            equipamentos.append(principal)
            # Sub-itens: são equipamentos filhos, com seus próprios pontos.
            for j, sub in enumerate(subitens):
                filho = Equipamento.objects.create(
                    setor=setor, equipamento_pai=principal, tag=f"{tag}-{j + 1}",
                    nome=sub, classe_iso=classe, potencia_kw=Decimal(pot),
                    rotacao_nominal_rpm=rpm,
                )
                Componente.objects.create(equipamento=filho, nome="Mancal LA")
                Componente.objects.create(equipamento=filho, nome="Mancal LOA")
                equipamentos.append(filho)

        tecnico = User.objects.filter(perfil="TECNICO").first() or User.objects.filter(
            perfil="ADMIN"
        ).first()

        # --- 6 meses de inspeções -------------------------------------------
        total_osps = 0
        laudo_final = None
        for volta in range(6):
            # Do mês mais antigo para o mais recente.
            data_insp = (hoje.replace(day=15) - timedelta(days=30 * (5 - volta)))
            inspecao = Inspecao.objects.create(
                cliente=cliente, tipo_analise=TipoAnalise.VIBRACAO,
                tecnico=tecnico, data=data_insp, status="CONCLUIDA",
                observacoes=f"Rota mensal de análise vibracional — {data_insp:%m/%Y}.",
            )

            for eq in equipamentos:
                # Severidade cresce um pouco ao longo dos meses (tendência real).
                base = random.uniform(0.8, 3.2) + volta * 0.35
                if random.random() < 0.18:      # alguns pontos evoluem para crítico
                    base += random.uniform(4.0, 7.5)
                m = MedicaoVibracao.objects.create(
                    inspecao=inspecao, equipamento=eq, instrumento=instrumento,
                    ponto_medicao=random.choice(["Mancal LA", "Mancal LOA"]),
                    numero_mancal=random.choice([1, 2]),
                    direcao=random.choice([Direcao.HORIZONTAL, Direcao.VERTICAL, Direcao.AXIAL]),
                    parametro=random.choice([ParametroMedicao.VELOCIDADE, ParametroMedicao.ACELERACAO]),
                    rotacao_rpm=eq.rotacao_nominal_rpm,
                    velocidade_rms=Decimal(f"{base:.2f}"),
                    aceleracao_rms=Decimal(f"{random.uniform(0.3, 2.6):.2f}"),
                    fator_crista=Decimal(f"{random.uniform(2.5, 6.5):.2f}"),
                    temperatura=Decimal(f"{random.uniform(38, 72):.1f}"),
                )
                # A data da medição é gerada automaticamente: reposiciona no mês.
                MedicaoVibracao.objects.filter(pk=m.pk).update(
                    data_hora=timezone.make_aware(
                        timezone.datetime.combine(data_insp, timezone.datetime.min.time())
                    )
                )

            # --- OSPs do mês ------------------------------------------------
            criticos = [
                m for m in MedicaoVibracao.objects.filter(inspecao=inspecao)
                if m.criticidade in ("ALERTA", "CRITICO")
            ]
            for m in criticos[:5]:
                nome_anom, recomendacao = random.choice(ANOMALIAS_RECOMENDACOES)
                gr = (
                    GrauRisco.GR1 if m.velocidade_rms > 11
                    else GrauRisco.GR2 if m.velocidade_rms > 7
                    else GrauRisco.GR3 if m.velocidade_rms > 4.5
                    else GrauRisco.GR4
                )
                # Meses antigos já foram tratados; os recentes seguem em aberto.
                acomp = (
                    Acompanhamento.CORRIGIDA if volta < 3
                    else Acompanhamento.REINCIDENTE if random.random() < 0.2
                    else Acompanhamento.ABERTA
                )
                mo_h = Decimal(random.choice([2, 4, 6, 8]))
                osp = OrdemServico.objects.filter(
                    equipamento=m.equipamento, inspecao=inspecao
                ).first() or OrdemServico(
                    cliente=cliente, equipamento=m.equipamento, inspecao=inspecao
                )
                osp.titulo = f"{m.equipamento.tag} — {m.equipamento.nome}"
                osp.grau_risco = gr
                osp.acompanhamento = acomp
                osp.tipo_anomalia = cat_anomalias[nome_anom]
                osp.tipo_componente = random.choice(list(cat_componentes.values()))
                osp.componente = m.equipamento.nome
                osp.anomalia = f"{nome_anom} identificado no {m.ponto_medicao} ({m.codigo_ponto})."
                osp.recomendacao = recomendacao
                osp.amplitude_velocidade = m.velocidade_rms
                osp.amplitude_aceleracao = m.aceleracao_rms
                osp.responsavel = tecnico
                # Avaliação de Resultados: preditiva x emergência evitada.
                osp.pred_mao_obra_h = mo_h
                osp.pred_mao_obra_valor = mo_h * Decimal("150")
                osp.pred_material_valor = Decimal(random.choice([450, 900, 1800, 3200]))
                osp.emerg_mao_obra_h = mo_h * 4
                osp.emerg_mao_obra_valor = mo_h * Decimal("150") * 4
                osp.emerg_material_valor = osp.pred_material_valor * Decimal("2.5")
                osp.emerg_producao_h = Decimal(random.choice([8, 16, 24]))
                osp.emerg_producao_valor = Decimal(random.choice([9000, 18000, 32000]))
                osp.save()
                OrdemServico.objects.filter(pk=osp.pk).update(
                    criado_em=timezone.make_aware(
                        timezone.datetime.combine(data_insp, timezone.datetime.min.time())
                    )
                )
                total_osps += 1

            # Laudo do último mês — é o que abre o relatório completo.
            if volta == 5:
                laudo_final = Laudo.objects.create(
                    inspecao=inspecao,
                    titulo="Análise Vibracional em Equipamentos Dinâmicos",
                    responsavel=tecnico,
                    criticidade_geral="CRITICO",
                    data_medicao_campo=data_insp,
                    data_upload_osps=data_insp + timedelta(days=7),
                    data_upload_relatorio=data_insp + timedelta(days=14),
                    diagnostico="Conjunto avaliado apresenta anomalias em evolução nos mancais.",
                    recomendacoes="Executar as OSPs conforme o grau de risco atribuído.",
                    conclusao="Recomenda-se manter a periodicidade mensal de monitoramento.",
                )

        self.stdout.write(self.style.SUCCESS("\nCenário do relatório criado:"))
        self.stdout.write(f"  Cliente        : {cliente.nome}")
        self.stdout.write(f"  Equipamentos   : {len(equipamentos)} (com sub-itens)")
        self.stdout.write(f"  Inspeções      : 6 meses")
        self.stdout.write(f"  Medições       : {MedicaoVibracao.objects.filter(inspecao__cliente=cliente).count()}")
        self.stdout.write(f"  OSPs           : {total_osps}")
        if laudo_final:
            self.stdout.write(self.style.SUCCESS(f"\n  >>> Abra o relatorio em: /laudos/{laudo_final.id}/relatorio"))
            self.stdout.write(f"      (laudo {laudo_final.numero})\n")
