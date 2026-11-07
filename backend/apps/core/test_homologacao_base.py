"""
Massa de dados compartilhada pelos testes de pré-homologação (QA).

Não contém nenhum TestCase: só funções/constantes reutilizadas por
`test_homologacao_fluxo.py`, `test_homologacao_perfis.py` e
`test_homologacao_isolamento.py`.

Cada cliente recebe um parque completo (área, setor, equipamento, rota),
coleta (inspeções de vibração, termografia e sensitiva com medições), a OSP
gerada AUTOMATICAMENTE pelo motor de regras, laudo emitido (renderer de PDF
mockado) e rascunho, relatório de rotas com análise, ensaio de fluido, serviço
corretivo com economia e uma notificação — de modo que o teste de isolamento
possa procurar qualquer rastro do cliente B nas respostas do cliente A.
"""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model

from apps.cadastros.models import (
    Area, Cliente, Componente, Condicao, Equipamento, ModuloTecnico, Rota, Setor,
    TecnologiaAnalise,
)

User = get_user_model()

SENHA = "SenhaSuperForte#2026!!"
PDF_FALSO = b"%PDF-1.4\n% QA homologacao - renderer mockado\n%%EOF"

#: Perfis de cliente existentes no código (Anexo I 2.1.2.4 a 2.1.2.7) e o nível usado nos testes.
PERFIS_CLIENTE = {
    "CLIENTE_CORP": "MASTER",   # 2.1.2.4 gestor corporativo (único que convida colegas)
    "CLIENTE_LOCAL": "SENIOR",  # 2.1.2.5 gestor local
    "CLIENTE_PCM": "PLENO",     # 2.1.2.6 PCM
    "CLIENTE_MANUT": "JUNIOR",  # 2.1.2.7 manutentores
}
PERFIS_INTERNOS = {
    "ADMIN": "MASTER",    # 2.1.2.1
    "GESTOR": "SENIOR",   # 2.1.2.2
    "TECNICO": "PLENO",   # 2.1.2.3
}


def criar_usuario(email, perfil, nivel="PLENO", cliente=None, **extra):
    extra.setdefault("conselho_classe", "CREA-QA 12345" if perfil in PERFIS_INTERNOS else "")
    return User.objects.create_user(
        email=email, password=SENHA, nome=email.split("@")[0].replace(".", " ").title(),
        perfil=perfil, nivel=nivel, cliente=cliente, **extra,
    )


def criar_internos(sufixo=""):
    return {
        perfil: criar_usuario(f"{perfil.lower()}{sufixo}@thermo.qa", perfil, nivel)
        for perfil, nivel in PERFIS_INTERNOS.items()
    }


def criar_clientes_usuarios(cliente, rotulo):
    return {
        perfil: criar_usuario(f"{perfil.lower()}.{rotulo}@cliente.qa", perfil, nivel, cliente=cliente)
        for perfil, nivel in PERFIS_CLIENTE.items()
    }


def laudo_emitido(laudo, usuario):
    """Emite o laudo pelo serviço real, com o renderer de PDF (Chromium) mockado."""
    from apps.laudos.services import emitir_laudo

    with patch("apps.laudos.pdf.gerar_pdf", return_value=PDF_FALSO):
        emitido, _ = emitir_laudo(laudo, usuario)
    return emitido


