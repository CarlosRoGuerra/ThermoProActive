"""
Pré-homologação (QA) — matriz de perfis x endpoints principais.

Os 7 perfis do Anexo I 2.1.2 (3 internos + 4 de cliente; o contrato lista QUATRO
perfis de cliente, 2.1.2.4 a 2.1.2.7, não cinco) são exercitados contra listar /
detalhar / criar / alterar / excluir em cadastros, coletas, OSP (inclusive cada
transição de status), laudos, relatórios, usuários/minha-equipe e notificações.

* "Esperado" deriva do contrato (2.1.1.4/2.1.1.6/2.7), dos docs 12-17 e das classes de
  permissão (`apps.accounts.permissions`). Quando a regra não está confirmada, a linha
  recebe `confirmar=True`: o teste fixa o comportamento ATUAL e o relatório lista a
  linha como "a confirmar com o cliente".
* Cada célula (perfil x operação) roda em um savepoint que é desfeito, para que uma
  exclusão/edição de um perfil não contamine a célula do próximo.
* Níveis usados: ADMIN=MASTER, GESTOR=SÊNIOR, TECNICO=PLENO, CLIENTE_CORP=MASTER,
  CLIENTE_LOCAL=SÊNIOR, CLIENTE_PCM=PLENO, CLIENTE_MANUT=JÚNIOR.
* Se a variável de ambiente QA_MATRIZ_JSON apontar para um arquivo, cada célula é gravada
  nele (JSON lines) — usado para montar a tabela do relatório.

Execução: cd backend && python manage.py test apps.core.test_homologacao_perfis --parallel 1
"""
import json
import os
from datetime import date

from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.coletas.models import Achado, Carregamento, Inspecao, StatusCarregamento
from apps.osp.models import OrdemServico

from unittest.mock import patch

from .test_homologacao_base import PDF_FALSO, construir_cliente, criar_internos

INTERNOS = ["ADMIN", "GESTOR", "TECNICO"]
CLIENTES = ["CLIENTE_CORP", "CLIENTE_LOCAL", "CLIENTE_PCM", "CLIENTE_MANUT"]
PERFIS = INTERNOS + CLIENTES
TODOS_OK = {p: 200 for p in PERFIS}


def esperado(internos=None, clientes=None, **por_perfil):
    """Monta {perfil: código}. `internos`/`clientes` valem para o grupo; `por_perfil` sobrescreve."""
    tabela = {}
    for p in INTERNOS:
        tabela[p] = internos
    for p in CLIENTES:
        tabela[p] = clientes
    tabela.update(por_perfil)
    return tabela


class MatrizDePerfisBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.internos = criar_internos()
        cls.d = construir_cliente("A", "11.111.111/0001-11", cls.internos["TECNICO"], cls.internos["GESTOR"])
        cls.b = construir_cliente("B", "22.222.222/0001-22", cls.internos["TECNICO"], cls.internos["GESTOR"])
        cls.usuarios = {**cls.internos, **cls.d.usuarios}
        # inspeção vazia (sem medições/laudos/OSP) para testar a exclusão
        cls.inspecao_vazia = Inspecao.objects.create(
            cliente=cls.d.cliente, tecnico=cls.internos["TECNICO"], data=date(2026, 10, 25), tipo_analise="VIBRACAO",
        )

    def setUp(self):
        cache.clear()
        self.api = APIClient()
        self.saida = os.environ.get("QA_MATRIZ_JSON")

    # ------------------------------------------------------------------ mecânica
    def matriz(self, operacao, metodo, url, dados, previsto, confirmar=False, nota="", preparar=None, extra=None):
        """
        `previsto`: {perfil: int | set[int]}. `preparar`: callable executada dentro do savepoint
        ANTES da requisição (ex.: forçar o status da OSP). `extra`: callable(resposta, perfil) para
        asserts adicionais nas células que passaram.
        """
        for perfil in PERFIS:
            with self.subTest(operacao=operacao, perfil=perfil):
                usuario = self.usuarios[perfil]
                self.api.force_authenticate(usuario)
                with transaction.atomic():
                    if preparar:
                        preparar()
                    if dados is None:
                        resposta = getattr(self.api, metodo)(url)
                    else:
                        resposta = getattr(self.api, metodo)(url, dados, format="json")
                    transaction.set_rollback(True)
                aceitos = previsto[perfil]
                aceitos = aceitos if isinstance(aceitos, (set, tuple, list)) else {aceitos}
                if self.saida:
                    with open(self.saida, "a", encoding="utf-8") as f:
                        f.write(json.dumps({
                            "grupo": type(self).__name__, "operacao": operacao, "metodo": metodo.upper(),
                            "url": url, "perfil": perfil, "esperado": sorted(aceitos), "obtido": resposta.status_code,
                            "ok": resposta.status_code in aceitos, "confirmar": confirmar, "nota": nota,
                        }, ensure_ascii=False) + "\n")
                self.assertIn(
                    resposta.status_code, aceitos,
                    f"{operacao} [{metodo.upper()} {url}] como {perfil}: esperado {sorted(aceitos)}, "
                    f"obtido {resposta.status_code} -> {getattr(resposta, 'data', '')}",
                )
                if extra and resposta.status_code < 300:
                    extra(resposta, perfil)


