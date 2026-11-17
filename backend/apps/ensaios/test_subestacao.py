"""
Ensaios elétricos de subestação (TC, TP, DJ, CS e RP) — docs/25.

O que estes testes seguram:
  - cada fórmula com o número que a norma/o método dá (erro de relação, pickup, tempo,
    simultaneidade, joelho da curva de excitação);
  - nenhum limite universal: erro de relação sai da classe da placa; sem classe na tabela,
    "sem critério"; tolerância de relé só a que foi lançada;
  - catálogo com as formas de ficha e sem limite numérico cadastrado;
  - a placa usada no laudo é a do momento do lançamento (não muda depois);
  - a fila e a API separam a subestação do transformador (TRF) e do fluido;
  - o relatório (dossiê) tem as cinco chaves de módulo e as fichas por série;
  - cliente vê só os equipamentos da própria empresa.
"""
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, ModuloTecnico, Setor, TecnologiaAnalise
from apps.coletas.models import Carregamento, ItemInspecao, Relatorio
from apps.coletas.relatorio_tecnico.modulos import MODULOS, modulo_da_tecnologia

from . import calculos_subestacao as cs
from .contexto import registrar_contexto
from .models import (
    MODULOS_SUBESTACAO,
    DadosPlacaSubestacao,
    Ensaio,
    FormaEnsaio,
    ParametroEnsaio,
    RegistroEnsaioSubestacao,
    ResultadoEnsaio,
    ValorParametro,
)
from .relatorio_subestacao import avaliar_resultado_subestacao

User = get_user_model()
TC, TP, DJ, CS, RP = (ModuloTecnico.ENSAIO_ELETRICO_TC, ModuloTecnico.ENSAIO_ELETRICO_TP,
                      ModuloTecnico.ENSAIO_ELETRICO_DJ, ModuloTecnico.ENSAIO_ELETRICO_CS,
                      ModuloTecnico.ENSAIO_ELETRICO_RP)
TRF = ModuloTecnico.ENSAIO_ELETRICO


# ------------------------------- Cálculos -----------------------------------
class CalculosSubestacaoTest(SimpleTestCase):
    def test_erro_admissivel_pela_classe_da_norma(self):
        # IEC 61869-2: medição 0,5 = ±0,5 %; proteção 5P = ±1 %, 10P = ±3 %.
        self.assertEqual(cs.erro_admissivel_relacao("0,5", "TC"), D("0.5"))
        self.assertEqual(cs.erro_admissivel_relacao(" 0.5 ", "TC"), D("0.5"))
        self.assertEqual(cs.erro_admissivel_relacao("5P", "TC"), D("1"))
        self.assertEqual(cs.erro_admissivel_relacao("10p", "TC"), D("3"))
        # IEC 61869-3: TP de proteção 3P = ±3 %, 6P = ±6 %.
        self.assertEqual(cs.erro_admissivel_relacao("3P", "TP"), D("3"))
        self.assertEqual(cs.erro_admissivel_relacao("6P", "TP"), D("6"))
        # Classe fora da tabela (ou vazia) = sem critério, nunca um número inventado.
        self.assertIsNone(cs.erro_admissivel_relacao("7", "TC"))
        self.assertIsNone(cs.erro_admissivel_relacao("", "TP"))
        self.assertIsNone(cs.erro_admissivel_relacao("0,5", "DJ"))

    def test_erro_de_relacao_e_percentual(self):
        self.assertAlmostEqual(float(cs.erro_relacao(D("120.4"), D("120"))), 0.3333, places=3)
        self.assertEqual(cs.erro_relacao(None, D("120")), None)
        self.assertEqual(cs.erro_percentual(D("5.1"), D("5")), D("2"))
        self.assertEqual(cs.erro_percentual(D("4.6"), D("5")), D("-8"))
        self.assertIsNone(cs.erro_percentual(D("4"), D("0")))
        self.assertIsNone(cs.erro_percentual(None, D("5")))

    def test_tolerancia_so_com_valor_lancado(self):
        self.assertTrue(cs.dentro_da_tolerancia(D("-4.9"), D("5")))
        self.assertFalse(cs.dentro_da_tolerancia(D("5.1"), D("5")))
        self.assertIsNone(cs.dentro_da_tolerancia(D("1"), None))
        self.assertIsNone(cs.dentro_da_tolerancia(None, D("5")))

    def test_simultaneidade_entre_polos(self):
        self.assertEqual(cs.simultaneidade([D("30.1"), D("30.4"), D("29.9")]), D("0.5"))
        self.assertEqual(cs.simultaneidade([D("30.1"), None, D("30.4")]), D("0.3"))
        self.assertIsNone(cs.simultaneidade([D("30.1")]))
        self.assertIsNone(cs.simultaneidade([None, None]))

    def test_joelho_da_curva_de_excitacao(self):
        # Joelho (IEEE C57.13): primeira tensão em que +10 % de tensão exige +50 % de corrente.
        curva = [(D(100), D(1)), (D(200), D(2)), (D(300), D(3)), (D(400), D(6)), (D(500), D(20))]
        self.assertEqual(cs.joelho_excitacao(curva), D(400))
        # Curva linear não tem joelho dentro dos pontos lançados.
        self.assertIsNone(cs.joelho_excitacao([(D(100), D(1)), (D(200), D(2))]))
        self.assertIsNone(cs.joelho_excitacao([(D(100), D(1))]))


