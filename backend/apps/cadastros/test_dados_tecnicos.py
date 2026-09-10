"""
Testes de dados técnicos específicos por tipo de equipamento (Motor Elétrico,
Transformador) — extensão 1-para-1 de Equipamento, discriminada por
TipoEquipamento.categoria_tecnica.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cadastros.models import (
    Area,
    CategoriaTecnica,
    ClasseISO,
    Cliente,
    DadosTecnicosMotor,
    Equipamento,
    Setor,
    TipoBase,
    TipoEquipamento,
)

from . import rules


class ClassificarClasseIsoTest(TestCase):
    """Regra pura — ISO 10816-3 pela potência e rigidez da base."""

    def test_ate_15kw_e_classe_i(self):
        self.assertEqual(rules.classificar_classe_iso(Decimal("10"), None), ClasseISO.I)
        self.assertEqual(rules.classificar_classe_iso(Decimal("15"), None), ClasseISO.I)

    def test_de_15_a_75kw_e_classe_ii(self):
        self.assertEqual(rules.classificar_classe_iso(Decimal("50"), None), ClasseISO.II)
        self.assertEqual(rules.classificar_classe_iso(Decimal("75"), None), ClasseISO.II)

    def test_acima_de_75kw_rigida_e_classe_iii(self):
        self.assertEqual(
            rules.classificar_classe_iso(Decimal("100"), TipoBase.RIGIDA), ClasseISO.III
        )

    def test_acima_de_75kw_flexivel_e_classe_iv(self):
        self.assertEqual(
            rules.classificar_classe_iso(Decimal("100"), TipoBase.FLEXIVEL), ClasseISO.IV
        )

    def test_acima_de_75kw_sem_base_nao_decide(self):
        # Não força um chute entre III e IV sem saber o tipo de base.
        self.assertIsNone(rules.classificar_classe_iso(Decimal("100"), None))

    def test_sem_potencia_nao_decide(self):
        self.assertIsNone(rules.classificar_classe_iso(None, TipoBase.RIGIDA))


class DadosTecnicosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Exemplo Indústria Têxtil", cnpj="11.111.111/0001-11")
        area = Area.objects.create(cliente=cls.cliente, nome="Área")
        cls.setor = Setor.objects.create(area=area, nome="Setor")
        cls.tipo_motor = TipoEquipamento.objects.create(
            nome="Motor elétrico", categoria_tecnica=CategoriaTecnica.MOTOR_ELETRICO,
        )
        cls.tipo_transformador = TipoEquipamento.objects.create(
            nome="Transformador", categoria_tecnica=CategoriaTecnica.TRANSFORMADOR,
        )
        cls.tipo_generico = TipoEquipamento.objects.create(nome="Ventilador")
        cls.analista = get_user_model().objects.create_user(
            email="analista@example.com", nome="Analista", perfil="TECNICO", nivel="MASTER",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)

    def criar_equipamento(self, tipo, tag="MOT-1"):
        return Equipamento.objects.create(setor=self.setor, tag=tag, nome="Equipamento", tipo_equipamento=tipo)

    # --- Criação / edição -----------------------------------------------------

    def test_cria_dados_de_motor_via_api(self):
        eq = self.criar_equipamento(self.tipo_motor)
        resposta = self.api.post("/api/dados-tecnicos-motor/", {
            "equipamento": eq.pk, "potencia_kw": "100", "tensao_v": "380",
            "corrente_a": "180", "rotacao_rpm": 1780, "fator_potencia": "0.89",
            "fator_servico": "1.15", "classe_isolacao": "F", "rendimento_pct": "94.5",
            "rolamento_loa": "6316", "rolamento_la": "6318", "tipo_base": "RIGIDA",
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["classe_isolacao"], "F")

    def test_edita_dados_de_motor_e_recalcula_a_classe_iso(self):
        eq = self.criar_equipamento(self.tipo_motor)
        dados = DadosTecnicosMotor.objects.create(equipamento=eq, potencia_kw="50", tipo_base="RIGIDA")
        eq.refresh_from_db()
        self.assertEqual(eq.classe_iso, ClasseISO.II)  # 50 kW, base ainda não pesa

        resposta = self.api.patch(f"/api/dados-tecnicos-motor/{dados.pk}/", {"potencia_kw": "100"}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        eq.refresh_from_db()
        self.assertEqual(eq.classe_iso, ClasseISO.III)  # agora >75kW + rígida já registrada

    def test_cria_dados_de_transformador_via_api(self):
        eq = self.criar_equipamento(self.tipo_transformador, tag="TRF-1")
        resposta = self.api.post("/api/dados-tecnicos-transformador/", {
            "equipamento": eq.pk, "potencia_kva": "500", "tensao_primaria_v": "13800",
            "tensao_secundaria_v": "380", "impedancia_pct": "5.5", "grupo_ligacao": "Dyn1",
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["grupo_ligacao"], "Dyn1")

    # --- Equipamento antigo (retrocompatibilidade) -----------------------------

    def test_equipamento_sem_dados_tecnicos_continua_servindo_normalmente(self):
        # Simula um cadastro anterior a esta migração: nenhuma linha em
        # DadosTecnicosMotor/Transformador, classe_iso manual preservada.
        eq = self.criar_equipamento(self.tipo_generico, tag="VEN-9")
        eq.classe_iso = ClasseISO.III
        eq.save()
        resposta = self.api.get(f"/api/equipamentos/{eq.pk}/")
        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(resposta.data["dados_motor"])
        self.assertIsNone(resposta.data["dados_transformador"])
        self.assertEqual(resposta.data["classe_iso"], "III")  # não foi mexido
        self.assertEqual(resposta.data["categoria_tecnica"], "")

    # --- Regra ISO propagando para o cadastro -----------------------------------

    def test_motor_com_potencia_e_base_atualiza_classe_iso_do_equipamento(self):
        eq = self.criar_equipamento(self.tipo_motor)
        self.assertEqual(eq.classe_iso, ClasseISO.II)  # default do model
        DadosTecnicosMotor.objects.create(equipamento=eq, potencia_kw="120", tipo_base=TipoBase.FLEXIVEL)
        eq.refresh_from_db()
        self.assertEqual(eq.classe_iso, ClasseISO.IV)

    def test_motor_acima_de_75kw_sem_base_nao_altera_classe_iso_existente(self):
        eq = self.criar_equipamento(self.tipo_motor)
        eq.classe_iso = ClasseISO.II
        eq.save()
        DadosTecnicosMotor.objects.create(equipamento=eq, potencia_kw="120")  # sem tipo_base
        eq.refresh_from_db()
        self.assertEqual(eq.classe_iso, ClasseISO.II)  # não decidiu, não mexeu

    def test_potencia_rotacao_tensao_fp_sincronizam_do_motor_para_o_equipamento(self):
        eq = self.criar_equipamento(self.tipo_motor)
        DadosTecnicosMotor.objects.create(
            equipamento=eq, potencia_kw="30", rotacao_rpm=1780,
            tensao_v="380", fator_potencia="0.89",
        )
        eq.refresh_from_db()
        self.assertEqual(eq.potencia_kw, Decimal("30.00"))
        self.assertEqual(eq.rotacao_nominal_rpm, 1780)
        self.assertEqual(eq.tensao_nominal, Decimal("380.00"))
        self.assertEqual(eq.fator_potencia_nominal, Decimal("0.890"))

    # --- Campos opcionais / obrigatórios ----------------------------------------

    def test_todos_os_campos_tecnicos_sao_opcionais_exceto_o_vinculo(self):
        eq = self.criar_equipamento(self.tipo_motor)
        dados = DadosTecnicosMotor.objects.create(equipamento=eq)  # nada preenchido
        self.assertIsNone(dados.potencia_kw)
        self.assertIsNone(dados.tensao_v)
        self.assertEqual(dados.classe_isolacao, "")

    def test_equipamento_e_obrigatorio_na_api(self):
        resposta = self.api.post("/api/dados-tecnicos-motor/", {"potencia_kw": "10"}, format="json")
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("equipamento", resposta.data)

    def test_um_equipamento_nao_pode_ter_dois_registros_de_dados_de_motor(self):
        eq = self.criar_equipamento(self.tipo_motor)
        DadosTecnicosMotor.objects.create(equipamento=eq)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                DadosTecnicosMotor.objects.create(equipamento=eq)

    def test_api_rejeita_segundo_registro_de_motor_no_mesmo_equipamento(self):
        eq = self.criar_equipamento(self.tipo_motor)
        DadosTecnicosMotor.objects.create(equipamento=eq)
        resposta = self.api.post("/api/dados-tecnicos-motor/", {"equipamento": eq.pk}, format="json")
        self.assertEqual(resposta.status_code, 400)

    def test_rejeita_fator_de_potencia_fora_de_0_a_1(self):
        eq = self.criar_equipamento(self.tipo_motor)
        resposta = self.api.post(
            "/api/dados-tecnicos-motor/", {"equipamento": eq.pk, "fator_potencia": "1.5"}, format="json"
        )
        self.assertEqual(resposta.status_code, 400)
        self.assertIn("fator_potencia", resposta.data)

    # --- Catálogo: categoria_tecnica explícita, não inferida por nome -----------

    def test_categoria_tecnica_do_tipo_aparece_no_equipamento(self):
        eq = self.criar_equipamento(self.tipo_motor)
        resposta = self.api.get(f"/api/equipamentos/{eq.pk}/")
        self.assertEqual(resposta.data["categoria_tecnica"], CategoriaTecnica.MOTOR_ELETRICO)

    def test_tipo_generico_sem_categoria_nao_aparece_como_motor_ou_transformador(self):
        eq = self.criar_equipamento(self.tipo_generico, tag="VEN-2")
        resposta = self.api.get(f"/api/equipamentos/{eq.pk}/")
        self.assertEqual(resposta.data["categoria_tecnica"], "")

    # --- Integração com Economia energética (mesmo mecanismo já testado) --------

    def test_dados_do_motor_alimentam_o_serializer_usado_pela_economia(self):
        from apps.servicos.models import ServicoCampo, TipoServico
        from apps.servicos.serializers import ServicoCampoSerializer

        eq = self.criar_equipamento(self.tipo_motor, tag="MOT-ECO")
        DadosTecnicosMotor.objects.create(equipamento=eq, tensao_v="440", fator_potencia="0.91")
        eq.refresh_from_db()
        servico = ServicoCampo.objects.create(
            cliente=self.cliente, equipamento=eq, tipo=TipoServico.BALANCEAMENTO,
            analista=self.analista, data_execucao="2026-09-10",
        )
        dados_serializados = ServicoCampoSerializer(servico).data
        self.assertEqual(dados_serializados["equipamento_tensao_nominal"], "440.00")
        self.assertEqual(dados_serializados["equipamento_fator_potencia_nominal"], "0.910")
