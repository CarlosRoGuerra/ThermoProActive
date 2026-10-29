"""Validação de lançamento e preservação dos critérios das campanhas anteriores."""
from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import DadosTecnicosTransformador, ModuloTecnico

from .models import ColetaFluido, ParametroEnsaio, ReferenciaParametro, RegistroEnsaioEletrico, ResultadoEnsaio
from . import calculos, calculos_fluidos
from .test_fluidos import CenarioFluidos
from .tests import CenarioTransformador


class ConformidadeResultadosTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)
        self.rel, (self.item,) = self.rota(date(2026, 10, 21), [self.redutor])
        ColetaFluido.objects.create(
            item=self.item, aplicacao="LUBRIFICANTE", produto=self.produto, data_coleta=date(2026, 10, 21),
        )

    def dados(self, valores=None, **extras):
        dados = {
            "item": self.item.pk, "ensaio": self.ensaio["EF"].pk, "situacao": "REALIZADO",
            "data_analise": "2026-10-21", "data_proxima": "2026-11-21",
            "valores": valores if valores is not None else [{"parametro": self.param[("EF", "FE")].pk, "valor": "20"}],
        }
        dados.update(extras)
        return dados

    def criar_api(self, **extras):
        resposta = self.api.post("/api/resultados-ensaio/", self.dados(**extras), format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta

    def test_medido_exige_numero_ou_texto_e_estados_nao_medidos_nao_aceitam_numero(self):
        base = {"parametro": self.param[("EF", "FE")].pk}
        invalidos = [dict(base), dict(base, estado="MEDIDO", valor_texto="   ")]
        invalidos += [dict(base, estado=estado, valor="0.1") for estado in (
            "ABAIXO_LD", "ABAIXO_LQ", "NAO_DETECTADO", "ACIMA_ESCALA", "INDISPONIVEL",
        )]
        for valor in invalidos:
            with self.subTest(valor=valor):
                resposta = self.api.post("/api/resultados-ensaio/", self.dados(valores=[valor]), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("valores", resposta.data)
        self.assertFalse(ResultadoEnsaio.objects.exists())

    def test_estado_abaixo_ld_preserva_limite_e_texto_sem_converter_em_zero(self):
        resposta = self.criar_api(valores=[{
            "parametro": self.param[("EF", "FE")].pk, "estado": "ABAIXO_LD",
            "limite_deteccao": "0.5", "valor_texto": "<0,5", "metodo": "Método do laboratório",
        }])
        resultado = ResultadoEnsaio.objects.get(pk=resposta.data["id"])
        valor = resultado.valores.get()
        self.assertIsNone(valor.valor)
        self.assertEqual(valor.limite_deteccao, Decimal("0.5"))
        self.assertEqual(valor.valor_texto, "<0,5")
        self.assertEqual(valor.metodo, "Método do laboratório")

    def test_ld_positivo_e_posicao_nao_negativa(self):
        for extras in ({"limite_deteccao": "0"}, {"limite_deteccao": "-0.1"}, {"posicao": "-0.01"}):
            with self.subTest(extras=extras):
                valor = {"parametro": self.param[("EF", "FE")].pk, "valor": "1", **extras}
                resposta = self.api.post("/api/resultados-ensaio/", self.dados(valores=[valor]), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        self.criar_api(valores=[{"parametro": self.param[("EF", "FE")].pk, "valor": "0", "posicao": "0"}])

    def test_chave_parametro_serie_posicao_nao_pode_duplicar(self):
        valor = {"parametro": self.param[("EF", "FE")].pk, "valor": "10", "serie": "R", "posicao": "60.00"}
        resposta = self.api.post("/api/resultados-ensaio/", self.dados(valores=[valor, dict(valor, valor="11")]), format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("valores", resposta.data)
        self.assertFalse(ResultadoEnsaio.objects.exists())
        criado = self.criar_api(valores=[valor, dict(valor, serie="S")])
        self.assertEqual(ResultadoEnsaio.objects.get(pk=criado.data["id"]).valores.count(), 2)

    def test_parametros_de_outro_ensaio_e_calculados_sao_recusados(self):
        for parametro in (self.param[("FQ", "VISC40")], self.param[("CP", "ISO4406")]):
            with self.subTest(parametro=parametro.codigo):
                resposta = self.api.post("/api/resultados-ensaio/", self.dados(
                    valores=[{"parametro": parametro.pk, "valor": "10"}],
                ), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertFalse(ResultadoEnsaio.objects.exists())

    def test_patch_datas_considera_valores_ja_persistidos(self):
        criado = self.criar_api()
        for mudanca in ({"data_proxima": "2026-10-20"}, {"data_analise": "2026-11-22"}):
            with self.subTest(mudanca=mudanca):
                resposta = self.api.patch(f"/api/resultados-ensaio/{criado.data['id']}/", mudanca, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("data_proxima", resposta.data)
        registro = ResultadoEnsaio.objects.get(pk=criado.data["id"])
        self.assertEqual(registro.data_analise, date(2026, 10, 21))
        self.assertEqual(registro.revisoes.count(), 0)

    def test_patch_nao_realoca_resultado_para_outro_ensaio_ou_equipamento(self):
        criado = self.criar_api()
        _, (outro_item,) = self.rota(date(2026, 10, 21), [self.uh])
        for mudanca in ({"item": outro_item.pk}, {"ensaio": self.ensaio["FQ"].pk}):
            with self.subTest(mudanca=mudanca):
                resposta = self.api.patch(f"/api/resultados-ensaio/{criado.data['id']}/", mudanca, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        registro = ResultadoEnsaio.objects.get(pk=criado.data["id"])
        self.assertEqual(registro.item_id, self.item.pk)
        self.assertEqual(registro.ensaio_id, self.ensaio["EF"].pk)

    def test_edicao_guarda_revisao_com_autor_data_valores_e_criterios_anteriores(self):
        criado = self.criar_api()
        registro = ResultadoEnsaio.objects.get(pk=criado.data["id"])
        contexto_anterior = registro.contexto_tecnico
        self.assertTrue(contexto_anterior.get("parametros"))
        resposta = self.api.patch(f"/api/resultados-ensaio/{registro.pk}/", {
            "valores": [{"parametro": self.param[("EF", "FE")].pk, "valor": "30"}],
        }, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(registro.valores.get().valor, Decimal("30"))
        revisao = registro.revisoes.get()
        self.assertEqual(revisao.autor_id, self.tecnico.pk)
        self.assertIsNotNone(revisao.criado_em)
        self.assertEqual(Decimal(revisao.dados["valores"][0]["valor"]), Decimal("20"))
        self.assertEqual(revisao.dados["contexto_tecnico"], contexto_anterior)
        self.assertEqual(resposta.data["revisoes"][0]["autor"], self.tecnico.pk)

    def test_catalogo_e_referencias_alterados_nao_reclassificam_resultado_salvo(self):
        parametro = self.param[("EF", "FE")]
        referencia = ReferenciaParametro.objects.create(
            parametro=parametro, equipamento=self.redutor, tipo="MAXIMO", limite_alerta="25", limite_critico="50",
            origem="RESPONSAVEL_TECNICO", fonte="Critério sintético para teste de histórico",
        )
        criado = self.criar_api()
        url = f"/api/resultados-ensaio/{criado.data['id']}/"
        linha = lambda aval: next(l for l in aval["linhas"] if l["codigo"] == "FE")
        antes = linha(criado.data["avaliacao"])
        self.assertEqual(antes["status"], "ROTINA")
        ReferenciaParametro.objects.filter(pk=referencia.pk).update(limite_alerta="1", limite_critico="2")
        ParametroEnsaio.objects.filter(pk=parametro.pk).update(unidade="unidade revisada", norma="Fonte revisada")
        depois = self.api.get(url)
        self.assertEqual(depois.status_code, 200)
        atual = linha(depois.data["avaliacao"])
        self.assertEqual(atual["status"], antes["status"])
        self.assertEqual(atual["referencia"], antes["referencia"])
        self.assertEqual((atual["unidade"], atual["norma"]), (antes["unidade"], antes["norma"]))
        texto = self.api.patch(url, {"conclusao": "Texto revisado"}, format="json")
        self.assertEqual(texto.status_code, 200, texto.data)
        self.assertEqual(linha(texto.data["avaliacao"])["status"], "ROTINA")
        tecnico = self.api.patch(url, {
            "valores": [{"parametro": parametro.pk, "valor": "20"}],
        }, format="json")
        self.assertEqual(tecnico.status_code, 200, tecnico.data)
        self.assertEqual(linha(tecnico.data["avaliacao"])["status"], "CRITICA")
        registro = ResultadoEnsaio.objects.get(pk=criado.data["id"])
        self.assertEqual(registro.revisoes.count(), 2)

    def test_resultado_legado_sem_contexto_nao_recebe_snapshot_por_leitura(self):
        legado = self.resultado(self.item, "EF", {"FE": 12})
        self.assertEqual(legado.contexto_tecnico, {})
        self.assertEqual(self.api.get(f"/api/resultados-ensaio/{legado.pk}/").status_code, 200)
        legado.refresh_from_db()
        self.assertEqual(legado.contexto_tecnico, {})
        self.assertFalse(legado.revisoes.exists())

    def test_exclusao_preserva_valores_e_revisoes_do_resultado(self):
        criado = self.criar_api()
        url = f"/api/resultados-ensaio/{criado.data['id']}/"
        editado = self.api.patch(url, {"conclusao": "Revisão antes da exclusão"}, format="json")
        self.assertEqual(editado.status_code, 200, editado.data)
        self.api.force_authenticate(self.master)
        excluido = self.api.delete(url)
        self.assertEqual(excluido.status_code, 204)
        registro = ResultadoEnsaio.objects.get(pk=criado.data["id"])
        self.assertFalse(registro.ativo)
        self.assertEqual(registro.valores.count(), 1)
        self.assertEqual(registro.revisoes.count(), 2)
        self.assertEqual(registro.revisoes.first().autor_id, self.master.pk)
        self.assertEqual(registro.revisoes.first().dados["conclusao"], "Revisão antes da exclusão")
        self.assertEqual(self.api.get(url).status_code, 404)

    def test_contexto_novo_registra_autor_data_e_origem(self):
        criado = self.criar_api()
        contexto = ResultadoEnsaio.objects.get(pk=criado.data["id"]).contexto_tecnico
        self.assertEqual(contexto["registrado_por"], self.tecnico.pk)
        self.assertEqual(contexto["origem"], "API")
        self.assertTrue(contexto["registrado_em"])

    def test_oleo_novo_revisado_preserva_base_da_amostra_anterior(self):
        parametro = self.param[("FQ", "VISC40")]
        criado = self.criar_api(
            ensaio=self.ensaio["FQ"].pk, valores=[{"parametro": parametro.pk, "valor": "220"}],
        )
        linha = lambda resposta: next(l for l in resposta["avaliacao"]["linhas"] if l["codigo"] == "VISC40")
        antes = linha(criado.data)
        self.assertEqual(antes["referencia"]["valor_base"], Decimal("220"))
        type(self.produto).objects.filter(pk=self.produto.pk).update(viscosidade_40c_cst="440")
        depois = self.api.get(f"/api/resultados-ensaio/{criado.data['id']}/")
        self.assertEqual(depois.status_code, 200)
        self.assertEqual(linha(depois.data)["referencia"], antes["referencia"])
        self.assertEqual(linha(depois.data)["status"], antes["status"])


class LimitesAnaliticosTest(SimpleTestCase):
    """Exemplos sintéticos: limite analítico não é o limite técnico da aplicação."""

    def test_abaixo_ld_nao_implica_conformidade_sem_evidencia_suficiente(self):
        for estado in ("ABAIXO_LD", "ABAIXO_LQ", "NAO_DETECTADO"):
            for ld, esperado in ((None, None), ("0", None), ("10.1", None), ("10", True), ("9.9", True)):
                with self.subTest(estado=estado, ld=ld):
                    self.assertEqual(calculos.avaliar(
                        valor=None, texto="", estado=estado, tipo_limite="MAXIMO", limite=Decimal("10"),
                        limite_superior=None, referencia_texto="", limite_deteccao=ld,
                    ), esperado)

    def test_minimo_nao_e_reprovado_quando_ld_nao_permite_concluir(self):
        for ld, esperado in ((None, None), ("11", None), ("10", False), ("1", False)):
            with self.subTest(ld=ld):
                self.assertEqual(calculos.avaliar(
                    valor=None, texto="", estado="ABAIXO_LD", tipo_limite="MINIMO", limite=Decimal("10"),
                    limite_superior=None, referencia_texto="", limite_deteccao=ld,
                ), esperado)

    def test_fluido_so_aceita_ld_abaixo_de_todos_os_limites_maximos(self):
        for ld, esperado in ((None, None), ("-1", None), ("0", None), ("11", None),
                             ("6", None), ("5", "ROTINA"), ("4.9", "ROTINA")):
            with self.subTest(ld=ld):
                resultado = calculos_fluidos.classificar(
                    tipo="MAXIMO", estado="ABAIXO_LD", limite_alerta="5", limite_critico="10", limite_deteccao=ld,
                )
                self.assertEqual(resultado["status"], esperado)

    def test_fundo_de_escala_e_indisponivel_nao_sao_confundidos_com_abaixo_ld(self):
        for estado in ("ACIMA_ESCALA", "INDISPONIVEL"):
            with self.subTest(estado=estado):
                self.assertIsNone(calculos.avaliar(
                    valor=None, texto="", estado=estado, tipo_limite="MAXIMO", limite=Decimal("10"),
                    limite_superior=None, referencia_texto="", limite_deteccao="1",
                ))
                self.assertIsNone(calculos_fluidos.classificar(
                    tipo="MAXIMO", estado=estado, limite_alerta="5", limite_deteccao="1",
                )["status"])


class ContextoTransformadorTest(CenarioTransformador, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar_parque()

    def test_editar_placa_tap_e_referencia_nao_muda_erro_do_rxt_historico(self):
        _, item = self.item_de_rota(ModuloTecnico.ENSAIO_ELETRICO)
        registro = RegistroEnsaioEletrico.objects.create(
            item=item, data_ensaio=date(2025, 12, 26), tensao_tap_v=Decimal("11400"), tap="5",
        )
        api = APIClient()
        api.force_authenticate(self.tecnico)
        resposta = api.post("/api/resultados-ensaio/", {
            "item": item.pk, "ensaio": self.ensaio["RXT"].pk, "situacao": "REALIZADO",
            "valores": [{"parametro": self.param[("RXT", "MEDIDA")].pk, "valor": "51.7", "serie": "Fase 1"}],
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        antes = resposta.data["avaliacao"]
        DadosTecnicosTransformador.objects.filter(equipamento=self.trafo).update(tensao_secundaria_fase_v="110")
        RegistroEnsaioEletrico.objects.filter(pk=registro.pk).update(tensao_tap_v="13800", tap="1")
        ParametroEnsaio.objects.filter(pk=self.param[("RXT", "ERRO")].pk).update(limite="-0.1", limite_superior="0.1")
        depois = api.get(f"/api/resultados-ensaio/{resposta.data['id']}/")
        self.assertEqual(depois.status_code, 200)
        self.assertEqual(depois.data["avaliacao"]["campanhas"], antes["campanhas"])
        self.assertEqual(depois.data["avaliacao"]["limite"], antes["limite"])
        self.assertEqual(depois.data["avaliacao"]["status"], antes["status"])
