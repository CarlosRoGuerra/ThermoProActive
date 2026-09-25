"""
Ensaios de transformador (óleo isolante e ensaios elétricos).

Os números vêm dos relatórios de referência do cliente — 2025-12_TRF-001_Óleo.pdf
e 2025-12_TRF-001_ENDe.pdf: os cálculos têm de reproduzir o que está impresso lá
(TG/TGC, relação nominal, erro do R×T, resistência corrigida do R×O, IP/IA).
As fichas saem do mesmo dossiê das outras tecnologias, no mesmo shell.
"""
import io
import zipfile
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import SimpleTestCase, TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.cadastros.models import (
    Area,
    Cliente,
    DadosTecnicosTransformador,
    Equipamento,
    Instrumento,
    ModuloTecnico,
    Setor,
    TecnologiaAnalise,
)
from apps.coletas.models import Carregamento, ItemInspecao, Relatorio

from . import calculos
from .models import (
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    ParametroEnsaio,
    PontoColeta,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    TipoFluido,
    ValorParametro,
)

User = get_user_model()
D = Decimal


def q(valor, casas=2):
    """Arredonda como a ficha imprime (meio para cima)."""
    return Decimal(valor).quantize(Decimal(1).scaleb(-casas), rounding=ROUND_HALF_UP)


# Valores do relatório de referência de óleo (laudos 20260109001/002/003).
FQ = {"VISCOSIDADE": "40.00", "DENSIDADE": "0.85", "FATOR_POTENCIA": "1.50", "NEUTRALIZACAO": "0.02",
      "TEOR_AGUA": "14.00", "RIGIDEZ": "63.00", "TENSAO_INTERFACIAL": "24.00", "COR": "1.00"}
CR = {"H2": "10", "O2": "4500", "N2": "50000", "CH4": "28", "CO": "480", "CO2": "5000", "C2H4": "15",
      "C2H6": "11.5", "C2H2": "0"}
# R×I do relatório de ensaios elétricos (laudo 20251226012): tempo → (AT-BT-Massa, AT-Massa-BT, BT-Massa-AT) em MΩ.
RXI = {
    15: (250, 550, 150), 30: (900, 1000, 400), 45: (1790, 2500, 800), 60: (3000, 4000, 900),
    120: (3150, 4500, 950), 180: (3225, 5000, 1000), 240: (3300, 5000, 1040), 300: (3300, 5000, 1070),
    360: (3320, 5000, 1090), 420: (3310, 5000, 1100), 480: (3325, 5000, 1100), 540: (3330, 5000, 1125),
    600: (3325, 5000, 1100),
}
RXI_SERIES = (("AT-BT-Massa", 5000), ("AT-Massa-BT", 5000), ("BT-Massa-AT", 500))
RXT_FASES = {"Fase 1 (H1-H2/X0-X2)": "51.700", "Fase 2 (H2-H3/X0-X3)": "51.600", "Fase 3 (H3-H1/X0-X1)": "51.630"}
RXO = {"H1H2": "3.51", "H1H3": "3.60", "H2H3": "3.65", "X0X1": "1.46", "X0X2": "1.45", "X0X3": "1.47"}


