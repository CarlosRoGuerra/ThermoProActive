"""
Análise de fluidos lubrificantes e hidráulicos (FQ, EF e CP).

O que estes testes seguram:
  - regra acordada de solicitação: lubrificante → FQ + EF; hidráulico → FQ + EF + CP;
  - nenhum limite universal no catálogo: a classificação só sai de referência
    cadastrada (escopo, origem, vigência) — sem ela, "sem referência";
  - código ISO 4406 das contagens por mL e comparação com a meta, só com meta;
  - histórico por equipamento → ensaio → parâmetro → data (tendência);
  - relatório no shell comum, sem nada de vibração;
  - escrita só da equipe interna; cliente vê só o que é dele.
"""
import io
import json
import zipfile
from datetime import date
from decimal import Decimal as D

from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Equipamento, ModuloTecnico, Setor, TecnologiaAnalise, TipoEquipamento
from apps.coletas.models import Carregamento, ItemInspecao, Relatorio

from . import calculos_fluidos as cf
from .models import (
    ColetaFluido,
    Ensaio,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    ResultadoEnsaio,
    ValorParametro,
)

User = get_user_model()
FLUIDO = ModuloTecnico.FLUIDO_LUBRIFICANTE


# ------------------------------- Cálculos -----------------------------------
class Iso4406Test(SimpleTestCase):
    def test_codigo_do_relatorio_midori_2016(self):
        # Contagens por 100 mL do relatório 2016.11.0882 (÷ 100 = por mL); o PDF imprime 21/21/19 e 22/22/21.
        self.assertEqual(cf.codigo_iso4406(D("16127.07"), D("11760.71"), D("3713.57"))[0], "21/21/19")
        self.assertEqual(cf.codigo_iso4406(D("25820.78"), D("23800.71"), D("16495.35"))[0], "22/22/21")

    def test_limites_da_escala(self):
        self.assertEqual(cf.escala_iso4406(D("80")), 13)        # "até e inclusive" 80
        self.assertEqual(cf.escala_iso4406(D("80.01")), 14)
        self.assertEqual(cf.escala_iso4406(D("1300")), 17)      # a escala não dobra exato: 640–1.300
        self.assertEqual(cf.escala_iso4406(D("1300.5")), 18)
        self.assertEqual(cf.escala_iso4406(0), 0)
        self.assertEqual(cf.texto_escala(cf.escala_iso4406(D("2600000"))), ">28")
        self.assertIsNone(cf.escala_iso4406(None))

    def test_codigo_incompleto_nao_e_inventado(self):
        texto, escalas = cf.codigo_iso4406(D("5000"), None, D("100"))
        self.assertIsNone(texto)
        self.assertEqual(escalas, [19, None, 14])

    def test_comparacao_com_a_meta(self):
        self.assertEqual(cf.comparar_com_meta([19, 17, 14], cf.ler_codigo("17/15/12")), 2)
        self.assertEqual(cf.comparar_com_meta([16, 14, 11], cf.ler_codigo("17/15/12")), -1)
        self.assertIsNone(cf.comparar_com_meta([19, 17, 14], None))
        self.assertIsNone(cf.ler_codigo("17-15-12"))

    def test_classificacao_so_com_limite_cadastrado(self):
        self.assertIsNone(cf.classificar(tipo="MAXIMO", valor=D("58"))["status"])
        self.assertEqual(cf.classificar(tipo="MAXIMO", valor=D("58"), limite_alerta=50, limite_critico=100)["status"],
                         "ALERTA")
        self.assertEqual(cf.classificar(tipo="MAXIMO", valor=D("120"), limite_alerta=50, limite_critico=100)["status"],
                         "CRITICA")
        self.assertEqual(cf.classificar(tipo="MINIMO", valor=D("30"), limite_alerta=40)["status"], "ALERTA")
        v = cf.classificar(tipo="VARIACAO", valor=D("39.2"), valor_base=D("46"), limite_alerta=10, limite_critico=20)
        self.assertEqual((v["status"], v["variacao_pct"]), ("ALERTA", D("-14.8")))
        self.assertEqual(cf.classificar(tipo="QUALITATIVO", texto="turvo", referencia_texto="Límpido")["status"],
                         "ALERTA")
        meta = cf.classificar(tipo="CODIGO_ISO", escalas=[19, 17, 14], referencia_texto="17/15/12", limite_critico=3)
        self.assertEqual((meta["status"], meta["excesso"]), ("ALERTA", 2))

    def test_tendencia(self):
        t = cf.tendencia([D("12"), D("17"), D("24"), D("58")])
        self.assertEqual(t["direcao"], "SOBE")
        self.assertEqual(t["pct_anterior"], D("141.7"))
        self.assertIsNone(cf.tendencia([D("12")]))