# -------------------------------- Catálogo ----------------------------------
class CatalogoSubestacaoTest(TestCase):
    def test_siglas_de_cada_equipamento(self):
        esperado = {
            TC: {"RELA", "EXC", "ISO", "OHM"},
            TP: {"RELA", "ISO", "OHM"},
            DJ: {"RCON", "ISO", "TEMP"},
            CS: {"RCON", "ISO"},
            RP: {"PICK", "TEMP"},
        }
        for modulo, siglas in esperado.items():
            obtido = set(Ensaio.objects.filter(modulo=modulo).values_list("sigla", flat=True))
            self.assertEqual(obtido, siglas, modulo)

    def test_formas_de_ficha(self):
        self.assertEqual(Ensaio.objects.get(modulo=TC, sigla="EXC").forma, FormaEnsaio.CURVA)
        self.assertEqual(Ensaio.objects.get(modulo=RP, sigla="PICK").forma, FormaEnsaio.MEDICAO)
        self.assertEqual(Ensaio.objects.get(modulo=TRF, sigla="RXT").forma, FormaEnsaio.TABELA)

    def test_nenhum_limite_numerico_cadastrado(self):
        for p in ParametroEnsaio.objects.filter(ensaio__modulo__in=MODULOS_SUBESTACAO):
            self.assertIn(p.tipo_limite, ("INFORMATIVO", "QUALITATIVO"), p.codigo)
            self.assertIsNone(p.limite, p.codigo)

    def test_todo_ensaio_tem_norma_ou_metodo_citado(self):
        for p in ParametroEnsaio.objects.filter(ensaio__modulo__in=MODULOS_SUBESTACAO):
            self.assertTrue(p.norma, f"{p.ensaio.sigla}.{p.codigo} sem norma/método")

    def test_modulos_saem_do_planejado_e_tem_relatorio(self):
        for modulo in MODULOS_SUBESTACAO:
            self.assertIn(modulo, MODULOS)
            tec = TecnologiaAnalise(nome="Teste", modulo_tecnico=modulo)
            self.assertEqual(modulo_da_tecnologia(tec).chave, modulo)


