"""
Testes de "quantidade de planos" (1 ou 2, nunca 3) e "ponto de foco" (só ele recebe
Trial Run — Trim Run continua livre em qualquer ponto).

Cobre o critério de aceite pedido pelo cliente: plano físico (BalanceamentoPlano) não é
a mesma coisa que etapa de medição (Reference/Trial/Trim Run em BalanceamentoPonto).
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, Setor

from .models import BalanceamentoPlano, BalanceamentoPonto, ServicoCampo, TipoServico


class PontoFocoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Exemplo Indústria Têxtil", cnpj="11.111.111/0001-11")
        area = Area.objects.create(cliente=cls.cliente, nome="Área")
        setor = Setor.objects.create(area=area, nome="Setor")
        cls.equipamento = Equipamento.objects.create(setor=setor, tag="EX-1", nome="Exaustor", classe_iso="II")
        cls.analista = get_user_model().objects.create_user(
            email="analista@example.com", nome="Analista", perfil="TECNICO", nivel="MASTER",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)
        self.servico = ServicoCampo.objects.create(
            cliente=self.cliente, equipamento=self.equipamento, tipo=TipoServico.BALANCEAMENTO,
            analista=self.analista, data_execucao="2026-09-10", rotacao_hz="29.74",
        )

    def criar_ponto(self, servico=None, numero_mancal=1, reference_mms="12.31"):
        resposta = self.api.post("/api/balanceamento-pontos/", {
            "servico": (servico or self.servico).pk, "numero_mancal": numero_mancal, "direcao": "H",
            "reference_mms": reference_mms, "reference_fase": "110",
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta.data

    def test_reference_run_zero_e_rejeitado_pela_api(self):
        # A curva de redução divide pela referência — zero quebraria o cálculo. A regra
        # pura já é testada em CurvaReducaoTest; aqui confirmamos que a API (não só a
        # função) barra isso antes de chegar a salvar.
        resposta = self.api.post("/api/balanceamento-pontos/", {
            "servico": self.servico.pk, "numero_mancal": 1, "direcao": "H",
            "reference_mms": "0", "reference_fase": "110",
        }, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("reference_mms", resposta.data)
        self.assertFalse(BalanceamentoPonto.objects.exists())

    # --- Quantidade de planos: 1 ou 2, nunca 3 -----------------------------

    def test_plano_numero_1_e_2_sao_aceitos(self):
        for numero in (1, 2):
            with self.subTest(numero=numero):
                resposta = self.api.post("/api/balanceamento-planos/", {
                    "servico": self.servico.pk, "numero": numero,
                }, format="json")
                self.assertEqual(resposta.status_code, 201, resposta.data)

    def test_plano_numero_3_rejeitado_pelo_serializer(self):
        resposta = self.api.post("/api/balanceamento-planos/", {
            "servico": self.servico.pk, "numero": 3,
        }, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("numero", resposta.data)
        self.assertFalse(BalanceamentoPlano.objects.exists())

    def test_plano_numero_3_rejeitado_pelo_banco_mesmo_contornando_o_serializer(self):
        # Defesa em profundidade: mesmo criando direto pelo ORM (sem passar pelo
        # serializer), o CheckConstraint do banco não deixa existir um plano 3.
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                BalanceamentoPlano.objects.create(servico=self.servico, numero=3)

    # --- Ponto de foco -------------------------------------------------------

    def test_ponto_foco_deve_pertencer_ao_mesmo_servico(self):
        ponto = self.criar_ponto()
        outro_servico = ServicoCampo.objects.create(
            cliente=self.cliente, equipamento=self.equipamento, tipo=TipoServico.BALANCEAMENTO,
            analista=self.analista, data_execucao="2026-09-10",
        )
        ponto_de_outro = self.criar_ponto(servico=outro_servico)
        resposta = self.api.patch(
            f"/api/servicos/{self.servico.pk}/", {"ponto_foco": ponto_de_outro["id"]}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        resposta = self.api.patch(
            f"/api/servicos/{self.servico.pk}/", {"ponto_foco": ponto["id"]}, format="json"
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(resposta.data["ponto_foco"], ponto["id"])

    def test_trial_run_so_no_ponto_de_foco(self):
        p1 = self.criar_ponto(numero_mancal=1, reference_mms="12.31")
        p2 = self.criar_ponto(numero_mancal=2, reference_mms="8.00")

        # Sem ponto de foco escolhido ainda: nenhum dos dois pode receber Trial Run.
        for p in (p1, p2):
            resposta = self.api.patch(
                f'/api/balanceamento-pontos/{p["id"]}/', {"trial_mms": "20", "trial_fase": "100"}, format="json"
            )
            self.assertEqual(resposta.status_code, 400)
            self.assertIn("trial_mms", resposta.data)

        # Escolhido p1 como foco (maior amplitude):
        foco = self.api.patch(f"/api/servicos/{self.servico.pk}/", {"ponto_foco": p1["id"]}, format="json")
        self.assertEqual(foco.status_code, 200, foco.data)

        ok = self.api.patch(
            f'/api/balanceamento-pontos/{p1["id"]}/', {"trial_mms": "23.95", "trial_fase": "133"}, format="json"
        )
        self.assertEqual(ok.status_code, 200, ok.data)

        ainda_rejeita = self.api.patch(
            f'/api/balanceamento-pontos/{p2["id"]}/', {"trial_mms": "15", "trial_fase": "90"}, format="json"
        )
        self.assertEqual(ainda_rejeita.status_code, 400)

    def test_trim_run_livre_em_qualquer_ponto_mesmo_sem_ser_o_foco(self):
        # Trim Run não é restrito ao ponto de foco — "Todos os pontos: Trim Run -> SIM".
        p1 = self.criar_ponto(numero_mancal=1)
        p2 = self.criar_ponto(numero_mancal=2)
        self.api.patch(f"/api/servicos/{self.servico.pk}/", {"ponto_foco": p1["id"]}, format="json")
        for p in (p1, p2):
            resposta = self.api.patch(
                f'/api/balanceamento-pontos/{p["id"]}/', {"trim_mms": "1.70", "trim_fase": "136"}, format="json"
            )
            self.assertEqual(resposta.status_code, 200, resposta.data)
            self.assertTrue(resposta.data["completo"])

    def test_apagar_ponto_foco_desfaz_a_referencia_no_servico(self):
        ponto = self.criar_ponto()
        self.api.patch(f"/api/servicos/{self.servico.pk}/", {"ponto_foco": ponto["id"]}, format="json")
        resposta = self.api.delete(f'/api/balanceamento-pontos/{ponto["id"]}/')
        self.assertEqual(resposta.status_code, 204)
        self.servico.refresh_from_db()
        self.assertIsNone(self.servico.ponto_foco_id)

    # --- Compatibilidade com dados antigos ------------------------------------

    def test_dados_antigos_sem_ponto_foco_e_identificacao_continuam_legiveis(self):
        # Simula um registro criado ANTES desta migração: sem ponto_foco no serviço e
        # sem identificação no ponto (os dois campos são aditivos, com default vazio).
        ponto = BalanceamentoPonto.objects.create(
            servico=self.servico, numero_mancal=1, direcao="H",
            reference_mms="12.31", reference_fase="110",
            trial_mms="23.95", trial_fase="133", trim_mms="1.70", trim_fase="136",
        )
        resposta = self.api.get(f"/api/servicos/{self.servico.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.data["ponto_foco"])
        ponto_serializado = next(p for p in resposta.data["pontos"] if p["id"] == ponto.id)
        self.assertEqual(ponto_serializado["identificacao"], "")
        self.assertEqual(ponto_serializado["trial_mms"], "23.95")
        self.assertTrue(ponto_serializado["completo"])