# ======================================================================== CADASTROS
class CadastrosPorPerfil(MatrizDePerfisBase):
    """2.2.1 — o parque é cadastrado pela CONTRATADA; cliente só consulta (decisão de 21/09)."""

    def test_leitura_do_parque_e_liberada_a_todos_e_escopada(self):
        d = self.d
        for recurso, pk in (("clientes", d.cliente.pk), ("areas", d.area.pk), ("setores", d.setor.pk),
                            ("equipamentos", d.equipamento.pk), ("rotas", d.rota.pk),
                            ("componentes", d.componente.pk)):
            self.matriz(f"listar {recurso}", "get", f"/api/{recurso}/", None, TODOS_OK)
            self.matriz(f"detalhar {recurso}", "get", f"/api/{recurso}/{pk}/", None, TODOS_OK)

    def test_criacao_so_pelos_internos(self):
        d = self.d
        corpos = {
            "clientes": {"nome": "Cliente Novo QA", "cnpj": "45.723.174/0001-10"},
            "areas": {"cliente": d.cliente.pk, "nome": "Area nova QA"},
            "setores": {"area": d.area.pk, "nome": "Setor novo QA"},
            "equipamentos": {"setor": d.setor.pk, "tag": "NOVO-QA-01", "nome": "Equipamento novo QA"},
            "rotas": {"cliente": d.cliente.pk, "nome": "Rota nova QA"},
            "componentes": {"equipamento": d.equipamento.pk, "nome": "Componente novo QA"},
        }
        for recurso, corpo in corpos.items():
            self.matriz(f"criar {recurso}", "post", f"/api/{recurso}/", corpo, esperado(201, 403))

    def test_alteracao_so_pelos_internos(self):
        d = self.d
        alvos = {"clientes": d.cliente.pk, "areas": d.area.pk, "setores": d.setor.pk,
                 "equipamentos": d.equipamento.pk, "rotas": d.rota.pk, "componentes": d.componente.pk}
        campo = {"clientes": "nome_fantasia", "areas": "nome", "setores": "nome", "equipamentos": "nome",
                 "rotas": "nome", "componentes": "nome"}
        for recurso, pk in alvos.items():
            self.matriz(f"alterar {recurso}", "patch", f"/api/{recurso}/{pk}/", {campo[recurso]: "Alterado QA"},
                        esperado(200, 403))

    def test_exclusao_exige_master_ou_senior_e_cliente_nunca_exclui(self):
        d = self.d
        # Exclusão é lógica (soft-delete). Júnior/Pleno alimentam mas não apagam (docs/permissions).
        previsto = esperado(204, 403, TECNICO=403)
        for recurso, pk in (("equipamentos", d.equipamento2.pk), ("rotas", d.rota.pk), ("areas", d.area.pk),
                            ("componentes", d.componente.pk)):
            self.matriz(f"excluir {recurso}", "delete", f"/api/{recurso}/{pk}/", None, previsto)

    def test_catalogos_de_sistema_so_master_interno_altera(self):
        """2.2.1.5-2.2.1.14: 'dados de sistema' só o Master (interno) cura; Master de CLIENTE não."""
        previsto_escrita = esperado(403, 403, ADMIN=201)
        self.matriz("listar tipos de anomalia", "get", "/api/tipos-anomalia/", None, TODOS_OK)
        self.matriz("listar normas", "get", "/api/normas/", None, TODOS_OK)
        self.matriz("criar tipo de anomalia", "post", "/api/tipos-anomalia/", {"nome": "Anomalia catalogo QA"},
                    previsto_escrita)
        self.matriz("criar tipo de equipamento", "post", "/api/tipos-equipamento/", {"nome": "Tipo QA"}, previsto_escrita)
        self.matriz("criar condicao", "post", "/api/condicoes/", {"nome": "Condicao QA", "sigla": "QA"}, previsto_escrita)

    def test_instrumentos_leitura_geral_escrita_master(self):
        self.matriz("listar instrumentos", "get", "/api/instrumentos/", None, TODOS_OK, confirmar=True,
                    nota="Cliente lê o cadastro de instrumentação (marca/série/calibração) da CONTRATADA. A confirmar.")
        self.matriz("criar instrumento", "post", "/api/instrumentos/",
                    {"tipo": "Coletor", "marca": "QA", "modelo": "Q1", "numero_serie": "QA-0001"},
                    esperado(403, 403, ADMIN=201))

    def test_criterios_de_vibracao_so_equipe_interna(self):
        self.matriz("listar criterios de vibracao", "get", "/api/criterios-vibracao/", None, esperado(200, 403))
        self.matriz("alterar criterio de vibracao", "patch", "/api/criterios-vibracao/1/", {"fonte": "x"},
                    esperado(403, 403, ADMIN={200, 404}))

    def test_empresas_contratadas_so_equipe_interna(self):
        """
        Cadastro do PRESTADOR (CNPJ, e-mail e contato do gestor da CONTRATADA).
        Na linha de base desta homologação o cliente recebia 200 e lia o cadastro inteiro; o agente de
        segurança restringiu a rota à equipe interna (achado A-05). O teste fixa o comportamento corrigido.
        """
        self.matriz("listar empresas contratadas", "get", "/api/empresas/", None, esperado(200, 403))
        self.matriz("criar empresa", "post", "/api/empresas/", {"nome": "Contratada QA", "cnpj": "45.723.174/0001-10"},
                    esperado(201, 403))


