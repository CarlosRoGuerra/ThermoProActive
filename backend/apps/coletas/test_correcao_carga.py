"""
Correção da temperatura pela carga (C.T.M.) — fórmula do Fabrício (16/11/2026).

O caso de referência é o exemplo do próprio documento: disjuntor de 100 A em carga de 70 A,
TM 100 °C, TA 30 °C → ΔT2 = 115,71 °C e T2 = 145,7 °C na carga de 90 %.
"""
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Condicao, Equipamento, ModuloTecnico, Setor, TecnologiaAnalise
from apps.coletas.correcao_carga import calcular
from apps.coletas.models import Achado, Carregamento, ItemInspecao, Relatorio


def correcao(**dados):
    base = dict(temperatura_medida=D("100.0"), temperatura_referencia=None, temperatura_ambiente=D("30.0"),
                carga_digitada=None, corrente_nominal=D("100.00"), correntes={"R": D("70.00"), "S": None, "T": None},
                fase="")
    return calcular(**{**base, **dados})


class FormulaTest(SimpleTestCase):
    def test_exemplo_do_documento(self):
        c = correcao()
        self.assertEqual((c.carga_percentual, c.carga_calculada, c.corrente_trabalho, c.fase), (D("70.0"), True, D("70.00"), "R"))
        self.assertEqual(round(c.fator, 6), round((D("90") / D("70")) ** 2, 6))
        self.assertEqual(c.temperatura_medida_corrigida, D("145.7"))
        self.assertEqual(c.pendencia, "")

    def test_delta_corrigido_e_a_referencia_corrigida_pela_mesma_formula(self):
        # TR 50 °C: TR2 = 30 + 20 × (90/70)² = 63,1; ΔT corrigido = (100 − 50) × (90/70)² = 82,7 = TM2 − TR2.
        c = correcao(temperatura_referencia=D("50.0"))
        self.assertEqual((c.temperatura_referencia_corrigida, c.delta_t_corrigido), (D("63.1"), D("82.7")))
        # O ΔT corrigido não depende do ambiente: sai mesmo sem TA (a T. medida corrigida não).
        sem_ta = correcao(temperatura_referencia=D("50.0"), temperatura_ambiente=None)
        self.assertEqual((sem_ta.delta_t_corrigido, sem_ta.temperatura_medida_corrigida), (D("82.7"), None))
        self.assertIn("temperatura ambiente", sem_ta.pendencia)

    def test_carga_digitada_quando_as_correntes_nao_foram_medidas(self):
        c = correcao(corrente_nominal=None, correntes={"R": None, "S": None, "T": None}, carga_digitada=D("70.0"))
        self.assertEqual((c.carga_percentual, c.carga_calculada, c.temperatura_medida_corrigida), (D("70.0"), False, D("145.7")))
        # Correntes sem a nominal: a carga continua a digitada.
        c = correcao(corrente_nominal=None, carga_digitada=D("70.0"))
        self.assertEqual((c.carga_calculada, c.temperatura_medida_corrigida), (False, D("145.7")))

    def test_carga_calculada_prevalece_sobre_a_digitada(self):
        c = correcao(carga_digitada=D("50.0"))
        self.assertEqual((c.carga_percentual, c.carga_calculada), (D("70.0"), True))

    def test_qual_corrente_vale_com_varias_fases(self):
        tres = {"R": D("62.00"), "S": D("70.00"), "T": D("61.00")}
        # Sem fase escolhida, não adivinha: pede a fase e não corrige.
        c = correcao(correntes=tres, carga_digitada=D("40.0"))
        self.assertIsNone(c.temperatura_medida_corrigida)
        self.assertEqual(c.carga_percentual, D("40.0"))  # o digitado fica, mas não é usado
        self.assertIn("informe a fase", c.pendencia)
        # Fase escolhida.
        c = correcao(correntes=tres, fase="S")
        self.assertEqual((c.corrente_trabalho, c.fase, c.temperatura_medida_corrigida), (D("70.00"), "S", D("145.7")))
        # Todas as fases: a maior.
        c = correcao(correntes=tres, fase="MAIOR")
        self.assertEqual((c.corrente_trabalho, c.fase), (D("70.00"), "S"))
        # Fase escolhida sem corrente medida.
        c = correcao(correntes=tres | {"T": None}, fase="T")
        self.assertIsNone(c.temperatura_medida_corrigida)
        self.assertIn("fase T não foi medida", c.pendencia)

    def test_nao_corrige_com_carga_de_90_por_cento_ou_mais(self):
        for corrente in ("90.00", "100.00", "105.00"):
            c = correcao(correntes={"R": D(corrente), "S": None, "T": None})
            self.assertIsNone(c.temperatura_medida_corrigida, corrente)
            self.assertIn("não se aplica", c.pendencia)
        self.assertEqual(correcao(correntes={"R": D("89.90"), "S": None, "T": None}).temperatura_medida_corrigida, D("100.2"))

    def test_sem_carga_ou_com_carga_zero_nao_corrige(self):
        nada = correcao(corrente_nominal=None, correntes={"R": None, "S": None, "T": None})
        self.assertIsNone(nada.temperatura_medida_corrigida)
        self.assertIn("% de carga", nada.pendencia)
        zero = correcao(correntes={"R": D("0"), "S": None, "T": None})
        self.assertIsNone(zero.temperatura_medida_corrigida)
        self.assertIn("carga zero", zero.pendencia)

    def test_sem_temperatura_medida_nao_ha_pendencia(self):
        # Vibração e afins: nada a corrigir, nenhum aviso.
        c = correcao(temperatura_medida=None)
        self.assertEqual((c.temperatura_medida_corrigida, c.pendencia), (None, ""))
        self.assertEqual(c.carga_percentual, D("70.0"))

    def test_extrapolacao_que_nao_cabe_no_campo_nao_quebra(self):
        c = correcao(correntes={"R": D("0.01"), "S": None, "T": None}, temperatura_medida=D("900.0"))
        self.assertIsNone(c.temperatura_medida_corrigida)
        self.assertIn("baixa demais", c.pendencia)

    def test_arredonda_meio_para_cima(self):
        # (90/60)² = 2,25; 30 + 10,1 × 2,25 = 52,725 → 52,7; 30 + 10,2 × 2,25 = 52,95 → 53,0 (não 52,9).
        def t2(tm):
            return correcao(temperatura_medida=D(tm), correntes={"R": D("60.00"), "S": None, "T": None}).temperatura_medida_corrigida
        self.assertEqual((t2("40.1"), t2("40.2")), (D("52.7"), D("53.0")))


