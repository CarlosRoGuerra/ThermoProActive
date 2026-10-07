"""
Relatório técnico = shell comum + módulo técnico da tecnologia.

O que estes testes seguram: o módulo sai do vínculo explícito da tecnologia
(nunca do nome), o shell tem os próprios dados (não lê os KPIs do módulo) e o que
é técnico — médias de diagnóstico, tabela normativa da carta — só aparece na
tecnologia que mede aquilo.
"""
import importlib
import io
import zipfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Condicao, Equipamento, ModuloTecnico, Setor, TecnologiaAnalise
from apps.coletas.models import Achado, Carregamento, ItemInspecao, Relatorio

User = get_user_model()


class RelatorioTecnicoModularTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.tecnico = User.objects.create_user(
            email="tecnico@thermo.com", nome="Técnico", perfil="TECNICO", nivel="PLENO",
        )
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Utilidades"), nome="Painéis")
        cls.eq1 = Equipamento.objects.create(setor=setor, tag="QGBT-01", nome="Quadro geral")
        cls.eq2 = Equipamento.objects.create(setor=setor, tag="TRF-01", nome="Transformador")
        cls.gr3 = Condicao.objects.create(nome="Grau de Risco MODERADO", sigla="GR-3", gera_acao=True)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def relatorio(self, modulo, nome="Tecnologia X"):
        """Relatório com 3 linhas na rota (2 do mesmo equipamento) e 1 análise que mede tudo."""
        tecnologia = TecnologiaAnalise.objects.create(nome=nome, sigla="TX", modulo_tecnico=modulo)
        rel = Relatorio.objects.create(
            cliente=self.cliente, tecnologia=tecnologia,
            numero=f"RT-TX-2026-09-24-{Relatorio.objects.count() + 1:05d}", data_termino=date(2026, 9, 24),
        )
        rota = Carregamento.objects.create(
            cliente=self.cliente, tecnologia=tecnologia, analista=self.tecnico, relatorio=rel,
        )
        item = ItemInspecao.objects.create(carregamento=rota, equipamento=self.eq1, ordem=1, condicao=self.gr3)
        ItemInspecao.objects.create(carregamento=rota, equipamento=self.eq1, ordem=2, condicao=self.gr3)
        ItemInspecao.objects.create(carregamento=rota, equipamento=self.eq2, ordem=3, condicao=self.gr3)
        Achado.objects.create(
            item=item, componente_texto="DJ5", anomalia_texto="Aquecimento",
            velocidade_global=Decimal("4.200"), aceleracao_global=Decimal("1.100"),
            temperatura_medida=Decimal("78.4"), temperatura_referencia=Decimal("41.0"),
        )
        return rel

    def dossie(self, rel):
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/dossie/")
        self.assertEqual(r.status_code, 200, r.data)
        return r.data

    def carta_xml(self, rel):
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/carta-docx/")
        self.assertEqual(r.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            return z.read("word/document.xml").decode("utf-8")

    def test_modulo_vem_do_vinculo_explicito_da_tecnologia(self):
        self.assertEqual(self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))["modulo"], "VIBRACAO")
        self.assertEqual(self.dossie(self.relatorio(ModuloTecnico.TERMOGRAFIA))["modulo"], "TERMOGRAFIA")
        # O nome não decide nada: "Termografia" sem vínculo não vira termografia nem vibração.
        r = self.api.get(f"/api/relatorios-inspecao/{self.relatorio('', nome='Termografia Infravermelha').pk}/dossie/")
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.data["codigo"], "modulo_nao_configurado")

    # --- Sem fallback para a vibração ------------------------------------------

    def test_tecnologia_sem_modulo_nao_herda_o_layout_da_vibracao(self):
        rel = self.relatorio("", nome="Alinhamento a Laser")
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/dossie/")
        self.assertEqual(r.status_code, 409)
        self.assertIn("não tem módulo técnico configurado", r.data["detail"])
        self.assertNotIn("secao_d", r.data)
        # A carta .docx também recusa, em vez de sair com a tabela ISO-10816.
        r = self.api.get(f"/api/relatorios-inspecao/{rel.pk}/carta-docx/")
        self.assertEqual(r.status_code, 409)

    def test_modulo_planejado_avisa_que_nao_foi_implementado(self):
        for modulo in (ModuloTecnico.ALINHAMENTO_EIXOS, ModuloTecnico.ENSAIO_ELETRICO_TC,
                       ModuloTecnico.TERMOGRAFIA_MECANICA):
            with self.subTest(modulo=modulo):
                r = self.api.get(f"/api/relatorios-inspecao/{self.relatorio(modulo).pk}/dossie/")
                self.assertEqual(r.status_code, 409)
                self.assertEqual(r.data["codigo"], "modulo_nao_implementado")
                self.assertIn("ainda não foi implementado", r.data["detail"])

    def test_inspecao_generica_e_neutra(self):
        rel = self.relatorio(ModuloTecnico.INSPECAO_GENERICA, nome="Análise Sensitiva Sensorial")
        d = self.dossie(rel)
        self.assertEqual(d["modulo"], "INSPECAO_GENERICA")
        self.assertEqual(d["secao_b"]["diagnostico_medio"], {"velocidade": None, "aceleracao": None, "temperatura": None})
        self.assertNotIn("tabela_severidade", d["carta"])
        siglas = [g["sigla"] for g in d["carta"]["glossario"]]
        self.assertNotIn("LA", siglas)
        self.assertNotIn("LOA", siglas)
        ok = next(g for g in d["carta"]["glossario"] if g["sigla"] == "OK")
        self.assertNotIn("térmica", ok["texto"])
        self.assertNotIn("dinâmica", " ".join(d["carta"]["consideracoes"]))
        xml = self.carta_xml(rel)
        self.assertNotIn("Faixas de Velocidade", xml)
        self.assertNotIn("10816", xml)
        self.assertIn("Seção D – Ordens de Serviços Preditivos", xml)

    def test_balanceamento_mantem_a_tabela_de_severidade_por_escolha_declarada(self):
        d = self.dossie(self.relatorio(ModuloTecnico.BALANCEAMENTO, nome="Balanceamento"))
        self.assertEqual(d["modulo"], "BALANCEAMENTO")
        self.assertTrue(d["carta"]["tabela_severidade"])

    # --- Perfil normativo da vibração na carta ---------------------------------

    def test_tabela_de_severidade_identifica_o_limite_acordado_com_o_cliente(self):
        rel = self.relatorio(ModuloTecnico.VIBRACAO)
        carta = self.dossie(rel)["carta"]
        classe_ii = next(c for c in carta["tabela_severidade"] if c["classe"] == "II")
        self.assertEqual(classe_ii["limites"]["bc"], Decimal("4.49"))
        self.assertEqual(classe_ii["origem"], "ACORDO_CLIENTE")
        self.assertEqual(classe_ii["referencia_norma"]["limites"]["bc"], Decimal("2.80"))
        classe_i = next(c for c in carta["tabela_severidade"] if c["classe"] == "I")
        self.assertEqual(classe_i["origem"], "NORMA")
        self.assertEqual(len(carta["notas_severidade"]), 1)
        nota = carta["notas_severidade"][0]
        self.assertIn("4,49", nota)
        self.assertIn("2,80", nota)
        self.assertIn("acordo com o cliente", nota)
        xml = self.carta_xml(rel)
        self.assertIn("Norma ISO-10816-1", xml)
        self.assertNotIn("ISO-20816-3", xml)
        self.assertIn("por acordo com o cliente", xml)

    def test_relatorio_depois_de_07_10_2026_usa_os_grupos_da_iso_20816(self):
        rel = self.relatorio(ModuloTecnico.VIBRACAO)
        Relatorio.objects.filter(pk=rel.pk).update(data_termino=date(2026, 10, 31))
        carta = self.dossie(rel)["carta"]
        self.assertEqual([(c["classe"], c["rotulo"], c["norma"]) for c in carta["tabela_severidade"]],
                         [("I", "Classe I", "ISO 10816-1"), ("G2", "Grupo 2", "ISO 20816-3"),
                          ("G1", "Grupo 1", "ISO 20816-3")])
        self.assertTrue(all("responsável técnico" in n for n in carta["notas_severidade"]))
        xml = self.carta_xml(rel)
        self.assertIn("Norma ISO-10816-1 / ISO-20816-3", xml)
        self.assertIn("Grupos de Máquina", xml)
        self.assertIn("Grupo 2", xml)
        self.assertIn("11.00", xml)  # linha extra da escala: o limite crítico do Grupo 1
        self.assertNotIn("Classe II", xml)

    def test_criterio_do_cliente_prevalece_e_nao_vaza_para_outro_cliente(self):
        from apps.cadastros.models import CriterioSeveridadeVibracao

        CriterioSeveridadeVibracao.objects.create(
            norma_codigo="ISO 10816-1", norma_edicao="1995", classe="II", limite_ab=Decimal("1.12"),
            limite_bc=Decimal("3.50"), limite_cd=Decimal("7.10"), origem="ACORDO_CLIENTE", fonte="Contrato X",
            cliente=self.cliente,
        )
        carta = self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))["carta"]
        self.assertEqual(next(c for c in carta["tabela_severidade"] if c["classe"] == "II")["limites"]["bc"],
                         Decimal("3.50"))
        outro = Cliente.objects.create(nome="Indústria B", cnpj="22.222.222/0001-22")
        from apps.cadastros.criterios import criterio_vigente
        # Até 06/10/2026 a Classe II valia com o acordo de 4,49; depois, os grupos da ISO 20816-3.
        self.assertEqual(criterio_vigente("II", date(2026, 9, 30), cliente_id=outro.id).limite_bc, Decimal("4.49"))

    def test_shell_tem_o_proprio_total_de_equipamentos(self):
        d = self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))
        # 3 linhas na relação, mas só 2 equipamentos ("adicionar linha" repete o QGBT-01).
        self.assertEqual(d["secao_c"]["total"], 3)
        self.assertEqual(d["secao_c"]["equip_monitorados"], 2)
        self.assertEqual(d["secao_b"]["equip_monitorados"], d["secao_c"]["equip_monitorados"])

    def test_media_de_diagnostico_so_das_grandezas_da_tecnologia(self):
        def medias(modulo):
            m = self.dossie(self.relatorio(modulo))["secao_b"]["diagnostico_medio"]
            return m["velocidade"], m["aceleracao"], m["temperatura"]

        d = Decimal
        self.assertEqual(medias(ModuloTecnico.VIBRACAO), (d("4.20"), d("1.10"), None))
        self.assertEqual(medias(ModuloTecnico.TERMOGRAFIA), (None, None, d("78.4")))
        # Balanceamento: o layout de antes (todas as médias que houver), agora declarado.
        self.assertEqual(medias(ModuloTecnico.BALANCEAMENTO), (d("4.20"), d("1.10"), d("78.4")))
        # Inspeção genérica: nenhuma grandeza de outra técnica.
        self.assertEqual(medias(ModuloTecnico.INSPECAO_GENERICA), (None, None, None))

    def test_folha_da_osp_segue_com_todas_as_medicoes_do_achado(self):
        folha = self.dossie(self.relatorio(ModuloTecnico.TERMOGRAFIA))["secao_d"][0]
        self.assertEqual(folha["temperatura_medida"], Decimal("78.4"))
        self.assertEqual(folha["delta_t"], Decimal("37.4"))
        self.assertEqual(folha["grau_risco"], "GR-3")

    def test_carta_docx_so_traz_a_tabela_iso_quando_o_modulo_pede(self):
        marca = "Faixas de Velocidade e Classes de Máquina"
        self.assertIn(marca, self.carta_xml(self.relatorio(ModuloTecnico.VIBRACAO)))
        self.assertIn(marca, self.carta_xml(self.relatorio(ModuloTecnico.BALANCEAMENTO)))
        self.assertNotIn(marca, self.carta_xml(self.relatorio(ModuloTecnico.INSPECAO_GENERICA)))
        termo = self.carta_xml(self.relatorio(ModuloTecnico.TERMOGRAFIA))
        self.assertNotIn(marca, termo)
        # O resto da carta (conteúdo da inspeção por rota) continua igual.
        self.assertIn("Seção D – Ordens de Serviços Preditivos", termo)
        self.assertIn("foi diagnosticada 1 anomalia", termo)

    def test_carta_da_termografia_usa_o_glossario_do_relatorio_de_referencia(self):
        rel = self.relatorio(ModuloTecnico.TERMOGRAFIA)
        textos = self.dossie(rel)["carta"]
        siglas = [g["sigla"] for g in textos["glossario"]]
        self.assertIn("M.T.A.", siglas)
        self.assertNotIn("LOA", siglas)  # termo de vibração
        gr1 = next(g for g in textos["glossario"] if g["sigla"] == "GR-1")
        self.assertIn("ΔT > 100,0°C", gr1["texto"])
        # Título de grupo não tem texto — e a carta .docx não imprime travessão nele.
        self.assertEqual(textos["glossario"][0], {"n": "6.1", "sigla": "Temperaturas", "texto": ""})
        # 23 termos não cabem numa folha A4 da carta em PDF: segue em outra a partir do 6.3.
        self.assertEqual(textos["quebras_glossario"], ["6.3"])
        xml = self.carta_xml(rel)
        self.assertIn("Máxima Temperatura Admissível", xml)
        self.assertNotIn("Lado Oposto ao Acoplamento", xml)
        self.assertIn("avaliação termográfica", xml)

    def test_carta_da_vibracao_segue_com_os_textos_do_modelo_word(self):
        textos = self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))["carta"]
        self.assertEqual([g["sigla"] for g in textos["glossario"]][-2:], ["LA", "LOA"])
        self.assertIn("Seção D – Ordens de Serviços Preditivos [corretiva orientada pela preditiva]", textos["conteudo"])
        self.assertEqual(len(textos["consideracoes"]), 3)
        self.assertEqual(textos["quebras_glossario"], [])

    def test_folha_traz_as_temperaturas_corrigidas_mesmo_vazias(self):
        folha = self.dossie(self.relatorio(ModuloTecnico.TERMOGRAFIA))["secao_d"][0]
        self.assertIn("temperatura_medida_corrigida", folha)
        self.assertIsNone(folha["delta_t_corrigido"])

    def test_migracao_preenche_o_modulo_pela_mesma_regra_que_o_front_usava(self):
        migracao = importlib.import_module("apps.cadastros.migrations.0026_tecnologiaanalise_modulo_tecnico")
        casos = {
            "Análise Vibracional em Sistemas Mecânicos Dinâmicos": "VIBRACAO",
            "Termografia Infravermelha em Sistemas Elétricos": "TERMOGRAFIA",
            "Inspeção por infravermelho": "TERMOGRAFIA",
            "Balanceamento Dinâmico em Campo": "",
            "Análise de Fluídos Isolantes Minerais - Físico Química": "",
            "Análise Sensitiva Sensorial": "",
        }
        for nome, esperado in casos.items():
            self.assertEqual(migracao.modulo_pelo_nome(nome), esperado, nome)


    def test_migracao_associa_modulo_explicito_as_tecnologias_que_caiam_no_padrao(self):
        from django.apps import apps as registro

        migracao = importlib.import_module("apps.cadastros.migrations.0031_dados_modulo_das_tecnologias")
        bal = TecnologiaAnalise.objects.create(nome="Balanceamento", sigla="BALDC", tipo_corretiva="BALANCEAMENTO")
        aflh = TecnologiaAnalise.objects.create(nome="Análise de Fluídos Lubrificantes e Hidráulicos", sigla="AFLH")
        alee = TecnologiaAnalise.objects.create(nome="Alinhamento a Laser Entre Eixos", sigla="ALEE")
        asse = TecnologiaAnalise.objects.create(nome="Análise Sensitiva Sensorial", sigla="ASSE")
        Relatorio.objects.create(cliente=self.cliente, tecnologia=asse, numero="RT-ASSE-1", data_termino=date(2026, 8, 14))
        aqen = TecnologiaAnalise.objects.create(nome="Análise da Qualidade de Energia", sigla="AQEN")
        termo = TecnologiaAnalise.objects.create(nome="Termografia", sigla="TI-SE", modulo_tecnico="TERMOGRAFIA")
        migracao.carregar(registro, None)
        esperado = {bal: "BALANCEAMENTO", aflh: "FLUIDO_LUBRIFICANTE", alee: "ALINHAMENTO_EIXOS",
                    asse: "INSPECAO_GENERICA", aqen: "", termo: "TERMOGRAFIA"}
        for tec, modulo in esperado.items():
            tec.refresh_from_db()
            self.assertEqual(tec.modulo_tecnico, modulo, tec.nome)