# ======================================================================== COLETAS
class ColetasPorPerfil(MatrizDePerfisBase):
    """2.3 — lançar medição é trabalho técnico da CONTRATADA; cliente consulta o resultado."""

    def _liberar_para_cliente(self):
        """S-24: o cliente só lê rota transferida e achado confirmado para ele (e relatório finalizado)."""
        d = self.d
        Carregamento.objects.filter(pk=d.carregamento.pk).update(status=StatusCarregamento.TRANSFERIDA)
        Achado.objects.filter(pk=d.achado.pk).update(visivel_cliente=True)
        rel_fluido = d.coleta_fluido.item.carregamento.relatorio
        rel_fluido.data_finalizacao = date(2026, 10, 21)
        rel_fluido.save(update_fields=["data_finalizacao"])

    def test_rascunhos_internos_ficam_fora_da_api_do_cliente(self):
        """S-24: antes da liberação, cliente recebe 404 (não 403) nas rotas de rascunho; interno continua lendo."""
        d = self.d
        rascunhos = (f"/api/carregamentos/{d.carregamento.pk}/", f"/api/achados/{d.achado.pk}/",
                     f"/api/coletas-fluido/{d.coleta_fluido.pk}/", f"/api/resultados-ensaio/{d.resultado_ensaio.pk}/")
        for url in rascunhos:
            self.matriz(f"ler rascunho {url}", "get", url, None, esperado(200, 404))

    def test_leitura(self):
        d = self.d
        self._liberar_para_cliente()
        for url in ("/api/inspecoes/", f"/api/inspecoes/{d.inspecao.pk}/", "/api/medicoes-vibracao/",
                    f"/api/medicoes-vibracao/{d.vibracao.pk}/", "/api/medicoes-termografia/",
                    f"/api/medicoes-termografia/{d.termografia.pk}/", "/api/medicoes-tecnicas/",
                    f"/api/medicoes-tecnicas/{d.tecnica.pk}/", "/api/relatorios-inspecao/",
                    f"/api/relatorios-inspecao/{d.relatorio.pk}/", "/api/carregamentos/",
                    f"/api/carregamentos/{d.carregamento.pk}/", "/api/itens-inspecao/", "/api/achados/",
                    f"/api/achados/{d.achado.pk}/", "/api/eventos-preditivos/",
                    f"/api/medicoes-vibracao/{d.vibracao.pk}/analise-preditiva/"):
            self.matriz(f"ler {url}", "get", url, None, TODOS_OK)

    def test_documentos_do_relatorio_de_rotas_para_todos(self):
        d = self.d
        self.matriz("secao C do relatorio", "get", f"/api/relatorios-inspecao/{d.relatorio.pk}/secao-c/", None, TODOS_OK)
        self.matriz("dossie do relatorio", "get", f"/api/relatorios-inspecao/{d.relatorio.pk}/dossie/", None,
                    esperado({200, 409}, {200, 409}))

    def test_criar_inspecao_e_medicoes(self):
        d, eq = self.d, self.d.equipamento
        self.matriz("criar inspecao", "post", "/api/inspecoes/",
                    {"cliente": d.cliente.pk, "tipo_analise": "VIBRACAO", "data": "2026-10-28"}, esperado(201, 403))
        self.matriz("criar medicao de vibracao", "post", "/api/medicoes-vibracao/",
                    {"inspecao": d.inspecao.pk, "equipamento": eq.pk, "ponto_medicao": "Novo ponto", "direcao": "V",
                     "velocidade_rms": "1.00", "rotacao_rpm": 1800}, esperado(201, 403))
        self.matriz("criar medicao termografica", "post", "/api/medicoes-termografia/",
                    {"inspecao": d.inspecao_termo.pk, "equipamento": d.equipamento2.pk, "ponto_medicao": "Quadro",
                     "sistema": "ELETRICO", "temperatura_ponto": "50", "temperatura_referencia": "40",
                     "emissividade": "0.95"}, esperado(201, 403))
        self.matriz("criar medicao tecnica (sensitiva)", "post", "/api/medicoes-tecnicas/",
                    {"inspecao": d.inspecao_sens.pk, "equipamento": d.equipamento2.pk, "ponto_medicao": "Ponto novo",
                     "grandeza": "Parecer", "subtipo": "SENSITIVA", "parametros": {"criticidade": "NORMAL"}},
                    esperado(201, 403))

    def test_alterar_e_excluir(self):
        d = self.d
        self.matriz("alterar inspecao", "patch", f"/api/inspecoes/{d.inspecao.pk}/", {"observacoes": "Alterada QA"},
                    esperado(200, 403))
        self.matriz("alterar medicao de vibracao", "patch", f"/api/medicoes-vibracao/{d.vibracao.pk}/",
                    {"ponto_medicao": "Ponto renomeado"}, esperado(200, 403))
        # Inspeção SEM registros: Master/Sênior excluem; Pleno não; cliente nunca.
        self.matriz("excluir inspecao vazia", "delete", f"/api/inspecoes/{self.inspecao_vazia.pk}/", None,
                    esperado(204, 403, TECNICO=403))
        # Inspeção COM medições/laudo/OSP é preservada (400 para quem tem direito de excluir).
        self.matriz("excluir inspecao com historico", "delete", f"/api/inspecoes/{d.inspecao.pk}/", None,
                    esperado(400, 403, TECNICO=403))
        self.matriz("excluir medicao", "delete", f"/api/medicoes-vibracao/{d.vibracao.pk}/", None,
                    esperado(400, 403, TECNICO=403))
        self.matriz("alterar achado", "patch", f"/api/achados/{d.achado.pk}/", {"observacao": "x"},
                    esperado({200, 400}, 403))
        self.matriz("excluir achado", "delete", f"/api/achados/{d.achado.pk}/", None,
                    esperado({204, 400}, 403, TECNICO=403))

    def test_acoes_da_folha_de_campo_so_internas(self):
        d = self.d
        self.matriz("transferir rota", "post", f"/api/carregamentos/{d.carregamento.pk}/transferir/", {},
                    esperado({200, 400}, 403))
        self.matriz("descartar rota", "post", f"/api/carregamentos/{d.carregamento.pk}/descartar/", {},
                    esperado(204, 403))
        self.matriz("definir condicao em lote", "post", f"/api/carregamentos/{d.carregamento.pk}/definir-condicao/",
                    {"itens": [d.item.pk], "condicao": d.item.condicao_id}, esperado({200, 400}, 403))
        self.matriz("alterar item da folha", "patch", f"/api/itens-inspecao/{d.item.pk}/", {"ordem": 5},
                    esperado(200, 403))

    def test_ensaios_fluidos_e_corretiva(self):
        d = self.d
        self._liberar_para_cliente()
        for url in (f"/api/coletas-fluido/{d.coleta_fluido.pk}/", f"/api/resultados-ensaio/{d.resultado_ensaio.pk}/",
                    "/api/fluidos-inspecao/", "/api/transformadores-inspecao/", "/api/fluidos-historico/",
                    f"/api/servicos/{d.servico.pk}/", f"/api/servicos/{d.servico.pk}/relatorio/",
                    "/api/balanceamento-planos/", "/api/economias/", "/api/atividades-corretivas/"):
            self.matriz(f"ler {url}", "get", url, None, TODOS_OK)
        self.matriz("alterar coleta de fluido", "patch", f"/api/coletas-fluido/{d.coleta_fluido.pk}/",
                    {"observacoes": "x"}, esperado({200, 400}, 403))
        self.matriz("excluir resultado de ensaio", "delete", f"/api/resultados-ensaio/{d.resultado_ensaio.pk}/", None,
                    esperado({204, 400}, 403, TECNICO=403))
        self.matriz("alterar servico corretivo", "patch", f"/api/servicos/{d.servico.pk}/", {"observacoes": "x"},
                    esperado(200, 403))
        self.matriz("alterar economia", "patch", f"/api/economias/{d.economia.pk}/", {"custo_kwh": "0.40"},
                    esperado({200, 400}, 403))

    def test_catalogos_do_ensaio_leitura_geral(self):
        self.matriz("listar ensaios", "get", "/api/ensaios/", None, TODOS_OK)
        self.matriz("listar parametros de ensaio", "get", "/api/parametros-ensaio/", None, TODOS_OK)
        self.matriz("listar referencias de parametro", "get", "/api/referencias-parametro/", None, esperado(200, 403))


