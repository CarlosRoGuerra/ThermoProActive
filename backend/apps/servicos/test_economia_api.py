"""
Testes de API da Economia energética: integração com o cadastro do equipamento
(tensão/FP) e validação contra resultados matematicamente inválidos (correntes/regime/
dias/FP/investimento fora do domínio físico).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor

from .models import ServicoCampo, TipoServico


class EconomiaApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Exemplo Indústria Têxtil", cnpj="11.111.111/0001-11")
        area = Area.objects.create(cliente=cls.cliente, nome="Área")
        setor = Setor.objects.create(area=area, nome="Setor")
        cls.equipamento_com_placa = Equipamento.objects.create(
            setor=setor, tag="EX-1", nome="Exaustor", classe_iso="II",
            tensao_nominal="380", fator_potencia_nominal="0.93",
        )
        cls.equipamento_sem_placa = Equipamento.objects.create(
            setor=setor, tag="EX-2", nome="Exaustor sem placa", classe_iso="II",
        )
        cls.analista = get_user_model().objects.create_user(
            email="analista@example.com", nome="Analista", perfil="TECNICO",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)

    def criar_servico(self, equipamento):
        servico = ServicoCampo.objects.create(
            cliente=self.cliente, equipamento=equipamento, tipo=TipoServico.BALANCEAMENTO,
            analista=self.analista, data_execucao="2026-09-10",
        )
        return servico

    def payload_valido(self, servico):
        return {
            "servico": servico.pk, "tensao_v": "380", "corrente_antes_a": "71",
            "corrente_apos_a": "66.2", "fator_potencia": "0.93", "horas_dia": "20",
            "dias_ano": 365, "custo_kwh": "0.35", "investimento": "1606",
        }

    # --- Integração com o cadastro do equipamento ---------------------------

    def test_servico_expoe_tensao_e_fp_do_cadastro_quando_existem(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        resposta = self.api.get(f"/api/servicos/{servico.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.data["equipamento_tensao_nominal"], "380.00")
        self.assertEqual(resposta.data["equipamento_fator_potencia_nominal"], "0.930")

    def test_servico_expoe_nulo_quando_equipamento_nao_tem_placa_cadastrada(self):
        # "Não assumir valores": sem dado no cadastro, o front precisa saber que falta,
        # não receber um número qualquer.
        servico = self.criar_servico(self.equipamento_sem_placa)
        resposta = self.api.get(f"/api/servicos/{servico.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.data["equipamento_tensao_nominal"])
        self.assertIsNone(resposta.data["equipamento_fator_potencia_nominal"])

    # --- Validação contra resultados matematicamente inválidos ---------------

    def test_cria_economia_com_dados_validos(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        resposta = self.api.post("/api/economias/", self.payload_valido(servico), format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["reducao_corrente_a"], "4.80")

    def test_rejeita_corrente_negativa(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = {**self.payload_valido(servico), "corrente_antes_a": "-5"}
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("corrente_antes_a", resposta.data)

    def test_rejeita_regime_diario_acima_de_24h(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = {**self.payload_valido(servico), "horas_dia": "25"}
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("horas_dia", resposta.data)

    def test_rejeita_dias_por_ano_acima_de_366(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = {**self.payload_valido(servico), "dias_ano": 400}
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("dias_ano", resposta.data)

    def test_rejeita_fator_de_potencia_fora_de_0_a_1(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        for valor in ("-0.1", "1.5"):
            with self.subTest(fator_potencia=valor):
                payload = {**self.payload_valido(servico), "fator_potencia": valor}
                resposta = self.api.post("/api/economias/", payload, format="json")
                self.assertEqual(resposta.status_code, 400)
                self.assertIn("fator_potencia", resposta.data)

    def test_rejeita_investimento_negativo(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = {**self.payload_valido(servico), "investimento": "-100"}
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("investimento", resposta.data)

    def test_investimento_e_obrigatorio_na_api(self):
        # Nulo só é permitido no banco para registros anteriores a este campo existir —
        # pela API é sempre exigido, como as demais entradas da economia.
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = self.payload_valido(servico)
        del payload["investimento"]
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("investimento", resposta.data)

    def test_rejeita_custo_kwh_negativo(self):
        servico = self.criar_servico(self.equipamento_com_placa)
        payload = {**self.payload_valido(servico), "custo_kwh": "-0.35"}
        resposta = self.api.post("/api/economias/", payload, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("custo_kwh", resposta.data)