def construir_cliente(rotulo, cnpj, tecnico, gestor):
    """
    Parque + coleta + OSP + laudo + relatório + fluido + corretiva do cliente `rotulo`
    (ex.: "A"/"B"). `tecnico` é o responsável pela coleta, `gestor` emite o laudo.
    Devolve um SimpleNamespace com tudo que os testes precisam.
    """
    from apps.coletas.models import (
        Achado, Carregamento, Inspecao, ItemInspecao, MedicaoTecnica, MedicaoTermografia,
        MedicaoVibracao, Relatorio,
    )
    from apps.ensaios.models import ColetaFluido, Ensaio, ResultadoEnsaio
    from apps.laudos.models import Laudo
    from apps.laudos.services import gerar_laudo_de_inspecao
    from apps.notificacoes.models import EventoNotificacao, Notificacao
    from apps.osp.models import OrdemServico
    from apps.servicos.models import BalanceamentoPlano, EconomiaEnergetica, ServicoCampo, TipoServico

    d = SimpleNamespace(rotulo=rotulo)
    d.cliente = Cliente.objects.create(
        nome=f"Industria {rotulo} QA", cnpj=cnpj, unidade_negocio=f"Unidade {rotulo}",
        contato_gestor=f"Contato Gestor {rotulo}",
    )
    d.area = Area.objects.create(cliente=d.cliente, nome=f"Area Secreta {rotulo}")
    d.setor = Setor.objects.create(area=d.area, nome=f"Setor Secreto {rotulo}")
    d.equipamento = Equipamento.objects.create(
        setor=d.setor, tag=f"TAG-{rotulo}-01", nome=f"Bomba Sigilosa {rotulo}", classe_iso="G2", tipo_base="RIGIDA",
    )
    d.equipamento2 = Equipamento.objects.create(
        setor=d.setor, tag=f"TAG-{rotulo}-02", nome=f"Ventilador Sigiloso {rotulo}", classe_iso="G2", tipo_base="RIGIDA",
    )
    d.componente = Componente.objects.create(equipamento=d.equipamento, nome=f"Mancal Sigiloso {rotulo}")
    d.rota = Rota.objects.create(cliente=d.cliente, nome=f"Rota Secreta {rotulo}")
    d.rota.equipamentos.add(d.equipamento, d.equipamento2)
    d.usuarios = criar_clientes_usuarios(d.cliente, rotulo.lower())

    # --- Coleta: vibração CRÍTICA (8,0 mm/s, Grupo 2 base rígida - ISO 20816-3) -> motor de regras -> OSP automática ---
    d.inspecao = Inspecao.objects.create(
        cliente=d.cliente, tecnico=tecnico, data=date(2026, 10, 20), tipo_analise="VIBRACAO",
        observacoes=f"Observacao reservada {rotulo}",
    )
    d.vibracao = MedicaoVibracao.objects.create(
        inspecao=d.inspecao, equipamento=d.equipamento, componente=d.componente,
        ponto_medicao=f"Mancal LA {rotulo}", direcao="H", velocidade_rms=Decimal("8.00"),
        rotacao_rpm=1800, coletado_por=tecnico,
    )
    d.inspecao_termo = Inspecao.objects.create(
        cliente=d.cliente, tecnico=tecnico, data=date(2026, 10, 21), tipo_analise="TERMOGRAFIA",
    )
    d.termografia = MedicaoTermografia.objects.create(
        inspecao=d.inspecao_termo, equipamento=d.equipamento2, ponto_medicao=f"Painel {rotulo}",
        sistema="ELETRICO", temperatura_ponto=Decimal("70"), temperatura_referencia=Decimal("40"),
        emissividade=Decimal("0.95"), coletado_por=tecnico,
    )
    d.inspecao_sens = Inspecao.objects.create(
        cliente=d.cliente, tecnico=tecnico, data=date(2026, 10, 22), tipo_analise="SENSITIVA",
    )
    d.tecnica = MedicaoTecnica.objects.create(
        inspecao=d.inspecao_sens, equipamento=d.equipamento2, tipo="SENSITIVA", subtipo="SENSITIVA",
        ponto_medicao=f"Ponto sensitivo {rotulo}", grandeza="Parecer qualitativo", valor=None,
        parametros={"criticidade": "ALERTA", "observacao": f"Ruido anormal {rotulo}"}, coletado_por=tecnico,
    )
    d.osp = OrdemServico.objects.filter(cliente=d.cliente).order_by("pk").first()

    # --- Laudo emitido (PDF mockado) + rascunho ---
    laudo = gerar_laudo_de_inspecao(d.inspecao, responsavel=gestor)
    d.laudo = laudo_emitido(laudo, gestor)
    d.laudo_rascunho = gerar_laudo_de_inspecao(d.inspecao_termo, responsavel=gestor)

    # --- Fluxo campo -> escritório (relatório de rotas, análise) ---
    d.tecnologia = TecnologiaAnalise.objects.create(
        nome=f"Vibracao QA {rotulo}", sigla=f"V{rotulo}", modulo_tecnico=ModuloTecnico.VIBRACAO,
    )
    d.relatorio = Relatorio.objects.create(
        cliente=d.cliente, tecnologia=d.tecnologia, numero=f"RT-QA-{rotulo}-00001",
        data_inicio=date(2026, 10, 20), data_termino=date(2026, 10, 24),
    )
    d.carregamento = Carregamento.objects.create(
        cliente=d.cliente, tecnologia=d.tecnologia, analista=tecnico, relatorio=d.relatorio, rota=d.rota,
    )
    gr3 = Condicao.objects.filter(sigla__iexact="GR3").first() or Condicao.objects.first()
    d.item = ItemInspecao.objects.create(
        carregamento=d.carregamento, equipamento=d.equipamento, ordem=1, condicao=gr3,
    )
    d.achado = Achado.objects.create(
        item=d.item, componente_texto=f"Componente reservado {rotulo}",
        anomalia_texto=f"Anomalia reservada {rotulo}", velocidade_global=Decimal("4.200"),
    )

    # --- Fluido (ensaio) ---
    tec_fluido = TecnologiaAnalise.objects.create(
        nome=f"Fluidos QA {rotulo}", sigla=f"F{rotulo}", modulo_tecnico=ModuloTecnico.FLUIDO_LUBRIFICANTE,
    )
    rel_f = Relatorio.objects.create(
        cliente=d.cliente, tecnologia=tec_fluido, numero=f"RT-QA-F{rotulo}-00001",
        data_inicio=date(2026, 10, 20), data_termino=date(2026, 10, 20),
    )
    carr_f = Carregamento.objects.create(
        cliente=d.cliente, tecnologia=tec_fluido, analista=tecnico, relatorio=rel_f,
    )
    d.item_fluido = ItemInspecao.objects.create(carregamento=carr_f, equipamento=d.equipamento, ordem=1)
    d.coleta_fluido = ColetaFluido.objects.create(
        item=d.item_fluido, aplicacao="LUBRIFICANTE", data_coleta=date(2026, 10, 20),
        fluido_informado=f"Oleo Reservado {rotulo}",
    )
    ensaio = Ensaio.objects.filter(modulo=ModuloTecnico.FLUIDO_LUBRIFICANTE).order_by("pk").first()
    d.resultado_ensaio = (
        ResultadoEnsaio.objects.create(item=d.item_fluido, ensaio=ensaio, situacao="REALIZADO")
        if ensaio else None
    )

    # --- Corretiva (balanceamento) + economia ---
    d.servico = ServicoCampo.objects.create(
        cliente=d.cliente, equipamento=d.equipamento, tipo=TipoServico.BALANCEAMENTO,
        analista=tecnico, data_execucao=date(2026, 10, 23), observacoes=f"Servico reservado {rotulo}",
    )
    d.plano = BalanceamentoPlano.objects.create(servico=d.servico, numero=1, descricao=f"Plano {rotulo}")
    d.economia = EconomiaEnergetica.objects.create(
        servico=d.servico, tensao_v=Decimal("380"), corrente_antes_a=Decimal("71"),
        corrente_apos_a=Decimal("66.2"), fator_potencia=Decimal("0.93"), horas_dia=Decimal("20"),
        dias_ano=365, custo_kwh=Decimal("0.35"), investimento=Decimal("1606"),
    )

    # --- Notificação privada de um usuário do cliente ---
    d.notificacao = Notificacao.objects.create(
        destinatario=d.usuarios["CLIENTE_PCM"], evento=EventoNotificacao.NOVA_OSP,
        titulo=f"Aviso reservado {rotulo}", mensagem=f"TAG-{rotulo}-01 requer atencao",
    )
    d.laudos_total = Laudo.objects.filter(cliente_documento=d.cliente).count()
    return d