# ======================================================================== OSP
class OSPPorPerfil(MatrizDePerfisBase):
    """2.6 — fluxo da OSP: status só por /status/; aprovação pelo cliente depende da chave."""

    def _forcar(self, status):
        return lambda: OrdemServico.objects.filter(pk=self.d.osp.pk).update(status=status)

    def test_leitura(self):
        osp = self.d.osp
        for url in ("/api/osps/", f"/api/osps/{osp.pk}/", f"/api/osps/{osp.pk}/historico/",
                    "/api/osps/?sla_vencido=true", f"/api/osps/?status=ABERTA"):
            self.matriz(f"ler {url}", "get", url, None, TODOS_OK)

    def test_criacao_so_pelos_internos(self):
        d = self.d
        self.matriz("abrir OSP manual", "post", "/api/osps/",
                    {"cliente": d.cliente.pk, "equipamento": d.equipamento2.pk, "inspecao": d.inspecao_sens.pk,
                     "titulo": "OSP manual QA"},
                    esperado(201, 403))

    def test_nova_osp_pela_tela_nao_exige_inspecao(self):
        """
        O formulário "Nova OSP" do painel (frontend/src/app/(admin)/osps/osp-form.tsx) envia cliente,
        equipamento, título e campos técnicos — SEM `inspecao` (a OSP manual não nasce de uma coleta).
        O modelo aceita `inspecao` nulo; a API tem de aceitar o mesmo corpo.
        """
        d = self.d
        corpo = {"cliente": d.cliente.pk, "equipamento": d.equipamento2.pk, "titulo": "OSP aberta pela tela",
                 "grau_risco": "GR3", "componente": "", "anomalia": "Ruido", "recomendacao": "Inspecionar",
                 "observacao": "", "descricao_corretiva": "", "acompanhamento": "ABERTA", "resultado_confirmacao": "PENDENTE",
                 "amplitude_velocidade": None, "amplitude_aceleracao": None}
        self.api.force_authenticate(self.usuarios["GESTOR"])
        r = self.api.post("/api/osps/", corpo, format="json")
        self.assertEqual(r.status_code, 201, f"criar OSP manual pela tela falhou: {r.status_code} {r.data}")

    def test_edicao_campos_tecnicos_e_prazo(self):
        osp = self.d.osp
        self.matriz("alterar descricao (campo tecnico)", "patch", f"/api/osps/{osp.pk}/",
                    {"descricao": "Descricao revisada QA"}, esperado(200, 200),
                    confirmar=True,
                    nota="Cliente recebe 200, mas o campo é descartado (somente leitura p/ o Portal). Teste de conteúdo em ClienteNaoTocaNoDiagnostico.",
                    extra=lambda r, p: self.assertEqual(
                        r.data["descricao"] == "Descricao revisada QA", p in INTERNOS, f"{p}: descrição"))
        self.matriz("alterar prazo SLA", "patch", f"/api/osps/{osp.pk}/", {"sla_data": "2027-01-15"},
                    esperado(200, 200, TECNICO=403),
                    extra=lambda r, p: self.assertEqual(
                        r.data["sla_data"] == "2027-01-15", p in ("ADMIN", "GESTOR"), f"{p}: sla_data"))

    def test_retorno_do_cliente(self):
        osp = self.d.osp
        self.matriz("cliente devolve descricao da corretiva", "patch", f"/api/osps/{osp.pk}/",
                    {"descricao_corretiva": "Rolamento trocado"}, esperado(200, 200), confirmar=True,
                    nota="Qualquer perfil de cliente (inclusive Manutentor e Gestor Local) pode devolver retorno e CUSTOS; "
                         "docs/15 só restringe a mudança de status. A confirmar quem pode informar custo real.",
                    extra=lambda r, p: self.assertEqual(r.data["descricao_corretiva"], "Rolamento trocado"))
        self.matriz("cliente informa custo real", "patch", f"/api/osps/{osp.pk}/", {"custo_real": "1234.50"},
                    esperado(200, 200), confirmar=True,
                    nota="Custo real alimenta o ROI da Seção D; hoje qualquer perfil de cliente informa.")

    def test_exclusao_nunca(self):
        osp = self.d.osp
        # Quem tem direito de excluir recebe 405 (OSP é cancelada, não apagada); os demais, 403.
        self.matriz("excluir OSP", "delete", f"/api/osps/{osp.pk}/", None, esperado(405, 403, TECNICO=403))

    def test_transicoes_de_status_por_perfil(self):
        osp = self.d.osp
        url = f"/api/osps/{osp.pk}/status/"
        internos_todos = esperado(200, 403)
        gestao = esperado(200, 403, TECNICO=403)
        self.matriz("ABERTA -> EM_ANALISE", "patch", url, {"status": "EM_ANALISE"}, internos_todos,
                    preparar=self._forcar("ABERTA"))
        self.matriz("EM_ANALISE -> EM_EXECUCAO", "patch", url, {"status": "EM_EXECUCAO"}, internos_todos,
                    preparar=self._forcar("EM_ANALISE"))
        self.matriz("EM_EXECUCAO -> AGUARDANDO_APROVACAO", "patch", url, {"status": "AGUARDANDO_APROVACAO"},
                    internos_todos, preparar=self._forcar("EM_EXECUCAO"))
        self.matriz("AGUARDANDO_APROVACAO -> FINALIZADA (aprovar)", "patch", url, {"status": "FINALIZADA"}, gestao,
                    preparar=self._forcar("AGUARDANDO_APROVACAO"))
        self.matriz("AGUARDANDO_APROVACAO -> EM_EXECUCAO sem motivo (rejeitar)", "patch", url,
                    {"status": "EM_EXECUCAO"}, esperado(400, 403, TECNICO=403),
                    preparar=self._forcar("AGUARDANDO_APROVACAO"))
        self.matriz("AGUARDANDO_APROVACAO -> EM_EXECUCAO com motivo (rejeitar)", "patch", url,
                    {"status": "EM_EXECUCAO", "motivo": "Falta evidencia"}, gestao,
                    preparar=self._forcar("AGUARDANDO_APROVACAO"))
        self.matriz("cancelar com motivo", "patch", url, {"status": "CANCELADA", "motivo": "Duplicada"}, gestao,
                    preparar=self._forcar("ABERTA"))
        self.matriz("cancelar sem motivo", "patch", url, {"status": "CANCELADA"}, esperado(400, 403, TECNICO=403),
                    preparar=self._forcar("ABERTA"))
        self.matriz("reabrir FINALIZADA", "patch", url, {"status": "ABERTA", "motivo": "Falha voltou"}, gestao,
                    preparar=self._forcar("FINALIZADA"))
        self.matriz("transicao invalida ABERTA -> FINALIZADA", "patch", url, {"status": "FINALIZADA"},
                    esperado(409, 403, TECNICO=403), preparar=self._forcar("ABERTA"))
        self.matriz("status inexistente", "patch", url, {"status": "INVENTADO"}, esperado(400, 400))

    @override_settings(OSP_APROVACAO_PELO_CLIENTE=True)
    def test_aprovacao_pelo_cliente_habilitada(self):
        """Com OSP_APROVACAO_PELO_CLIENTE=true: Gestor Corp., Gestor Local e PCM aprovam; Manutentor nunca."""
        url = f"/api/osps/{self.d.osp.pk}/status/"
        previsto = esperado(200, 200, TECNICO=403, CLIENTE_MANUT=403)
        self.matriz("aprovar (chave do cliente ligada)", "patch", url, {"status": "FINALIZADA"}, previsto,
                    confirmar=True, nota="Quem aprova a execução ainda não foi respondido pelo cliente (docs/15 §4 item 1).",
                    preparar=self._forcar("AGUARDANDO_APROVACAO"))
        self.matriz("cancelar (chave do cliente ligada)", "patch", url, {"status": "CANCELADA", "motivo": "x"},
                    esperado(200, 403, TECNICO=403), preparar=self._forcar("ABERTA"))


