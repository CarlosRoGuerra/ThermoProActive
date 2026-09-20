# -*- coding: utf-8 -*-
"""
Cenário COMPLETO de ponta a ponta, para conferir o Relatório Técnico cheio.

Percorre todas as etapas do fluxo real, na ordem em que a equipe as executa:

    cadastro (prestador, cliente, catálogos, instrumentação, norma)
      → hierarquia Área → Setor → Equipamento (com dados de placa)
      → rota de inspeção
      → carregamento da rota em campo  (nº do Relatório Técnico nasce aqui)
      → condição de cada equipamento
      → análises (achados) com componente, anomalia, recomendação e medições
      → imagens das análises (tendência, espectro, foto real)
      → transferência para o escritório
      → confirmação das análises → Ordem de Serviço por análise
      → avaliação de resultados (preditiva × emergencial) e confirmação do diagnóstico
      → Relatório Técnico completo: capa + seções A, B, C e D

Cria também uma segunda campanha de MANUTENÇÃO CORRETIVA (balanceamento
dinâmico), com Reference/Trial/Trim Run, planos, massa de correção e economia
energética — é o que faz a Análise final exibir o painel de balanceamento.

ISOLAMENTO: tudo é criado sob um CNPJ próprio (ver CNPJ_DEMO). Nenhum outro
cliente é tocado. Rodar de novo apaga e recria apenas os dados deste CNPJ.

Uso:  python manage.py seed_relatorio_completo
"""
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import (
    Area,
    Cliente,
    Componente,
    Condicao,
    DadosTecnicosTransformador,
    Empresa,
    Equipamento,
    Instrumento,
    Norma,
    Rota,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoEquipamento,
    TipoRecomendacao,
)
from apps.coletas.models import (
    Achado,
    AchadoImagem,
    Carregamento,
    ItemInspecao,
    Relatorio,
    StatusCarregamento,
)
from apps.osp.models import OrdemServico, PRAZO_GR_DIAS
from apps.servicos.models import (
    BalanceamentoPlano,
    BalanceamentoPonto,
    EconomiaEnergetica,
    ServicoCampo,
)

User = get_user_model()

CNPJ_DEMO = "99.888.777/0001-66"
HOJE = date.today()


