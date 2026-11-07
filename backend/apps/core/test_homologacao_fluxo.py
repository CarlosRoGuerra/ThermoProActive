"""
Pré-homologação (QA) — fluxo ponta a ponta pela API REAL, com sessão em cookie.

login (cookie HttpOnly + CSRF) -> cadastro mínimo -> coleta com medição crítica
-> motor de regras classifica -> OSP gerada automaticamente -> transições de
status com histórico -> notificação/entrega registradas -> laudo emitido (renderer
do PDF mockado) -> portal do cliente vê o que é dele -> relatórios/exportações
com escopo -> logout revoga a sessão.

Todas as chamadas passam por `APIClient(enforce_csrf_checks=True)` com os cookies
`tpa_access`/`tpa_refresh`; nada usa `force_authenticate`.

Execução: cd backend && python manage.py test apps.core.test_homologacao_fluxo --parallel 1
"""
import csv
import io
import re
from unittest.mock import patch

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from openpyxl import load_workbook
from rest_framework.test import APIClient

from apps.cadastros.models import Cliente
from apps.notificacoes.models import EntregaNotificacao, EventoNotificacao, Notificacao
from apps.osp.models import HistoricoOSP, OrdemServico

from .test_homologacao_base import PDF_FALSO, SENHA, criar_internos, criar_usuario


class Sessao:
    """Cliente HTTP que se comporta como o navegador: cookie de sessão + cabeçalho CSRF."""

    def __init__(self, contexto, email, senha=SENHA):
        self.http = APIClient(enforce_csrf_checks=True)
        self.csrf = self.http.get("/api/auth/csrf/").data["csrfToken"]
        self.resposta_login = self.http.post(
            f"/api/auth/{contexto}/login/", {"email": email, "password": senha},
            format="json", HTTP_X_CSRFTOKEN=self.csrf,
        )

    def get(self, url, **extra):
        return self.http.get(url, **extra)

    def _escrita(self, metodo, url, dados=None, **extra):
        return getattr(self.http, metodo)(url, dados, format="json", HTTP_X_CSRFTOKEN=self.csrf, **extra)

    def post(self, url, dados=None, **extra):
        return self._escrita("post", url, dados, **extra)

    def patch(self, url, dados=None, **extra):
        return self._escrita("patch", url, dados, **extra)

    def delete(self, url, **extra):
        return self._escrita("delete", url, None, **extra)