class CorrecaoNaAnaliseTest(TestCase):
    """A análise grava os valores calculados e a OSP do relatório mostra os mesmos."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.analista = get_user_model().objects.create_user(
            email="analista@thermo.com", nome="Analista", perfil="TECNICO", nivel="SENIOR",
        )
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Matriz"), nome="Cabine")
        cls.equipamento = Equipamento.objects.create(setor=setor, nome="QGBT-1")
        cls.gr3 = Condicao.objects.create(nome="Grau de Risco MODERADO", sigla="GR-3", gera_acao=True)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)
        tecnologia = TecnologiaAnalise.objects.create(nome="Termografia", sigla="TE", modulo_tecnico=ModuloTecnico.TERMOGRAFIA)
        self.rel = Relatorio.objects.create(cliente=self.cliente, tecnologia=tecnologia,
                                            numero="RT-TE-2026-05-18-00001", data_termino=date(2026, 5, 18))
        rota = Carregamento.objects.create(cliente=self.cliente, tecnologia=tecnologia, analista=self.analista, relatorio=self.rel)
        item = ItemInspecao.objects.create(carregamento=rota, equipamento=self.equipamento, ordem=1, condicao=self.gr3)
        self.achado = Achado.objects.create(item=item, componente_texto="Disjuntor(es) DJ7", condicao=self.gr3,
                                            temperatura_medida=D("100.0"), temperatura_referencia=D("50.0"))

    def test_salvar_a_analise_calcula_e_a_osp_mostra(self):
        r = self.api.patch(f"/api/achados/{self.achado.pk}/", {
            "temperatura_ambiente": "30.0", "corrente_nominal": "100.00",
            "corrente_a": "62.00", "corrente_b": "70.00", "corrente_c": "61.00", "fase_anomalia": "S",
            # Valores mandados para os campos calculados são ignorados.
            "carga_percentual": "10.0", "temperatura_medida_corrigida": "999.9", "delta_t_corrigido": "999.9",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual((r.data["carga_percentual"], r.data["temperatura_medida_corrigida"], r.data["delta_t_corrigido"]),
                         ("70.0", "145.7", "82.7"))
        self.assertEqual(r.data["correcao_carga"], {"carga_calculada": True, "corrente_trabalho": "70.00", "fase": "S",
                                                    "fator": "1.6531", "pendencia": ""})

        folha = self.api.get(f"/api/relatorios-inspecao/{self.rel.pk}/dossie/").data["secao_d"][0]
        self.assertEqual((folha["carga_percentual"], folha["temperatura_medida_corrigida"], folha["delta_t_corrigido"]),
                         (D("70.0"), D("145.7"), D("82.7")))
        self.assertEqual(folha["delta_t"], D("50.0"))  # o ΔT medido não muda

    def test_trocar_a_entrada_recalcula_e_tirar_a_carga_limpa(self):
        self.api.patch(f"/api/achados/{self.achado.pk}/", {"temperatura_ambiente": "30.0", "carga_percentual": "70.0"}, format="json")
        self.achado.refresh_from_db()
        self.assertEqual(self.achado.temperatura_medida_corrigida, D("145.7"))
        self.api.patch(f"/api/achados/{self.achado.pk}/", {"carga_percentual": None}, format="json")
        self.achado.refresh_from_db()
        self.assertEqual((self.achado.temperatura_medida_corrigida, self.achado.delta_t_corrigido), (None, None))

    def test_save_parcial_grava_os_derivados(self):
        self.achado.temperatura_ambiente = D("30.0")
        self.achado.carga_percentual = D("70.0")
        self.achado.save(update_fields=["temperatura_ambiente", "carga_percentual"])
        self.achado.refresh_from_db()
        self.assertEqual(self.achado.temperatura_medida_corrigida, D("145.7"))
