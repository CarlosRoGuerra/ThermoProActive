"""
Anexo I 3.1.11 — entidade Sensores (cadastro; sem ingestão IoT).

Cobre: CRUD por perfil interno, escopo do cliente pelo equipamento (falha fechada),
impedimento de apontar para equipamento de outro cliente, validações de faixa e de data.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Nivel
from apps.cadastros.models import Area, Cliente, Equipamento, Sensor, Setor, TipoEquipamento

User = get_user_model()


class SensorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.a = Cliente.objects.create(nome="Cliente A", cnpj="11.111.111/0001-11")
        cls.b = Cliente.objects.create(nome="Cliente B", cnpj="22.222.222/0001-22")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        cls.eq_a = Equipamento.objects.create(
            setor=Setor.objects.create(area=Area.objects.create(cliente=cls.a, codigo="A", nome="A"),
                                       codigo="A", nome="A"),
            tag="A-001", nome="Motor A", tipo_equipamento=tipo)
        cls.eq_b = Equipamento.objects.create(
            setor=Setor.objects.create(area=Area.objects.create(cliente=cls.b, codigo="B", nome="B"),
                                       codigo="B", nome="B"),
            tag="B-001", nome="Motor B", tipo_equipamento=tipo)
        mk = lambda e, p, **kw: User.objects.create_user(email=e, password="x", nome=e, perfil=p, **kw)  # noqa: E731
        cls.tecnico = mk("tec@thermo.test", "TECNICO")
        cls.cli_a = mk("a@a.test", "CLIENTE_PCM", cliente=cls.a)
        cls.cli_b = mk("b@b.test", "CLIENTE_PCM", cliente=cls.b)
        cls.sensor_a = Sensor.objects.create(
            equipamento=cls.eq_a, ponto_instalacao="Mancal LA", tipo="ACELEROMETRO",
            grandeza="aceleração", unidade="mm/s", faixa_minima=Decimal("0"), faixa_maxima=Decimal("50"))
        cls.sensor_b = Sensor.objects.create(
            equipamento=cls.eq_b, ponto_instalacao="Mancal LB", tipo="PT100")

    def api(self, usuario=None):
        c = APIClient()
        if usuario is not None:
            c.force_authenticate(usuario)
        return c

    def payload(self, **extra):
        base = {"equipamento": self.eq_a.pk, "ponto_instalacao": "Carcaça", "tipo": "TERMOPAR",
                "fabricante": "Fab", "modelo": "M1", "numero_serie": "S-1", "unidade": "°C",
                "faixa_minima": "-20", "faixa_maxima": "300", "status": "ATIVO"}
        base.update(extra)
        return base

    def test_interno_cadastra_sensor(self):
        r = self.api(self.tecnico).post("/api/sensores/", self.payload(), format="json")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(r.json()["tipo_display"], "Termopar")

    def test_cliente_le_apenas_os_sensores_do_proprio_cliente(self):
        ids = [x["id"] for x in self.api(self.cli_a).get("/api/sensores/").json()["results"]]
        self.assertIn(self.sensor_a.pk, ids)
        self.assertNotIn(self.sensor_b.pk, ids)
        self.assertEqual(self.api(self.cli_a).get(f"/api/sensores/{self.sensor_b.pk}/").status_code, 404)

    def test_cliente_nao_cria_sensor(self):
        self.assertEqual(self.api(self.cli_a).post("/api/sensores/", self.payload(), format="json").status_code, 403)

    def test_cliente_nao_aponta_para_equipamento_de_outro_cliente(self):
        # Cliente não escreve (403 pela permissão). Interno pode cadastrar para qualquer cliente
        # (é o trabalho dele), mas o cliente de outro tenant nunca consegue o vínculo.
        r = self.api(self.cli_a).post("/api/sensores/", self.payload(equipamento=self.eq_b.pk), format="json")
        self.assertEqual(r.status_code, 403)
        self.assertFalse(Sensor.objects.filter(equipamento=self.eq_b, ponto_instalacao="Carcaça").exists())

    def test_cliente_sem_vinculo_nao_ve_nada(self):
        sem = User.objects.create_user(email="s@s.test", password="x", nome="s", perfil="CLIENTE_PCM")
        self.assertEqual(self.api(sem).get("/api/sensores/").json()["count"], 0)

    def test_faixa_invertida_e_recusada(self):
        r = self.api(self.tecnico).post("/api/sensores/", self.payload(faixa_minima="10", faixa_maxima="5"),
                                        format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("faixa_maxima", r.json())

    def test_data_futura_e_recusada(self):
        futuro = (date.today() + timedelta(days=3)).isoformat()
        r = self.api(self.tecnico).post("/api/sensores/", self.payload(data_ultima_calibracao=futuro), format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("data_ultima_calibracao", r.json())

    def test_exclusao_e_logica(self):
        master = User.objects.create_user(email="m@thermo.test", password="x", nome="m", perfil="TECNICO",
                                          nivel=Nivel.MASTER)
        r = self.api(master).delete(f"/api/sensores/{self.sensor_a.pk}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(Sensor.objects.get(pk=self.sensor_a.pk).ativo)

    def test_filtro_por_equipamento(self):
        r = self.api(self.tecnico).get(f"/api/sensores/?equipamento={self.eq_b.pk}")
        self.assertEqual([x["id"] for x in r.json()["results"]], [self.sensor_b.pk])

    def test_sem_login_nao_acessa(self):
        self.assertIn(self.api(None).get("/api/sensores/").status_code, (401, 403))
