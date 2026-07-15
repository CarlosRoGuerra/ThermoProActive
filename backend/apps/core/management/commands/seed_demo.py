"""
Popula o banco com dados de demonstração coerentes para validar o fluxo:
login → cadastros → coleta de vibração → laudo.

Uso:  python manage.py seed_demo
Idempotente: pode ser executado várias vezes (usa get_or_create).
"""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import (
    Area,
    Cliente,
    Componente,
    Empresa,
    Equipamento,
    Instrumento,
    Norma,
    Rota,
    Setor,
    TecnologiaAnalise,
    TipoComponente,
    TipoCriticidade,
    TipoEquipamento,
)
from apps.coletas.models import (
    Direcao,
    Inspecao,
    MedicaoTecnica,
    MedicaoTermografia,
    MedicaoVibracao,
    SistemaTermografia,
    TipoAnalise,
)
from apps.laudos.services import gerar_laudo_de_inspecao

User = get_user_model()


class Command(BaseCommand):
    help = "Cria dados de demonstração do ThermoProActive."

    @transaction.atomic
    def handle(self, *args, **options):
        # --- Empresa contratada (Guerra IT / ThermoProActive prestadora) ---
        empresa, _ = Empresa.objects.get_or_create(
            cnpj="39.923.567/0001-75",
            defaults={"nome": "ThermoProActive Serviços Ltda", "cidade_uf": "Paulínia/SP"},
        )

        # --- Cliente contratante (planta industrial exemplo) ---
        cliente, _ = Cliente.objects.get_or_create(
            cnpj="11.222.333/0001-44",
            defaults={
                "nome": "Indústria Exemplo S.A.",
                "unidade_negocio": "Planta Campinas",
                "cidade_uf": "Campinas/SP",
            },
        )

        # --- Usuários (1 por perfil-chave) ---
        users = {
            "admin@thermoproactive.com": ("Administrador Demo", "ADMIN", {"is_staff": True, "is_superuser": True}),
            "tecnico@thermoproactive.com": ("Técnico Analista", "TECNICO", {"conselho_classe": "CREA-SP 123456"}),
            "cliente@exemplo.com": ("Gestor PCM Cliente", "CLIENTE_PCM", {"cliente": cliente}),
        }
        criados = {}
        for email, (nome, perfil, extra) in users.items():
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"nome": nome, "perfil": perfil, "empresa": empresa, **extra},
            )
            if created:
                user.set_password("thermo123")
                user.save()
            criados[perfil] = user
        tecnico = criados["TECNICO"]

        # --- Catálogos / tabelas de referência (módulo 2.2) ---
        for nivel, (nome, cor) in enumerate(
            [("Normal", "#10b981"), ("Alerta", "#f59e0b"), ("Crítico", "#ef4444")]
        ):
            TipoCriticidade.objects.get_or_create(nome=nome, defaults={"cor": cor, "nivel": nivel})
        for codigo, titulo, orgao in [
            ("ISO 20816", "Vibração mecânica — avaliação por medições em partes não rotativas", "ISO"),
            ("NBR 15572", "Ensaios não destrutivos — Termografia", "ABNT"),
            ("IEEE 43", "Resistência de isolamento de máquinas rotativas", "IEEE"),
        ]:
            Norma.objects.get_or_create(codigo=codigo, defaults={"nome": titulo, "orgao": orgao})
        for nome, sigla in [("Análise de Vibração", "VIB"), ("Termografia", "TERMO"), ("Ensaios Elétricos", "EE")]:
            TecnologiaAnalise.objects.get_or_create(nome=nome, defaults={"sigla": sigla})
        for nome in ["Bomba centrífuga", "Motor elétrico", "Ventilador", "Redutor"]:
            TipoEquipamento.objects.get_or_create(nome=nome)
        for nome in ["Mancal", "Rolamento", "Acoplamento", "Motor"]:
            TipoComponente.objects.get_or_create(nome=nome)

        # --- Hierarquia de localização ---
        area, _ = Area.objects.get_or_create(cliente=cliente, nome="Utilidades")
        setor, _ = Setor.objects.get_or_create(area=area, nome="Casa de Bombas")

        equipamento, _ = Equipamento.objects.get_or_create(
            setor=setor,
            tag="BBA-101",
            defaults={
                "nome": "Bomba Centrífuga de Água de Resfriamento",
                "tipo": "Bomba centrífuga",
                "fabricante": "KSB",
                "potencia_kw": Decimal("45"),
                "rotacao_nominal_rpm": 1780,
                "classe_iso": "II",
            },
        )
        mancal_la, _ = Componente.objects.get_or_create(equipamento=equipamento, nome="Mancal LA")
        Componente.objects.get_or_create(equipamento=equipamento, nome="Mancal LOA")

        instrumento, _ = Instrumento.objects.get_or_create(
            tipo="Coletor de vibração",
            defaults={"marca": "SKF", "modelo": "Microlog", "numero_serie": "SN-0001"},
        )

        # --- Rota de inspeção (item 2.2.1.18) ---
        rota, _ = Rota.objects.get_or_create(
            cliente=cliente,
            nome="Rota Mensal — Utilidades",
            defaults={"periodicidade_dias": 30, "descricao": "Rota preditiva mensal."},
        )
        rota.equipamentos.add(equipamento)

        # --- Inspeção + medições (uma normal, uma crítica) ---
        inspecao, nova = Inspecao.objects.get_or_create(
            cliente=cliente,
            tecnico=tecnico,
            data=date.today(),
            tipo_analise=TipoAnalise.VIBRACAO,
            defaults={"observacoes": "Rota preditiva mensal — Casa de Bombas."},
        )
        if nova:
            MedicaoVibracao.objects.create(
                inspecao=inspecao, equipamento=equipamento, componente=mancal_la,
                instrumento=instrumento, ponto_medicao="Mancal LA", direcao=Direcao.HORIZONTAL,
                rotacao_rpm=1780, velocidade_rms=Decimal("1.90"), fator_crista=Decimal("3.1"),
            )
            MedicaoVibracao.objects.create(
                inspecao=inspecao, equipamento=equipamento, componente=mancal_la,
                instrumento=instrumento, ponto_medicao="Mancal LA", direcao=Direcao.VERTICAL,
                rotacao_rpm=1780, velocidade_rms=Decimal("9.40"), fator_crista=Decimal("6.2"),
            )

        # --- Inspeção de Termografia (item 2.3.2.2) ---
        insp_termo, nova_termo = Inspecao.objects.get_or_create(
            cliente=cliente,
            tecnico=tecnico,
            data=date.today(),
            tipo_analise=TipoAnalise.TERMOGRAFIA,
            defaults={"observacoes": "Termografia de painéis elétricos."},
        )
        if nova_termo:
            MedicaoTermografia.objects.create(
                inspecao=insp_termo, equipamento=equipamento, instrumento=instrumento,
                ponto_medicao="Conexão fase R", sistema=SistemaTermografia.ELETRICO,
                temperatura_ponto=Decimal("42.0"), temperatura_referencia=Decimal("40.0"),
                temperatura_ambiente=Decimal("30.0"), carga_percentual=Decimal("80"),
            )
            MedicaoTermografia.objects.create(
                inspecao=insp_termo, equipamento=equipamento, instrumento=instrumento,
                ponto_medicao="Conexão fase T", sistema=SistemaTermografia.ELETRICO,
                temperatura_ponto=Decimal("78.0"), temperatura_referencia=Decimal("40.0"),
                temperatura_ambiente=Decimal("30.0"), carga_percentual=Decimal("80"),
            )

        # --- Inspeção de Ensaios Elétricos (item 2.3.2.5) ---
        insp_ee, nova_ee = Inspecao.objects.get_or_create(
            cliente=cliente,
            tecnico=tecnico,
            data=date.today(),
            tipo_analise=TipoAnalise.ENSAIO_ELETRICO,
            defaults={"observacoes": "Ensaio de resistência de isolação do motor."},
        )
        if nova_ee:
            MedicaoTecnica.objects.create(
                inspecao=insp_ee, equipamento=equipamento, tipo=TipoAnalise.ENSAIO_ELETRICO,
                ponto_medicao="Enrolamento do estator", grandeza="Resistência de isolação",
                valor=Decimal("1500"), unidade="MΩ",
            )
            MedicaoTecnica.objects.create(
                inspecao=insp_ee, equipamento=equipamento, tipo=TipoAnalise.ENSAIO_ELETRICO,
                ponto_medicao="Enrolamento (fase U)", grandeza="Resistência de isolação",
                valor=Decimal("50"), unidade="MΩ",
            )

        # --- Laudos gerados a partir das inspeções ---
        if not inspecao.laudos.exists():
            gerar_laudo_de_inspecao(inspecao, responsavel=tecnico)
        if not insp_termo.laudos.exists():
            gerar_laudo_de_inspecao(insp_termo, responsavel=tecnico)

        # --- Custos de exemplo nas OSPs (relatório financeiro 2.9.1.5) ---
        from apps.osp.models import OrdemServico

        for osp in OrdemServico.objects.filter(custo_estimado__isnull=True):
            osp.custo_estimado = Decimal("2500.00")
            osp.custo_real = Decimal("1800.00")
            osp.save(update_fields=["custo_estimado", "custo_real"])

        self.stdout.write(self.style.SUCCESS("Seed concluído."))
        self.stdout.write("Usuários (senha: thermo123):")
        for email in users:
            self.stdout.write(f"  - {email}")
