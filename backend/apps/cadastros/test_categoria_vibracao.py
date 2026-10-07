"""
Cadastro técnico por tipo de equipamento e perfil normativo da vibração.

  - o tipo decide o datasheet (categoria técnica) e se há classe de vibração —
    sempre por vínculo explícito, nunca pelo nome;
  - transformador não tem dados de motor nem classe ISO de vibração;
  - os limites de severidade vêm do critério cadastrado (norma, origem, vigência),
    e o acordo com o cliente (Classe II, 4,49 mm/s) não passa por valor da ISO.
"""
import importlib
from datetime import date
from decimal import Decimal as D

from django.apps import apps as registro
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.coletas import rules as rules_vibracao

from . import criterios
from .models import (
    Area,
    CategoriaTecnica,
    Cliente,
    CriterioSeveridadeVibracao,
    DadosTecnicosTransformador,
    Equipamento,
    Setor,
    TipoEquipamento,
)

User = get_user_model()


class CadastroPorTipoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Área"), nome="Setor")
        cls.tipo_motor = TipoEquipamento.objects.create(nome="Motor elétrico", analise_vibracao=True,
                                                        categoria_tecnica=CategoriaTecnica.MOTOR_ELETRICO)
        cls.tipo_trafo = TipoEquipamento.objects.create(nome="Transformador",
                                                        categoria_tecnica=CategoriaTecnica.TRANSFORMADOR)
        cls.tipo_bomba = TipoEquipamento.objects.create(nome="Bomba centrífuga", analise_vibracao=True)
        cls.tipo_painel = TipoEquipamento.objects.create(nome="Painel de comando")
        cls.master = User.objects.create_user(email="m@thermo.com", nome="Master", perfil="TECNICO", nivel="MASTER")
        cls.tecnico = User.objects.create_user(email="t@thermo.com", nome="Técnico", perfil="TECNICO", nivel="PLENO")
        cls.leitor = User.objects.create_user(email="c@a.com", nome="PCM", perfil="CLIENTE_PCM", cliente=cls.cliente)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.master)

    def criar(self, tipo, tag, **extra):
        r = self.api.post("/api/equipamentos/", {"setor": self.setor.id, "tag": tag, "nome": tag,
                                                  "tipo_equipamento": tipo.id if tipo else None, **extra},
                          format="json")
        self.assertEqual(r.status_code, 201, r.data)
        return r.data

    # --- Transformador × motor ------------------------------------------------
    def test_transformador_nao_tem_classe_iso_nem_criterio_de_vibracao(self):
        eq = self.criar(self.tipo_trafo, "TRF-01")
        self.assertEqual(eq["categoria_tecnica"], "TRANSFORMADOR")
        self.assertFalse(eq["analise_vibracao"])
        self.assertEqual(eq["classe_iso"], "")
        self.assertIsNone(eq["criterio_vibracao"])
        # Mesmo que a API receba uma classe, ela não vira dado do transformador.
        r = self.api.patch(f"/api/equipamentos/{eq['id']}/", {"classe_iso": "II"}, format="json")
        self.assertEqual(r.data["classe_iso"], "")

    def test_transformador_nao_aceita_dados_de_motor(self):
        eq = self.criar(self.tipo_trafo, "TRF-02")
        r = self.api.post("/api/dados-tecnicos-motor/", {"equipamento": eq["id"], "potencia_kw": "75",
                                                          "rotacao_rpm": 1780, "fator_potencia": "0.86"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Transformador", str(r.data["equipamento"]))
        r = self.api.post("/api/dados-tecnicos-transformador/", {"equipamento": eq["id"], "potencia_kva": "500",
                                                                  "grupo_ligacao": "Dyn1"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)

    def test_motor_nao_aceita_dados_de_transformador_e_calcula_a_classe(self):
        eq = self.criar(self.tipo_motor, "MOT-01")
        r = self.api.post("/api/dados-tecnicos-transformador/", {"equipamento": eq["id"], "potencia_kva": "500"},
                          format="json")
        self.assertEqual(r.status_code, 400)
        r = self.api.post("/api/dados-tecnicos-motor/", {"equipamento": eq["id"], "potencia_kw": "100",
                                                          "tipo_base": "RIGIDA"}, format="json")
        self.assertEqual(r.status_code, 201, r.data)
        eq = self.api.get(f"/api/equipamentos/{eq['id']}/").data
        self.assertEqual(eq["classe_iso"], "G2")  # 100 kW: Grupo 2 da ISO 20816-3
        self.assertEqual(eq["criterio_vibracao"]["norma"], "ISO 20816-3")
        self.assertEqual(eq["criterio_vibracao"]["origem"], "RESPONSAVEL_TECNICO")

    def test_tipo_sem_categoria_nao_ganha_datasheet_nem_pelo_nome(self):
        tipo = TipoEquipamento.objects.create(nome="Transformador seco")  # nome sugestivo, sem categoria
        eq = self.criar(tipo, "TRF-03")
        self.assertEqual(eq["categoria_tecnica"], "")
        r = self.api.post("/api/dados-tecnicos-transformador/", {"equipamento": eq["id"]}, format="json")
        self.assertEqual(r.status_code, 400)
        sem_tipo = self.criar(None, "SEM-01")
        r = self.api.post("/api/dados-tecnicos-motor/", {"equipamento": sem_tipo["id"]}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_painel_nao_e_avaliado_por_vibracao_e_bomba_e(self):
        painel = self.criar(self.tipo_painel, "QGBT-1")
        self.assertFalse(painel["analise_vibracao"])
        self.assertEqual(painel["classe_iso"], "")
        bomba = self.criar(self.tipo_bomba, "BBA-01", classe_iso="G2")
        self.assertTrue(bomba["analise_vibracao"])
        self.assertEqual(bomba["classe_iso"], "G2")
        self.assertEqual(bomba["criterio_vibracao"]["limites"]["cd"], D("7.10"))
        self.assertEqual(bomba["criterio_vibracao"]["origem"], "RESPONSAVEL_TECNICO")

    def test_maquina_avaliada_por_vibracao_sempre_tem_grupo(self):
        # "Não existe equipamento sem classe definida" (responsável técnico, 07/10/2026).
        r = self.api.post("/api/equipamentos/", {"setor": self.setor.id, "tag": "BBA-02", "nome": "Bomba",
                                                  "tipo_equipamento": self.tipo_bomba.id}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("classe_iso", r.data)
        # Classe histórica da ISO 10816-1 não entra em cadastro novo…
        r = self.api.post("/api/equipamentos/", {"setor": self.setor.id, "tag": "BBA-03", "nome": "Bomba",
                                                  "tipo_equipamento": self.tipo_bomba.id, "classe_iso": "III"},
                          format="json")
        self.assertEqual(r.status_code, 400)
        # …mas o equipamento antigo continua editável sem trocar a classe.
        antigo = Equipamento.objects.create(setor=self.setor, tag="BBA-04", nome="Antiga",
                                            tipo_equipamento=self.tipo_bomba, classe_iso="III")
        r = self.api.patch(f"/api/equipamentos/{antigo.id}/", {"nome": "Antiga 2", "classe_iso": "III"}, format="json")
        self.assertEqual(r.status_code, 200, r.data)
        # O motor tem o grupo pela potência do datasheet, salvo depois do equipamento.
        self.criar(self.tipo_motor, "MOT-09")

    # --- Catálogo -------------------------------------------------------------
    def test_catalogo_impede_transformador_com_vibracao(self):
        r = self.api.patch(f"/api/tipos-equipamento/{self.tipo_trafo.id}/", {"analise_vibracao": True}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_catalogo_nao_troca_categoria_com_datasheet_existente(self):
        eq = Equipamento.objects.create(setor=self.setor, tag="TRF-9", nome="Trafo", tipo_equipamento=self.tipo_trafo)
        DadosTecnicosTransformador.objects.create(equipamento=eq, potencia_kva=D("500"))
        r = self.api.patch(f"/api/tipos-equipamento/{self.tipo_trafo.id}/",
                           {"categoria_tecnica": "MOTOR_ELETRICO"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("categoria_tecnica", r.data)

    # --- Migração de dados ----------------------------------------------------
    def test_migracao_associa_categoria_por_nome_exato_ou_evidencia_e_so_no_vazio(self):
        migracao = importlib.import_module("apps.cadastros.migrations.0029_dados_categoria_vibracao_criterios")
        exato = TipoEquipamento.objects.create(nome="  Transformador a Óleo ")
        parecido = TipoEquipamento.objects.create(nome="Transformadores e reatores")
        evidencia = TipoEquipamento.objects.create(nome="TPA Trafo de Potência")
        eq = Equipamento.objects.create(setor=self.setor, tag="X", nome="X", tipo_equipamento=evidencia)
        DadosTecnicosTransformador.objects.create(equipamento=eq)
        ja_definido = TipoEquipamento.objects.create(nome="Transformador", categoria_tecnica="MOTOR_ELETRICO")
        migracao.carregar(registro, None)
        for tipo, esperado in ((exato, "TRANSFORMADOR"), (parecido, ""), (evidencia, "TRANSFORMADOR"),
                               (ja_definido, "MOTOR_ELETRICO")):
            tipo.refresh_from_db()
            self.assertEqual(tipo.categoria_tecnica, esperado, tipo.nome)

    # --- Critérios (perfil normativo) -----------------------------------------
    def test_carga_inicial_separa_norma_de_acordo(self):
        norma_ii = CriterioSeveridadeVibracao.objects.get(classe="II", origem="NORMA")
        self.assertEqual(norma_ii.limite_bc, D("2.80"))
        acordo = CriterioSeveridadeVibracao.objects.get(classe="II", origem="ACORDO_CLIENTE")
        self.assertEqual(acordo.limite_bc, D("4.49"))
        self.assertIn("16/09/2026", acordo.fonte)
        # Até 06/10/2026: as classes da ISO 10816-1 (com o acordo da Classe II).
        antes, depois = date(2026, 9, 30), date(2026, 10, 7)
        for classe in ("I", "II", "III", "IV"):
            self.assertEqual(criterios.faixas_vigentes(classe, antes), rules_vibracao.FAIXAS_ISO_VRMS[classe], classe)
        # A partir de 07/10/2026: Classe I + Grupos 2 e 1 da ISO 20816-3; II–IV encerradas.
        for classe in ("I", "G2", "G1"):
            self.assertEqual(criterios.faixas_vigentes(classe, depois), rules_vibracao.FAIXAS_ISO_VRMS[classe], classe)
        for classe in ("II", "III", "IV"):
            self.assertIsNone(criterios.criterio_vigente(classe, depois), classe)
        g2, g1 = (criterios.criterio_vigente(c, depois) for c in ("G2", "G1"))
        self.assertEqual((g2.limite_cd, g1.limite_cd), (D("7.10"), D("11.00")))  # os críticos informados
        self.assertEqual((g2.norma_codigo, g2.norma_edicao, g2.origem), ("ISO 20816-3", "2022", "RESPONSAVEL_TECNICO"))
        self.assertIn("07/10/2026", g2.fonte)

    def test_tabela_da_carta_por_data(self):
        antes = criterios.tabela_severidade(date(2026, 9, 30))
        self.assertEqual([c["classe"] for c in antes], ["I", "II", "III", "IV"])
        depois = criterios.tabela_severidade(date(2026, 10, 7))
        self.assertEqual([(c["classe"], c["rotulo"]) for c in depois],
                         [("I", "Classe I"), ("G2", "Grupo 2"), ("G1", "Grupo 1")])
        notas = criterios.notas_tabela_severidade(depois)
        self.assertEqual(len(notas), 2)  # os grupos: critério do responsável técnico, com a fonte
        self.assertTrue(notas[0].startswith("Grupo 2: critério do responsável técnico — ISO 20816-3:2022"))

    def test_migracao_reclassifica_pela_potencia(self):
        migracao = importlib.import_module("apps.cadastros.migrations.0033_criterios_iso_20816")
        casos = {"P10": ("II", D("10")), "P90": ("III", D("90")), "P400": ("III", D("400")),
                 "SEMP2": ("II", None), "SEMP3": ("IV", None)}
        eqs = {tag: Equipamento.objects.create(setor=self.setor, tag=tag, nome=tag, tipo_equipamento=self.tipo_bomba,
                                               classe_iso=classe, potencia_kw=p)
               for tag, (classe, p) in casos.items()}
        migracao.carregar(registro, None)
        esperado = {"P10": "I", "P90": "G2", "P400": "G1", "SEMP2": "G2", "SEMP3": "IV"}
        for tag, eq in eqs.items():
            eq.refresh_from_db()
            self.assertEqual(eq.classe_iso, esperado[tag], tag)

    def test_classificacao_usa_o_criterio_do_cliente_e_a_vigencia(self):
        self.assertEqual(rules_vibracao.classificar_vibracao("II", D("3.5"),
                                                            faixas=criterios.faixas_vigentes("II")).zona_iso, "B")
        CriterioSeveridadeVibracao.objects.create(
            norma_codigo="ISO 10816-1", classe="II", limite_ab=D("1.12"), limite_bc=D("2.80"), limite_cd=D("7.10"),
            origem="ACORDO_CLIENTE", fonte="Contrato 2027", cliente=self.cliente, vigencia_inicio=date(2027, 1, 1),
        )
        antes = criterios.faixas_vigentes("II", data=date(2026, 12, 31), cliente_id=self.cliente.id)
        depois = criterios.faixas_vigentes("II", data=date(2027, 1, 2), cliente_id=self.cliente.id)
        self.assertEqual(rules_vibracao.classificar_vibracao("II", D("3.5"), faixas=antes).zona_iso, "B")
        self.assertEqual(rules_vibracao.classificar_vibracao("II", D("3.5"), faixas=depois).zona_iso, "C")

    def test_sem_classe_o_diagnostico_avisa(self):
        r = rules_vibracao.classificar_vibracao("", D("3.0"))
        self.assertIn("Classe da máquina não definida", r.diagnostico)

    def test_api_de_criterios_e_interna_e_so_o_master_altera(self):
        corpo = {"norma_codigo": "ISO 10816-1", "classe": "I", "limite_ab": "0.71", "limite_bc": "1.80",
                 "limite_cd": "4.50", "origem": "NORMA"}
        leitor = APIClient()
        leitor.force_authenticate(self.leitor)
        self.assertEqual(leitor.get("/api/criterios-vibracao/").status_code, 403)
        tecnico = APIClient()
        tecnico.force_authenticate(self.tecnico)
        self.assertEqual(tecnico.get("/api/criterios-vibracao/").status_code, 200)
        self.assertEqual(tecnico.post("/api/criterios-vibracao/", corpo, format="json").status_code, 403)
        self.assertEqual(self.api.post("/api/criterios-vibracao/", {**corpo, "limite_bc": "0.50"}, format="json")
                         .status_code, 400)
        self.assertEqual(self.api.post("/api/criterios-vibracao/", {**corpo, "origem": "ACORDO_CLIENTE"},
                                       format="json").status_code, 400)  # acordo sem fonte
        self.assertEqual(self.api.post("/api/criterios-vibracao/", corpo, format="json").status_code, 201)