# --------------------------------------------------------------------------
# Imagens: o relatório mostra tendência, espectro e foto real por análise.
# Geradas aqui para o documento não sair com moldura vazia.
# --------------------------------------------------------------------------
def _png(desenhar, largura=800, altura=600):
    """Gera um PNG em memória. Sem Pillow, devolve None e as imagens são puladas."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:  # pragma: no cover
        return None
    img = Image.new("RGB", (largura, altura), "#ffffff")
    desenhar(ImageDraw.Draw(img), largura, altura)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def img_tendencia(valores):
    def desenhar(d, w, h):
        m = 70
        d.rectangle([m, m, w - m, h - m], outline="#94a3b8")
        d.text((m, 24), "Tendencia da velocidade global (mm/s)", fill="#0f172a")
        if len(valores) < 2:
            return
        maior = max(valores) or 1
        passo = (w - 2 * m) / (len(valores) - 1)
        pontos = [
            (m + i * passo, (h - m) - (v / maior) * (h - 2 * m))
            for i, v in enumerate(valores)
        ]
        # Limite de alerta (ISO): a linha que dá sentido à curva.
        y_lim = (h - m) - (4.5 / maior) * (h - 2 * m)
        if m < y_lim < h - m:
            d.line([(m, y_lim), (w - m, y_lim)], fill="#dc2626", width=2)
            d.text((w - m - 150, y_lim - 18), "limite 4,5 mm/s", fill="#dc2626")
        d.line(pontos, fill="#1d4ed8", width=4)
        for x, y in pontos:
            d.ellipse([x - 5, y - 5, x + 5, y + 5], fill="#1d4ed8")
    return _png(desenhar)


def img_espectro(picos):
    def desenhar(d, w, h):
        m = 70
        d.rectangle([m, m, w - m, h - m], outline="#94a3b8")
        d.text((m, 24), "Espectro de velocidade — 0 a 1000 Hz", fill="#0f172a")
        for hz, amp in picos:
            x = m + (hz / 1000) * (w - 2 * m)
            y = (h - m) - amp * ((h - 2 * m) / 6)
            d.line([(x, h - m), (x, max(m, y))], fill="#1d4ed8", width=3)
            d.text((x - 12, max(m, y) - 20), f"{hz}Hz", fill="#334155")
    return _png(desenhar)


def img_real(texto):
    def desenhar(d, w, h):
        d.rectangle([0, 0, w, h], fill="#e2e8f0")
        d.rectangle([60, 120, w - 60, h - 120], fill="#94a3b8", outline="#475569", width=3)
        d.ellipse([w // 2 - 90, h // 2 - 90, w // 2 + 90, h // 2 + 90], fill="#64748b", outline="#334155", width=4)
        d.text((70, 60), texto, fill="#0f172a")
    return _png(desenhar)


def img_termica(temp_max, temp_ambiente, legenda):
    """Simula a paleta 'iron' de uma câmera termográfica, com o ponto quente marcado."""
    def desenhar(d, w, h):
        # Gradiente vertical simples imitando a paleta iron (roxo → amarelo → branco).
        for y in range(h):
            t = y / h
            r = int(20 + t * 235)
            g = int(0 + (t ** 2) * 200)
            b = int(80 * (1 - t))
            d.line([(0, h - y - 1), (w, h - y - 1)], fill=(r, g, b))
        cx, cy = int(w * 0.62), int(h * 0.45)
        for raio, alpha in ((90, 40), (60, 70), (32, 110), (14, 160)):
            cor = (255, min(255, 200 + alpha // 3), 255 - alpha)
            d.ellipse([cx - raio, cy - raio, cx + raio, cy + raio], outline=cor, width=4)
        d.rectangle([0, 0, w, 46], fill=(15, 23, 42))
        d.text((12, 12), legenda, fill="#f8fafc")
        d.text((w - 150, 12), f"Max {temp_max:.1f}°C", fill="#fecaca")
        d.text((w - 150, h - 30), f"Amb {temp_ambiente:.1f}°C", fill="#e2e8f0")
    return _png(desenhar)


def assinatura(nome):
    def desenhar(d, w, h):
        d.line([(20, h - 30), (w - 20, h - 30)], fill="#0f172a", width=2)
        d.text((30, h // 2 - 10), nome, fill="#1e293b")
    return _png(desenhar, largura=420, altura=120)


class Command(BaseCommand):
    help = "Cria um cenário completo (campo → escritório → OSP → Relatório Técnico)."

    @transaction.atomic
    def handle(self, *args, **options):
        w = self.stdout.write

        # ------------------------------------------------------------------
        # 0. Limpa APENAS o cenário deste CNPJ (idempotência sem colateral)
        # ------------------------------------------------------------------
        antigo = Cliente.objects.filter(cnpj=CNPJ_DEMO).first()
        if antigo:
            # O login do Portal do Cliente aponta pra este cliente com PROTECT —
            # precisa sair antes, senão a exclusão do cliente falha.
            User.objects.filter(cliente=antigo).delete()
            ServicoCampo.objects.filter(cliente=antigo).delete()
            OrdemServico.objects.filter(cliente=antigo).delete()
            Carregamento.objects.filter(cliente=antigo).delete()
            Relatorio.objects.filter(cliente=antigo).delete()
            Rota.objects.filter(cliente=antigo).delete()
            Equipamento.objects.filter(setor__area__cliente=antigo).delete()
            Area.objects.filter(cliente=antigo).delete()
            antigo.delete()
            w("  cenário anterior deste CNPJ removido")

        # ------------------------------------------------------------------
        # 1. Prestador — sai no cabeçalho, no rodapé e na capa
        #    Só PREENCHE o que está vazio; nunca sobrescreve o que já existe.
        # ------------------------------------------------------------------
        prestador = Empresa.objects.ativos().order_by("id").first()
        if prestador is None:
            prestador = Empresa.objects.create(
                nome="ThermoProActive Serviços Ltda", cnpj="39.923.567/0001-75"
            )
        padroes_prestador = {
            "inscricao_estadual": "Isenta",
            "cep": "13140-000",
            "logradouro": "Rua Ary Barroso",
            "numero": "120",
            "bairro": "Jardim Planalto",
            "cidade": "Paulínia",
            "uf": "SP",
            "contato_gestor": "Fabrício Papa",
            "departamento": "Engenharia de Manutenção Preditiva",
            "email": "contato@thermoproactive.com.br",
            "telefone": "11970677559",
            "site": "www.thermoproactive.com.br",
        }
        alterados = []
        for campo, valor in padroes_prestador.items():
            if not getattr(prestador, campo, ""):
                setattr(prestador, campo, valor)
                alterados.append(campo)
        if alterados:
            prestador.save()
        w(f"  prestador: {prestador.nome} (campos preenchidos: {len(alterados)})")

        # ------------------------------------------------------------------
        # 2. Cliente (contratante) — capa do relatório
        # ------------------------------------------------------------------
        cliente = Cliente.objects.create(
            nome="Papelera Santa Clara Indústria de Papel S.A.",
            nome_fantasia="Santa Clara Papel",
            cnpj=CNPJ_DEMO,
            unidade_negocio="Unidade Americana",
            cep="13470-450",
            logradouro="Rodovia Luiz de Queiroz, km 132",
            numero="4500",
            complemento="Galpão Industrial B",
            bairro="Distrito Industrial Abdo Najar",
            cidade="Americana",
            uf="SP",
            contato_gestor="Eng. Ricardo Menezes",
            departamento="Engenharia e Manutenção",
            email="manutencao@santaclarapapel.com.br",
            telefone="1934567890",
        )
        w(f"  cliente: {cliente.nome}")

        # ------------------------------------------------------------------
        # 3. Catálogos — alimentam os seletores e a Seção B
        # ------------------------------------------------------------------
        vibracao, _ = TecnologiaAnalise.objects.get_or_create(
            nome="Análise de Vibração",
            defaults={"sigla": "VIB", "descricao": "Medição de vibração global e espectral (ISO 10816/20816)."},
        )
        balanceamento, _ = TecnologiaAnalise.objects.get_or_create(
            nome="Balanceamento Dinâmico em Campo",
            defaults={
                "sigla": "BALDC",
                "tipo_corretiva": "BALANCEAMENTO",
                "descricao": "Correção de desbalanceamento de rotores no próprio equipamento.",
            },
        )
        # Garante o vínculo corretivo mesmo se a tecnologia já existia sem ele.
        if not balanceamento.tipo_corretiva:
            balanceamento.tipo_corretiva = "BALANCEAMENTO"
            balanceamento.save(update_fields=["tipo_corretiva"])

        # Graus de risco — a sigla precisa normalizar para GR1..GR4 (regra da OSP).
        GRAUS = [
            ("GR-0", "Grau de Risco INEXISTENTE", 0, "#16a34a", False),
            ("GR-4", "Grau de Risco BAIXO — acompanhar na próxima rota", 4, "#65a30d", True),
            ("GR-3", "Grau de Risco MODERADO — programar intervenção", 3, "#ca8a04", True),
            ("GR-2", "Grau de Risco ALTO — intervir na próxima parada", 2, "#ea580c", True),
            ("GR-1", "Grau de Risco CRÍTICO — intervenção imediata", 1, "#dc2626", True),
        ]
        condicoes = {}
        for sigla, nome, nivel, cor, gera in GRAUS:
            c, _ = Condicao.objects.get_or_create(
                sigla=sigla, defaults={"nome": nome, "nivel": nivel, "cor": cor, "gera_acao": gera}
            )
            condicoes[sigla] = c

        def catalogo(modelo, nomes, tecnologia=None):
            saida = {}
            for n in nomes:
                o, _ = modelo.objects.get_or_create(nome=n)
                o.tecnologias.add(tecnologia or vibracao)
                saida[n] = o
            return saida

        componentes = catalogo(TipoComponente, [
            "Rolamento LOA", "Rolamento LA", "Rotor", "Acoplamento", "Base", "Correias e polias",
        ])
        anomalias = catalogo(TipoAnomalia, [
            "Desbalanceamento", "Desalinhamento", "Folga mecânica",
            "Degradação de rolamento", "Cavitação",
        ])
        recomendacoes = catalogo(TipoRecomendacao, [
            "Balancear o rotor em campo",
            "Realinhar o conjunto motor-bomba",
            "Substituir o rolamento",
            "Reapertar a fixação da base",
            "Manter acompanhamento periódico do equipamento.",
        ])

        norma, _ = Norma.objects.get_or_create(
            codigo="ISO 10816-3",
            defaults={"nome": "Vibração mecânica — avaliação em máquinas não rotativas", "orgao": "ISO"},
        )
        norma.tecnologias.add(vibracao)
        norma2, _ = Norma.objects.get_or_create(
            codigo="ISO 21940-11",
            defaults={"nome": "Vibração mecânica — qualidade de balanceamento de rotores rígidos", "orgao": "ISO"},
        )
        norma2.tecnologias.add(balanceamento)

        instrumento, _ = Instrumento.objects.get_or_create(
            numero_serie="SKF-MIC-2291",
            defaults={
                "tipo": "Coletor e analisador de vibração",
                "marca": "SKF",
                "modelo": "Microlog Analyzer AX",
                "data_ultima_calibracao": HOJE - timedelta(days=120),
                "periodicidade_calibracao": 12,
                "entidade_calibracao": "RBC — Rede Brasileira de Calibração",
                "software_analise": "SKF @ptitude Analyst",
            },
        )
        instrumento.tecnologias.add(vibracao, balanceamento)

        # --- Terceira tecnologia: Termografia — dado de sistema novo, cadastrado
        # do mesmo jeito que Vibração/Balanceamento (nada de atalho paralelo). ---
        termografia, _ = TecnologiaAnalise.objects.get_or_create(
            nome="Termografia Infravermelha",
            defaults={
                "sigla": "TERMO",
                "descricao": "Inspeção termográfica de painéis, conexões e máquinas elétricas (NBR 15572).",
            },
        )
        componentes_termo = catalogo(TipoComponente, [
            "Conexão do barramento", "Disjuntor", "Bucha de entrada", "Enrolamento", "Contator",
        ], termografia)
        anomalias_termo = catalogo(TipoAnomalia, [
            "Ponto quente por mau contato", "Sobrecarga de fase", "Conexão frouxa",
        ], termografia)
        recomendacoes_termo = catalogo(TipoRecomendacao, [
            "Reapertar a conexão identificada",
            "Balancear as fases do circuito",
            "Substituir o disjuntor",
        ], termografia)
        # A recomendação de acompanhamento é comum às três tecnologias.
        recomendacoes["Manter acompanhamento periódico do equipamento."].tecnologias.add(termografia)

        norma3, _ = Norma.objects.get_or_create(
            codigo="NBR 15572",
            defaults={"nome": "Ensaios não destrutivos — Termografia", "orgao": "ABNT"},
        )
        norma3.tecnologias.add(termografia)

        instrumento_termo, _ = Instrumento.objects.get_or_create(
            numero_serie="FLIR-E76-58821",
            defaults={
                "tipo": "Câmera termográfica",
                "marca": "FLIR",
                "modelo": "E76",
                "data_ultima_calibracao": HOJE - timedelta(days=200),
                "periodicidade_calibracao": 12,
                "entidade_calibracao": "RBC — Rede Brasileira de Calibração",
                "software_analise": "FLIR Thermal Studio",
            },
        )
        instrumento_termo.tecnologias.add(termografia)

        w("  catálogos: 5 graus de risco, 3 tecnologias, 9 componentes, 8 anomalias, "
          "8 recomendações, 3 normas, 2 instrumentos")

        # ------------------------------------------------------------------
        # 4. Analista — assina o relatório
        # ------------------------------------------------------------------
        analista, criado = User.objects.get_or_create(
            email="analista.preditiva@thermoproactive.com.br",
            defaults={
                "nome": "Fabrício Papa",
                "perfil": "TECNICO",
                "nivel": "SENIOR",
                "cargo": "Analista de Manutenção Preditiva",
                "conselho_classe": "CREA-SP 5069874521",
                "is_active": True,
            },
        )
        if criado:
            analista.set_password("thermo123")
            analista.save()
        if not analista.assinatura_digital:
            dados = assinatura(analista.nome)
            if dados:
                analista.assinatura_digital.save("assinatura_fabricio.png", ContentFile(dados), save=True)
        w(f"  analista: {analista.nome} ({analista.conselho_classe})")

        # Gestor do cliente — login do Portal do Cliente, para a etapa final do
        # fluxo (Confirmação → OSP → Relatório Técnico → Portal do Cliente).
        gestor_cliente, criado = User.objects.get_or_create(
            email="pcm@santaclarapapel.com.br",
            defaults={
                "nome": "Eng. Ricardo Menezes",
                "perfil": "CLIENTE_PCM",
                "nivel": "PLENO",
                "cargo": "Coordenador de PCM",
                "cliente": cliente,
                "is_active": True,
            },
        )
        if not criado:
            gestor_cliente.cliente = cliente
            gestor_cliente.save(update_fields=["cliente"])
        if criado:
            gestor_cliente.set_password("thermo123")
            gestor_cliente.save()
        w(f"  portal do cliente: {gestor_cliente.email} / thermo123 ({gestor_cliente.get_perfil_display()})")

        # ------------------------------------------------------------------
        # 5. Hierarquia e equipamentos, com dados de placa completos
        # ------------------------------------------------------------------
        tipo_bomba, _ = TipoEquipamento.objects.get_or_create(nome="Bomba centrífuga")
        tipo_exaustor, _ = TipoEquipamento.objects.get_or_create(nome="Exaustor")
        tipo_motor, _ = TipoEquipamento.objects.get_or_create(nome="Motor elétrico")

        # Categoria técnica explícita no tipo — é ela que decide qual datasheet
        # (Motor/Transformador) o equipamento ganha, sem inferir pelo nome.
        tipo_transformador, criado_tt = TipoEquipamento.objects.get_or_create(
            nome="Transformador de distribuição", defaults={"categoria_tecnica": "TRANSFORMADOR"}
        )
        if not criado_tt and not tipo_transformador.categoria_tecnica:
            tipo_transformador.categoria_tecnica = "TRANSFORMADOR"
            tipo_transformador.save(update_fields=["categoria_tecnica"])
        tipo_quadro, _ = TipoEquipamento.objects.get_or_create(nome="Quadro elétrico")

        area = Area.objects.create(cliente=cliente, codigo="A-02", nome="Máquina de Papel")
        s_bombas = Setor.objects.create(area=area, codigo="6110", nome="Casa de Bombas")
        s_exaust = Setor.objects.create(area=area, codigo="6220", nome="Exaustão e Secagem")
        s_eletrica = Setor.objects.create(area=area, codigo="6300", nome="Subestação e Quadros Elétricos")

        def equipar(setor, tag, nome, tipo_eq, kw, rpm, iso, crit, fab, mod, serie, tensao, fp):
            eq = Equipamento.objects.create(
                setor=setor, tag=tag, nome=nome, tipo_equipamento=tipo_eq, tipo=tipo_eq.nome,
                fabricante=fab, modelo=mod, numero_serie=serie,
                potencia_kw=Decimal(kw), rotacao_nominal_rpm=rpm,
                tensao_nominal=Decimal(tensao), fator_potencia_nominal=Decimal(fp),
                classe_iso=iso, criticidade=crit,
            )
            for c in ("Rolamento LOA", "Rolamento LA"):
                Componente.objects.create(equipamento=eq, nome=c)
            return eq

        bba01 = equipar(s_bombas, "BBA-01-MP", "Bomba de Massa da Máquina de Papel", tipo_bomba,
                        "75", 1780, "III", "A", "KSB", "Megachem 125-400", "KSB-778210", "440", "0.87")
        bba02 = equipar(s_bombas, "BBA-02-VC", "Bomba de Vácuo do Setor de Prensas", tipo_bomba,
                        "45", 1770, "II", "B", "Nash", "2BE1 353", "NSH-441092", "440", "0.85")
        exa05 = equipar(s_exaust, "EXA-05-ME", "Exaustor da Capota de Secagem — Motor", tipo_motor,
                        "37", 3560, "II", "A", "WEG", "W22 IR3 Premium", "WEG-2210457", "380", "0.86")
        exa06 = equipar(s_exaust, "EXA-06-RT", "Exaustor de Ar de Processo — Rotor", tipo_exaustor,
                        "30", 1760, "II", "B", "Otam", "RLS-800", "OTM-330871", "380", "0.84")

        # Equipamentos elétricos — alvo típico de termografia, sem os campos de
        # motor (potência/RPM não fazem sentido aqui; a placa é outra).
        trf01 = Equipamento.objects.create(
            setor=s_eletrica, tag="TRF-01-SE", nome="Transformador da Subestação Principal",
            tipo_equipamento=tipo_transformador, fabricante="WEG", modelo="Trifásico a óleo 750 kVA",
            numero_serie="WEG-TRF-99871", criticidade="A",
        )
        DadosTecnicosTransformador.objects.create(
            equipamento=trf01, potencia_kva=Decimal("750.00"),
            tensao_primaria_v=Decimal("13800.00"), tensao_secundaria_v=Decimal("380.00"),
            impedancia_pct=Decimal("5.50"), grupo_ligacao="Dyn1",
        )
        for c in ("Bucha de entrada", "Conexão do barramento"):
            Componente.objects.create(equipamento=trf01, nome=c)

        qgbt01 = Equipamento.objects.create(
            setor=s_eletrica, tag="QGBT-01", nome="Quadro Geral de Baixa Tensão — Máquina de Papel",
            tipo_equipamento=tipo_quadro, fabricante="Steck", modelo="QGBT modular 400A",
            numero_serie="STK-QGBT-2201", criticidade="B",
        )
        for c in ("Disjuntor", "Contator"):
            Componente.objects.create(equipamento=qgbt01, nome=c)

        w(f"  hierarquia: {area.nome} → 3 setores → 6 equipamentos (com dados de placa)")

        # ------------------------------------------------------------------
        # 6. CAMPANHA 1 — Análise de Vibração (gera o Relatório Técnico)
        # ------------------------------------------------------------------
        rota_vib = Rota.objects.create(
            cliente=cliente, nome="Rota Mensal — Máquina de Papel", tecnologia=vibracao,
            descricao="Rota preditiva mensal dos ativos críticos da MP.", periodicidade_dias=30,
        )
        rota_vib.equipamentos.set([bba01, bba02, exa05, exa06])

        data_coleta = HOJE - timedelta(days=6)
        relatorio = Relatorio.objects.create(
            cliente=cliente, tecnologia=vibracao,
            numero=f"RT-VIB-{data_coleta:%Y-%m-%d}-00101",
            data_inicio=data_coleta, data_termino=data_coleta,
            data_finalizacao=HOJE - timedelta(days=2),
            consideracoes_finais=(
                "Dos 4 equipamentos inspecionados, 3 apresentaram anomalia com ação recomendada. "
                "O exaustor EXA-05-ME concentra o maior risco: desbalanceamento com amplitude "
                "acima do limite da Zona C da ISO 10816-3, com tendência de crescimento nas "
                "últimas três coletas. Recomenda-se o balanceamento dinâmico em campo na próxima "
                "parada programada, antes que a degradação alcance os rolamentos."
            ),
        )
        carreg = Carregamento.objects.create(
            cliente=cliente, tecnologia=vibracao, relatorio=relatorio, rota=rota_vib,
            instrumento=instrumento, analista=analista, data_coleta=data_coleta,
            status=StatusCarregamento.TRANSFERIDA,
        )

        # (equipamento, condição, componente, anomalia, recomendação, vel, acel, detalhe, obs)
        ANALISES = [
            (exa05, "GR-1", "Rotor", "Desbalanceamento", "Balancear o rotor em campo",
             "11.80", "3.90", "Ponto 1H — mancal LOA",
             "Amplitude predominante em 1×RPM (59,3 Hz), típica de desbalanceamento. "
             "Crescimento de 42% em relação à coleta anterior."),
            (bba01, "GR-2", "Acoplamento", "Desalinhamento", "Realinhar o conjunto motor-bomba",
             "7.40", "2.10", "Ponto 2A — axial no acoplamento",
             "Componente axial elevada com 2×RPM dominante. Verificar calços e alinhamento a laser."),
            (bba02, "GR-3", "Rolamento LOA", "Degradação de rolamento", "Substituir o rolamento",
             "4.90", "5.60", "Ponto 3H — mancal LOA",
             "Envelope com energia nas frequências de defeito da pista externa (BPFO). "
             "Ainda sem reflexo na velocidade global; acompanhar."),
            (exa06, "GR-0", "Base", "", "Manter acompanhamento periódico do equipamento.",
             "1.60", "0.90", "Ponto 4H — mancal LOA",
             "Equipamento dentro da Zona A da ISO 10816-3. Nenhuma ação necessária."),
        ]

        achados = []
        for ordem, (eq, grau, comp, anom, rec, vel, acel, detalhe, obs) in enumerate(ANALISES, start=1):
            item = ItemInspecao.objects.create(
                carregamento=carreg, equipamento=eq, condicao=condicoes[grau], ordem=ordem
            )
            achado = Achado.objects.create(
                item=item,
                tipo_componente=componentes.get(comp),
                detalhe=detalhe,
                tipo_anomalia=anomalias.get(anom) if anom else None,
                recomendacao=recomendacoes.get(rec),
                observacoes=obs,
                condicao=condicoes[grau],
                velocidade_global=Decimal(vel),
                aceleracao_global=Decimal(acel),
                confirmada=True,
                visivel_cliente=True,
            )
            achados.append(achado)

            # Imagens: tendência das 4 últimas coletas, espectro e foto do ponto.
            base = float(vel)
            tend = img_tendencia([base * 0.55, base * 0.68, base * 0.81, base])
            if tend:
                AchadoImagem.objects.create(
                    achado=achado, tipo="TENDENCIA",
                    legenda=f"Evolução da velocidade global — {eq.tag}",
                    arquivo=ContentFile(tend, name=f"tendencia_{eq.tag}.png"),
                )
            rpm_hz = (eq.rotacao_nominal_rpm or 1800) / 60
            esp = img_espectro([(round(rpm_hz), base * 0.8), (round(rpm_hz * 2), base * 0.3),
                                (round(rpm_hz * 3), base * 0.15)])
            if esp:
                AchadoImagem.objects.create(
                    achado=achado, tipo="ESPECTRO",
                    legenda=f"Espectro de velocidade — {eq.tag} ({detalhe})",
                    arquivo=ContentFile(esp, name=f"espectro_{eq.tag}.png"),
                )
            real = img_real(f"{eq.tag} - {eq.nome}")
            if real:
                AchadoImagem.objects.create(
                    achado=achado, tipo="REAL", legenda=f"Vista do ponto de medição — {eq.tag}",
                    arquivo=ContentFile(real, name=f"real_{eq.tag}.png"),
                )

        w(f"  campanha de vibração: relatório {relatorio.numero}, {len(achados)} análises, "
          f"{AchadoImagem.objects.filter(achado__in=achados).count()} imagens")

        # ------------------------------------------------------------------
        # 7. Ordens de Serviço — uma por análise com ação, pela regra do sistema
        # ------------------------------------------------------------------
        # Prazo por Grau de Risco: o MESMO PRAZO_GR_DIAS que a OSP usa de verdade
        # (GR1: 3d, GR2: 10d, GR3: 20d, GR4: 30d) — nada de tabela própria do seed
        # que pareça realista mas divirja da regra real do sistema.
        def gerar_osps(achados_lote, custos, data_referencia, finalizar_grau=None,
                       em_execucao_grau=None, descricao_finalizacao=""):
            """Confirma cada achado com ação e gera a OSP, pela mesma chamada que a
            Análise final usa (`OrdemServico.gerar_de_achado`) — sem atalho paralelo."""
            criadas = []
            for achado in achados_lote:
                if not (achado.condicao and achado.condicao.gera_acao):
                    continue  # GR-0 não abre ordem de serviço
                osp = OrdemServico.gerar_de_achado(achado)
                tag = achado.item.equipamento.tag
                if tag in custos:
                    (pmo_h, pmo_v, pmat, pprod_h, pprod_v,
                     emo_h, emo_v, emat, eprod_h, eprod_v) = custos[tag]
                    osp.pred_mao_obra_h = Decimal(pmo_h)
                    osp.pred_mao_obra_valor = Decimal(pmo_v)
                    osp.pred_material_valor = Decimal(pmat)
                    osp.pred_producao_h = Decimal(pprod_h)
                    osp.pred_producao_valor = Decimal(pprod_v)
                    osp.emerg_mao_obra_h = Decimal(emo_h)
                    osp.emerg_mao_obra_valor = Decimal(emo_v)
                    osp.emerg_material_valor = Decimal(emat)
                    osp.emerg_producao_h = Decimal(eprod_h)
                    osp.emerg_producao_valor = Decimal(eprod_v)
                dias = PRAZO_GR_DIAS.get(osp.grau_risco, 30)
                osp.sla_data = data_referencia + timedelta(days=dias)
                osp.prioridade = {"GR1": "URGENTE", "GR2": "ALTA", "GR3": "MEDIA"}.get(osp.grau_risco, "BAIXA")
                if osp.grau_risco == finalizar_grau:
                    # Já executada e confirmada: alimenta a taxa de acerto do diagnóstico.
                    osp.status = "FINALIZADA"
                    osp.resultado_confirmacao = "CONFIRMADO"
                    osp.descricao_corretiva = descricao_finalizacao
                elif osp.grau_risco == em_execucao_grau:
                    osp.status = "EM_EXECUCAO"
                else:
                    osp.status = "PLANEJADA"
                osp.save()
                criadas.append(osp)
            return criadas

        CUSTOS = {
            "EXA-05-ME": (6, 780, 450, 2, 3200, 28, 4100, 9800, 16, 48000),
            "BBA-01-MP": (4, 520, 180, 1, 1600, 20, 2900, 6400, 12, 36000),
            "BBA-02-VC": (5, 650, 1250, 2, 3200, 24, 3400, 8900, 14, 42000),
        }
        osps = gerar_osps(
            achados, CUSTOS, data_coleta, finalizar_grau="GR3",
            descricao_finalizacao=(
                "Rolamento substituído. Ao desmontar, constatou-se descascamento na pista "
                "externa, confirmando o diagnóstico da análise de envelope."
            ),
        )
        w(f"  ordens de serviço: {len(osps)} geradas (1 finalizada e confirmada)")

        # ------------------------------------------------------------------
        # 8. CAMPANHA 2 — Balanceamento dinâmico (painel da Análise final)
        # ------------------------------------------------------------------
        rota_bal = Rota.objects.create(
            cliente=cliente, nome="Corretiva — Balanceamento do Exaustor 05",
            tecnologia=balanceamento, descricao="Atividade corretiva gerada pela análise de vibração.",
        )
        rota_bal.equipamentos.set([exa05])

        data_bal = HOJE - timedelta(days=1)
        rel_bal = Relatorio.objects.create(
            cliente=cliente, tecnologia=balanceamento,
            numero=f"RT-BALDC-{data_bal:%Y-%m-%d}-00102",
            data_inicio=data_bal, data_termino=data_bal,
            consideracoes_finais=(
                "Balanceamento dinâmico em campo executado em um plano de correção. "
                "A amplitude caiu de 11,80 para 1,35 mm/s (88,6% de redução), levando o "
                "equipamento da Zona C para a Zona A da ISO 10816-3."
            ),
        )
        carreg_bal = Carregamento.objects.create(
            cliente=cliente, tecnologia=balanceamento, relatorio=rel_bal, rota=rota_bal,
            instrumento=instrumento, analista=analista, data_coleta=data_bal,
            tipo_corretiva="BALANCEAMENTO", status=StatusCarregamento.TRANSFERIDA,
        )
        item_bal = ItemInspecao.objects.create(
            carregamento=carreg_bal, equipamento=exa05, condicao=condicoes["GR-0"], ordem=1
        )
        achado_bal = Achado.objects.create(
            item=item_bal,
            tipo_componente=componentes["Rotor"],
            detalhe="Rotor do exaustor — plano único",
            tipo_anomalia=anomalias["Desbalanceamento"],
            recomendacao=recomendacoes["Manter acompanhamento periódico do equipamento."],
            observacoes="Desbalanceamento corrigido em campo. Equipamento liberado para operação.",
            condicao=condicoes["GR-0"],
            velocidade_global=Decimal("1.35"),
            aceleracao_global=Decimal("0.80"),
            confirmada=True, visivel_cliente=True,
        )

        servico = ServicoCampo.objects.create(
            item=item_bal, cliente=cliente, equipamento=exa05, tipo="BALANCEAMENTO",
            achado=achado_bal, relatorio=rel_bal, analista=analista, instrumento=instrumento,
            data_execucao=data_bal,
            rotacao_hz=Decimal("59.33"), rotacao_rpm=3560,
            custo_servico=Decimal("1980.00"),
            observacoes="Massa de correção fixada na face externa do rotor, a 30° do ponto de referência.",
        )
        plano = BalanceamentoPlano.objects.create(
            servico=servico, numero=1, descricao="Face externa do rotor",
            massa_teste_g=Decimal("30.00"), angulo_teste=Decimal("0.0"),
            massa_final_g=Decimal("18.50"), angulo_final=Decimal("30.0"),
        )
        ponto_foco = BalanceamentoPonto.objects.create(
            servico=servico, plano=plano, numero_mancal=1, direcao="H",
            identificacao="Motor — Mancal LOA",
            reference_mms=Decimal("11.80"), reference_fase=Decimal("212.0"),
            trial_mms=Decimal("7.95"), trial_fase=Decimal("168.0"),
            trim_mms=Decimal("1.35"), trim_fase=Decimal("45.0"),
        )
        BalanceamentoPonto.objects.create(
            servico=servico, plano=plano, numero_mancal=2, direcao="V",
            identificacao="Motor — Mancal LA",
            reference_mms=Decimal("6.20"), trim_mms=Decimal("1.10"),
        )
        servico.ponto_foco = ponto_foco
        servico.save(update_fields=["ponto_foco"])

        EconomiaEnergetica.objects.create(
            servico=servico,
            tensao_v=Decimal("380"), corrente_antes_a=Decimal("62.40"),
            corrente_apos_a=Decimal("58.10"), fator_potencia=Decimal("0.86"),
            horas_dia=Decimal("22"), dias_ano=330, custo_kwh=Decimal("0.62"),
            investimento=Decimal("1980.00"),
        )
        w(f"  balanceamento: {rel_bal.numero} — 11,80 → 1,35 mm/s, 2 pontos, economia calculada")

        # ------------------------------------------------------------------
        # 9. CAMPANHA 3 — Termografia Elétrica (terceira tecnologia, dados novos)
        # ------------------------------------------------------------------
        rota_termo = Rota.objects.create(
            cliente=cliente, nome="Rota Trimestral — Termografia Elétrica", tecnologia=termografia,
            descricao="Inspeção termográfica da subestação, QGBT e motores críticos.",
            periodicidade_dias=90,
        )
        # O motor do EXA-05 entra também aqui: o mesmo ativo, visto por duas
        # tecnologias — é assim que o histórico por equipamento fica completo.
        rota_termo.equipamentos.set([trf01, qgbt01, exa05])

        data_termo = HOJE - timedelta(days=3)
        rel_termo = Relatorio.objects.create(
            cliente=cliente, tecnologia=termografia,
            numero=f"RT-TERMO-{data_termo:%Y-%m-%d}-00103",
            data_inicio=data_termo, data_termino=data_termo,
            data_finalizacao=HOJE - timedelta(days=1),
            consideracoes_finais=(
                "Inspeção termográfica trimestral da subestação e do QGBT da Máquina de Papel. "
                "O transformador principal apresentou ponto quente na bucha de entrada da fase B, "
                "com ΔT de 36,3°C acima da referência — classificado como risco alto pela NBR 15572. "
                "O QGBT apresentou aquecimento moderado em um disjuntor, compatível com conexão "
                "frouxa. O motor do exaustor EXA-05-ME, já em acompanhamento pela vibração, não "
                "apresentou anomalia térmica."
            ),
        )
        carreg_termo = Carregamento.objects.create(
            cliente=cliente, tecnologia=termografia, relatorio=rel_termo, rota=rota_termo,
            instrumento=instrumento_termo, analista=analista, data_coleta=data_termo,
            status=StatusCarregamento.TRANSFERIDA,
        )

        # (equipamento, condição, componente, anomalia, recomendação, temp_medida,
        #  temp_referencia, carga%, corrente A/B/C, tensão A/B/C, detalhe, obs)
        ANALISES_TERMO = [
            (trf01, "GR-2", "Bucha de entrada", "Ponto quente por mau contato",
             "Reapertar a conexão identificada", "78.4", "42.1", "68.0",
             "64.10", "71.80", "63.90", "13800", "13750", "13820",
             "Bucha de entrada — fase B",
             "ΔT de 36,3°C acima da referência (critério NBR 15572: crítico acima de 30°C em "
             "carga comparável). Corrente da fase B 12% acima das demais — indício de mau contato, "
             "não de sobrecarga do circuito."),
            (qgbt01, "GR-3", "Disjuntor", "Conexão frouxa",
             "Reapertar a conexão identificada", "54.2", "38.0", "55.0",
             "148.30", "151.20", "149.00", "380", "381", "379",
             "Disjuntor do alimentador do exaustor EXA-05",
             "ΔT de 16,2°C acima da referência — risco moderado. Fases equilibradas, descarta "
             "sobrecarga; aquecimento localizado no borne de saída."),
            (exa05, "GR-0", "Enrolamento", "",
             "Manter acompanhamento periódico do equipamento.", "44.0", "41.0", "72.0",
             "58.20", "57.90", "58.40", "380", "380", "381",
             "Carcaça do motor — lado acoplamento",
             "ΔT de 3,0°C, dentro da normalidade. Sem indício de sobrecarga ou falha de "
             "isolamento; motor já sob acompanhamento pela análise de vibração."),
        ]

        achados_termo = []
        for ordem, (eq, grau, comp, anom, rec, tmed, tref, carga, ca, cb, cc, ta, tb, tc,
                    detalhe, obs) in enumerate(ANALISES_TERMO, start=1):
            item = ItemInspecao.objects.create(
                carregamento=carreg_termo, equipamento=eq, condicao=condicoes[grau], ordem=ordem
            )
            achado = Achado.objects.create(
                item=item,
                tipo_componente=componentes_termo.get(comp),
                detalhe=detalhe,
                tipo_anomalia=anomalias_termo.get(anom) if anom else None,
                recomendacao=recomendacoes_termo.get(rec) or recomendacoes.get(rec),
                observacoes=obs,
                condicao=condicoes[grau],
                temperatura_medida=Decimal(tmed),
                temperatura_referencia=Decimal(tref),
                carga_percentual=Decimal(carga),
                corrente_a=Decimal(ca), corrente_b=Decimal(cb), corrente_c=Decimal(cc),
                tensao_a=Decimal(ta), tensao_b=Decimal(tb), tensao_c=Decimal(tc),
                confirmada=True,
                visivel_cliente=True,
            )
            achados_termo.append(achado)

            termica = img_termica(float(tmed), float(tref), f"{eq.tag} — {detalhe}")
            if termica:
                AchadoImagem.objects.create(
                    achado=achado, tipo="TERMICA",
                    legenda=f"Termograma — {eq.tag} ({detalhe})",
                    arquivo=ContentFile(termica, name=f"termica_{eq.tag}.png"),
                )
            real = img_real(f"{eq.tag} - {eq.nome}")
            if real:
                AchadoImagem.objects.create(
                    achado=achado, tipo="REAL", legenda=f"Vista do ponto de medição — {eq.tag}",
                    arquivo=ContentFile(real, name=f"real_termo_{eq.tag}.png"),
                )

        w(f"  campanha de termografia: relatório {rel_termo.numero}, {len(achados_termo)} análises, "
          f"{AchadoImagem.objects.filter(achado__in=achados_termo).count()} imagens")

        CUSTOS_TERMO = {
            "TRF-01-SE": (8, 980, 620, 3, 5400, 32, 5200, 18500, 20, 72000),
            "QGBT-01": (3, 410, 95, 1, 1200, 10, 1600, 2100, 4, 9600),
        }
        osps_termo = gerar_osps(
            achados_termo, CUSTOS_TERMO, data_termo, em_execucao_grau="GR2",
        )
        w(f"  ordens de serviço (termografia): {len(osps_termo)} geradas (1 em execução)")

        # ------------------------------------------------------------------
        # Resumo
        # ------------------------------------------------------------------
        w("")
        w(self.style.SUCCESS("Cenário completo criado."))
        w("")
        w(f"  Cliente          : {cliente.nome} ({cliente.cnpj})")
        w(f"  Relatório (vibração)   : {relatorio.numero}  (id={relatorio.id})")
        w(f"  Relatório (balanceamento): {rel_bal.numero}  (id={rel_bal.id})")
        w(f"  Relatório (termografia): {rel_termo.numero}  (id={rel_termo.id})")
        w(f"  Ordens de serviço total : {len(osps) + len(osps_termo)}")
        w(f"  Portal do cliente       : {gestor_cliente.email} / thermo123")
        w("")
        w("  Abra em:")
        w(f"    Relatório Técnico (vibração)   →  /relatorios-inspecao/{relatorio.id}")
        w(f"    Relatório Técnico (termografia) →  /relatorios-inspecao/{rel_termo.id}")
        w(f"    Impressão com nº de página  →  /imprimir/{relatorio.id}")
        w(f"    Carta ao cliente            →  /carta/{relatorio.id}")
        w(f"    Análise final (balanceamento) → /inspecoes/final/{achado_bal.id}")
        w("    Ordens de serviço           →  /osps")
        w("    Análise de campo (rotas)    →  /inspecoes/campo")