def texto_pdf(conteudo: bytes) -> str:
    """Extrai o texto dos fluxos do ReportLab (ASCII85 + Flate)."""
    import base64
    import zlib

    partes = []
    for bruto in re.findall(rb"stream\r?\n(.*?)endstream", conteudo, re.S):
        try:
            partes.append(zlib.decompress(base64.a85decode(b"<~" + bruto.strip(), adobe=True)).decode("latin-1"))
        except Exception:
            partes.append(bruto.decode("latin-1"))
    return "\n".join(partes)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class FluxoPontaAPontaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.internos = criar_internos()
        cls.admin, cls.gestor, cls.tecnico = (cls.internos[p] for p in ("ADMIN", "GESTOR", "TECNICO"))
        # O cliente B existe só para provar que o fluxo do A não o toca nem o enxerga.
        cls.cliente_b = Cliente.objects.create(nome="Industria B Vizinha", cnpj="99.999.999/0001-99")

    def setUp(self):
        cache.clear()  # o login tem throttle por IP

    # ------------------------------------------------------------------ utilidades
    def logar(self, contexto, usuario):
        s = Sessao(contexto, usuario.email)
        self.assertEqual(s.resposta_login.status_code, 200, s.resposta_login.data)
        return s

    def ok(self, resposta, esperado=200, passo=""):
        self.assertEqual(resposta.status_code, esperado, f"[{passo}] {getattr(resposta, 'data', resposta.content)}")
        return resposta

    # ------------------------------------------------------------------ o fluxo
    def test_fluxo_completo_login_coleta_osp_laudo_portal_relatorios(self):
        # ============ 1. LOGIN REAL (cookie HttpOnly + CSRF) ============
        admin = Sessao("admin", self.admin.email)
        self.assertEqual(admin.resposta_login.status_code, 200, admin.resposta_login.data)
        cookies = admin.resposta_login.cookies
        for nome in ("tpa_access", "tpa_refresh"):
            self.assertIn(nome, cookies, "cookie de sessão ausente")
            self.assertTrue(cookies[nome]["httponly"], f"{nome} deve ser HttpOnly")
            self.assertEqual(cookies[nome]["samesite"], "Lax")
        self.assertNotIn("access", admin.resposta_login.data)  # token nunca no corpo
        self.assertNotIn("refresh", admin.resposta_login.data)
        eu = self.ok(admin.get("/api/auth/me/"), passo="me").data
        self.assertEqual((eu["perfil"], eu["email"]), ("ADMIN", self.admin.email))

        # escrita sem o cabeçalho CSRF é recusada mesmo com sessão válida
        sem_csrf = admin.http.post("/api/clientes/", {"nome": "X", "cnpj": "1"}, format="json")
        self.assertEqual(sem_csrf.status_code, 403)

        # ============ 2. CADASTRO MÍNIMO (API, perfil ADMIN) ============
        cliente = self.ok(admin.post("/api/clientes/", {
            "nome": "Industria Homologacao A", "cnpj": "12.345.678/0001-95", "unidade_negocio": "Matriz",
        }), 201, "cliente").data
        area = self.ok(admin.post("/api/areas/", {"cliente": cliente["id"], "nome": "Utilidades"}), 201, "area").data
        setor = self.ok(admin.post("/api/setores/", {"area": area["id"], "nome": "Bombas"}), 201, "setor").data
        eq = self.ok(admin.post("/api/equipamentos/", {
            "setor": setor["id"], "tag": "BB-HOM-01", "nome": "Bomba de processo",
            "classe_iso": "G2", "tipo_base": "RIGIDA",
        }), 201, "equipamento").data
        rota = self.ok(admin.post("/api/rotas/", {
            "cliente": cliente["id"], "nome": "Rota mensal", "equipamentos": [eq["id"]],
        }), 201, "rota").data
        self.assertEqual(rota["qtd_equipamentos"], 1)
        pcm = criar_usuario("pcm.hom@cliente.qa", "CLIENTE_PCM", "PLENO", cliente=Cliente.objects.get(pk=cliente["id"]))
        manut = criar_usuario("manut.hom@cliente.qa", "CLIENTE_MANUT", "JUNIOR", cliente=pcm.cliente)

        # ============ 3. COLETA (técnico, medição normal + crítica) ============
        tecnico = self.logar("admin", self.tecnico)
        insp = self.ok(tecnico.post("/api/inspecoes/", {
            "cliente": cliente["id"], "tipo_analise": "VIBRACAO", "data": "2026-10-27",
            "observacoes": "Rota mensal de vibracao",
        }), 201, "inspecao").data
        self.assertEqual(insp["tecnico"], self.tecnico.pk)  # assume o usuário autenticado
        medicao_ok = self.ok(tecnico.post("/api/medicoes-vibracao/", {
            "inspecao": insp["id"], "equipamento": eq["id"], "ponto_medicao": "Mancal LOA",
            "direcao": "H", "velocidade_rms": "1.00", "rotacao_rpm": 1800,
        }), 201, "medicao normal").data
        self.assertEqual(medicao_ok["criticidade"], "NORMAL")
        self.assertFalse(OrdemServico.objects.filter(cliente_id=cliente["id"]).exists(), "medição normal não gera OSP")

        # ============ 4. ANÁLISE: motor de regras classifica a criticidade ============
        with self.captureOnCommitCallbacks(execute=True):
            critica = self.ok(tecnico.post("/api/medicoes-vibracao/", {
                "inspecao": insp["id"], "equipamento": eq["id"], "ponto_medicao": "Mancal LA",
                "direcao": "H", "velocidade_rms": "8.00", "rotacao_rpm": 1800,
            }), 201, "medicao critica").data
        self.assertEqual(critica["criticidade"], "CRITICO")
        self.assertEqual(critica["zona_iso"], "D")
        self.assertEqual(critica["classificacao_status"], "CLASSIFICADA")
        analise = self.ok(tecnico.get(f"/api/medicoes-vibracao/{critica['id']}/analise-preditiva/"), passo="analise").data
        self.assertEqual(analise["status"], "CLASSIFICADA")
        self.assertEqual(analise["snapshot"]["motor"], "vibracao_v2")  # regra e entradas congeladas (auditoria)
        insp_det = self.ok(tecnico.get(f"/api/inspecoes/{insp['id']}/"), passo="inspecao").data
        self.assertEqual(insp_det["criticidade_maxima"], "CRITICO")
        self.assertEqual(insp_det["qtd_medicoes"], 2)

        # ============ 5. OSP GERADA AUTOMATICAMENTE ============
        osps = self.ok(tecnico.get(f"/api/osps/?equipamento={eq['id']}"), passo="osps").data["results"]
        self.assertEqual(len(osps), 1, "exatamente uma OSP automática")
        osp = osps[0]
        self.assertTrue(osp["gerada_automaticamente"])
        self.assertEqual((osp["status"], osp["prioridade"], osp["criticidade_origem"]), ("ABERTA", "ALTA", "CRITICO"))
        self.assertEqual(osp["responsavel"], self.tecnico.pk)
        self.assertEqual(osp["cliente"], cliente["id"])
        self.assertEqual(osp["equipamento_tag"], "BB-HOM-01")
        self.assertIsNotNone(osp["sla_data"], "SLA definido")
        # idempotência: nova medição crítica na mesma inspeção/equipamento não duplica
        with self.captureOnCommitCallbacks(execute=True):
            self.ok(tecnico.post("/api/medicoes-vibracao/", {
                "inspecao": insp["id"], "equipamento": eq["id"], "ponto_medicao": "Mancal LOA", "direcao": "V",
                "velocidade_rms": "9.00", "rotacao_rpm": 1800,
            }), 201, "segunda critica")
        self.assertEqual(OrdemServico.objects.filter(cliente_id=cliente["id"]).count(), 1)
        historico = self.ok(tecnico.get(f"/api/osps/{osp['id']}/historico/"), passo="historico inicial").data
        self.assertEqual([h["tipo"] for h in historico], ["CRIACAO"])
        self.assertEqual(historico[0]["ator_nome"], "Sistema")

        # ============ 6. NOTIFICAÇÕES REGISTRADAS (alerta interno + entrega por canal) ============
        nova = Notificacao.objects.filter(evento=EventoNotificacao.NOVA_OSP)
        self.assertEqual(set(nova.values_list("destinatario_id", flat=True)), {pcm.pk, self.tecnico.pk})
        self.assertFalse(nova.filter(destinatario=manut).exists(), "manutentor não recebe 'Nova OSP' (premissa docs/17)")
        entregas = EntregaNotificacao.objects.filter(notificacao__in=nova, canal="EMAIL")
        self.assertEqual(entregas.count(), 2)
        # E-mail em backend de desenvolvimento = SIMULADO (nunca "ENVIADO")
        self.assertEqual(set(entregas.values_list("status", flat=True)), {"SIMULADO"})
        self.assertFalse(EntregaNotificacao.objects.filter(status="ENVIADO").exists())

        # ============ 7. TRANSIÇÕES DE STATUS (somente por /status/) + histórico ============
        # PATCH genérico não muda status
        self.ok(tecnico.patch(f"/api/osps/{osp['id']}/", {"status": "FINALIZADA"}), 200, "patch generico")
        self.assertEqual(OrdemServico.objects.get(pk=osp["id"]).status, "ABERTA")
        # técnico não pode pular etapas nem aprovar
        self.assertEqual(tecnico.patch(f"/api/osps/{osp['id']}/status/", {"status": "FINALIZADA"}).status_code, 403)
        self.assertEqual(tecnico.patch(f"/api/osps/{osp['id']}/status/", {"status": "EM_EXECUCAO"}).status_code, 409)
        for destino in ("EM_ANALISE", "EM_EXECUCAO", "AGUARDANDO_APROVACAO"):
            r = self.ok(tecnico.patch(f"/api/osps/{osp['id']}/status/", {"status": destino}), 200, destino)
            self.assertEqual((r.data["status"], r.data["alterado"]), (destino, True))
        # repetir é no-op (não duplica histórico)
        r = self.ok(tecnico.patch(f"/api/osps/{osp['id']}/status/", {"status": "AGUARDANDO_APROVACAO"}), 200, "noop")
        self.assertFalse(r.data["alterado"])
        # aprovação pendente notificou a gestão
        self.assertTrue(Notificacao.objects.filter(
            evento=EventoNotificacao.APROVACAO_PENDENTE, destinatario=self.gestor).exists())
        # o cliente (PCM) não aprova por padrão (OSP_APROVACAO_PELO_CLIENTE=False) e o técnico não finaliza
        pcm_s = self.logar("portal", pcm)
        negado = pcm_s.patch(f"/api/osps/{osp['id']}/status/", {"status": "FINALIZADA"})
        self.assertEqual(negado.status_code, 403)
        self.assertEqual(negado.data["codigo"], "sem_permissao")
        # cancelar exige motivo
        gestor = self.logar("admin", self.gestor)
        self.assertEqual(gestor.patch(f"/api/osps/{osp['id']}/status/", {"status": "CANCELADA"}).status_code, 400)
        # retorno de informação do cliente (único campo editável por ele) é auditado
        retorno = self.ok(pcm_s.patch(f"/api/osps/{osp['id']}/", {
            "descricao_corretiva": "Rolamento substituido", "titulo": "tentativa de alterar diagnostico",
        }), 200, "retorno cliente")
        self.assertEqual(retorno.data["descricao_corretiva"], "Rolamento substituido")
        self.assertNotEqual(retorno.data["titulo"], "tentativa de alterar diagnostico")
        fin = self.ok(gestor.patch(f"/api/osps/{osp['id']}/status/", {"status": "FINALIZADA"}), 200, "aprova")
        self.assertEqual(fin.data["status"], "FINALIZADA")
        self.assertEqual(fin.data["aprovado_por"], self.gestor.pk)
        self.assertIsNotNone(fin.data["aprovado_em"])
        # OSP não se exclui
        self.assertEqual(gestor.delete(f"/api/osps/{osp['id']}/").status_code, 405)
        hist = self.ok(gestor.get(f"/api/osps/{osp['id']}/historico/"), passo="historico final").data
        self.assertEqual(
            [(h["tipo"], h["status_novo"]) for h in hist],
            [("CRIACAO", "ABERTA"), ("STATUS", "EM_ANALISE"), ("STATUS", "EM_EXECUCAO"),
             ("STATUS", "AGUARDANDO_APROVACAO"), ("RETORNO_CLIENTE", "AGUARDANDO_APROVACAO"),
             ("APROVACAO", "FINALIZADA")],
        )
        self.assertEqual(hist[-1]["ator_perfil"], "GESTOR")
        self.assertEqual(HistoricoOSP.objects.filter(osp_id=osp["id"]).count(), len(hist))

        # ============ 8. LAUDO: gerar -> revisar rascunho -> emitir (PDF mockado) ============
        rascunho = self.ok(gestor.post("/api/laudos/gerar/", {"inspecao": insp["id"]}), 201, "gerar laudo").data
        self.assertEqual((rascunho["status"], rascunho["criticidade_geral"]), ("RASCUNHO", "CRITICO"))
        self.assertTrue(rascunho["numero"].startswith("RT.AV."))
        self.assertIn("BB-HOM-01", rascunho["diagnostico"])
        # rascunho é invisível ao cliente
        pcm_lista = self.ok(pcm_s.get("/api/laudos/"), passo="laudos cliente antes").data["results"]
        self.assertEqual(pcm_lista, [])
        self.assertEqual(pcm_s.get(f"/api/laudos/{rascunho['id']}/").status_code, 404)
        self.ok(gestor.patch(f"/api/laudos/{rascunho['id']}/", {"conclusao": "Substituir rolamento do mancal LA."}),
                200, "editar rascunho")
        # só o responsável técnico emite; técnico (não responsável) é barrado
        self.assertEqual(tecnico.post(f"/api/laudos/{rascunho['id']}/emitir/").status_code, 403)
        # PDF ainda indisponível antes da emissão
        self.assertEqual(gestor.get(f"/api/laudos/{rascunho['id']}/pdf/").status_code, 400)
        with patch("apps.laudos.pdf.gerar_pdf", return_value=PDF_FALSO) as renderer, \
                self.captureOnCommitCallbacks(execute=True):
            emitido = self.ok(gestor.post(f"/api/laudos/{rascunho['id']}/emitir/"), 200, "emitir").data
        self.assertEqual(renderer.call_count, 1)
        self.assertEqual(emitido["status"], "EMITIDO")
        self.assertTrue(emitido["pdf_disponivel"])
        self.assertEqual(emitido["assinatura"]["usuario_id"], self.gestor.pk)
        self.assertFalse(emitido["assinatura"]["assinatura_criptografica"])
        pdf = self.ok(gestor.get(f"/api/laudos/{rascunho['id']}/pdf/"), passo="pdf")
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertEqual(bytes(pdf.content), PDF_FALSO)
        self.assertEqual(pdf["X-Content-SHA256"], emitido["pdf_hash"])
        self.assertIn("no-store", pdf["Cache-Control"])
        # imutável depois de emitido; reemitir é idempotente
        self.assertEqual(gestor.patch(f"/api/laudos/{rascunho['id']}/", {"conclusao": "x"}).status_code, 400)
        with patch("apps.laudos.pdf.gerar_pdf", return_value=PDF_FALSO) as renderer:
            self.ok(gestor.post(f"/api/laudos/{rascunho['id']}/emitir/"), 200, "reemitir")
        renderer.assert_not_called()
        self.assertEqual(gestor.delete(f"/api/laudos/{rascunho['id']}/").status_code, 400)
        eventos = [e["acao"] for e in self.ok(gestor.get(f"/api/laudos/{rascunho['id']}/eventos/"), passo="eventos").data]
        self.assertEqual(eventos, ["GERADO", "EDITADO", "EMITIDO"])
        # 2.10.2.3: laudo concluído notifica o cliente
        self.assertTrue(Notificacao.objects.filter(evento=EventoNotificacao.LAUDO_CONCLUIDO, destinatario=pcm).exists())

        # ============ 9. PORTAL: o usuário do cliente enxerga o que é dele ============
        self.assertEqual(Sessao("admin", pcm.email).resposta_login.status_code, 401, "cliente não entra no login interno")
        self.assertEqual(Sessao("portal", self.admin.email).resposta_login.status_code, 401, "interno não entra no portal")
        pcm_s = self.logar("portal", pcm)
        eu_cliente = self.ok(pcm_s.get("/api/auth/me/"), passo="me cliente").data
        self.assertEqual((eu_cliente["perfil"], eu_cliente["cliente"]), ("CLIENTE_PCM", cliente["id"]))
        visao = self.ok(pcm_s.get("/api/portal/visao-geral/"), passo="visao geral").data
        self.assertEqual(visao["cliente"]["nome"], "Industria Homologacao A")
        ind = visao["indicadores"]
        self.assertEqual((ind["equipamentos_monitorados"], ind["laudos_disponiveis"], ind["inspecoes"]), (1, 1, 1))
        self.assertEqual(ind["osps_abertas"], 0, "a OSP já foi finalizada")
        self.assertEqual([e["equipamento__tag"] for e in visao["equipamentos_atencao"]], ["BB-HOM-01"])
        self.assertEqual({h["tipo"] for h in visao["historico"]}, {"laudo", "inspecao", "osp"})
        self.assertNotIn("Vizinha", str(visao))
        laudos_cliente = self.ok(pcm_s.get("/api/laudos/"), passo="laudos cliente").data["results"]
        self.assertEqual([l["id"] for l in laudos_cliente], [rascunho["id"]])
        baixado = self.ok(pcm_s.get(f"/api/laudos/{rascunho['id']}/pdf/"), passo="pdf cliente")
        self.assertEqual(bytes(baixado.content), PDF_FALSO)
        # cliente consulta, não escreve no parque
        self.assertEqual(pcm_s.post("/api/equipamentos/", {"setor": setor["id"], "tag": "X", "nome": "X"}).status_code, 403)
        self.assertEqual(pcm_s.post("/api/inspecoes/", {"cliente": cliente["id"], "tipo_analise": "VIBRACAO",
                                                          "data": "2026-10-28"}).status_code, 403)
        self.assertEqual(pcm_s.post(f"/api/laudos/{rascunho['id']}/cancelar/", {"motivo": "x"}).status_code, 403)
        osps_cliente = self.ok(pcm_s.get("/api/osps/"), passo="osps cliente").data["results"]
        self.assertEqual([(o["id"], o["status"]) for o in osps_cliente], [(osp["id"], "FINALIZADA")])
        self.assertEqual(self.ok(pcm_s.get("/api/inspecoes/"), passo="inspecoes cliente").data["count"], 1)
        dash = self.ok(pcm_s.get("/api/dashboard/"), passo="dashboard cliente").data
        self.assertEqual(dash["total_medicoes"], 3)
        self.assertEqual(pcm_s.get("/api/dashboard/executivo/").status_code, 403)
        # notificações do cliente: só as dele, com a entrega por canal
        minhas = self.ok(pcm_s.get("/api/notificacoes/"), passo="notificacoes cliente").data["results"]
        eventos_cliente = {n["evento"] for n in minhas}
        self.assertTrue({"NOVA_OSP", "LAUDO_CONCLUIDO"} <= eventos_cliente, eventos_cliente)
        email = next(e for n in minhas if n["evento"] == "NOVA_OSP" for e in n["entregas"] if e["canal"] == "EMAIL")
        self.assertEqual(email["status"], "SIMULADO")
        resumo = self.ok(pcm_s.get("/api/notificacoes/resumo/"), passo="resumo").data["nao_lidas"]
        self.assertEqual(resumo, len(minhas))
        self.ok(pcm_s.post(f"/api/notificacoes/{minhas[0]['id']}/lida/"), 200, "marcar lida")
        self.assertEqual(pcm_s.get("/api/notificacoes/resumo/").data["nao_lidas"], resumo - 1)

        # ============ 10. RELATÓRIOS E EXPORTAÇÕES (escopo do cliente) ============
        catalogo = {r["key"] for r in self.ok(pcm_s.get("/api/relatorios/"), passo="catalogo").data}
        self.assertTrue({"tecnico", "gerencial", "equipamento", "falhas", "historico"} <= catalogo)
        self.assertFalse({"financeiro", "produtividade", "painel-executivo"} & catalogo)
        previa = self.ok(pcm_s.get("/api/relatorios/tecnico/?formato=json"), passo="previa").data
        self.assertEqual(previa["total_linhas"], 3)
        self.assertEqual({l[2] for l in previa["linhas"]}, {"BB-HOM-01"})
        csv_r = self.ok(pcm_s.get("/api/relatorios/tecnico/?formato=csv"), passo="csv")
        self.assertIn("text/csv", csv_r["Content-Type"])
        self.assertIn('filename="relatorio_tecnico_', csv_r["Content-Disposition"])
        linhas_csv = list(csv.reader(io.StringIO(csv_r.content.decode("utf-8-sig")), delimiter=";"))
        self.assertEqual(linhas_csv[0], previa["colunas"])
        self.assertEqual(len(linhas_csv) - 1, 3)
        xlsx = self.ok(pcm_s.get("/api/relatorios/tecnico/?formato=xlsx"), passo="xlsx")
        self.assertIn("spreadsheetml", xlsx["Content-Type"])
        planilha = [[c.value for c in row] for row in load_workbook(io.BytesIO(xlsx.content)).active.iter_rows()]
        self.assertEqual(len(planilha) - 1, 3)
        self.assertTrue(all(l[2] == "BB-HOM-01" for l in planilha[1:]))
        pdf_r = self.ok(pcm_s.get("/api/relatorios/equipamento/?formato=pdf"), passo="pdf relatorio")
        self.assertTrue(bytes(pdf_r.content).startswith(b"%PDF"))
        self.assertIn("BB-HOM-01", texto_pdf(pdf_r.content))
        # filtros no servidor (400 se malformados) e relatórios restritos
        self.assertEqual(pcm_s.get("/api/relatorios/tecnico/?data_inicio=2026-13-40").status_code, 400)
        self.assertEqual(pcm_s.get("/api/relatorios/tecnico/?formato=docx").status_code, 400)
        self.assertEqual(pcm_s.get("/api/relatorios/nao-existe/").status_code, 404)
        for key in ("financeiro", "painel-executivo", "produtividade"):
            self.assertEqual(pcm_s.get(f"/api/relatorios/{key}/").status_code, 403, key)
        # a equipe interna tem os relatórios financeiros
        fin_r = self.ok(admin.get("/api/relatorios/financeiro/?formato=csv"), passo="financeiro interno")
        self.assertIn("text/csv", fin_r["Content-Type"])
        exec_r = self.ok(admin.get("/api/dashboard/executivo/"), passo="executivo interno").data
        self.assertEqual(exec_r["kpis"]["osps_finalizadas"], 1)

        # ============ 11. LOGOUT revoga a sessão (replay do cookie antigo falha) ============
        token_antigo = pcm_s.http.cookies["tpa_access"].value
        self.assertEqual(pcm_s.post("/api/auth/logout/").status_code, 204)
        self.assertIn(pcm_s.get("/api/auth/me/").status_code, (401, 403))
        replay = APIClient()
        replay.cookies["tpa_access"] = token_antigo
        self.assertIn(replay.get("/api/auth/me/").status_code, (401, 403), "sessão revogada não pode ser reaproveitada")

    # ------------------------------------------------------------------ casos negativos do fluxo
    def test_api_exige_autenticacao(self):
        anon = APIClient()
        for rota in ("/api/clientes/", "/api/osps/", "/api/laudos/", "/api/inspecoes/", "/api/relatorios/",
                     "/api/dashboard/", "/api/portal/visao-geral/", "/api/notificacoes/", "/api/usuarios/",
                     "/api/auth/me/", "/api/equipamentos/"):
            with self.subTest(rota=rota):
                self.assertIn(anon.get(rota).status_code, (401, 403))

    def test_senha_errada_e_mensagem_generica_sem_cookie(self):
        s = Sessao("admin", self.admin.email, senha="senha-errada-123")
        self.assertEqual(s.resposta_login.status_code, 401)
        self.assertNotIn("tpa_access", s.resposta_login.cookies)
        inexistente = Sessao("admin", "ninguem@thermo.qa")
        self.assertEqual(inexistente.resposta_login.data, s.resposta_login.data)  # não revela se o e-mail existe

    def test_login_sem_csrf_e_recusado(self):
        http = APIClient(enforce_csrf_checks=True)
        r = http.post("/api/auth/admin/login/", {"email": self.admin.email, "password": SENHA}, format="json")
        self.assertEqual(r.status_code, 403)

    def test_bloqueio_apos_tentativas_repetidas(self):
        # 8 falhas bloqueiam a conta por 15 min; a 9a tentativa com a senha CERTA também é recusada.
        for _ in range(8):
            cache.clear()
            Sessao("admin", self.tecnico.email, senha="errada-errada-1")
        cache.clear()
        s = Sessao("admin", self.tecnico.email)
        self.assertEqual(s.resposta_login.status_code, 429)

    def test_sessao_renovada_pelo_refresh_e_rotacionada(self):
        s = self.logar("admin", self.gestor)
        antigo_refresh = s.http.cookies["tpa_refresh"].value
        r = s.post("/api/auth/session/refresh/")
        self.assertEqual(r.status_code, 204)
        self.assertNotEqual(s.http.cookies["tpa_refresh"].value, antigo_refresh)
        self.assertEqual(s.get("/api/auth/me/").status_code, 200)
        # o refresh antigo foi para a lista negra: reuso é recusado
        reuso = APIClient(enforce_csrf_checks=True)
        csrf = reuso.get("/api/auth/csrf/").data["csrfToken"]
        reuso.cookies["tpa_refresh"] = antigo_refresh
        self.assertEqual(reuso.post("/api/auth/session/refresh/", format="json", HTTP_X_CSRFTOKEN=csrf).status_code, 401)

    def test_aprovacao_pelo_cliente_so_quando_habilitada(self):
        """OSP_APROVACAO_PELO_CLIENTE: PCM do cliente aprova a execução apenas com a chave ligada."""
        from .test_homologacao_base import construir_cliente

        d = construir_cliente("A", "11.111.111/0001-11", self.tecnico, self.gestor)
        OrdemServico.objects.filter(pk=d.osp.pk).update(status="AGUARDANDO_APROVACAO")
        pcm = self.logar("portal", d.usuarios["CLIENTE_PCM"])
        manut = self.logar("portal", d.usuarios["CLIENTE_MANUT"])
        self.assertEqual(pcm.patch(f"/api/osps/{d.osp.pk}/status/", {"status": "FINALIZADA"}).status_code, 403)
        with override_settings(OSP_APROVACAO_PELO_CLIENTE=True):
            self.assertEqual(manut.patch(f"/api/osps/{d.osp.pk}/status/", {"status": "FINALIZADA"}).status_code, 403,
                             "manutentor nunca aprova")
            self.ok(pcm.patch(f"/api/osps/{d.osp.pk}/status/", {"status": "FINALIZADA"}), 200, "pcm aprova")
        d.osp.refresh_from_db()
        self.assertEqual((d.osp.status, d.osp.aprovado_por_id), ("FINALIZADA", d.usuarios["CLIENTE_PCM"].pk))

    def test_laudo_cancelado_mantem_pdf_e_marca_cabecalho(self):
        from .test_homologacao_base import construir_cliente

        d = construir_cliente("A", "11.111.111/0001-11", self.tecnico, self.gestor)
        gestor = self.logar("admin", self.gestor)
        self.assertEqual(gestor.post(f"/api/laudos/{d.laudo.pk}/cancelar/", {"motivo": ""}).status_code, 400)
        self.ok(gestor.post(f"/api/laudos/{d.laudo.pk}/cancelar/", {"motivo": "Dados do campo revisados"}), 200, "cancelar")
        pdf = self.ok(gestor.get(f"/api/laudos/{d.laudo.pk}/pdf/"), passo="pdf cancelado")
        self.assertEqual(pdf["X-Documento-Status"], "CANCELADO")
        rev = self.ok(gestor.post(f"/api/laudos/{d.laudo.pk}/revisar/", {"motivo": "Nova medição"}), 201, "revisar")
        self.assertEqual((rev.data["versao"], rev.data["status"]), (2, "RASCUNHO"))
        self.assertTrue(rev.data["numero"].endswith("-V2"))
        versoes = self.ok(gestor.get(f"/api/laudos/{rev.data['id']}/versoes/"), passo="versoes").data
        self.assertEqual([v["versao"] for v in versoes], [1, 2])

    # ------------------------------------------------------------------ ciclo de vida da sessão
    def test_access_token_revogado_pelo_logout_nao_vale_como_bearer(self):
        """O logout revoga a sessão; o access token antigo não pode continuar valendo no cabeçalho Bearer."""
        s = self.logar("admin", self.gestor)
        token = s.http.cookies["tpa_access"].value
        self.assertEqual(s.post("/api/auth/logout/").status_code, 204)
        bearer = APIClient()
        r = bearer.get("/api/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertIn(r.status_code, (401, 403), "access token continua aceito via Bearer após o logout")

    def test_conta_suspensa_perde_a_sessao_ativa(self):
        """Suspender/bloquear o usuário deve derrubar as sessões já abertas, não só impedir novos logins."""
        from apps.accounts.models import EstadoConta

        s = self.logar("admin", self.tecnico)
        self.assertEqual(s.get("/api/auth/me/").status_code, 200)
        self.tecnico.estado = EstadoConta.SUSPENDED
        self.tecnico.save(update_fields=["estado"])
        self.assertIn(s.get("/api/osps/").status_code, (401, 403), "conta SUSPENSA continua operando com a sessão aberta")
        novo = Sessao("admin", self.tecnico.email)
        self.assertEqual(novo.resposta_login.status_code, 401, "conta suspensa não pode abrir nova sessão")

    def test_usuario_desativado_perde_a_sessao_ativa(self):
        s = self.logar("admin", self.gestor)
        self.gestor.is_active = False
        self.gestor.save(update_fields=["is_active"])
        self.assertIn(s.get("/api/osps/").status_code, (401, 403))

    def test_troca_de_senha_encerra_as_outras_sessoes(self):
        a = self.logar("admin", self.gestor)
        b = self.logar("admin", self.gestor)
        nova = "Outra#Senha-Muito-Longa-2026!"
        r = a.post("/api/auth/seguranca/alterar-senha/", {"senha_atual": SENHA, "nova_senha": nova})
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual(a.get("/api/auth/me/").status_code, 200)
        self.assertIn(b.get("/api/auth/me/").status_code, (401, 403), "outra sessão sobreviveu à troca de senha")
        cache.clear()
        self.assertEqual(Sessao("admin", self.gestor.email, senha=SENHA).resposta_login.status_code, 401)
        cache.clear()
        self.assertEqual(Sessao("admin", self.gestor.email, senha=nova).resposta_login.status_code, 200)

    # ------------------------------------------------------------------ onboarding e recuperação
    def test_convite_cria_acesso_do_portal_de_uso_unico(self):
        """2.1.1.5 multiusuários: Master convida; link de uso único; o convidado entra no portal do cliente."""
        cliente = Cliente.objects.create(nome="Industria Convite", cnpj="45.723.174/0001-10")
        admin = self.logar("admin", self.admin)
        mail.outbox.clear()
        r = admin.post("/api/auth/convites/", {
            "nome": "Novo Colaborador", "email": "novo.colab@cliente.qa", "tipo": "portal",
            "perfil": "CLIENTE_LOCAL", "nivel": "PLENO", "cliente": cliente.pk,
        })
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(len(mail.outbox), 1)
        token = re.search(r"convite/([A-Za-z0-9_\-]+)", mail.outbox[0].body).group(1)
        self.assertNotIn(token, str(r.data), "o token só viaja por e-mail")
        publico = APIClient()
        self.assertEqual(publico.get(f"/api/auth/convites/{token}/").data["email"], "novo.colab@cliente.qa")
        self.assertEqual(publico.post(f"/api/auth/convites/{token}/", {"senha": "123", "aceitou_termos": True},
                                      format="json").status_code, 400, "senha fraca recusada")
        self.assertEqual(publico.post(f"/api/auth/convites/{token}/", {"senha": SENHA, "aceitou_termos": False},
                                      format="json").status_code, 400, "sem aceite dos termos")
        aceite = publico.post(f"/api/auth/convites/{token}/", {"senha": SENHA, "aceitou_termos": True}, format="json")
        self.assertEqual(aceite.status_code, 201, aceite.data)
        self.assertEqual(publico.get(f"/api/auth/convites/{token}/").status_code, 410, "token de uso único")
        # (a rota pública de convite tem throttle de 5/hora por IP: não há mais chamadas aqui)
        novo = Sessao("portal", "novo.colab@cliente.qa")
        self.assertEqual(novo.resposta_login.status_code, 200, novo.resposta_login.data)
        eu = novo.get("/api/auth/me/").data
        self.assertEqual((eu["perfil"], eu["cliente"]), ("CLIENTE_LOCAL", cliente.pk))
        self.assertEqual(novo.get("/api/usuarios/").status_code, 403)

    def test_recuperacao_de_senha_resposta_neutra_e_token_de_uso_unico(self):
        """2.1.1.2: resposta idêntica para e-mail existente/inexistente; token expira após o uso."""
        publico = APIClient(enforce_csrf_checks=True)
        csrf = publico.get("/api/auth/csrf/").data["csrfToken"]
        mail.outbox.clear()
        existente = publico.post("/api/auth/admin/esqueci-senha/", {"email": self.gestor.email}, format="json",
                                 HTTP_X_CSRFTOKEN=csrf)
        inexistente = publico.post("/api/auth/admin/esqueci-senha/", {"email": "ninguem@thermo.qa"}, format="json",
                                   HTTP_X_CSRFTOKEN=csrf)
        self.assertEqual((existente.status_code, inexistente.status_code), (200, 200))
        self.assertEqual(existente.data, inexistente.data)
        self.assertEqual(len(mail.outbox), 1)
        token = re.search(r"token=([A-Za-z0-9_\-]+)", mail.outbox[0].body).group(1)
        self.assertTrue(publico.post("/api/auth/token/status/", {"token": token}, format="json").data["valid"])
        antiga = self.logar("admin", self.gestor)
        nova = "Redefinida#Senha-Longa-2026!"
        self.assertEqual(publico.post("/api/auth/redefinir-senha/", {"token": token, "nova_senha": "curta"},
                                      format="json").status_code, 400)
        ok = publico.post("/api/auth/redefinir-senha/", {"token": token, "nova_senha": nova}, format="json")
        self.assertEqual(ok.status_code, 200, ok.data)
        self.assertIn(antiga.get("/api/auth/me/").status_code, (401, 403), "sessões antigas devem cair na redefinição")
        self.assertEqual(publico.post("/api/auth/redefinir-senha/", {"token": token, "nova_senha": nova + "x"},
                                      format="json").status_code, 400, "token reutilizado")
        cache.clear()
        self.assertEqual(Sessao("admin", self.gestor.email, senha=nova).resposta_login.status_code, 200)

    def test_recuperacao_no_portal_nao_serve_para_conta_interna(self):
        publico = APIClient()
        mail.outbox.clear()
        publico.post("/api/auth/portal/esqueci-senha/", {"email": self.gestor.email}, format="json")
        self.assertEqual(len(mail.outbox), 0, "e-mail de conta interna não recebe link pelo portal")


class RobustezDasExportacoesTest(TestCase):
    """2.9.2: exportar PDF/Excel/CSV não pode quebrar por causa do texto digitado em campo."""

    TEXTOS_HOSTIS = [
        "Mancal <b>LA sem fechar",
        "x </para> y",
        "<font color=red>vermelho",
        "<a href='http://exemplo.invalido'>link",
        "<img src='file:///etc/hosts' width=10 height=10/>",
        "a & b < c > d",
        "=HYPERLINK(\"http://exemplo.invalido\",\"clique\")",
    ]

    @classmethod
    def setUpTestData(cls):
        from .test_homologacao_base import construir_cliente

        cls.internos = criar_internos()
        cls.d = construir_cliente("A", "11.111.111/0001-11", cls.internos["TECNICO"], cls.internos["GESTOR"])

    def test_pdf_csv_e_xlsx_aceitam_texto_com_marcacao(self):
        from apps.coletas.models import MedicaoTecnica

        for usuario in (self.internos["GESTOR"], self.d.usuarios["CLIENTE_PCM"]):
            api = APIClient()
            api.raise_request_exception = False  # queremos ver o 500, não a exceção do cliente de teste
            api.force_authenticate(usuario)
            for texto in self.TEXTOS_HOSTIS:
                m = MedicaoTecnica.objects.create(
                    inspecao=self.d.inspecao_sens, equipamento=self.d.equipamento2, tipo="SENSITIVA",
                    subtipo="SENSITIVA", ponto_medicao=texto[:80], grandeza="Parecer", valor=None,
                    parametros={"criticidade": "NORMAL"}, coletado_por=self.internos["TECNICO"],
                )
                try:
                    for key in ("tecnico", "equipamento", "falhas", "historico"):
                        for formato in ("pdf", "csv", "xlsx"):
                            with self.subTest(perfil=usuario.perfil, texto=texto, relatorio=key, formato=formato):
                                r = api.get(f"/api/relatorios/{key}/?formato={formato}")
                                self.assertEqual(r.status_code, 200, f"exportação {key}.{formato} quebrou com o texto {texto!r}")
                finally:
                    m.delete()


class ListagensDeterministicasTest(TestCase):
    """Paginação sobre queryset sem ordenação pode repetir/pular linhas entre páginas (PostgreSQL)."""

    def test_nenhuma_listagem_paginada_e_desordenada(self):
        import importlib
        import warnings

        from rest_framework.pagination import PageNumberPagination  # noqa: F401

        interno = criar_internos()["ADMIN"]
        api = APIClient()
        api.force_authenticate(interno)
        desordenadas = []
        for app in ("accounts", "cadastros", "coletas", "ensaios", "servicos", "osp", "laudos", "notificacoes"):
            router = getattr(importlib.import_module(f"apps.{app}.urls"), "router")
            for prefixo, _viewset, _base in router.registry:
                with warnings.catch_warnings(record=True) as avisos:
                    warnings.simplefilter("always")
                    resposta = api.get(f"/api/{prefixo}/")
                if resposta.status_code == 200 and any("UnorderedObjectListWarning" in a.category.__name__ for a in avisos):
                    desordenadas.append(prefixo)
        self.assertEqual(desordenadas, [], f"listagens paginadas sem ordenação determinística: {desordenadas}")