# ------------------------------ Cálculos (puros) ------------------------------
class CalculosDoRelatorioDeReferenciaTest(SimpleTestCase):
    def test_tg_e_tgc_da_cromatografia(self):
        gases = {k: D(v) for k, v in CR.items()}
        self.assertEqual(calculos.soma_gases(gases, calculos.GASES_TODOS), D("60044"))  # "TG = 60.044"
        self.assertEqual(calculos.soma_gases(gases, calculos.GASES_COMBUSTIVEIS), D("544"))  # "TGC = 544"
        # Gás não informado fica fora da soma; nenhum gás → sem indicador (nunca zero).
        self.assertEqual(calculos.soma_gases({"H2": D("10"), "CH4": None}, calculos.GASES_COMBUSTIVEIS), D("10"))
        self.assertIsNone(calculos.soma_gases({}, calculos.GASES_TODOS))

    def test_relacao_nominal_e_erro_do_rxt(self):
        nominal = calculos.relacao_nominal(D("11400"), D("380"), D("220"), "DYn1")
        self.assertEqual(q(nominal, 3), D("51.818"))
        erros = [q(calculos.erro_relacao_pct(D(m), nominal)) for m in RXT_FASES.values()]
        self.assertEqual(erros, [D("-0.23"), D("-0.42"), D("-0.36")])
        # Sem a tensão de fase da placa, a estrela usa a de linha ÷ √3.
        self.assertEqual(q(calculos.relacao_nominal(D("11400"), D("380"), None, "Dyn1"), 3), D("51.962"))
        # Triângulo nos dois lados: tensões de linha.
        self.assertEqual(calculos.relacao_nominal(D("13800"), D("440"), None, "Dd0"), D("13800") / D("440"))
        self.assertIsNone(calculos.relacao_nominal(D("11400"), D("380"), D("220"), ""))
        self.assertIsNone(calculos.erro_relacao_pct(D("51.7"), None))

    def test_resistencia_ohmica_por_fase_e_corrigida_a_75_graus(self):
        # AT em triângulo, medida entre linhas: fase = 1,5 × leitura; BT em estrela, do neutro: a própria leitura.
        fases = {k: calculos.resistencia_fase(D(v), triangulo=k.startswith("H"), com_neutro="0" in k)
                 for k, v in RXO.items()}
        self.assertEqual([q(fases[k]) for k in ("H1H2", "H1H3", "H2H3")], [D("5.27"), D("5.40"), D("5.48")])
        self.assertEqual(fases["X0X1"], D("1.46"))
        corrigidas = [q(calculos.corrigir_temperatura(fases[k], D("45"))) for k in RXO]
        self.assertEqual(corrigidas, [D("5.83"), D("5.98"), D("6.06"), D("1.62"), D("1.61"), D("1.63")])
        self.assertEqual(calculos.resistencia_fase(D("2"), triangulo=False, com_neutro=False), D("1"))
        self.assertIsNone(calculos.corrigir_temperatura(D("5"), None))

    def test_indices_de_polarizacao_e_absorcao(self):
        self.assertEqual(q(calculos.indice_polarizacao(D("3325"), D("3000")), 3), D("1.108"))
        self.assertEqual(q(calculos.indice_absorcao(D("3000"), D("900")), 3), D("3.333"))
        self.assertIsNone(calculos.indice_polarizacao(D("3325"), None))
        self.assertIsNone(calculos.indice_polarizacao(None, D("3000")))

    def test_grau_de_polimerizacao_pela_equacao_de_de_pablo(self):
        self.assertEqual(q(calculos.grau_polimerizacao_de_pablo(D("0.010"))), D("798.65"))
        self.assertIsNone(calculos.grau_polimerizacao_de_pablo(None))

    def test_percentual_do_limite_para_os_graficos(self):
        self.assertEqual(calculos.percentual_do_limite(D("40"), D("50")), D("80"))
        self.assertEqual(calculos.percentual_do_limite(D("63"), D("40")), D("157.5"))
        # Acetileno: referência 0,0 não tem percentual (a barra não sai, como na ficha).
        self.assertIsNone(calculos.percentual_do_limite(D("0"), D("0")))
        self.assertIsNone(calculos.percentual_do_limite(None, D("50")))

    def test_avaliacao_por_tipo_de_limite_e_estado_do_valor(self):
        def avaliar(tipo, valor=None, limite=None, sup=None, texto="", estado="MEDIDO", ref=""):
            return calculos.avaliar(valor=valor, texto=texto, estado=estado, tipo_limite=tipo, limite=limite,
                                    limite_superior=sup, referencia_texto=ref)

        self.assertTrue(avaliar("MAXIMO", D("40"), D("50")))
        self.assertTrue(avaliar("MAXIMO", D("0"), D("0")))  # acetileno 0,0 com referência 0,0
        self.assertFalse(avaliar("MAXIMO", D("51"), D("50")))
        self.assertTrue(avaliar("MINIMO", D("63"), D("40")))
        self.assertFalse(avaliar("MINIMO", D("39.9"), D("40")))
        self.assertTrue(avaliar("FAIXA", D("-0.42"), D("-0.5"), D("0.5")))
        self.assertFalse(avaliar("FAIXA", D("0.74"), D("-0.5"), D("0.5")))
        self.assertTrue(avaliar("QUALITATIVO", texto="límpido", ref="Límpido"))
        self.assertFalse(avaliar("QUALITATIVO", texto="Turvo", ref="Límpido"))
        # Abaixo do LD: dentro de um máximo, fora de um mínimo; indisponível e informativo não se avaliam.
        self.assertTrue(avaliar("MAXIMO", None, D("50"), estado="ABAIXO_LD"))
        self.assertFalse(avaliar("MINIMO", None, D("800"), estado="ABAIXO_LQ"))
        self.assertIsNone(avaliar("MAXIMO", D("99"), D("50"), estado="INDISPONIVEL"))
        self.assertIsNone(avaliar("INFORMATIVO", D("1")))
        self.assertIsNone(avaliar("MAXIMO", None, D("50")))