# ------------------------------- Cenário ------------------------------------
class CenarioSubestacao:
    @classmethod
    def criar(cls):
        cls.cliente = Cliente.objects.create(nome="Subestação Exemplo Ltda", cnpj="66.666.666/0001-66")
        cls.outro = Cliente.objects.create(nome="Outra Empresa", cnpj="77.777.777/0001-77")
        cls.tecnico = User.objects.create_user(email="tecnico-se@thermo.com", nome="Técnico", perfil="TECNICO",
                                               nivel="PLENO")
        cls.leitor_outro = User.objects.create_user(email="pcm-se@outra.com", nome="PCM", perfil="CLIENTE_PCM",
                                                    cliente=cls.outro)
        cls.setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Subestações"),
                                         nome="SE-01")
        cls.tc = Equipamento.objects.create(setor=cls.setor, tag="TC-01", nome="TC 600/5 A", fabricante="Fab")
        cls.placa_tc = DadosPlacaSubestacao.objects.create(
            equipamento=cls.tc, relacao_texto="600/5 A", relacao_transformacao=D("120"), classe_exatidao="0,5",
            polaridade="Subtrativa", numero_nucleos=2, corrente_nominal_a=D("600"),
        )
        cls.dj = Equipamento.objects.create(setor=cls.setor, tag="DJ-01", nome="Disjuntor 15 kV", fabricante="Fab")
        cls.tec = {
            TC: TecnologiaAnalise.objects.create(nome="Ensaios de TC", sigla="ETC", modulo_tecnico=TC),
            DJ: TecnologiaAnalise.objects.create(nome="Ensaios de DJ", sigla="EDJ", modulo_tecnico=DJ),
            RP: TecnologiaAnalise.objects.create(nome="Ensaios de relé", sigla="ERP", modulo_tecnico=RP),
            TRF: TecnologiaAnalise.objects.create(nome="Ensaios de TRF", sigla="ETR", modulo_tecnico=TRF),
        }
        cls.ensaio = {(e.modulo, e.sigla): e for e in Ensaio.objects.filter(modulo__in=(*MODULOS_SUBESTACAO, TRF))}
        cls.param = {(p.ensaio.modulo, p.ensaio.sigla, p.codigo): p
                     for p in ParametroEnsaio.objects.select_related("ensaio")}
        cls.contador = 0

    @classmethod
    def rota(cls, tecnologia, equipamentos, data=date(2026, 11, 2), cliente=None):
        cliente = cliente or cls.cliente
        cls.contador += 1
        rel = Relatorio.objects.create(cliente=cliente, tecnologia=tecnologia, data_inicio=data, data_termino=data,
                                       numero=f"RT-SE-{cls.contador:05d}")
        rota = Carregamento.objects.create(cliente=cliente, tecnologia=tecnologia, analista=cls.tecnico,
                                           relatorio=rel, data_coleta=data)
        itens = [ItemInspecao.objects.create(carregamento=rota, equipamento=eq, ordem=i)
                 for i, eq in enumerate(equipamentos, start=1)]
        return rel, itens

    @classmethod
    def resultado(cls, item, modulo, sigla, valores, **campos):
        """Lança como a tela: valores (codigo, serie, posicao, valor ou texto) e depois o contexto técnico."""
        campos.setdefault("situacao", "REALIZADO")
        r = ResultadoEnsaio.objects.create(item=item, ensaio=cls.ensaio[(modulo, sigla)], **campos)
        for codigo, serie, posicao, valor in valores:
            try:
                numero, texto = D(str(valor)), ""      # "120.40" é número; "Subtrativa" é texto
            except (TypeError, ArithmeticError):
                numero, texto = None, str(valor)
            ValorParametro.objects.create(
                resultado=r, parametro=cls.param[(modulo, sigla, codigo)], serie=serie,
                posicao=None if posicao is None else D(posicao), valor=numero, valor_texto=texto,
            )
        registrar_contexto(r, autor=cls.tecnico)
        return r