# ======================================================================== LAUDOS
class LaudosPorPerfil(MatrizDePerfisBase):
    """2.5 — cliente só enxerga laudo EMITIDO (ou cancelado já emitido) do próprio cliente."""

    def test_leitura_de_laudo_emitido(self):
        l = self.d.laudo
        for url in ("/api/laudos/", f"/api/laudos/{l.pk}/", f"/api/laudos/{l.pk}/documento/",
                    f"/api/laudos/{l.pk}/previa/", f"/api/laudos/{l.pk}/relatorio-tecnico/",
                    f"/api/laudos/{l.pk}/versoes/", f"/api/laudos/{l.pk}/anexos/"):
            self.matriz(f"ler {url}", "get", url, None, TODOS_OK)
        # S-24: histórico de decisões do laudo é só da equipe técnica.
        for url in (f"/api/laudos/{l.pk}/eventos/", f"/api/laudos/{l.pk}/historico/"):
            self.matriz(f"ler {url}", "get", url, None, esperado(200, 403))
        self.matriz("baixar PDF emitido", "get", f"/api/laudos/{l.pk}/pdf/", None, TODOS_OK,
                    extra=lambda r, p: self.assertEqual(bytes(r.content), PDF_FALSO))

    def test_rascunho_invisivel_ao_cliente(self):
        r = self.d.laudo_rascunho
        self.matriz("ler rascunho", "get", f"/api/laudos/{r.pk}/", None, esperado(200, 404))
        self.matriz("PDF do rascunho", "get", f"/api/laudos/{r.pk}/pdf/", None, esperado(400, 404))

    def test_lista_do_cliente_so_tem_emitidos(self):
        self.api.force_authenticate(self.usuarios["CLIENTE_PCM"])
        corpo = self.api.get("/api/laudos/").data["results"]
        self.assertEqual({l["status"] for l in corpo}, {"EMITIDO"})
        self.assertNotIn(self.d.laudo_rascunho.pk, [l["id"] for l in corpo])

    def test_gerar_editar_emitir_cancelar_revisar(self):
        d, g = self.d, self.internos["GESTOR"]
        self.matriz("gerar laudo da inspecao", "post", "/api/laudos/gerar/", {"inspecao": d.inspecao_sens.pk},
                    esperado(201, 403))
        self.matriz("criar laudo manual", "post", "/api/laudos/",
                    {"inspecao": d.inspecao_sens.pk, "titulo": "Laudo manual QA", "responsavel": g.pk},
                    esperado(201, 403))
        self.matriz("editar rascunho", "patch", f"/api/laudos/{d.laudo_rascunho.pk}/", {"conclusao": "Texto QA"},
                    esperado(200, 403))
        self.matriz("editar laudo emitido", "patch", f"/api/laudos/{d.laudo.pk}/", {"conclusao": "Texto QA"},
                    esperado(400, 403))
        # Só o responsável técnico atribuído aprova a emissão (GESTOR é o responsável na massa).
        with patch("apps.laudos.pdf.gerar_pdf", return_value=PDF_FALSO):
            self.matriz("emitir rascunho", "post", f"/api/laudos/{d.laudo_rascunho.pk}/emitir/", {},
                        esperado(403, 403, GESTOR=200))
        self.matriz("cancelar laudo (responsavel ou Master interno)", "post", f"/api/laudos/{d.laudo.pk}/cancelar/",
                    {"motivo": "Revisao QA"}, esperado(403, 403, ADMIN=200, GESTOR=200))
        self.matriz("revisar laudo emitido", "post", f"/api/laudos/{d.laudo.pk}/revisar/", {"motivo": "Nova coleta"},
                    esperado(201, 403))
        self.matriz("excluir laudo", "delete", f"/api/laudos/{d.laudo.pk}/", None, esperado(400, 403, TECNICO=403))
        self.matriz("anexar evidencia (POST sem arquivo)", "post", f"/api/laudos/{d.laudo_rascunho.pk}/anexos/", {},
                    esperado(400, 403))

    def test_templates_so_internos_e_master_escreve(self):
        self.matriz("listar templates", "get", "/api/templates-laudo/", None, esperado(200, 403))
        self.matriz("criar template", "post", "/api/templates-laudo/", {"nome": "Template QA", "configuracao": {}},
                    esperado(403, 403, ADMIN=201))