# ------------------------------ Caso TRF-001 ------------------------------
class CenarioTransformador:
    """Transformador TRF-001 dos relatórios de referência, com os dois relatórios de 26/12/2025."""

    @classmethod
    def criar_parque(cls):
        cls.cliente = Cliente.objects.create(nome="Novaprom Food Ingredients Ltda", cnpj="02.916.265/0219-14")
        cls.outro_cliente = Cliente.objects.create(nome="Outra Indústria", cnpj="11.111.111/0001-11")
        cls.tecnico = User.objects.create_user(email="tecnico@thermo.com", nome="Técnico", perfil="TECNICO",
                                               nivel="PLENO")
        cls.setor = Setor.objects.create(
            area=Area.objects.create(cliente=cls.cliente, nome="Subestações"),
            nome="SE-01 - Subestação Caldeira/Kelco",
        )
        cls.trafo = Equipamento.objects.create(
            setor=cls.setor, tag="TRF-001", nome="Transformador Trifásico", fabricante="MEGA", modelo="TFC-500,1",
            numero_serie="91839", ano_fabricacao=1996,
        )
        DadosTecnicosTransformador.objects.create(
            equipamento=cls.trafo, potencia_kva=D("500"), tensao_primaria_v=D("13800"), tensao_secundaria_v=D("380"),
            tensao_secundaria_fase_v=D("220"), impedancia_pct=D("4.49"), grupo_ligacao="DYn1",
            volume_oleo_l=D("540"), possui_tanque_expansao=False,
        )
        cls.ensaio = {e.sigla: e for e in Ensaio.objects.all()}
        cls.param = {(p.ensaio.sigla, p.codigo): p for p in ParametroEnsaio.objects.select_related("ensaio")}

    @classmethod
    def item_de_rota(cls, modulo, data=date(2025, 12, 26), equipamento=None, cliente=None):
        cliente = cliente or cls.cliente
        tecnologia, _ = TecnologiaAnalise.objects.get_or_create(
            modulo_tecnico=modulo, defaults={"nome": f"Tecnologia {modulo}", "sigla": modulo[:4]},
        )
        rel = Relatorio.objects.create(
            cliente=cliente, tecnologia=tecnologia, numero=f"RT-{modulo[:4]}-{Relatorio.objects.count() + 1:05d}",
            data_inicio=data, data_termino=data,
        )
        rota = Carregamento.objects.create(cliente=cliente, tecnologia=tecnologia, analista=cls.tecnico,
                                           relatorio=rel, data_coleta=data)
        item = ItemInspecao.objects.create(carregamento=rota, equipamento=equipamento or cls.trafo, ordem=1)
        return rel, item

    @classmethod
    def resultado(cls, item, sigla, valores=(), **campos):
        """`valores`: (codigo, valor, extras) — extras vira serie/posicao/estado/valor_texto."""
        campos.setdefault("situacao", "REALIZADO")
        r = ResultadoEnsaio.objects.create(item=item, ensaio=cls.ensaio[sigla], **campos)
        ValorParametro.objects.bulk_create([
            ValorParametro(resultado=r, parametro=cls.param[(sigla, codigo)],
                           valor=D(valor) if valor is not None else None, **extras)
            for codigo, valor, extras in valores
        ])
        return r

    @classmethod
    def relatorio_oleo(cls, data=date(2025, 12, 26), fq=FQ):
        rel, item = cls.item_de_rota(ModuloTecnico.OLEO_ISOLANTE, data)
        coleta = ColetaOleo.objects.create(
            item=item, data_coleta=data, amostrador="Fabrício Papa", temperatura_amostra_c=D("45.0"),
            temperatura_ambiente_c=D("31.0"), umidade_relativa_pct=D("58.0"),
            ponto_coleta=PontoColeta.objects.get(nome="Dreno Inferior Lado AT"),
            tipo_fluido=TipoFluido.objects.get(nome="Óleo Mineral B [Parafínico]"),
        )
        coleta.ensaios.set([cls.ensaio[s] for s in ("FQ", "CR", "PCB")])
        InspecaoVisualColeta.objects.bulk_create([
            InspecaoVisualColeta(coleta=coleta, item_checklist=i, estado="OK" if i.grupo == "GERAL" else "NA")
            for i in ItemChecklistVisual.objects.all()
        ])
        comum = {"criticidade": "ROTINA", "data_analise": date(2026, 1, 7), "data_proxima": date(2026, 12, 26),
                 "recomendacao": "Realizar nova amostragem dentro de 12 meses."}
        cls.resultado(item, "FQ", [(k, v, {}) for k, v in fq.items()] + [("APARENCIA", None, {"valor_texto": "Límpido"})],
                      numero_laudo="20260109001", **comum)
        cls.resultado(item, "CR", [(k, v, {}) for k, v in CR.items()], numero_laudo="20260109002", **comum)
        cls.resultado(item, "PCB", [("PCB", "0.5", {})], numero_laudo="20260109003",
                      informacoes_adicionais="* Valor de PCB expresso em Somatória de Aroclor 1242 / 1254 / 1260",
                      **comum)
        cls.resultado(item, "2FAL", situacao="NAO_COLETADO", criticidade="ROTINA", conclusao="Amostra não coletada!",
                      recomendacao="Recomenda-se realizar amostragem de equipamento com 10 anos ou mais de vida.")
        return rel, item

    @classmethod
    def relatorio_eletrico(cls, fases=RXT_FASES):
        rel, item = cls.item_de_rota(ModuloTecnico.ENSAIO_ELETRICO)
        registro = RegistroEnsaioEletrico.objects.create(
            item=item, data_ensaio=date(2025, 12, 26), analista="Fabrício Papa", tap="5", tensao_tap_v=D("11400"),
            temperatura_oleo_c=D("45.0"), temperatura_ambiente_c=D("35.0"), umidade_relativa_pct=D("54.0"),
        )
        registro.ensaios.set([cls.ensaio[s] for s in ("RXT", "RXI", "RXO")])
        instrumento = {
            modelo: Instrumento.objects.create(tipo=tipo, marca="Instrum", modelo=modelo, numero_serie=serie)
            for tipo, modelo, serie in (("TTR", "TTR-2000i", "IN-811721-24984"),
                                        ("Megôhmetro", "DMG-5Ki", "IN-811172-24990"),
                                        ("Microhmímetro", "MicroHM 10i", "IN-811172-24988"))
        }
        comum = {"criticidade": "ROTINA", "data_analise": date(2025, 12, 26), "data_proxima": date(2026, 12, 23),
                 "recomendacao": "Realizar novo ensaio no prazo de 12 meses."}
        cls.resultado(item, "RXT", [("MEDIDA", v, {"serie": f}) for f, v in fases.items()],
                      numero_laudo="20251226011", instrumento=instrumento["TTR-2000i"], **comum)
        valores = [("TENSAO", str(v), {"serie": s}) for s, v in RXI_SERIES]
        for tempo, leituras in RXI.items():
            valores += [("RESISTENCIA", str(r), {"serie": s, "posicao": D(tempo)})
                        for (s, _), r in zip(RXI_SERIES, leituras)]
        cls.resultado(item, "RXI", valores, numero_laudo="20251226012", instrumento=instrumento["DMG-5Ki"], **comum)
        cls.resultado(item, "RXO", [(k, v, {}) for k, v in RXO.items()], numero_laudo="20251226013",
                      instrumento=instrumento["MicroHM 10i"], **comum)
        return rel, item


