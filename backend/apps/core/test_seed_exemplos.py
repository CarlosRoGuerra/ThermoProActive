"""
`seed_relatorios_exemplo`: cada relatório de exemplo abre pela API (dossiê e carta
.docx) com o conteúdo que o exemplo promete, e rodar de novo não duplica nada.
"""
import io

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from apps.coletas.models import Relatorio
from apps.core.management.commands.seed_relatorio_completo import CNPJ_DEMO
from apps.osp.models import OrdemServico


class SeedRelatoriosExemploTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_relatorios_exemplo", stdout=io.StringIO())

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(get_user_model().objects.create_user(
            email="leitor@thermo.com", nome="Leitor", perfil="GESTOR"))

    def relatorio(self, prefixo):
        return Relatorio.objects.filter(cliente__cnpj=CNPJ_DEMO, numero__startswith=prefixo).order_by("-data_termino").first()

    def dossie(self, prefixo):
        rel = self.relatorio(prefixo)
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/dossie/")
        self.assertEqual(r.status_code, 200, (prefixo, getattr(r, "data", None)))
        carta = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/carta-docx/")
        self.assertEqual(carta.status_code, 200, prefixo)
        return r.data

    def test_analises_e_osps(self):
        for prefixo, modulo in (("RT-VIB", "VIBRACAO"), ("RT-TERMO", "TERMOGRAFIA"), ("RT-BALDC", "BALANCEAMENTO")):
            with self.subTest(prefixo=prefixo):
                self.assertEqual(self.dossie(prefixo)["modulo"], modulo)
        self.assertGreater(OrdemServico.objects.filter(cliente__cnpj=CNPJ_DEMO).count(), 0)

    def test_oleo_isolante_com_historico_e_nao_conformidade(self):
        d = self.dossie("RT-AFIM")
        self.assertEqual(d["modulo"], "OLEO_ISOLANTE")
        fichas = {f["sigla"]: f for f in d["transformadores"][0]["ensaios"]}
        self.assertEqual(list(fichas), ["FQ", "CR", "PCB", "2FAL"])
        self.assertEqual(len(fichas["FQ"]["campanhas"]), 2)
        self.assertEqual(fichas["FQ"]["status"], "NAO_CONFORME")
        self.assertFalse(fichas["FQ"]["campanhas"][-1]["valores"]["TEOR_AGUA"]["conforme"])
        self.assertEqual(fichas["2FAL"]["situacao"], "NAO_COLETADO")
        self.assertEqual(d["kpis"]["parametros_fora"], 1)

    def test_ensaios_eletricos(self):
        d = self.dossie("RT-EE")
        self.assertEqual(d["modulo"], "ENSAIO_ELETRICO")
        fichas = {f["sigla"]: f["status"] for f in d["transformadores"][0]["ensaios"]}
        self.assertEqual(fichas, {"RXT": "CONFORME", "RXI": "CONFORME", "RXO": "SEM_CRITERIO"})

    def test_fluidos_com_referencias_e_meta(self):
        d = self.dossie("RT-AFLH")
        self.assertEqual(d["modulo"], "FLUIDO_LUBRIFICANTE")
        red, uh = d["amostras"]
        self.assertEqual([f["sigla"] for f in red["ensaios"]], ["FQ", "EF"])
        self.assertEqual([f["sigla"] for f in uh["ensaios"]], ["FQ", "EF", "CP"])
        ef_red = red["ensaios"][1]
        self.assertEqual(ef_red["status"], "CRITICA")  # Si 24 ppm sobre 2 do óleo novo
        cp = uh["ensaios"][2]
        self.assertEqual([c["codigo"] for c in cp["codigos"]], ["18/16/13", "19/17/14"])
        self.assertEqual(cp["situacao_meta"], "FORA")
        self.assertEqual(d["kpis"]["ensaios_pendentes"], 0)

    def test_rodar_de_novo_recria_sem_duplicar(self):
        antes = Relatorio.objects.filter(cliente__cnpj=CNPJ_DEMO).count()
        call_command("seed_relatorios_exemplo", stdout=io.StringIO())
        self.assertEqual(Relatorio.objects.filter(cliente__cnpj=CNPJ_DEMO).count(), antes)
