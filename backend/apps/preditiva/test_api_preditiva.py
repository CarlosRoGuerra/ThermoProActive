"""API e regras que dependem do banco: isolamento por cliente, permissões e sugestões.

Limites de vibração e demais valores são sintéticos (critério de teste), não normativos.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import (
    Area, Cliente, Componente, CriterioSeveridadeVibracao, Equipamento, Instrumento, Setor,
    TecnologiaAnalise, TipoAnomalia, TipoComponente, TipoRecomendacao,
)
from apps.coletas.models import Achado, Carregamento, Inspecao, ItemInspecao, MedicaoVibracao

from .models import AceitacaoSugestao, LimiteAlarmeSerie, MatrizRisco, RegraSugestao
from .sugestoes import aderencia, registrar_decisao, sugestoes_para_achado
from .risco import ranking_equipamentos


class PreditivaApiBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.cliente = Cliente.objects.create(nome="Cliente A", cnpj="31.111.111/0001-11")
        cls.outro = Cliente.objects.create(nome="Cliente B", cnpj="32.222.222/0001-22")
        cls.master = Usuario.objects.create_user(email="master-pred@t.test", nome="M", perfil="TECNICO", nivel="MASTER")
        cls.tecnico = Usuario.objects.create_user(email="tec-pred@t.test", nome="T", perfil="TECNICO", nivel="JUNIOR")
        cls.portal = Usuario.objects.create_user(email="portal-pred@t.test", nome="P", perfil="CLIENTE_PCM", cliente=cls.cliente)
        cls.portal_outro = Usuario.objects.create_user(email="outro-pred@t.test", nome="O", perfil="CLIENTE_PCM", cliente=cls.outro)

        area = Area.objects.create(nome="Área A", cliente=cls.cliente)
        setor = Setor.objects.create(nome="Setor A", area=area)
        cls.eq = Equipamento.objects.create(nome="Bomba A", tag="BOM-A", setor=setor, classe_iso="II", criticidade="A")
        cls.comp = Componente.objects.create(equipamento=cls.eq, nome="Mancal A")
        cls.instr = Instrumento.objects.create(tipo="Coletor", modelo="T", numero_serie="PRED-A")

        area_b = Area.objects.create(nome="Área B", cliente=cls.outro)
        setor_b = Setor.objects.create(nome="Setor B", area=area_b)
        cls.eq_outro = Equipamento.objects.create(nome="Bomba B", tag="BOM-B", setor=setor_b, classe_iso="II", criticidade="A")

        # Vinculado ao cliente: a carga inicial de critérios (global) não pode competir com ele.
        cls.criterio = CriterioSeveridadeVibracao.objects.create(
            cliente=cls.cliente, norma_codigo="TESTE", norma_edicao="1", classe="II", origem="RESPONSAVEL_TECNICO",
            fonte="Critério sintético de teste", limite_ab=Decimal("2"), limite_bc=Decimal("4"),
            limite_cd=Decimal("8"), vigencia_inicio=date(2025, 1, 1),
        )
        cls.inspecao = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tecnico, data=date(2026, 10, 1))
        cls.inspecao_b = Inspecao.objects.create(cliente=cls.outro, tecnico=cls.tecnico, data=date(2026, 10, 1))

    def cliente_api(self, usuario):
        api = APIClient()
        api.force_authenticate(usuario)
        return api

    def vibracoes(self, equipamento, inspecao, valores, componente, instrumento):
        base = timezone.make_aware(timezone.datetime(2026, 9, 1, 12))
        criadas = []
        for i, v in enumerate(valores):
            criadas.append(MedicaoVibracao.objects.create(
                inspecao=inspecao, equipamento=equipamento, componente=componente, instrumento=instrumento,
                ponto_medicao="LA", direcao="H", velocidade_rms=Decimal(str(v)), rotacao_rpm=1800,
                data_hora=base + timedelta(days=i * 10),
            ))
        return criadas


class TendenciaEndpointTest(PreditivaApiBase):
    def test_tendencia_com_limite_vigente_estima_e_respeita_tenant(self):
        self.vibracoes(self.eq, self.inspecao, [1.0, 1.4, 2.0, 2.5, 3.1, 3.6], self.comp, self.instr)
        ultima = MedicaoVibracao.objects.filter(equipamento=self.eq).order_by("-data_hora").first()
        url = f"/api/preditiva/tendencias/vibracao/{ultima.pk}/"

        r = self.cliente_api(self.portal).get(url)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["serie"]["status"], "TENDENCIA")
        self.assertTrue(r.data["limite"]["validado"])
        niveis = [p["nivel"] for p in r.data["serie"]["projecoes"]]
        self.assertEqual(niveis, ["ALERTA", "CRITICO"])

        self.assertEqual(self.cliente_api(self.portal_outro).get(url).status_code, 404)

    def test_sem_criterio_nao_ha_projecao(self):
        self.criterio.origem = "LEGADO"
        self.criterio.save()
        self.vibracoes(self.eq, self.inspecao, [1.0, 1.4, 2.0, 2.5, 3.1, 3.6], self.comp, self.instr)
        ultima = MedicaoVibracao.objects.filter(equipamento=self.eq).order_by("-data_hora").first()
        r = self.cliente_api(self.master).get(f"/api/preditiva/tendencias/vibracao/{ultima.pk}/")
        self.assertFalse(r.data["limite"]["validado"])
        self.assertEqual(r.data["serie"]["projecoes"], [])

    def test_termografia_limite_nao_validado_nao_projeta(self):
        LimiteAlarmeSerie.objects.create(modalidade="TERMOGRAFIA", grandeza="delta_t", unidade="°C",
                                         valor_alerta=Decimal("10"), origem="RESPONSAVEL_TECNICO",
                                         fonte="rascunho", validacao="PROVISORIA")
        r = self.cliente_api(self.master).get("/api/preditiva/tendencias/termografia/999999/")
        self.assertEqual(r.status_code, 404)


class RankingRiscoTest(PreditivaApiBase):
    def test_portal_ve_so_o_proprio_cliente(self):
        self.vibracoes(self.eq, self.inspecao, [1.0, 1.4, 2.0, 2.5, 3.1, 3.6], self.comp, self.instr)
        r_a = self.cliente_api(self.portal).get("/api/preditiva/risco/ranking/")
        tags = [i["equipamento"]["tag"] for i in r_a.data["itens"]]
        self.assertEqual(tags, ["BOM-A"])
        self.assertIn("priorização", r_a.data["aviso"])
        r_b = self.cliente_api(self.portal_outro).get("/api/preditiva/risco/ranking/")
        self.assertEqual([i["equipamento"]["tag"] for i in r_b.data["itens"]], ["BOM-B"])

    def test_ranking_decompoe_e_nao_inventa_componente_ausente(self):
        itens = ranking_equipamentos(Equipamento.objects.filter(pk=self.eq_outro.pk))
        self.assertFalse(itens[0]["completo"])
        self.assertIsNone(itens[0]["indice"])
        self.assertIn("sem_condicao_classificada", itens[0]["pendencias"])

    def test_matriz_provisoria_do_sistema_e_consumida(self):
        self.assertTrue(MatrizRisco.objects.filter(validacao="PROVISORIA", cliente__isnull=True).exists())


class SugestoesTest(PreditivaApiBase):
    def setUp(self):
        self.tec = TecnologiaAnalise.objects.create(nome="Vibração QA")
        self.anom = TipoAnomalia.objects.create(nome="Desbalanceamento QA")
        self.comp_t = TipoComponente.objects.create(nome="Mancal QA")
        self.rec_regra = TipoRecomendacao.objects.create(nome="Verificar balanceamento (regra)")
        self.rec_hist = TipoRecomendacao.objects.create(nome="Alinhamento (histórico)")
        self.rec_outro = TipoRecomendacao.objects.create(nome="Troca de rolamento")

    def achado(self, cliente, equipamento, recomendacao=None):
        carr = Carregamento.objects.create(cliente=cliente, tecnologia=self.tec, analista=self.tecnico)
        item = ItemInspecao.objects.create(carregamento=carr, equipamento=equipamento)
        return Achado.objects.create(item=item, tipo_componente=self.comp_t, tipo_anomalia=self.anom,
                                     recomendacao=recomendacao)

    def test_sem_regra_nem_historico_nao_sugere(self):
        a = self.achado(self.cliente, self.eq)
        r = sugestoes_para_achado(a)
        self.assertEqual(r["sugestoes"], [])

    def test_regra_exige_criticidade_conhecida(self):
        RegraSugestao.objects.create(nome="Regra QA", tecnologia=self.tec, tipo_componente=self.comp_t,
                                     tipo_anomalia=self.anom, criticidade_minima="ALERTA",
                                     recomendacao=self.rec_regra, validacao="PROVISORIA")
        a = self.achado(self.cliente, self.eq)
        self.assertEqual(sugestoes_para_achado(a)["sugestoes"], [])  # sem medição classificada

    def test_historico_do_mesmo_cliente_com_minimo_de_ocorrencias(self):
        for _ in range(3):
            self.achado(self.cliente, self.eq, recomendacao=self.rec_hist)
        self.achado(self.cliente, self.eq, recomendacao=self.rec_outro)  # 1 ocorrência: abaixo do mínimo
        a = self.achado(self.cliente, self.eq)
        sugestoes = sugestoes_para_achado(a)["sugestoes"]
        self.assertEqual(len(sugestoes), 1)
        self.assertEqual(sugestoes[0]["recomendacao"]["id"], self.rec_hist.pk)
        self.assertEqual((sugestoes[0]["contagem"], sugestoes[0]["total"]), (3, 4))

    def test_historico_nao_vaza_entre_clientes(self):
        for _ in range(3):
            self.achado(self.outro, self.eq_outro, recomendacao=self.rec_hist)
        a = self.achado(self.cliente, self.eq)
        self.assertEqual(sugestoes_para_achado(a)["sugestoes"], [])

    def test_decisao_so_para_sugestao_existente(self):
        for _ in range(3):
            self.achado(self.cliente, self.eq, recomendacao=self.rec_hist)
        a = self.achado(self.cliente, self.eq)
        with self.assertRaises(ValueError):
            registrar_decisao(a, self.rec_outro.pk, "HISTORICO", "ACEITA", self.tecnico)
        registro = registrar_decisao(a, self.rec_hist.pk, "HISTORICO", "ACEITA", self.tecnico)
        self.assertEqual(registro.recomendacao_final_id, self.rec_hist.pk)
        self.assertEqual(aderencia()["HISTORICO"]["taxa_aderencia"], 1.0)

    def test_edicao_exige_outra_recomendacao(self):
        for _ in range(3):
            self.achado(self.cliente, self.eq, recomendacao=self.rec_hist)
        a = self.achado(self.cliente, self.eq)
        with self.assertRaises(ValueError):
            registrar_decisao(a, self.rec_hist.pk, "HISTORICO", "EDITADA", self.tecnico,
                              recomendacao_final_id=self.rec_hist.pk)

    def test_endpoint_aceitacao_exige_interno(self):
        for _ in range(3):
            self.achado(self.cliente, self.eq, recomendacao=self.rec_hist)
        a = self.achado(self.cliente, self.eq)
        corpo = {"achado": a.pk, "recomendacao_sugerida": self.rec_hist.pk, "origem": "HISTORICO",
                 "decisao": "REJEITADA"}
        self.assertEqual(self.cliente_api(self.portal).post("/api/preditiva/aceitacoes-sugestao/", corpo, format="json").status_code, 403)
        r = self.cliente_api(self.tecnico).post("/api/preditiva/aceitacoes-sugestao/", corpo, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(AceitacaoSugestao.objects.count(), 1)


class CadastroPreditivoPermissoesTest(PreditivaApiBase):
    def test_master_escreve_tecnico_so_le_cliente_nao_acessa(self):
        corpo = {"nome": "Matriz QA", "peso_severidade": "0.50", "peso_tendencia": "0.50",
                 "consequencia": {"A": 3, "B": 2, "C": 1},
                 "faixas": [{"ate": 100, "rotulo": "UNICA"}], "validacao": "PROVISORIA"}
        url = "/api/preditiva/matrizes-risco/"
        self.assertEqual(self.cliente_api(self.tecnico).post(url, corpo, format="json").status_code, 403)
        self.assertEqual(self.cliente_api(self.portal).get(url).status_code, 403)
        self.assertEqual(self.cliente_api(self.master).post(url, corpo, format="json").status_code, 201)
        self.assertEqual(self.cliente_api(self.tecnico).get(url).status_code, 200)

    def test_matriz_invalida_e_recusada_pela_api(self):
        corpo = {"nome": "Ruim", "peso_severidade": "0.90", "peso_tendencia": "0.50",
                 "consequencia": {"A": 3, "B": 2, "C": 1},
                 "faixas": [{"ate": 100, "rotulo": "X"}], "validacao": "PROVISORIA"}
        r = self.cliente_api(self.master).post("/api/preditiva/matrizes-risco/", corpo, format="json")
        self.assertEqual(r.status_code, 400)

    def test_validada_sem_fonte_e_recusada(self):
        corpo = {"nome": "Sem fonte", "peso_severidade": "0.50", "peso_tendencia": "0.50",
                 "consequencia": {"A": 3, "B": 2, "C": 1},
                 "faixas": [{"ate": 100, "rotulo": "X"}], "validacao": "VALIDADA", "fonte": ""}
        r = self.cliente_api(self.master).post("/api/preditiva/matrizes-risco/", corpo, format="json")
        self.assertEqual(r.status_code, 400)