# ======================================================================== RELATÓRIOS, PAINÉIS E PORTAL
class RelatoriosEPortalPorPerfil(MatrizDePerfisBase):
    def test_catalogo_e_relatorios_comuns(self):
        self.matriz("catalogo de relatorios", "get", "/api/relatorios/", None, TODOS_OK)
        for key in ("tecnico", "gerencial", "equipamento", "falhas", "historico", "painel-operacional"):
            for formato in ("json", "csv", "xlsx", "pdf"):
                self.matriz(f"relatorio {key} ({formato})", "get", f"/api/relatorios/{key}/?formato={formato}",
                            None, TODOS_OK)

    def test_relatorios_gerenciais_e_financeiros_so_internos(self):
        for key in ("financeiro", "produtividade", "painel-executivo"):
            for formato in ("json", "csv", "xlsx", "pdf"):
                self.matriz(f"relatorio {key} ({formato})", "get", f"/api/relatorios/{key}/?formato={formato}",
                            None, esperado(200, 403), confirmar=(key == "financeiro"),
                            nota="Cliente não vê custos (docs/16 'cliente vê custos?' pendente)." if key == "financeiro" else "")

    def test_paineis(self):
        self.matriz("dashboard operacional", "get", "/api/dashboard/", None, TODOS_OK)
        self.matriz("dashboard executivo", "get", "/api/dashboard/executivo/", None, esperado(200, 403),
                    confirmar=True, nota="Executivo (custos, MTBF/MTTR, performance por unidade) só interno; confirmar com o cliente.")
        self.matriz("visao geral do portal", "get", "/api/portal/visao-geral/", None, TODOS_OK)

    def test_filtros_invalidos_sao_400_para_todos(self):
        self.matriz("filtro de data malformado", "get", "/api/relatorios/tecnico/?data_inicio=ontem", None,
                    esperado(400, 400))
        self.matriz("filtro de cliente malformado", "get", "/api/dashboard/?cliente=abc", None, esperado(400, 400))