# ------------------------------- Cenário ------------------------------------
class CenarioFluidos:
    @classmethod
    def criar(cls):
        cls.cliente = Cliente.objects.create(nome="Midori Auto Leather", cnpj="33.333.333/0001-33")
        cls.outro = Cliente.objects.create(nome="Outra Indústria", cnpj="44.444.444/0001-44")
        cls.master = User.objects.create_user(email="master@thermo.com", nome="Master", perfil="TECNICO",
                                              nivel="MASTER")
        cls.tecnico = User.objects.create_user(email="tecnico@thermo.com", nome="Técnico", perfil="TECNICO",
                                               nivel="PLENO")
        cls.leitor = User.objects.create_user(email="pcm@midori.com", nome="PCM", perfil="CLIENTE_PCM",
                                              cliente=cls.cliente)
        cls.leitor_outro = User.objects.create_user(email="pcm@outra.com", nome="PCM 2", perfil="CLIENTE_PCM",
                                                    cliente=cls.outro)
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Molhado"), nome="Enxugamento")
        tipo = TipoEquipamento.objects.create(nome="Redutor")
        cls.redutor = Equipamento.objects.create(setor=setor, tag="120-ENX-001", nome="Hidroredutor Inferior",
                                                 tipo_equipamento=tipo)
        cls.uh = Equipamento.objects.create(setor=setor, tag="120-ENX-002", nome="Unidade Hidráulica",
                                            tipo_equipamento=tipo)
        cls.tecnologia = TecnologiaAnalise.objects.create(
            nome="Análise de Fluídos Lubrificantes e Hidráulicos", sigla="AFLH", modulo_tecnico=FLUIDO,
        )
        cls.ensaio = {e.sigla: e for e in Ensaio.objects.filter(modulo=FLUIDO)}
        cls.param = {(p.ensaio.sigla, p.codigo): p
                     for p in ParametroEnsaio.objects.select_related("ensaio").filter(ensaio__modulo=FLUIDO)}
        cls.produto = ProdutoFluido.objects.create(nome="Óleo de engrenagem ISO VG 220", fabricante="Fab",
                                                   aplicacao="LUBRIFICANTE", grau_viscosidade="ISO VG 220",
                                                   viscosidade_40c_cst=D("220"))

    @classmethod
    def rota(cls, data, equipamentos, finalizado=None, cliente=None):
        cliente = cliente or cls.cliente
        rel = Relatorio.objects.create(cliente=cliente, tecnologia=cls.tecnologia, data_inicio=data, data_termino=data,
                                       numero=f"RT-AFLH-{Relatorio.objects.count() + 1:05d}",
                                       data_finalizacao=finalizado)
        rota = Carregamento.objects.create(cliente=cliente, tecnologia=cls.tecnologia, analista=cls.tecnico,
                                           relatorio=rel, data_coleta=data)
        itens = [ItemInspecao.objects.create(carregamento=rota, equipamento=eq, ordem=i)
                 for i, eq in enumerate(equipamentos, start=1)]
        return rel, itens

    @classmethod
    def resultado(cls, item, sigla, valores, **campos):
        campos.setdefault("situacao", "REALIZADO")
        r = ResultadoEnsaio.objects.create(item=item, ensaio=cls.ensaio[sigla], **campos)
        ValorParametro.objects.bulk_create([
            ValorParametro(resultado=r, parametro=cls.param[(sigla, codigo)], valor=D(str(v)) if v is not None else None)
            for codigo, v in valores.items()
        ])
        return r


class CatalogoFluidosTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()

    def test_tres_ensaios_com_parametros_configuraveis(self):
        self.assertEqual(sorted(self.ensaio), ["CP", "EF", "FQ"])
        fq = {p.codigo: p for p in self.ensaio["FQ"].parametros.all()}
        self.assertEqual(fq["VISC40"].norma, "ASTM D445")
        self.assertEqual(fq["TAN"].norma, "ASTM D664")
        self.assertEqual(fq["AGUA"].norma, "ASTM D6304")
        ef = list(self.ensaio["EF"].parametros.all())
        self.assertGreaterEqual(len(ef), 20)
        self.assertEqual({p.grupo for p in ef}, {"Metais de desgaste", "Contaminantes", "Aditivos"})
        self.assertTrue(all(p.norma == "ASTM D5185" and p.unidade == "ppm" for p in ef))
        cp = {p.codigo: p for p in self.ensaio["CP"].parametros.all()}
        self.assertTrue({"P4", "P6", "P14", "ISO4406"} <= set(cp))
        self.assertTrue(cp["ISO4406"].calculado)

    def test_nenhum_limite_universal_no_catalogo(self):
        for p in ParametroEnsaio.objects.filter(ensaio__modulo=FLUIDO):
            self.assertIn(p.tipo_limite, ("INFORMATIVO", "QUALITATIVO"), p.codigo)
            self.assertIsNone(p.limite, p.codigo)
        self.assertFalse(ReferenciaParametro.objects.exists())

    def test_fq_do_oleo_isolante_continua_separado(self):
        self.assertTrue(Ensaio.objects.filter(modulo=ModuloTecnico.OLEO_ISOLANTE, sigla="FQ").exists())
        self.assertNotEqual(Ensaio.objects.get(modulo=ModuloTecnico.OLEO_ISOLANTE, sigla="FQ").id, self.ensaio["FQ"].id)


class ColetaFluidoApiTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)
        _, (self.item_red, self.item_uh) = self.rota(date(2026, 9, 1), [self.redutor, self.uh])

    def coletar(self, item, aplicacao, **extra):
        return self.api.post("/api/coletas-fluido/", {
            "item": item.id, "aplicacao": aplicacao, "data_coleta": "2026-09-01", **extra,
        }, format="json")

    def siglas(self, coleta_id):
        return sorted(e.sigla for e in ColetaFluido.objects.get(pk=coleta_id).ensaios.all())

    def test_lubrificante_marca_fq_e_ef_sem_cp(self):
        r = self.coletar(self.item_red, "LUBRIFICANTE")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.siglas(r.data["id"]), ["EF", "FQ"])

    def test_hidraulico_marca_fq_ef_e_cp(self):
        r = self.coletar(self.item_uh, "HIDRAULICO")
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.siglas(r.data["id"]), ["CP", "EF", "FQ"])

    def test_lubrificante_pode_pedir_cp_quando_contratado(self):
        ensaios = [self.ensaio[s].id for s in ("FQ", "EF", "CP")]
        r = self.coletar(self.item_red, "LUBRIFICANTE", ensaios=ensaios)
        self.assertEqual(r.status_code, 201, r.data)
        self.assertEqual(self.siglas(r.data["id"]), ["CP", "EF", "FQ"])

    def test_padrao_aparece_no_catalogo_para_a_tela(self):
        r = self.api.get(f"/api/ensaios/?modulo={FLUIDO}")
        padrao = {e["sigla"]: e["padrao_em"] for e in r.data["results"]}
        self.assertEqual(padrao, {"FQ": ["HIDRAULICO", "LUBRIFICANTE"], "EF": ["HIDRAULICO", "LUBRIFICANTE"],
                                  "CP": ["HIDRAULICO"]})

    def test_validacoes_da_coleta(self):
        oleo = PontoColeta.objects.filter(modulo=ModuloTecnico.OLEO_ISOLANTE).first()
        self.assertEqual(self.coletar(self.item_red, "LUBRIFICANTE", ponto_coleta=oleo.id).status_code, 400)
        fq_isolante = Ensaio.objects.get(modulo=ModuloTecnico.OLEO_ISOLANTE, sigla="FQ")
        self.assertEqual(self.coletar(self.item_red, "LUBRIFICANTE", ensaios=[fq_isolante.id]).status_code, 400)
        self.assertEqual(self.coletar(self.item_red, "LUBRIFICANTE", data_ultima_troca="2026-09-10").status_code, 400)
        # Fluido hidráulico cadastrado não entra numa coleta de lubrificante.
        hid = ProdutoFluido.objects.create(nome="HLP 46", aplicacao="HIDRAULICO")
        self.assertEqual(self.coletar(self.item_red, "LUBRIFICANTE", produto=hid.id).status_code, 400)

    def test_item_de_rota_de_outra_tecnologia_e_recusado(self):
        vib = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB", modulo_tecnico="VIBRACAO")
        rota = Carregamento.objects.create(cliente=self.cliente, tecnologia=vib, analista=self.tecnico,
                                           data_coleta=date(2026, 9, 1))
        item = ItemInspecao.objects.create(carregamento=rota, equipamento=self.redutor, ordem=1)
        self.assertEqual(self.coletar(item, "LUBRIFICANTE").status_code, 400)

    def test_cp_salva_contagens_e_devolve_o_codigo_sem_meta(self):
        valores = [{"parametro": self.param[("CP", c)].id, "valor": v}
                   for c, v in (("P4", "4000"), ("P6", "1200"), ("P14", "100"))]
        r = self.api.post("/api/resultados-ensaio/", {
            "item": self.item_uh.id, "ensaio": self.ensaio["CP"].id, "situacao": "REALIZADO", "valores": valores,
        }, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        aval = r.data["avaliacao"]
        self.assertEqual(aval["tipo"], "CP")
        self.assertEqual(aval["codigos"][-1]["codigo"], "19/17/14")
        self.assertEqual(aval["situacao_meta"], "SEM_META")
        self.assertIsNone(aval["meta"])
        self.assertEqual(aval["status"], "SEM_CRITERIO")

    def test_cp_compara_com_a_meta_cadastrada(self):
        ReferenciaParametro.objects.create(parametro=self.param[("CP", "ISO4406")], equipamento=self.uh,
                                           tipo="CODIGO_ISO", referencia_texto="17/15/12", limite_critico=3,
                                           origem="FABRICANTE_EQUIPAMENTO", fonte="Manual da UH")
        r = self.resultado(self.item_uh, "CP", {"P4": 4000, "P6": 1200, "P14": 100})
        aval = self.api.get(f"/api/resultados-ensaio/{r.id}/").data["avaliacao"]
        self.assertEqual((aval["situacao_meta"], aval["excesso_meta"], aval["status"]), ("FORA", 2, "ALERTA"))
        self.assertEqual(aval["meta"]["texto"], "Meta 17/15/12 · Crítico a partir de +3")
        r.valores.all().delete()
        self.resultado(self.item_red, "CP", {"P4": 100, "P6": 30, "P14": 5})  # outro equipamento, sem meta
        ValorParametro.objects.bulk_create([ValorParametro(resultado=r, parametro=self.param[("CP", c)], valor=D(v))
                                            for c, v in (("P4", "600"), ("P6", "150"), ("P14", "20"))])
        aval = self.api.get(f"/api/resultados-ensaio/{r.id}/").data["avaliacao"]
        self.assertEqual((aval["codigos"][-1]["codigo"], aval["situacao_meta"]), ("16/14/11", "DENTRO"))

    def test_ef_aceita_varios_elementos_e_mostra_a_tendencia(self):
        _, (anterior,) = self.rota(date(2026, 3, 1), [self.redutor])
        self.resultado(anterior, "EF", {"FE": 12, "CU": 3, "SI": 8})
        r = self.resultado(self.item_red, "EF", {"FE": 58, "CU": 4, "SI": 9, "ZN": 300})
        aval = self.api.get(f"/api/resultados-ensaio/{r.id}/").data["avaliacao"]
        self.assertEqual([c["data"] for c in aval["campanhas"]], [date(2026, 3, 1), date(2026, 9, 1)])
        fe = next(linha for linha in aval["linhas"] if linha["codigo"] == "FE")
        self.assertEqual([v["valor"] for v in fe["valores"]], [D("12"), D("58")])
        self.assertEqual(fe["tendencia"]["direcao"], "SOBE")
        self.assertTrue(fe["sem_referencia"])
        self.assertIsNone(fe["status"])
        self.assertEqual(aval["grupos"], ["Metais de desgaste", "Contaminantes", "Aditivos"])

    def test_referencia_mais_especifica_e_vigente_ganha(self):
        fe = self.param[("EF", "FE")]
        ReferenciaParametro.objects.create(parametro=fe, tipo="MAXIMO", limite_alerta=100, limite_critico=200,
                                           origem="LABORATORIO", fonte="Laudo do laboratório")
        ReferenciaParametro.objects.create(parametro=fe, equipamento=self.redutor, tipo="MAXIMO", limite_alerta=50,
                                           limite_critico=150, origem="FABRICANTE_EQUIPAMENTO", fonte="Manual")
        ReferenciaParametro.objects.create(parametro=fe, equipamento=self.redutor, tipo="MAXIMO", limite_alerta=10,
                                           origem="CLIENTE", fonte="Acordo antigo", vigencia_fim=date(2025, 12, 31))
        r = self.resultado(self.item_red, "EF", {"FE": 58})
        linha = next(x for x in self.api.get(f"/api/resultados-ensaio/{r.id}/").data["avaliacao"]["linhas"]
                     if x["codigo"] == "FE")
        self.assertEqual(linha["status"], "ALERTA")
        self.assertEqual(linha["referencia"]["escopo"], "Equipamento")
        self.assertEqual(linha["referencia"]["origem"], "FABRICANTE_EQUIPAMENTO")
        # No outro equipamento vale a geral do laboratório: 58 está dentro.
        r2 = self.resultado(self.item_uh, "EF", {"FE": 58})
        linha = next(x for x in self.api.get(f"/api/resultados-ensaio/{r2.id}/").data["avaliacao"]["linhas"]
                     if x["codigo"] == "FE")
        self.assertEqual((linha["status"], linha["referencia"]["escopo"]), ("ROTINA", "Geral"))

    def test_fq_variacao_da_viscosidade_pelo_oleo_novo(self):
        ReferenciaParametro.objects.create(parametro=self.param[("FQ", "VISC40")], produto=self.produto,
                                           tipo="VARIACAO", valor_base=D("220"), limite_alerta=10, limite_critico=20,
                                           origem="FABRICANTE_FLUIDO", fonte="Ficha técnica do óleo")
        ColetaFluido.objects.create(item=self.item_red, aplicacao="LUBRIFICANTE", produto=self.produto,
                                    data_coleta=date(2026, 9, 1))
        r = self.resultado(self.item_red, "FQ", {"VISC40": "187.5"})
        linha = next(x for x in self.api.get(f"/api/resultados-ensaio/{r.id}/").data["avaliacao"]["linhas"]
                     if x["codigo"] == "VISC40")
        self.assertEqual((linha["status"], linha["variacao_pct"]), ("ALERTA", D("-14.8")))
        self.assertEqual(linha["referencia"]["escopo"], "Fluido")

    def test_referencia_valida_o_que_o_classificador_precisa(self):
        self.api.force_authenticate(self.master)
        base = {"parametro": self.param[("EF", "FE")].id, "origem": "LABORATORIO", "fonte": "Laudo"}
        self.assertEqual(self.api.post("/api/referencias-parametro/", {**base, "tipo": "MAXIMO"}, format="json")
                         .status_code, 400)
        self.assertEqual(self.api.post("/api/referencias-parametro/", {
            **base, "tipo": "MAXIMO", "limite_alerta": "100", "limite_critico": "50"}, format="json").status_code, 400)
        self.assertEqual(self.api.post("/api/referencias-parametro/", {
            **base, "tipo": "VARIACAO", "limite_alerta": "10"}, format="json").status_code, 400)
        self.assertEqual(self.api.post("/api/referencias-parametro/", {
            **base, "tipo": "MAXIMO", "limite_alerta": "50", "origem": "CLIENTE", "fonte": ""}, format="json")
            .status_code, 400)
        self.assertEqual(self.api.post("/api/referencias-parametro/", {
            "parametro": self.param[("CP", "ISO4406")].id, "tipo": "CODIGO_ISO", "referencia_texto": "17-15-12",
            "origem": "NORMA"}, format="json").status_code, 400)
        r = self.api.post("/api/referencias-parametro/", {
            **base, "tipo": "MAXIMO", "limite_alerta": "50", "limite_critico": "100",
            "equipamento": self.redutor.id, "cliente": self.outro.id}, format="json")
        self.assertEqual(r.status_code, 400)  # equipamento de outro cliente
        r = self.api.post("/api/referencias-parametro/", {
            **base, "tipo": "MAXIMO", "limite_alerta": "50", "limite_critico": "100"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)


class RelatorioFluidosTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()
        _, (anterior,) = cls.rota(date(2026, 3, 1), [cls.uh])
        cls.resultado(anterior, "CP", {"P4": 2000, "P6": 600, "P14": 60})
        cls.rel, (cls.item_red, cls.item_uh) = cls.rota(date(2026, 9, 1), [cls.redutor, cls.uh])
        ColetaFluido.objects.create(item=cls.item_red, aplicacao="LUBRIFICANTE", produto=cls.produto,
                                    data_coleta=date(2026, 9, 1), amostrador="Analista")
        uh = ColetaFluido.objects.create(item=cls.item_uh, aplicacao="HIDRAULICO", fluido_informado="HLP 46",
                                         data_coleta=date(2026, 9, 1))
        cls.item_red.coleta_fluido.ensaios.set([cls.ensaio["FQ"], cls.ensaio["EF"]])
        uh.ensaios.set([cls.ensaio["FQ"], cls.ensaio["EF"], cls.ensaio["CP"]])
        cls.resultado(cls.item_red, "FQ", {"VISC40": "212.4", "TAN": "0.35"}, criticidade="ROTINA",
                      numero_laudo="L-001")
        cls.resultado(cls.item_red, "EF", {"FE": 58, "SI": 21}, criticidade="ALERTA")
        cls.resultado(cls.item_uh, "CP", {"P4": 4000, "P6": 1200, "P14": 100}, criticidade="ALERTA")
        ReferenciaParametro.objects.create(parametro=cls.param[("EF", "FE")], equipamento=cls.redutor, tipo="MAXIMO",
                                           limite_alerta=50, limite_critico=150, origem="FABRICANTE_EQUIPAMENTO",
                                           fonte="Manual do redutor")
        ReferenciaParametro.objects.create(parametro=cls.param[("CP", "ISO4406")], equipamento=cls.uh,
                                           tipo="CODIGO_ISO", referencia_texto="17/15/12",
                                           origem="FABRICANTE_EQUIPAMENTO", fonte="Manual da UH")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def dossie(self):
        r = self.api.get(f"/api/relatorios-inspecao/{self.rel.pk}/dossie/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def test_fichas_por_amostra_com_historico(self):
        d = self.dossie()
        self.assertEqual(d["modulo"], FLUIDO)
        red, uh = d["amostras"]
        self.assertEqual([f["sigla"] for f in red["ensaios"]], ["FQ", "EF"])
        self.assertEqual([f["sigla"] for f in uh["ensaios"]], ["FQ", "EF", "CP"])
        self.assertEqual(red["coleta"]["fluido"], "Óleo de engrenagem ISO VG 220")
        self.assertEqual(red["coleta"]["aplicacao"], "LUBRIFICANTE")
        cp = uh["ensaios"][2]
        self.assertEqual([c["codigo"] for c in cp["codigos"]], ["18/16/13", "19/17/14"])
        self.assertEqual((cp["situacao_meta"], cp["status"]), ("FORA", "ALERTA"))
        # FQ e EF da UH foram pedidos e ainda não têm laudo.
        self.assertEqual(uh["ensaios"][0]["status"], "SEM_RESULTADO")
        ef = red["ensaios"][1]
        self.assertEqual(ef["status"], "ALERTA")
        self.assertEqual(ef["sem_referencia"], 1)  # o Si não tem referência

    def test_kpis_proprios_da_tecnologia(self):
        k = self.dossie()["kpis"]
        self.assertEqual((k["amostras"], k["equipamentos"]), (2, 2))
        self.assertEqual(k["ensaios_pendentes"], 2)
        self.assertEqual(k["limpeza"], {"dentro": 0, "fora": 1, "sem_meta": 0})
        self.assertEqual(k["parametros_alerta"], 2)  # Fe e o código ISO
        self.assertEqual({x["rotulo"]: x["total"] for x in k["laudos_por_criticidade"]}, {"Rotina": 1, "Alerta": 2})
        self.assertNotIn("diagnostico_medio", k)

    def test_carta_e_relatorio_sem_conteudo_de_vibracao(self):
        d = self.dossie()
        texto = json.dumps(d, default=str, ensure_ascii=False)
        for termo in ("10816", "20816", "Classe ISO", "mm/s", "Velocidade"):
            self.assertNotIn(termo, texto)
        self.assertEqual([g["sigla"] for g in d["carta"]["glossario"] if g["n"].startswith("6.1.")], ["FQ", "EF", "CP"])
        self.assertIn("Neste ciclo foram analisadas 2 amostras", d["carta"]["paragrafos"][0])
        r = self.api.get(f"/api/relatorios-inspecao/{self.rel.pk}/carta-docx/")
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            xml = z.read("word/document.xml").decode("utf-8")
        self.assertIn("Contagem de Partículas", xml)
        self.assertNotIn("Faixas de Velocidade", xml)
        self.assertNotIn("10816", xml)

    def test_historico_por_equipamento(self):
        r = self.api.get(f"/api/fluidos-historico/?equipamento={self.uh.id}")
        self.assertEqual(r.status_code, 200)
        cp = next(e for e in r.data["ensaios"] if e["sigla"] == "CP")
        self.assertEqual([c["codigo"] for c in cp["codigos"]], ["18/16/13", "19/17/14"])
        lista = self.api.get("/api/fluidos-historico/").data
        self.assertEqual({x["tag"]: x["coletas"] for x in lista}, {"120-ENX-001": 1, "120-ENX-002": 2})


class PermissoesFluidosTest(CenarioFluidos, TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.criar()
        cls.rel, (cls.item,) = cls.rota(date(2026, 9, 1), [cls.uh])
        cls.coleta = ColetaFluido.objects.create(item=cls.item, aplicacao="HIDRAULICO", data_coleta=date(2026, 9, 1))
        cls.res = cls.resultado(cls.item, "CP", {"P4": 4000, "P6": 1200, "P14": 100})

    def como(self, user):
        api = APIClient()
        api.force_authenticate(user)
        return api

    def test_cliente_consulta_mas_nao_altera_resultado(self):
        api = self.como(self.leitor)
        self.assertEqual(api.get(f"/api/resultados-ensaio/{self.res.id}/").status_code, 200)
        self.assertEqual(api.patch(f"/api/resultados-ensaio/{self.res.id}/", {"conclusao": "x"}, format="json")
                         .status_code, 403)
        self.assertEqual(api.post("/api/coletas-fluido/", {"item": self.item.id, "aplicacao": "HIDRAULICO",
                                                            "data_coleta": "2026-09-01"}, format="json").status_code, 403)

    def test_outro_cliente_nao_ve_nada(self):
        api = self.como(self.leitor_outro)
        self.assertEqual(api.get(f"/api/resultados-ensaio/{self.res.id}/").status_code, 404)
        self.assertEqual(api.get(f"/api/coletas-fluido/{self.coleta.id}/").status_code, 404)
        self.assertEqual(api.get("/api/fluidos-inspecao/").data["count"], 0)
        self.assertEqual(api.get(f"/api/fluidos-historico/?equipamento={self.uh.id}").status_code, 404)
        self.assertEqual(api.get("/api/fluidos-historico/").data, [])

    def test_portal_so_ve_historico_de_relatorio_finalizado(self):
        api = self.como(self.leitor)
        self.assertEqual(api.get("/api/fluidos-historico/").data, [])
        Relatorio.objects.filter(pk=self.rel.pk).update(data_finalizacao=date(2026, 9, 10))
        self.assertEqual([x["tag"] for x in api.get("/api/fluidos-historico/").data], ["120-ENX-002"])

    def test_referencias_so_para_a_equipe_e_so_o_master_altera(self):
        corpo = {"parametro": self.param[("EF", "FE")].id, "tipo": "MAXIMO", "limite_alerta": "50",
                 "origem": "LABORATORIO", "fonte": "Laudo"}
        self.assertEqual(self.como(self.leitor).get("/api/referencias-parametro/").status_code, 403)
        tecnico = self.como(self.tecnico)
        self.assertEqual(tecnico.get("/api/referencias-parametro/").status_code, 200)
        self.assertEqual(tecnico.post("/api/referencias-parametro/", corpo, format="json").status_code, 403)
        self.assertEqual(self.como(self.master).post("/api/referencias-parametro/", corpo, format="json")
                         .status_code, 201)
