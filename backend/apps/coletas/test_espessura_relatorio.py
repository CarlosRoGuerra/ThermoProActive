"""Relatório da espessura: registro do módulo, planejados continuam recusados e isolamento por cliente."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from apps.cadastros.models import Area, Cliente, Equipamento, Setor, TecnologiaAnalise
from apps.preditiva.models import LimiteAlarmeSerie, Validacao

from .models import Inspecao, MedicaoTecnica
from .relatorio_tecnico.modulos import ModuloNaoImplementado, modulo_da_tecnologia
from .relatorio_tecnico.espessura import MODULO_ESPESSURA, ultima_espessura


class RegistroDoModuloTest(SimpleTestCase):
    def test_espessura_resolve_modulo_implementado(self):
        modulo = modulo_da_tecnologia(TecnologiaAnalise(nome="Espessura QA", modulo_tecnico="ESPESSURA"))
        self.assertEqual(modulo.chave, "ESPESSURA")
        self.assertIs(modulo, MODULO_ESPESSURA)

    def test_chave_sem_modulo_continua_recusada(self):
        # Sem planejados pendentes (docs/25 implementou TC, TP, DJ, CS e RP): só chave desconhecida é recusada.
        with self.assertRaises(ModuloNaoImplementado):
            modulo_da_tecnologia(TecnologiaAnalise(nome="QA", modulo_tecnico="CHAVE_INEXISTENTE"))

    def test_glossario_e_consideracoes_da_espessura(self):
        siglas = [t[1] for t in MODULO_ESPESSURA.carta_glossario]
        self.assertIn("PER", siglas)
        self.assertIn("TCC", siglas)
        self.assertTrue(any("vida útil remanescente" in c for c in MODULO_ESPESSURA.carta_consideracoes))


class UltimaEspessuraTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Cliente Rel", cnpj="61.111.111/0001-61")
        cls.outro = Cliente.objects.create(nome="Cliente Rel 2", cnpj="62.222.222/0001-62")
        area = Area.objects.create(nome="A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="S", area=area)
        cls.eq = Equipamento.objects.create(nome="Vaso", tag="VSO-1", setor=setor)
        from apps.cadastros.models import Instrumento
        cls.instr = Instrumento.objects.create(tipo="Ultrassom", modelo="E", numero_serie="REL-1")
        from django.contrib.auth import get_user_model
        cls.tec = get_user_model().objects.create_user(email="rel-esp@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.insp = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tec, data=date(2026, 5, 10),
                                           tipo_analise="ESPESSURA")
        LimiteAlarmeSerie.objects.create(
            modalidade="ESPESSURA", grandeza="Espessura", unidade="mm", cliente=cls.cliente, sentido="INFERIOR",
            valor_alerta=Decimal("10"), valor_critico=Decimal("9"), origem="RESPONSAVEL_TECNICO",
            fonte="QA sintético", validacao=Validacao.VALIDADA,
        )
        MedicaoTecnica.objects.create(
            inspecao=cls.insp, equipamento=cls.eq, instrumento=cls.instr, tipo="ESPESSURA", subtipo="ESPESSURA",
            ponto_medicao="Casco", grandeza="Espessura", unidade="mm", valor=Decimal("9.5"),
            parametros={"material": "A516", "espessura_nominal_mm": "12"},
            data_hora=timezone.make_aware(timezone.datetime(2026, 5, 10, 9)),
        )

    def test_retorna_perda_e_condicao_da_ultima_medicao(self):
        r = ultima_espessura(self.cliente.pk, self.eq.pk, date(2026, 12, 31))
        self.assertEqual(r["perda_percentual"], "20.83")
        self.assertEqual(r["condicao"], "ALERTA")  # 9.5 <= 10 e > 9
        self.assertTrue(r["criterio_validado"])
        self.assertIsNone(r["taxa_mm_ano"])  # uma única leitura comparável

    def test_data_de_corte_exclui_medicoes_posteriores(self):
        self.assertIsNone(ultima_espessura(self.cliente.pk, self.eq.pk, date(2026, 1, 1)))

    def test_outro_cliente_nao_recebe_a_medicao(self):
        self.assertIsNone(ultima_espessura(self.outro.pk, self.eq.pk, None))