class SubestacaoAvaliacaoTest(CenarioSubestacao, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()

    def test_relacao_do_tc_avaliada_pela_classe_da_placa(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        r = self.resultado(item, TC, "RELA", [
            ("RELACAO_MEDIDA", "Núcleo 1", None, "120.40"),
            ("POLARIDADE", "Núcleo 1", None, "Subtrativa"),
            ("RELACAO_MEDIDA", "Núcleo 2", None, "121.00"),
            ("POLARIDADE", "Núcleo 2", None, "Aditiva"),
        ])
        a = avaliar_resultado_subestacao(r)
        self.assertEqual(a["tipo"], "MEDICAO")
        self.assertEqual(a["criterio"]["admissivel"], D("0.5"))
        linhas = {l["serie"]: l["celulas"] for l in a["linhas"]}
        self.assertTrue(linhas["Núcleo 1"]["ERRO_RELACAO"]["conforme"])            # 0,33 % ≤ 0,5 %
        self.assertFalse(linhas["Núcleo 2"]["ERRO_RELACAO"]["conforme"])           # 0,83 % > 0,5 %
        self.assertTrue(linhas["Núcleo 1"]["POLARIDADE"]["conforme"])              # igual à placa
        self.assertFalse(linhas["Núcleo 2"]["POLARIDADE"]["conforme"])             # diferente da placa
        self.assertEqual((a["avaliados"], a["fora"], a["status"]), (4, 2, "NAO_CONFORME"))

    def test_sem_classe_na_tabela_fica_sem_criterio(self):
        self.placa_tc.classe_exatidao = "7"
        self.placa_tc.save()
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        r = self.resultado(item, TC, "RELA", [("RELACAO_MEDIDA", "Núcleo 1", None, "120.40")])
        a = avaliar_resultado_subestacao(r)
        self.assertIsNone(a["criterio"]["admissivel"])
        self.assertIsNone(a["linhas"][0]["celulas"]["ERRO_RELACAO"]["conforme"])
        self.assertEqual((a["avaliados"], a["status"]), (0, "SEM_CRITERIO"))

    def test_laudo_guarda_a_placa_do_lancamento(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        r = self.resultado(item, TC, "RELA", [("RELACAO_MEDIDA", "Núcleo 1", None, "120.40")])
        self.placa_tc.classe_exatidao = "1"
        self.placa_tc.save()
        # A placa mudou depois do lançamento: o laudo continua com a classe 0,5 dele.
        self.assertEqual(avaliar_resultado_subestacao(r)["criterio"]["admissivel"], D("0.5"))
        self.placa_tc.classe_exatidao = "0,5"
        self.placa_tc.save()

    def test_rele_pickup_com_tolerancia_lancada(self):
        rele = Equipamento.objects.create(setor=self.setor, tag="RL-01", nome="Relé de proteção")
        rel, (item,) = self.rota(self.tec[RP], [rele])
        r = self.resultado(item, RP, "PICK", [
            ("ESPERADO", "50 — fase A", None, "5"), ("MEDIDO", "50 — fase A", None, "5.1"),
            ("TOLERANCIA", "50 — fase A", None, "3"),
            ("ESPERADO", "51 — fase A", None, "5"), ("MEDIDO", "51 — fase A", None, "5.4"),
            ("TOLERANCIA", "51 — fase A", None, "5"),
            ("ESPERADO", "50N — neutro", None, "1"), ("MEDIDO", "50N — neutro", None, "1.02"),
        ])
        a = avaliar_resultado_subestacao(r)
        linhas = {l["serie"]: l["celulas"] for l in a["linhas"]}
        self.assertEqual(linhas["50 — fase A"]["ERRO"]["valor"], D("2"))
        self.assertTrue(linhas["50 — fase A"]["ERRO"]["conforme"])
        self.assertFalse(linhas["51 — fase A"]["ERRO"]["conforme"])                 # 8 % > 5 % lançados
        self.assertIsNone(linhas["50N — neutro"]["ERRO"]["conforme"])               # sem tolerância = sem critério
        self.assertEqual((a["avaliados"], a["fora"]), (2, 1))
        self.assertEqual(a["status"], "NAO_CONFORME")

    def test_disjuntor_simultaneidade_entre_polos(self):
        rel, (item,) = self.rota(self.tec[DJ], [self.dj])
        r = self.resultado(item, DJ, "TEMP", [
            ("TEMPO_ABERTURA", "Polo A", None, "30.1"), ("TEMPO_ABERTURA", "Polo B", None, "30.4"),
            ("TEMPO_ABERTURA", "Polo C", None, "29.9"),
            ("TEMPO_FECHAMENTO", "Polo A", None, "50.0"), ("TEMPO_FECHAMENTO", "Polo B", None, "50.2"),
        ])
        a = avaliar_resultado_subestacao(r)
        self.assertEqual(a["indicadores"]["simultaneidade_abertura_ms"], D("0.5"))
        self.assertEqual(a["indicadores"]["simultaneidade_fechamento_ms"], D("0.2"))
        self.assertEqual(a["status"], "SEM_CRITERIO")

    def test_tc_curva_de_excitacao_com_joelho(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        pontos = [("100", "1"), ("200", "2"), ("300", "3"), ("400", "6"), ("500", "20")]
        r = self.resultado(item, TC, "EXC", [("CORRENTE_EXCITACAO", "Núcleo 1", t, i) for t, i in pontos])
        a = avaliar_resultado_subestacao(r)
        self.assertEqual(a["tipo"], "CURVA")
        self.assertEqual(a["joelhos"], {"Núcleo 1": D(400)})
        self.assertEqual(len(a["tabela"]), 5)
        self.assertEqual(a["status"], "SEM_CRITERIO")


class SubestacaoApiTest(CenarioSubestacao, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def test_lancamento_pela_api_e_fila(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        ids = {s: self.ensaio[(TC, s)].id for s in ("RELA", "EXC")}
        r = self.api.post("/api/registros-ensaio-subestacao/", {
            "item": item.id, "data_ensaio": "2026-11-02", "analista": "Técnico", "temperatura_ambiente_c": "25.0",
            "ensaios": [ids["RELA"], ids["EXC"]],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        pid = {c: self.param[(TC, "RELA", c)].id for c in ("RELACAO_MEDIDA", "POLARIDADE")}
        r = self.api.post("/api/resultados-ensaio/", {
            "item": item.id, "ensaio": ids["RELA"], "situacao": "REALIZADO", "numero_laudo": "SE-1",
            "valores": [
                {"parametro": pid["RELACAO_MEDIDA"], "serie": "Núcleo 1", "valor": "120.40"},
                {"parametro": pid["POLARIDADE"], "serie": "Núcleo 1", "valor_texto": "Subtrativa"},
            ],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["avaliacao"]["tipo"], "MEDICAO")
        self.assertEqual(r.data["avaliacao"]["status"], "CONFORME")

        fila = self.api.get(f"/api/subestacao-inspecao/?carregamento={item.carregamento_id}")
        self.assertEqual(fila.status_code, 200)
        linha = fila.data["results"][0]
        self.assertEqual(linha["modulo"], TC)
        self.assertEqual(linha["pendentes"], 1)            # EXC solicitado e sem laudo
        self.assertIsNotNone(linha["registro"])

    def test_placa_e_registro_so_de_subestacao(self):
        rel, (item_trf,) = self.rota(self.tec[TRF], [self.tc])
        r = self.api.post("/api/registros-ensaio-subestacao/", {
            "item": item_trf.id, "data_ensaio": "2026-11-02",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("item", r.data)
        r = self.api.post("/api/resultados-ensaio/", {
            "item": item_trf.id, "ensaio": self.ensaio[(TC, "RELA")].id, "situacao": "REALIZADO",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_medicao_exige_serie_e_curva_exige_tensao(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        r = self.api.post("/api/resultados-ensaio/", {
            "item": item.id, "ensaio": self.ensaio[(TC, "RELA")].id, "situacao": "REALIZADO",
            "valores": [{"parametro": self.param[(TC, "RELA", "RELACAO_MEDIDA")].id, "valor": "120"}],
        }, format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/resultados-ensaio/", {
            "item": item.id, "ensaio": self.ensaio[(TC, "EXC")].id, "situacao": "REALIZADO",
            "valores": [{"parametro": self.param[(TC, "EXC", "CORRENTE_EXCITACAO")].id, "serie": "Núcleo 1",
                         "valor": "1"}],
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_dossie_do_tc_com_fichas_por_serie(self):
        rel, (item,) = self.rota(self.tec[TC], [self.tc])
        self.resultado(item, TC, "RELA", [
            ("RELACAO_MEDIDA", "Núcleo 1", None, "120.40"), ("RELACAO_MEDIDA", "Núcleo 2", None, "121.00"),
        ])
        RegistroEnsaioSubestacao.objects.create(item=item, data_ensaio=date(2026, 11, 2), analista="Técnico")
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/dossie/")
        self.assertEqual(r.status_code, 200, r.data)
        d = r.data
        self.assertEqual(d["modulo"], TC)
        eq = d["equipamentos"][0]
        self.assertEqual(eq["tag"], "TC-01")
        self.assertEqual(eq["cadastro"]["relacao_transformacao"], D("120"))
        self.assertEqual([f["sigla"] for f in eq["ensaios"]], ["RELA"])     # só o solicitado/lançado
        self.assertEqual(eq["registro"]["data"], date(2026, 11, 2))
        destaque = d["kpis"]["destaques"][0]
        self.assertEqual(destaque["rotulo"], "Maior erro — RELA")
        self.assertAlmostEqual(float(destaque["valor"]), 0.8333, places=3)
        self.assertIn("admitido ± 0.5 %", destaque["detalhe"])
        self.assertIn("1 fora delas (RELA)", d["carta"]["paragrafos"][0])

    def test_cliente_so_ve_os_proprios_equipamentos(self):
        self.api.force_authenticate(self.leitor_outro)
        r = self.api.get("/api/dados-placa-subestacao/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"] if isinstance(r.data, dict) and "count" in r.data else len(r.data), 0)

    def test_placa_so_de_interno_edita(self):
        self.api.force_authenticate(self.leitor_outro)
        r = self.api.patch(f"/api/dados-placa-subestacao/{self.placa_tc.pk}/", {"classe_exatidao": "1"}, format="json")
        self.assertIn(r.status_code, (403, 404))
        self.placa_tc.refresh_from_db()
        self.assertEqual(self.placa_tc.classe_exatidao, "0,5")