# ======================================================================== USUÁRIOS, EQUIPE, NOTIFICAÇÕES
class UsuariosENotificacoesPorPerfil(MatrizDePerfisBase):
    def test_administracao_de_usuarios_so_master_interno(self):
        alvo = self.usuarios["CLIENTE_PCM"].pk
        self.matriz("listar usuarios", "get", "/api/usuarios/", None, esperado(403, 403, ADMIN=200))
        self.matriz("detalhar usuario", "get", f"/api/usuarios/{alvo}/", None, esperado(403, 403, ADMIN=200))
        self.matriz("alterar usuario", "patch", f"/api/usuarios/{alvo}/", {"cargo": "Cargo QA"},
                    esperado(403, 403, ADMIN=200))
        self.matriz("criar usuario direto (deve usar convite)", "post", "/api/usuarios/",
                    {"email": "novo@x.qa", "nome": "Novo"}, esperado(403, 403, ADMIN=405))
        self.matriz("listar solicitacoes de acesso", "get", "/api/solicitacoes-acesso/", None,
                    esperado(403, 403, ADMIN=200))

    def test_minha_equipe_so_cliente_e_so_da_propria_empresa(self):
        self.matriz("listar minha equipe", "get", "/api/minha-equipe/", None, esperado(403, 200))
        self.matriz("convites pendentes da equipe", "get", "/api/minha-equipe/convites/", None, esperado(403, 200))

        def so_a(resposta, perfil):
            emails = {u["email"] for u in resposta.data["results"]}
            self.assertTrue(emails, "equipe vazia")
            self.assertTrue(all(e.endswith("@cliente.qa") and ".a@" in e for e in emails), emails)
        self.matriz("equipe sem usuarios de outro cliente", "get", "/api/minha-equipe/", None,
                    esperado(403, 200), extra=so_a)

    def test_convites(self):
        d = self.d
        convite_pcm_a = {"nome": "Colega", "email": "colega@a.qa", "tipo": "portal", "perfil": "CLIENTE_PCM",
                         "nivel": "PLENO", "cliente": d.cliente.pk}
        # Só quem é Master convida: ADMIN (interno) e Gestor Corporativo (cliente, na própria empresa).
        self.matriz("convidar colega do cliente A", "post", "/api/auth/convites/", convite_pcm_a,
                    esperado(403, 403, ADMIN=201, CLIENTE_CORP=201))
        self.matriz("convidar para OUTRO cliente", "post", "/api/auth/convites/",
                    {**convite_pcm_a, "cliente": self.b.cliente.pk}, esperado(403, 403, ADMIN=201, CLIENTE_CORP=403))
        self.matriz("cliente tenta convidar Master", "post", "/api/auth/convites/", {**convite_pcm_a, "nivel": "MASTER"},
                    esperado(403, 403, ADMIN=201, CLIENTE_CORP=403))
        self.matriz("cliente tenta convidar interno", "post", "/api/auth/convites/",
                    {"nome": "Intruso", "email": "intruso@x.qa", "tipo": "admin", "perfil": "ADMIN", "nivel": "MASTER"},
                    esperado(403, 403, ADMIN=201, CLIENTE_CORP=403))

    def test_convite_por_tecnico_master_escala_privilegio(self):
        """
        A permissão de convidar olha só `nivel == MASTER`, não o perfil. Um TECNICO com nível Master
        (perfil de menor privilégio) consegue convidar um ADMIN. Documenta o comportamento ATUAL.
        A CONFIRMAR com o cliente: Master de qualquer perfil interno concede acesso Administrador?
        """
        from .test_homologacao_base import criar_usuario

        tecnico_master = criar_usuario("tecnico.master@thermo.qa", "TECNICO", "MASTER")
        self.api.force_authenticate(tecnico_master)
        r = self.api.post("/api/auth/convites/", {"nome": "Novo Admin", "email": "novo.admin@x.qa", "tipo": "admin",
                                                   "perfil": "ADMIN", "nivel": "MASTER"}, format="json")
        self.assertEqual(r.status_code, 201, "comportamento atual (a confirmar): Técnico-Master convida Administrador")

    def test_notificacoes_proprias(self):
        self.matriz("listar notificacoes", "get", "/api/notificacoes/", None, TODOS_OK)
        self.matriz("resumo de nao lidas", "get", "/api/notificacoes/resumo/", None, TODOS_OK)
        self.matriz("ler preferencias", "get", "/api/notificacoes/preferencias/", None, TODOS_OK)
        self.matriz("alterar preferencias", "put", "/api/notificacoes/preferencias/", {"email": False}, TODOS_OK)
        self.matriz("marcar todas como lidas", "post", "/api/notificacoes/marcar-todas/", {}, TODOS_OK)
        self.matriz("criar notificacao por API", "post", "/api/notificacoes/", {"titulo": "x"},
                    {p: 405 for p in PERFIS})

    def test_notificacao_de_outro_usuario_do_mesmo_cliente_nao_e_visivel(self):
        # a notificação da massa pertence ao PCM; Gestor Local/Manutentor do mesmo cliente não a enxergam
        notif = self.d.notificacao
        for perfil in PERFIS:
            self.api.force_authenticate(self.usuarios[perfil])
            r = self.api.get(f"/api/notificacoes/{notif.pk}/")
            self.assertEqual(r.status_code, 200 if perfil == "CLIENTE_PCM" else 404, perfil)

    def test_dados_do_proprio_usuario(self):
        self.matriz("/auth/me", "get", "/api/auth/me/", None, TODOS_OK)
        self.matriz("resumo de seguranca", "get", "/api/auth/seguranca/", None, TODOS_OK)
        self.matriz("sessoes ativas", "get", "/api/auth/seguranca/sessoes/", None, TODOS_OK)


class DocumentacaoDosPerfis(TestCase):
    def test_existem_sete_perfis_sendo_quatro_de_cliente(self):
        """O contrato (2.1.2.1 a 2.1.2.7) lista 3 internos + 4 de cliente. Não há 'cinco perfis de cliente'."""
        from apps.accounts.models import PERFIS_CLIENTE, PERFIS_INTERNOS, Perfil

        self.assertEqual(len(Perfil.values), 7)
        self.assertEqual((len(PERFIS_INTERNOS), len(PERFIS_CLIENTE)), (3, 4))
        self.assertEqual(
            sorted(p.value for p in PERFIS_CLIENTE),
            ["CLIENTE_CORP", "CLIENTE_LOCAL", "CLIENTE_MANUT", "CLIENTE_PCM"],
        )
