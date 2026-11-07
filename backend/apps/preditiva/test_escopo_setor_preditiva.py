"""Restrição de setor (2.1.1.6) nas rotas de análise preditiva e de coleta técnica.

Fora do setor permitido: o ranking omite o equipamento e o detalhe responde 404.
Sem restrição, o cliente vê o cliente inteiro. Interno nunca é restringido.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Nivel, Perfil, RestricaoSetorUsuario, User
from apps.cadastros.models import Area, Cliente, Empresa, Equipamento, Setor, TipoEquipamento
from apps.coletas.models import Inspecao, MedicaoTecnica, MedicaoVibracao


def _usuario(email, perfil, nivel, **vinculo):
    return User.objects.create_user(email=email, password="uma frase senha longa 2026", nome=email,
                                    perfil=perfil, nivel=nivel, **vinculo)


class EscopoSetorPreditivaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.empresa = Empresa.objects.create(nome="Prestadora", cnpj="11.222.333/0001-81")
        cls.cliente = Cliente.objects.create(nome="A", cnpj="11.111.111/0001-11")
        tipo = TipoEquipamento.objects.create(nome="Motor")
        area = Area.objects.create(cliente=cls.cliente, codigo="A1", nome="Planta")
        cls.setor1 = Setor.objects.create(area=area, codigo="S1", nome="Setor 1")
        cls.setor2 = Setor.objects.create(area=area, codigo="S2", nome="Setor 2")
        cls.eq1 = Equipamento.objects.create(setor=cls.setor1, tag="E-SETOR1", nome="Motor 1", tipo_equipamento=tipo)
        cls.eq2 = Equipamento.objects.create(setor=cls.setor2, tag="E-SETOR2", nome="Motor 2", tipo_equipamento=tipo)
        cls.interno = _usuario("int-preditiva@t.test", Perfil.GESTOR, Nivel.MASTER, empresa=cls.empresa)
        cls.restrito = _usuario("restrito-preditiva@t.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        RestricaoSetorUsuario.objects.create(usuario=cls.restrito, setor=cls.setor1)
        cls.livre = _usuario("livre-preditiva@t.test", Perfil.CLIENTE_PCM, Nivel.PLENO, cliente=cls.cliente)
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.interno, data=date(2026, 10, 1),
                                           tipo_analise="VIBRACAO")
        cls.base = timezone.make_aware(timezone.datetime(2026, 10, 1, 9))
        cls.vib2 = MedicaoVibracao.objects.create(inspecao=cls.insp, equipamento=cls.eq2, ponto_medicao="P2",
                                                  direcao="V", velocidade_rms=Decimal("1.00"), rotacao_rpm=1800,
                                                  data_hora=cls.base)
        cls.vib1 = MedicaoVibracao.objects.create(inspecao=cls.insp, equipamento=cls.eq1, ponto_medicao="P1",
                                                  direcao="V", velocidade_rms=Decimal("1.00"), rotacao_rpm=1800,
                                                  data_hora=cls.base)
        cls.esp2 = MedicaoTecnica.objects.create(
            inspecao=cls.insp, equipamento=cls.eq2, tipo="ESPESSURA", subtipo="ESPESSURA", ponto_medicao="Casco",
            grandeza="Espessura", unidade="mm", valor=Decimal("10.0"),
            parametros={"material": "A516", "espessura_nominal_mm": "12"}, data_hora=cls.base,
        )

    def api(self, usuario):
        c = APIClient()
        c.force_authenticate(usuario)
        return c

    def test_ranking_omite_equipamento_fora_do_setor(self):
        r = self.api(self.restrito).get("/api/preditiva/risco/ranking/")
        self.assertEqual(r.status_code, 200)
        tags = [item["equipamento"]["tag"] for item in r.data["itens"]]
        self.assertEqual(tags, ["E-SETOR1"])

    def test_ranking_sem_restricao_vê_o_cliente_inteiro(self):
        r = self.api(self.livre).get("/api/preditiva/risco/ranking/")
        tags = sorted(item["equipamento"]["tag"] for item in r.data["itens"])
        self.assertEqual(tags, ["E-SETOR1", "E-SETOR2"])

    def test_interno_nao_e_restringido(self):
        r = self.api(self.interno).get("/api/preditiva/risco/ranking/")
        tags = sorted(item["equipamento"]["tag"] for item in r.data["itens"])
        self.assertEqual(tags, ["E-SETOR1", "E-SETOR2"])

    def test_tendencia_de_medicao_fora_do_setor_da_404(self):
        self.assertEqual(self.api(self.restrito).get(f"/api/preditiva/tendencias/vibracao/{self.vib2.pk}/").status_code, 404)
        self.assertEqual(self.api(self.restrito).get(f"/api/preditiva/tendencias/vibracao/{self.vib1.pk}/").status_code, 200)

    def test_tendencia_sem_restricao_responde_ao_setor_2(self):
        self.assertEqual(self.api(self.livre).get(f"/api/preditiva/tendencias/vibracao/{self.vib2.pk}/").status_code, 200)

    def test_espessura_fora_do_setor_da_404(self):
        self.assertEqual(self.api(self.restrito).get(f"/api/preditiva/espessura/{self.esp2.pk}/").status_code, 404)
        self.assertEqual(self.api(self.livre).get(f"/api/preditiva/espessura/{self.esp2.pk}/").status_code, 200)