class RelatorioTransformadorTest(CenarioTransformador, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar_parque()

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def dossie(self, rel):
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/dossie/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def carta_xml(self, rel):
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/carta-docx/")
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            return z.read("word/document.xml").decode("utf-8")

    @staticmethod
    def ficha(d, sigla):
        return next(f for f in d["transformadores"][0]["ensaios"] if f["sigla"] == sigla)

    # --- Óleo isolante ---
    def test_relatorio_de_oleo_no_mesmo_shell(self):
        rel, _ = self.relatorio_oleo()
        d = self.dossie(rel)
        self.assertEqual(d["modulo"], "OLEO_ISOLANTE")
        # Shell: relação de equipamentos com o transformador; nada das inspeções por rota.
        self.assertEqual(d["secao_c"]["total"], 1)
        self.assertEqual(d["secao_c"]["grupos"][0]["linhas"][0]["tag"], "TRF-001")
        self.assertNotIn("secao_d", d)
        t = d["transformadores"][0]
        self.assertEqual(t["cadastro"]["tensao_secundaria_fase_v"], D("220.00"))
        self.assertEqual(t["cadastro"]["ano_fabricacao"], 1996)
        self.assertEqual(t["coleta"]["ponto_coleta"], "Dreno Inferior Lado AT")
        self.assertEqual(len(t["inspecao_visual"]), 20)
        # Ficha de 2-FAL sai mesmo sem ser solicitada, porque tem resultado ("amostra não coletada").
        self.assertEqual([f["sigla"] for f in t["ensaios"]], ["FQ", "CR", "PCB", "2FAL"])
        self.assertEqual({x["sigla"]: x["solicitado"] for x in t["tipos_ensaio"]},
                         {"FQ": True, "CR": True, "PCB": True, "2FAL": False})

    def test_fichas_de_oleo_avaliam_cada_parametro_pela_referencia_da_norma(self):
        rel, _ = self.relatorio_oleo()
        d = self.dossie(rel)
        fq = self.ficha(d, "FQ")
        self.assertEqual(fq["status"], "CONFORME")
        self.assertEqual((fq["avaliados"], fq["fora"]), (8, 0))  # Cor é informativa
        self.assertEqual(fq["campanhas"][0]["valores"]["APARENCIA"]["texto"], "Límpido")
        grafico = {g["codigo"]: g for g in fq["grafico"]}
        self.assertNotIn("COR", grafico)
        self.assertEqual(grafico["RIGIDEZ"]["tipo_limite"], "MINIMO")
        self.assertEqual(grafico["RIGIDEZ"]["percentual"], D("157.5"))

        cr = self.ficha(d, "CR")
        self.assertEqual(cr["indicadores"], {"TG": D("60044"), "TGC": D("544")})
        self.assertNotIn("TG", [p["codigo"] for p in cr["parametros"]])  # calculados não viram coluna
        self.assertIsNone({g["codigo"]: g for g in cr["grafico"]}["C2H2"]["percentual"])
        self.assertEqual(cr["numero_laudo"], "20260109002")
        self.assertEqual(cr["criticidade"], "Rotina")
        self.assertEqual(cr["rotulos"]["proxima"], "Data da Próxima Coleta")

        fal = self.ficha(d, "2FAL")
        self.assertEqual((fal["situacao"], fal["status_rotulo"]), ("NAO_COLETADO", "Amostra não coletada"))
        self.assertEqual(len(fal["notas"]), 4)
        self.assertEqual(fal["notas"][0], "1. Análise realizada conforme a Norma NBR-15349:2006;")

        k = d["kpis"]
        self.assertEqual((k["transformadores"], k["ensaios_solicitados"], k["ensaios_realizados"]), (1, 3, 3))
        self.assertEqual(k["parametros_fora"], 0)
        self.assertEqual(k["proxima_data"], date(2026, 12, 26))
        self.assertEqual({x["rotulo"]: x["total"] for x in k["inspecao_visual"]},
                         {"Condição Normal": 12, "Não Aplicável": 8})

    def test_parametro_fora_da_referencia_reprova_o_ensaio(self):
        rel, _ = self.relatorio_oleo(fq={**FQ, "TEOR_AGUA": "41.00", "RIGIDEZ": "38.00"})
        d = self.dossie(rel)
        fq = self.ficha(d, "FQ")
        self.assertEqual((fq["status"], fq["fora"]), ("NAO_CONFORME", 2))
        self.assertFalse(fq["campanhas"][0]["valores"]["TEOR_AGUA"]["conforme"])
        self.assertEqual(d["kpis"]["parametros_fora"], 2)
        self.assertIn("1 fora delas (FQ)", d["carta"]["paragrafos"][0])

    def test_historico_traz_as_campanhas_anteriores_em_ordem(self):
        self.relatorio_oleo(data=date(2024, 12, 20), fq={**FQ, "TEOR_AGUA": "12.00"})
        rel, _ = self.relatorio_oleo()
        fq = self.ficha(self.dossie(rel), "FQ")
        self.assertEqual([c["data"] for c in fq["campanhas"]], [date(2024, 12, 20), date(2025, 12, 26)])
        self.assertEqual([c["atual"] for c in fq["campanhas"]], [False, True])
        self.assertEqual(fq["campanhas"][0]["valores"]["TEOR_AGUA"]["valor"], D("12.000000"))
        # Avaliação e gráfico são da campanha atual.
        self.assertEqual({g["codigo"]: g for g in fq["grafico"]}["TEOR_AGUA"]["percentual"], D("35"))

    def test_carta_do_oleo_tem_textos_e_resumo_do_modulo(self):
        rel, _ = self.relatorio_oleo()
        carta = self.dossie(rel)["carta"]
        self.assertEqual(carta["quebras_glossario"], ["6.3"])
        self.assertIn("Seção D – Fichas da Análise do Óleo Isolante [coleta e resultados dos ensaios]",
                      carta["conteudo"])
        self.assertIn("TGC", [g["sigla"] for g in carta["glossario"]])
        resumo = carta["paragrafos"][0]
        self.assertIn("foi analisada 1 amostra de óleo isolante, com os ensaios FQ, CR e Teor PCB.", resumo)
        self.assertIn("2-FAL (amostra não coletada)", resumo)
        xml = self.carta_xml(rel)
        self.assertIn("Fichas da Análise do Óleo Isolante", xml)
        self.assertIn("foi analisada 1 amostra de óleo isolante", xml)
        self.assertNotIn("Faixas de Velocidade e Classes de Máquina", xml)  # tabela ISO é da vibração

    # --- Ensaios elétricos ---
    def test_relatorio_de_ensaios_eletricos_reproduz_a_referencia(self):
        rel, _ = self.relatorio_eletrico()
        d = self.dossie(rel)
        self.assertEqual(d["modulo"], "ENSAIO_ELETRICO")
        t = d["transformadores"][0]
        self.assertEqual(t["registro"]["tap"], "5")
        self.assertEqual([f["sigla"] for f in t["ensaios"]], ["RXT", "RXI", "RXO"])

        rxt = self.ficha(d, "RXT")
        campanha = rxt["campanhas"][0]
        self.assertEqual(q(campanha["nominal"], 3), D("51.818"))
        self.assertTrue(campanha["nominal_calculada"])
        self.assertEqual([q(f["erro"]) for f in campanha["fases"]], [D("-0.23"), D("-0.42"), D("-0.36")])
        self.assertEqual(rxt["status"], "CONFORME")
        self.assertEqual(rxt["limite"]["norma"], "ANSI NETA ATS 2009")
        self.assertEqual(rxt["rotulos"]["conclusao"], "Observações")

        rxi = self.ficha(d, "RXI")
        self.assertEqual([s["nome"] for s in rxi["series"]], ["AT-BT-Massa", "AT-Massa-BT", "BT-Massa-AT"])
        self.assertEqual([s["tensao"] for s in rxi["series"]], [D("5000"), D("5000"), D("500")])
        self.assertEqual(len(rxi["tempos"]), 13)
        self.assertEqual(q(rxi["series"][0]["ip"], 3), D("1.108"))
        self.assertEqual(q(rxi["series"][0]["ia"], 3), D("3.333"))
        self.assertEqual(rxi["status"], "CONFORME")
        self.assertEqual(rxi["rotulos"]["proxima"], "Data da Próxima Coleta")

        rxo = self.ficha(d, "RXO")
        corrigido, calculado, medido = rxo["campanhas"][0]["linhas"]
        self.assertEqual([corrigido["tipo"], calculado["tipo"], medido["tipo"]], ["Corrigido", "Calculado", "Medido"])
        self.assertEqual(q(corrigido["valores"]["H1H2"]), D("5.83"))
        self.assertEqual(q(corrigido["valores"]["X0X3"]), D("1.63"))
        # Calculado só onde a leitura muda (AT em triângulo), como na ficha de referência.
        self.assertEqual(sorted(calculado["valores"]), ["H1H2", "H1H3", "H2H3"])
        self.assertEqual(len(medido["valores"]), 6)
        self.assertEqual(rxo["status"], "SEM_CRITERIO")  # a ficha não traz critério de aceitação

        k = d["kpis"]
        self.assertEqual(q(k["maior_erro_relacao"]), D("0.42"))
        self.assertEqual(q(k["menor_ip"], 3), D("1.108"))
        # Instrumentação de cada ensaio entra no cabeçalho (item 4 da carta).
        modelos = [i["modelo"] for i in d["cabecalho"]["instrumentos"]]
        self.assertEqual(modelos, ["TTR-2000i", "DMG-5Ki", "MicroHM 10i"])
        self.assertEqual(rxt["instrumento"], "Marca: Instrum / Modelo: TTR-2000i / Serial: IN-811721-24984")

    def test_erro_de_relacao_fora_da_tolerancia(self):
        rel, _ = self.relatorio_eletrico(fases={**RXT_FASES, "Fase 3 (H3-H1/X0-X1)": "52.200"})
        d = self.dossie(rel)
        rxt = self.ficha(d, "RXT")
        self.assertEqual((rxt["status"], rxt["fora"]), ("NAO_CONFORME", 1))
        self.assertEqual(q(d["kpis"]["maior_erro_relacao"]), D("0.74"))

    def test_carta_dos_ensaios_eletricos(self):
        rel, _ = self.relatorio_eletrico()
        carta = self.dossie(rel)["carta"]
        self.assertEqual(carta["quebras_glossario"], ["6.2"])
        self.assertIn("foi ensaiado 1 transformador, com os ensaios R×T, R×I e R×O.", carta["paragrafos"][0])
        self.assertIn("R×O sem critério de aceitação definido", carta["paragrafos"][0])
        xml = self.carta_xml(rel)
        self.assertIn("Fichas dos Ensaios Elétricos", xml)
        self.assertIn("TTR-2000i", xml)
        self.assertIn("MicroHM 10i", xml)


# ------------------------------------ API ------------------------------------
class ApiEnsaiosTest(CenarioTransformador, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar_parque()
        cls.rel_oleo, cls.item_oleo = cls.item_de_rota(ModuloTecnico.OLEO_ISOLANTE)
        cls.rel_eletrico, cls.item_eletrico = cls.item_de_rota(ModuloTecnico.ENSAIO_ELETRICO)
        cls.portal = User.objects.create_user(email="pcm@novaprom.com", password="x", nome="PCM",
                                              perfil="CLIENTE_PCM", cliente=cls.cliente)
        cls.portal_outro = User.objects.create_user(email="pcm@outra.com", password="x", nome="PCM outra",
                                                    perfil="CLIENTE_PCM", cliente=cls.outro_cliente)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def test_lanca_resultado_com_valores_e_substitui_na_edicao(self):
        p = self.param
        r = self.api.post("/api/resultados-ensaio/", {
            "item": self.item_oleo.pk, "ensaio": self.ensaio["PCB"].pk, "situacao": "REALIZADO",
            "numero_laudo": "20260109003", "origem": "PLANILHA",
            "valores": [{"parametro": p[("PCB", "PCB")].pk, "valor": "0.5"}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["valores"][0]["parametro_codigo"], "PCB")
        # Abaixo do LD: sem número, com o limite de detecção do laboratório.
        r = self.api.patch(f"/api/resultados-ensaio/{r.data['id']}/", {
            "valores": [{"parametro": p[("PCB", "PCB")].pk, "valor": None, "estado": "ABAIXO_LD",
                         "limite_deteccao": "2.0"}],
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        valores = ValorParametro.objects.filter(resultado_id=r.data["id"])
        self.assertEqual(valores.count(), 1)
        self.assertIsNone(valores.get().valor)
        self.assertEqual(valores.get().estado, "ABAIXO_LD")

    def test_recusa_valor_incoerente(self):
        p = self.param
        base = {"item": self.item_oleo.pk, "ensaio": self.ensaio["FQ"].pk, "situacao": "REALIZADO"}
        # Parâmetro de outro ensaio.
        r = self.api.post("/api/resultados-ensaio/", {**base, "valores": [{"parametro": p[("CR", "H2")].pk,
                                                                           "valor": "10"}]}, format="json")
        self.assertEqual(r.status_code, 400)
        # Parâmetro calculado pelo sistema (erro do R×T) não se digita.
        r = self.api.post("/api/resultados-ensaio/", {
            "item": self.item_eletrico.pk, "ensaio": self.ensaio["RXT"].pk,
            "valores": [{"parametro": p[("RXT", "ERRO")].pk, "valor": "0.1"}],
        }, format="json")
        self.assertEqual(r.status_code, 400)
        # Ensaio de óleo num transformador da rota de ensaios elétricos.
        r = self.api.post("/api/resultados-ensaio/", {**base, "item": self.item_eletrico.pk}, format="json")
        self.assertEqual(r.status_code, 400)
        # Próxima coleta antes da análise.
        r = self.api.post("/api/resultados-ensaio/", {**base, "data_analise": "2026-01-07",
                                                      "data_proxima": "2025-12-26"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_coleta_com_checklist_e_ensaios_do_modulo(self):
        itens = list(ItemChecklistVisual.objects.all()[:2])
        r = self.api.post("/api/coletas-oleo/", {
            "item": self.item_oleo.pk, "data_coleta": "2025-12-26", "amostrador": "Fabrício Papa",
            "ensaios": [self.ensaio["FQ"].pk, self.ensaio["CR"].pk],
            "inspecao_visual": [{"item_checklist": itens[0].pk, "estado": "OK"},
                                {"item_checklist": itens[1].pk, "estado": "NC", "observacao": "Vazamento"}],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(ColetaOleo.objects.get(pk=r.data["id"]).inspecao_visual.count(), 2)
        r = self.api.post("/api/registros-ensaio-eletrico/", {
            "item": self.item_eletrico.pk, "data_ensaio": "2025-12-26", "ensaios": [self.ensaio["FQ"].pk],
        }, format="json")
        self.assertEqual(r.status_code, 400)  # FQ não é ensaio elétrico

    def test_portal_so_consulta_os_ensaios_da_propria_empresa(self):
        self.resultado(self.item_oleo, "PCB", [("PCB", "0.5", {})])
        cliente = APIClient()
        cliente.force_authenticate(self.portal)
        self.assertEqual(len(cliente.get("/api/resultados-ensaio/").data["results"]), 1)
        r = cliente.post("/api/resultados-ensaio/", {"item": self.item_oleo.pk, "ensaio": self.ensaio["FQ"].pk},
                         format="json")
        self.assertEqual(r.status_code, 403)
        outro = APIClient()
        outro.force_authenticate(self.portal_outro)
        self.assertEqual(outro.get("/api/resultados-ensaio/").data["results"], [])

    def test_catalogo_de_ensaios_por_modulo(self):
        r = self.api.get("/api/ensaios/", {"modulo": "ENSAIO_ELETRICO"})
        self.assertEqual([e["sigla"] for e in r.data["results"]], ["RXT", "RXI", "RXO"])
        rxt = r.data["results"][0]
        self.assertEqual(next(p for p in rxt["parametros"] if p["codigo"] == "ERRO")["norma"], "ANSI NETA ATS 2009")


# --------------------------- Lançamento pela tela ---------------------------
class LancamentoTransformadorTest(CenarioTransformador, TestCase):
    """O que as telas de campo e de escritório usam além do CRUD de ensaios."""

    @classmethod
    def setUpTestData(cls):
        cls.criar_parque()
        cls.rel_oleo, cls.item_oleo = cls.item_de_rota(ModuloTecnico.OLEO_ISOLANTE)
        cls.rel_eletrico, cls.item_eletrico = cls.item_de_rota(ModuloTecnico.ENSAIO_ELETRICO)
        cls.portal_outro = User.objects.create_user(email="pcm@outra.com", password="x", nome="PCM outra",
                                                    perfil="CLIENTE_PCM", cliente=cls.outro_cliente)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def test_carregamento_informa_o_modulo_da_tecnologia(self):
        carreg = self.item_oleo.carregamento
        self.assertEqual(self.api.get(f"/api/carregamentos/{carreg.pk}/").data["modulo_tecnico"], "OLEO_ISOLANTE")
        lista = self.api.get("/api/carregamentos/", {"cliente": self.cliente.pk}).data["results"]
        self.assertEqual({c["modulo_tecnico"] for c in lista}, {"OLEO_ISOLANTE", "ENSAIO_ELETRICO"})

    def test_salvar_resultado_devolve_os_calculos_da_ficha(self):
        RegistroEnsaioEletrico.objects.create(item=self.item_eletrico, data_ensaio=date(2025, 12, 26), tap="5",
                                              tensao_tap_v=D("11400"), temperatura_oleo_c=D("45.0"))
        r = self.api.post("/api/resultados-ensaio/", {
            "item": self.item_eletrico.pk, "ensaio": self.ensaio["RXT"].pk, "situacao": "REALIZADO",
            "valores": [{"parametro": self.param[("RXT", "MEDIDA")].pk, "serie": f, "valor": v}
                        for f, v in RXT_FASES.items()],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        avaliacao = r.data["avaliacao"]
        self.assertEqual(avaliacao["status"], "CONFORME")
        campanha = avaliacao["campanhas"][0]
        self.assertEqual(q(campanha["nominal"], 3), D("51.818"))
        self.assertEqual([q(f["erro"]) for f in campanha["fases"]], [D("-0.23"), D("-0.42"), D("-0.36")])

        r = self.api.post("/api/resultados-ensaio/", {
            "item": self.item_oleo.pk, "ensaio": self.ensaio["CR"].pk, "situacao": "REALIZADO",
            "valores": [{"parametro": self.param[("CR", k)].pk, "valor": v} for k, v in CR.items()],
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(r.data["avaliacao"]["indicadores"], {"TG": D("60044"), "TGC": D("544")})

    def test_fila_do_lancamento_mostra_o_que_falta_por_transformador(self):
        coleta = ColetaOleo.objects.create(item=self.item_oleo, data_coleta=date(2025, 12, 26))
        coleta.ensaios.set([self.ensaio["FQ"], self.ensaio["CR"]])
        self.resultado(self.item_oleo, "FQ", [("TEOR_AGUA", "14", {})])
        _, item_vibracao = self.item_de_rota(ModuloTecnico.VIBRACAO)

        r = self.api.get("/api/transformadores-inspecao/", {"carregamento__cliente": self.cliente.pk})
        self.assertEqual(r.status_code, 200)
        por_item = {t["id"]: t for t in r.data["results"]}
        self.assertNotIn(item_vibracao.pk, por_item)  # só rotas dos módulos de transformador
        oleo = por_item[self.item_oleo.pk]
        self.assertEqual((oleo["modulo"], oleo["registro"]["id"], oleo["pendentes"]), ("OLEO_ISOLANTE", coleta.pk, 1))
        self.assertEqual({e["sigla"]: (e["solicitado"], e["situacao"]) for e in oleo["ensaios"]}, {
            "FQ": (True, "REALIZADO"), "CR": (True, None), "PCB": (False, None), "2FAL": (False, None),
        })
        eletrico = por_item[self.item_eletrico.pk]
        self.assertEqual((eletrico["registro"], eletrico["pendentes"]), (None, 0))

        outro = APIClient()
        outro.force_authenticate(self.portal_outro)
        self.assertEqual(outro.get("/api/transformadores-inspecao/").data["results"], [])

    def test_fila_do_lancamento_nao_faz_consulta_por_transformador(self):
        def consultas():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.api.get("/api/transformadores-inspecao/").status_code, 200)
            return len(ctx.captured_queries)

        def mais_um_transformador_com_laudo():
            _, item = self.item_de_rota(ModuloTecnico.OLEO_ISOLANTE)
            ColetaOleo.objects.create(item=item, data_coleta=date(2025, 12, 26)).ensaios.set([self.ensaio["FQ"]])
            self.resultado(item, "FQ", [("TEOR_AGUA", "14", {})])

        # Parte de um cenário que já tem coleta e resultado: sem nenhum, o Django
        # nem roda os prefetches — a diferença não seria consulta por transformador.
        mais_um_transformador_com_laudo()
        antes = consultas()
        for _ in range(3):
            mais_um_transformador_com_laudo()
        self.assertEqual(consultas(), antes)
