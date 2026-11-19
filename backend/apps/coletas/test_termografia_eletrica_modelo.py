"""
Termografia em sistemas elétricos — o relatório segue o modelo do cliente
(RT.TE-2026.05.18.02326, Acco Brands – Foroni).

O que estes testes seguram: a carta com a estrutura do RT.TE (três datas, instrumentação
numerada, fluxo de trabalho no 6.11 e Considerações como item 7), a Seção C com a Área
pelo código e os painéis pelo nome, os campos da correção pela carga na OSP e o cadastro
de equipamento sem TAG (ou com a TAG da máquina repetida nos painéis). E que nada disso
vaza para o relatório de vibração.
"""
import io
import re
import zipfile
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Condicao, Equipamento, Instrumento, ModuloTecnico, Setor, TecnologiaAnalise
from apps.coletas.models import Achado, Carregamento, ItemInspecao, Relatorio
from apps.coletas.relatorio_tecnico.termografia import PLATAFORMA
from apps.osp.models import OrdemServico

User = get_user_model()


class TermografiaEletricaModeloTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.analista = User.objects.create_user(
            email="analista@thermo.com", nome="Analista", perfil="TECNICO", nivel="SENIOR",
        )
        cls.gr3 = Condicao.objects.create(nome="Grau de Risco MODERADO", sigla="GR-3", gera_acao=True)
        cls.ok = Condicao.objects.create(nome="Condição Normal de Operação", sigla="OK", gera_acao=False)
        # Áreas fora da ordem alfabética do código, para a ordem pelo código aparecer.
        filial = Area.objects.create(cliente=cls.cliente, codigo="004", nome="Alfa [Filial]")
        matriz = Area.objects.create(cliente=cls.cliente, codigo="001", nome="Zeta [Matriz]")
        cls.cabine = Setor.objects.create(area=matriz, nome="Cabine Elétrica")
        cls.cadernos = Setor.objects.create(area=filial, nome="Cadernos")
        # Painéis sem TAG, um com TAG e dois com a TAG da mesma máquina.
        cls.qgbt = Equipamento.objects.create(setor=cls.cabine, nome="QGBT-1")
        cls.banco = Equipamento.objects.create(setor=cls.cabine, nome="Banco de Capacitores - PNL.1")
        cls.compressor = Equipamento.objects.create(setor=cls.cabine, tag="00092", nome="PNL Compressor")
        cls.botteon1 = Equipamento.objects.create(setor=cls.cadernos, tag="00007", nome="Botteon 03 - PNL.01")
        cls.botteon2 = Equipamento.objects.create(setor=cls.cadernos, tag="00007", nome="Botteon 03 - PNL.02")
        cls.camera = Instrumento.objects.create(
            tipo="Termovisor / Câmera Termográfica", marca="FLIR", modelo="Série T", numero_serie="48805666",
            data_ultima_calibracao=date(2024, 5, 10), entidade_calibracao="VISOMES",
            software_analise="FLIR QuickReport | FLIR Thermal Studio",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)

    def relatorio(self, modulo=ModuloTecnico.TERMOGRAFIA):
        tecnologia = TecnologiaAnalise.objects.create(nome=f"Tecnologia {modulo}", sigla="TE", modulo_tecnico=modulo)
        rel = Relatorio.objects.create(
            cliente=self.cliente, tecnologia=tecnologia, data_inicio=date(2026, 5, 18), data_termino=date(2026, 5, 18),
            numero=f"RT-TE-2026-05-18-{Relatorio.objects.count() + 1:05d}", data_finalizacao=date(2026, 6, 1),
        )
        rota = Carregamento.objects.create(
            cliente=self.cliente, tecnologia=tecnologia, analista=self.analista, relatorio=rel, instrumento=self.camera,
        )
        # Ordem da rota de propósito diferente da alfabética.
        itens = {}
        for ordem, (eq, cond) in enumerate([
            (self.qgbt, self.gr3), (self.compressor, self.ok), (self.banco, self.ok),
            (self.botteon2, self.ok), (self.botteon1, self.ok),
        ], start=1):
            itens[eq.pk] = ItemInspecao.objects.create(carregamento=rota, equipamento=eq, ordem=ordem, condicao=cond)
        self.achado = Achado.objects.create(
            item=itens[self.qgbt.pk], componente_texto="Disjuntor(es) DJ7",
            anomalia_texto="Mau contato no(s) terminal(ais) prensado(s) de saída.", condicao=self.gr3,
            temperatura_medida=Decimal("87.0"), temperatura_referencia=Decimal("50.0"),
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
            xml = z.read("word/document.xml").decode("utf-8")
        # Texto corrido: o título numerado grava o número e o nome em trechos separados por tabulação.
        return re.sub(r"<[^>]+>", "", re.sub(r"<w:tab[^>]*/>", " ", xml))

    # --- Carta ---------------------------------------------------------------
    def test_carta_segue_a_estrutura_do_rt_te(self):
        carta = self.dossie(self.relatorio())["carta"]
        self.assertIs(carta["definicao_tecnica"], False)
        self.assertIs(carta["instrumentacao_numerada"], True)
        self.assertIs(carta["mostra_data_osps"], True)
        numeros = [g["n"] for g in carta["glossario"]]
        self.assertEqual(numeros[-8:], ["6.11", "6.11.1", "6.11.2", "6.11.3", "6.11.4", "6.11.5", "6.11.6", "6.11.7"])
        fluxo = {g["n"]: g for g in carta["glossario"]}
        self.assertEqual((fluxo["6.11"]["sigla"], fluxo["6.11"]["texto"]), ("Fluxo de Trabalho", ""))
        self.assertEqual(fluxo["6.11.2"]["sigla"], "")  # passo numerado, sem sigla
        # O sistema antigo do cliente não é citado: entra o nome desta plataforma.
        texto = " ".join(g["texto"] for g in carta["glossario"])
        self.assertIn(f"disponibiliza as OSP´s no {PLATAFORMA} até o 6º dia útil", texto)
        self.assertNotIn("MasterSys", texto)

    def test_vibracao_mantem_a_carta_do_modelo_word(self):
        carta = self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))["carta"]
        self.assertIs(carta["definicao_tecnica"], True)
        self.assertIs(carta["instrumentacao_numerada"], False)
        self.assertIs(carta["mostra_data_osps"], False)
        self.assertIsNone(carta["data_upload_osps"])
        self.assertNotIn("6.11", [g["n"] for g in carta["glossario"]])

    def test_data_das_osps_informada_ou_a_de_geracao(self):
        rel = self.relatorio()
        # Sem OSP e sem data informada: a carta não mostra a linha.
        self.assertIsNone(self.dossie(rel)["carta"]["data_upload_osps"])
        # Gerada a OSP, vale o dia em que ela ficou disponível no sistema.
        OrdemServico.gerar_de_achado(self.achado)
        self.assertEqual(self.dossie(rel)["carta"]["data_upload_osps"], timezone.localdate())
        # A data informada no relatório prevalece (relatório lançado depois do fato).
        r = self.api.patch(f"/api/relatorios-inspecao/{rel.pk}/", {"data_upload_osps": "2026-05-25"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        d = self.dossie(rel)
        self.assertEqual(d["carta"]["data_upload_osps"], date(2026, 5, 25))
        self.assertEqual(d["cabecalho"]["data_upload_osps"], date(2026, 5, 25))
        # Na vibração a linha não existe, mesmo com OSP gerada e data informada.
        vib = self.relatorio(ModuloTecnico.VIBRACAO)
        OrdemServico.gerar_de_achado(self.achado)
        Relatorio.objects.filter(pk=vib.pk).update(data_upload_osps=date(2026, 5, 25))
        self.assertIsNone(self.dossie(vib)["carta"]["data_upload_osps"])

    def test_carta_docx_tem_a_mesma_estrutura(self):
        rel = self.relatorio()
        Relatorio.objects.filter(pk=rel.pk).update(data_upload_osps=date(2026, 5, 25))
        xml = self.carta_xml(rel)
        self.assertIn("7. Considerações Importantes", xml)
        self.assertNotIn("Definição da Técnica", xml)
        self.assertNotIn("8. Considerações", xml)
        self.assertIn("Upload das OSP´s – 25/05/2026", xml)
        self.assertIn("4.1. Termovisor / Câmera Termográfica", xml)
        self.assertIn("Marca: FLIR | Modelo: Série T", xml)
        self.assertIn("Data da última calibração: 05/2024", xml)
        self.assertIn("4.2. Softwares de Análises:", xml)
        self.assertIn("6.11. Fluxo de Trabalho", xml)
        self.assertIn(f"plataforma {PLATAFORMA}", xml)
        # A vibração segue com os itens 7 e 8 e sem a linha das OSPs.
        vib = self.carta_xml(self.relatorio(ModuloTecnico.VIBRACAO))
        self.assertIn("7. Definição da Técnica", vib)
        self.assertIn("8. Considerações Importantes", vib)
        self.assertNotIn("Upload das OSP", vib)
        self.assertNotIn("4.1.", vib)

    # --- Seção C e OSP -------------------------------------------------------
    def test_secao_c_area_pelo_codigo_e_paineis_pelo_nome(self):
        d = self.dossie(self.relatorio())
        grupos = d["secao_c"]["grupos"]
        self.assertEqual([(g["area"], g["setor"]) for g in grupos],
                         [("001 - Zeta [Matriz]", "Cabine Elétrica"), ("004 - Alfa [Filial]", "Cadernos")])
        self.assertEqual([linha["equipamento"] for linha in grupos[0]["linhas"]],
                         ["Banco de Capacitores - PNL.1", "PNL Compressor", "QGBT-1"])
        self.assertEqual([(linha["tag"], linha["equipamento"]) for linha in grupos[1]["linhas"]],
                         [("00007", "Botteon 03 - PNL.01"), ("00007", "Botteon 03 - PNL.02")])
        self.assertEqual(d["secao_c"]["equip_monitorados"], 5)
        # A OSP mostra a Área do mesmo jeito.
        self.assertEqual(d["secao_d"][0]["area"], "001 - Zeta [Matriz]")

    def test_secao_c_da_vibracao_continua_pela_tag(self):
        grupos = self.dossie(self.relatorio(ModuloTecnico.VIBRACAO))["secao_c"]["grupos"]
        # Sem TAG primeiro (ordem da rota), depois as TAGs — o comportamento de antes.
        self.assertEqual([linha["equipamento"] for linha in grupos[0]["linhas"]],
                         ["QGBT-1", "Banco de Capacitores - PNL.1", "PNL Compressor"])

    def test_correcao_pela_carga_e_calculada_e_sai_na_osp(self):
        # Fórmula do cliente (correcao_carga.py): I1 = fase R (62 A) de 100 A → carga 62 %;
        # fator (90/62)² ≈ 2,1072; T. medida corrigida = 30 + (87 − 30) × fator = 150,1;
        # ΔT corrigido = 37 × fator = 78,0. Os valores digitados para os calculados são ignorados.
        rel = self.relatorio()
        r = self.api.patch(f"/api/achados/{self.achado.pk}/", {
            "corrente_nominal": "100.00", "corrente_a": "62.00", "corrente_b": "60.50", "corrente_c": "61.00",
            "fase_anomalia": "R", "temperatura_ambiente": "30.0",
            "carga_percentual": "10.0", "temperatura_medida_corrigida": "121.4", "delta_t_corrigido": "71.4",
        }, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        folha = self.dossie(rel)["secao_d"][0]
        self.assertEqual((folha["carga_percentual"], folha["temperatura_medida_corrigida"], folha["delta_t_corrigido"]),
                         (Decimal("62.0"), Decimal("150.1"), Decimal("78.0")))
        self.assertEqual(folha["corrente"], [Decimal("100.00"), Decimal("62.00"), Decimal("60.50"), Decimal("61.00")])
        # O ΔT medido continua derivado da medida e da referência — a correção não o altera.
        self.assertEqual(folha["delta_t"], Decimal("37.0"))


class EquipamentoSemTagTest(TestCase):
    """Painel elétrico costuma não ter TAG; os painéis de uma máquina repetem a TAG dela."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Matriz"), nome="Envelope")
        cls.master = User.objects.create_user(email="master@thermo.com", nome="Master", perfil="GESTOR", nivel="MASTER")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.master)

    def criar(self, **dados):
        return self.api.post("/api/equipamentos/", {"setor": self.setor.pk, **dados}, format="json")

    def test_tag_e_opcional_e_pode_repetir_com_outro_nome(self):
        self.assertEqual(self.criar(nome="QGBT-1").status_code, 201)
        self.assertEqual(self.criar(nome="QGBT-2", tag="").status_code, 201)
        self.assertEqual(self.criar(nome="MÁQ.31 - PNL.02", tag="00031").status_code, 201)
        self.assertEqual(self.criar(nome="MÁQ.31 - PNL.03", tag="00031").status_code, 201)
        self.assertEqual(Equipamento.objects.filter(setor=self.setor, tag="").count(), 2)

    def test_mesmo_setor_tag_e_nome_nao_se_repete(self):
        self.assertEqual(self.criar(nome="QGBT-1").status_code, 201)
        self.assertEqual(self.criar(nome="QGBT-1").status_code, 400)
        self.assertEqual(self.criar(nome="Bomba", tag="BBA-101").status_code, 201)
        self.assertEqual(self.criar(nome="Bomba", tag="BBA-101").status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Equipamento.objects.create(setor=self.setor, nome="QGBT-1")

    def test_equipamento_sem_tag_e_citado_pelo_nome(self):
        sem_tag = Equipamento.objects.create(setor=self.setor, nome="QTA")
        com_tag = Equipamento.objects.create(setor=self.setor, tag="BBA-101", nome="Bomba")
        self.assertEqual((sem_tag.rotulo_curto, com_tag.rotulo_curto), ("QTA", "BBA-101"))
        self.assertEqual((str(sem_tag), str(com_tag)), ("QTA", "BBA-101 — Bomba"))
