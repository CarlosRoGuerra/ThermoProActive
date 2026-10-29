"""Coleta técnica: integridade e segurança sem presumir limites normativos.

Os valores nos casos de classificação são critérios de teste explícitos. O
contrato enumera modalidades, mas não define números ou unidades obrigatórias.
"""
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Componente, CriterioSeveridadeVibracao, Equipamento, Instrumento, Setor
from apps.laudos.models import Laudo
from apps.osp.models import OrdemServico

from .models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao


class ConformidadeColetaTecnicaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="10.111.111/0001-10")
        cls.outro_cliente = Cliente.objects.create(nome="Indústria B", cnpj="20.222.222/0001-20")
        cls.tecnico = get_user_model().objects.create_user(
            email="coleta@thermo.test", nome="Analista", perfil="TECNICO", nivel="PLENO",
        )
        cls.portal = get_user_model().objects.create_user(
            email="cliente@thermo.test", nome="Cliente", perfil="CLIENTE_PCM", cliente=cls.cliente,
        )
        cls.portal_sem_vinculo = get_user_model().objects.create_user(
            email="sem-vinculo@thermo.test", nome="Sem vínculo", perfil="CLIENTE_PCM",
        )
        cls.setor = Setor.objects.create(
            area=Area.objects.create(cliente=cls.cliente, nome="Produção"), nome="Bombas",
        )
        cls.outro_setor = Setor.objects.create(
            area=Area.objects.create(cliente=cls.outro_cliente, nome="Produção"), nome="Bombas",
        )
        cls.equipamento = Equipamento.objects.create(
            setor=cls.setor, tag="BOM-01", nome="Bomba", classe_iso="II",
        )
        cls.outro_equipamento = Equipamento.objects.create(
            setor=cls.outro_setor, tag="BOM-02", nome="Bomba B", classe_iso="II",
        )
        cls.componente = Componente.objects.create(equipamento=cls.equipamento, nome="Mancal LA")
        cls.outro_componente = Componente.objects.create(equipamento=cls.outro_equipamento, nome="Mancal")
        cls.instrumento = Instrumento.objects.create(tipo="Coletor", modelo="Teste", numero_serie="QA-01")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)

    def inspecao(self, tipo, **extras):
        return Inspecao.objects.create(
            cliente=self.cliente, tecnico=self.tecnico, data=date(2026, 10, 21), tipo_analise=tipo, **extras,
        )

    def payload(self, tipo="ULTRASSOM", subtipo="MECANICO", **extras):
        unidade = {
            "TRANSFORMADOR_TTR": "", "TRANSFORMADOR_RI": "MΩ", "MOTOR_RI": "MΩ",
            "TRANSFORMADOR_RO": "Ω", "ESPESSURA": "mm", "QUALIDADE_ENERGIA": "%",
            "ALINHAMENTO_EIXOS": "mm", "ALINHAMENTO_POLIAS": "mm", "BALANCEAMENTO": "g",
        }.get(subtipo, "dB")
        if tipo == "FLUIDOS":
            ensaio = extras.get("parametros", {}).get("ensaio")
            unidade = "mg/kg" if ensaio in ("PCB", "2FAL") else "part./mL" if ensaio == "CP" else "ppm"
        dados = {
            "inspecao": self.inspecao(tipo).pk, "equipamento": self.equipamento.pk,
            "componente": self.componente.pk, "instrumento": self.instrumento.pk,
            "tipo": tipo, "subtipo": subtipo, "ponto_medicao": "Ponto 1",
            "grandeza": "Leitura", "valor": "12.2500", "unidade": unidade, "parametros": {},
        }
        dados.update(extras)
        return dados

    def criar(self, dados, endpoint="medicoes-tecnicas"):
        resposta = self.api.post(f"/api/{endpoint}/", dados, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta.data

    def test_subtipos_tecnicos_persistem_e_sao_consultados(self):
        modalidades = {
            "FLUIDOS": ("HIDRAULICO", "LUBRIFICANTE", "MINERAL_ISOLANTE"),
            "ENSAIO_ELETRICO": ("TRANSFORMADOR_TTR", "TRANSFORMADOR_RI", "TRANSFORMADOR_RO", "MOTOR_RI"),
            "ULTRASSOM": ("ELETRICO", "MECANICO"),
            "ESPESSURA": ("ESPESSURA",),
            "CORRETIVA": ("ALINHAMENTO_EIXOS", "ALINHAMENTO_POLIAS", "BALANCEAMENTO"),
            "SENSITIVA": ("SENSITIVA",),
            "QUALIDADE_ENERGIA": ("QUALIDADE_ENERGIA",),
        }
        for tipo, subtipos in modalidades.items():
            for subtipo in subtipos:
                with self.subTest(tipo=tipo, subtipo=subtipo):
                    dados = self.criar(self.payload(tipo, subtipo))
                    registro = MedicaoTecnica.objects.get(pk=dados["id"])
                    self.assertEqual((registro.tipo, registro.subtipo), (tipo, subtipo))
                    self.assertEqual(registro.valor, Decimal("12.2500"))
                    self.assertEqual(registro.instrumento_id, self.instrumento.pk)
                    consulta = self.api.get(f"/api/medicoes-tecnicas/{registro.pk}/")
                    self.assertEqual(consulta.status_code, 200)
                    self.assertEqual(consulta.data["subtipo"], subtipo)
                    self.assertEqual(consulta.data["classificacao_status"], "PENDENTE")
                    self.assertEqual(consulta.data["criticidade"], "")

    def test_novo_registro_exige_subtipo_compativel(self):
        for subtipo in (None, "", "TRANSFORMADOR_RI", "DESCONHECIDO"):
            with self.subTest(subtipo=subtipo):
                dados = self.payload(subtipo=subtipo)
                if subtipo is None:
                    dados.pop("subtipo")
                resposta = self.api.post("/api/medicoes-tecnicas/", dados, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("subtipo", resposta.data)
        self.assertFalse(MedicaoTecnica.objects.exists())

    def test_rejeita_tipo_divergente_da_inspecao_e_vibracao_no_endpoint_generico(self):
        for extras in ({"inspecao": self.inspecao("ESPESSURA").pk}, {"tipo": "VIBRACAO"}):
            with self.subTest(extras=extras):
                resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(**extras), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_rejeita_vinculos_inconsistentes_inclusive_em_patch_parcial(self):
        for campo, valor in (("equipamento", self.outro_equipamento.pk), ("componente", self.outro_componente.pk)):
            with self.subTest(campo=campo):
                dados = self.payload(**{campo: valor})
                resposta = self.api.post("/api/medicoes-tecnicas/", dados, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn(campo, resposta.data)
        criado = self.criar(self.payload())
        resposta = self.api.patch(
            f"/api/medicoes-tecnicas/{criado['id']}/", {"equipamento": self.outro_equipamento.pk}, format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertEqual(MedicaoTecnica.objects.get(pk=criado["id"]).equipamento_id, self.equipamento.pk)

    def test_parametros_devem_ser_objeto_json(self):
        for parametros in ([], [1], "texto", 42, True):
            with self.subTest(parametros=parametros):
                resposta = self.api.post(
                    "/api/medicoes-tecnicas/", self.payload(parametros=parametros), format="json",
                )
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("parametros", resposta.data)

    def test_valores_nao_finitos_e_capacidade_decimal_sao_rejeitados(self):
        for valor in ("NaN", "Infinity", "-Infinity", "10000000000.0000", "0.00001", "abc"):
            with self.subTest(valor=valor):
                resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(valor=valor), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("valor", resposta.data)

    def test_sem_criterio_nao_inventa_classificacao_ou_osp(self):
        # Valores altos de tecnologias diferentes nunca compartilham um limiar genérico.
        for tipo, subtipo in (("ULTRASSOM", "ELETRICO"), ("QUALIDADE_ENERGIA", "QUALIDADE_ENERGIA"),
                              ("CORRETIVA", "BALANCEAMENTO"), ("ENSAIO_ELETRICO", "MOTOR_RI")):
            with self.subTest(tipo=tipo):
                dados = self.criar(self.payload(tipo, subtipo, valor="9999"))
                self.assertEqual(dados["criticidade"], "")
                self.assertEqual(dados["classificacao_status"], "PENDENTE")
        self.assertFalse(OrdemServico.objects.exists())

    def test_edicao_preserva_autoria_data_e_metadados_da_coleta(self):
        dados = self.criar(self.payload(parametros={"arquivo_origem": "captura.csv", "observacao": "Primeira leitura"}))
        registro = MedicaoTecnica.objects.get(pk=dados["id"])
        instante = registro.data_hora
        resposta = self.api.patch(
            f"/api/medicoes-tecnicas/{registro.pk}/", {"valor": "13.7500"}, format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(registro.valor, Decimal("13.7500"))
        self.assertEqual(registro.data_hora, instante)
        self.assertEqual(registro.inspecao.tecnico_id, self.tecnico.pk)
        self.assertEqual(registro.instrumento_id, self.instrumento.pk)
        self.assertEqual(registro.parametros["arquivo_origem"], "captura.csv")

    def test_salvamento_sem_mudar_entradas_legadas_nao_reclassifica_medicao(self):
        dados = self.criar(self.payload())
        MedicaoTecnica.objects.filter(pk=dados["id"]).update(
            subtipo="", criticidade="CRITICO", diagnostico_sugerido="Decisão histórica do analista",
            classificacao_status="LEGADO",
        )
        with patch("apps.coletas.models.rules_tecnicas.classificar_tecnica", side_effect=AssertionError("reclassificação")):
            resposta = self.api.patch(
                f"/api/medicoes-tecnicas/{dados['id']}/", {}, format="json",
            )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro = MedicaoTecnica.objects.get(pk=dados["id"])
        self.assertEqual(registro.criticidade, "CRITICO")
        self.assertEqual(registro.diagnostico_sugerido, "Decisão histórica do analista")

    def test_portal_somente_consulta_dados_do_proprio_cliente(self):
        proprio = self.criar(self.payload())
        inspecao_alheia = Inspecao.objects.create(
            cliente=self.outro_cliente, tecnico=self.tecnico, data=date(2026, 10, 21), tipo_analise="ULTRASSOM",
        )
        alheio = self.criar(self.payload(
            inspecao=inspecao_alheia.pk, equipamento=self.outro_equipamento.pk, componente=None,
        ))
        self.api.force_authenticate(self.portal)
        lista = self.api.get("/api/medicoes-tecnicas/")
        self.assertEqual(lista.status_code, 200)
        self.assertEqual([d["id"] for d in lista.data["results"]], [proprio["id"]])
        self.assertEqual(self.api.get(f"/api/medicoes-tecnicas/{alheio['id']}/").status_code, 404)
        self.assertEqual(self.api.post("/api/medicoes-tecnicas/", self.payload(), format="json").status_code, 403)
        self.assertEqual(self.api.patch(
            f"/api/medicoes-tecnicas/{proprio['id']}/", {"valor": "8"}, format="json",
        ).status_code, 403)
        self.assertEqual(self.api.delete(f"/api/medicoes-tecnicas/{proprio['id']}/").status_code, 403)
        self.api.force_authenticate(self.portal_sem_vinculo)
        self.assertEqual(self.api.get("/api/medicoes-tecnicas/").data["results"], [])

    def test_exclusao_exige_nivel_e_autenticacao(self):
        criado = self.criar(self.payload())
        self.assertEqual(self.api.delete(f"/api/medicoes-tecnicas/{criado['id']}/").status_code, 403)
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get(f"/api/medicoes-tecnicas/{criado['id']}/").status_code, 401)
        self.assertTrue(MedicaoTecnica.objects.filter(pk=criado["id"]).exists())

    def termo(self, **extras):
        dados = {
            "inspecao": self.inspecao("TERMOGRAFIA").pk, "equipamento": self.equipamento.pk,
            "ponto_medicao": "Conexão", "sistema": "ELETRICO", "temperatura_ponto": "-10.0",
            "temperatura_referencia": "-15.0", "emissividade": "0.95",
        }
        dados.update(extras)
        return dados

    def test_quatro_sistemas_termograficos_preservam_temperaturas_e_delta(self):
        for sistema in ("ELETRICO", "MEC_DINAMICO", "MEC_ESTATICO", "PROCESSO"):
            with self.subTest(sistema=sistema):
                dados = self.criar(self.termo(sistema=sistema), "medicoes-termografia")
                registro = MedicaoTermografia.objects.get(pk=dados["id"])
                self.assertEqual(registro.sistema, sistema)
                self.assertEqual(registro.delta_t, Decimal("5.0"))
                self.assertEqual(dados["criticidade"], "")
                self.assertEqual(dados["classificacao_status"], "PENDENTE")

    def test_emissividade_e_carga_respeitam_limites_fisicos(self):
        for campo, valor in (("emissividade", "0"), ("emissividade", "-0.01"),
                             ("emissividade", "1.01"), ("carga_percentual", "-0.1")):
            with self.subTest(campo=campo, valor=valor):
                resposta = self.api.post("/api/medicoes-termografia/", self.termo(**{campo: valor}), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn(campo, resposta.data)
        for emissividade in ("0.01", "1.00"):
            with self.subTest(emissividade=emissividade):
                self.criar(self.termo(emissividade=emissividade, carga_percentual="0"), "medicoes-termografia")

    def test_geolocalizacao_valida_extremos_e_rejeita_fora_do_globo(self):
        base = {"cliente": self.cliente.pk, "tipo_analise": "ULTRASSOM", "data": "2026-10-21"}
        for latitude, longitude in (("-90", "-180"), ("90", "180")):
            with self.subTest(latitude=latitude, longitude=longitude):
                resposta = self.api.post("/api/inspecoes/", dict(base, latitude=latitude, longitude=longitude), format="json")
                self.assertEqual(resposta.status_code, 201, resposta.data)
                self.assertEqual(resposta.data["tecnico"], self.tecnico.pk)
        for campo, valor in (("latitude", "90.000001"), ("latitude", "-90.000001"),
                             ("longitude", "180.000001"), ("longitude", "-180.000001")):
            with self.subTest(campo=campo, valor=valor):
                resposta = self.api.post("/api/inspecoes/", dict(base, **{campo: valor}), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn(campo, resposta.data)

    def test_laudo_de_medicao_pendente_e_consultavel_sem_atestar_normalidade(self):
        medicao = self.criar(self.payload())
        resposta = self.api.post("/api/laudos/gerar/", {"inspecao": medicao["inspecao"]}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        laudo = Laudo.objects.get(pk=resposta.data["id"])
        self.assertEqual(laudo.criticidade_geral, "")
        self.assertNotIn("None", laudo.conclusao)
        self.assertIn("pendent", laudo.conclusao.lower())
        self.assertNotIn("Normal", laudo.conclusao)
        self.assertEqual(self.api.get(f"/api/laudos/{laudo.pk}/").status_code, 200)
        self.assertFalse(OrdemServico.objects.exists())

    def test_sensitiva_decisao_explicita_alimenta_osp_e_laudo(self):
        medicao = self.criar(self.payload(
            "SENSITIVA", "SENSITIVA", parametros={"criticidade": "CRITICO", "observacao": "Vazamento observado"},
        ))
        self.assertEqual(medicao["criticidade"], "CRITICO")
        osp = OrdemServico.objects.get(inspecao_id=medicao["inspecao"])
        self.assertEqual(osp.equipamento_id, self.equipamento.pk)
        self.assertEqual(osp.responsavel_id, self.tecnico.pk)
        self.assertIn("Vazamento observado", osp.descricao)
        resposta = self.api.post("/api/laudos/gerar/", {"inspecao": medicao["inspecao"]}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        self.assertEqual(resposta.data["criticidade_geral"], "CRITICO")

    def vibracao(self, **extras):
        dados = {
            "inspecao": self.inspecao("VIBRACAO").pk, "equipamento": self.equipamento.pk,
            "ponto_medicao": "Mancal LA", "direcao": "H", "velocidade_rms": "1.20",
            "subtipo": "MEC_DINAMICO", "parametros": {},
        }
        dados.update(extras)
        return dados

    def test_vibracao_rejeita_amplitudes_negativas(self):
        for campo in ("velocidade_rms", "aceleracao_rms", "deslocamento_pp", "fator_crista"):
            with self.subTest(campo=campo):
                resposta = self.api.post("/api/medicoes-vibracao/", self.vibracao(**{campo: "-0.01"}), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn(campo, resposta.data)

    def test_editar_metadados_vibracao_preserva_criterio_historico(self):
        dados = self.criar(self.vibracao(), "medicoes-vibracao")
        registro = MedicaoVibracao.objects.get(pk=dados["id"])
        historico = (registro.zona_iso, registro.criticidade, registro.diagnostico_sugerido, registro.criterio_aplicado)
        with patch("apps.coletas.models.rules.classificar_vibracao", side_effect=AssertionError("reclassificação")):
            resposta = self.api.patch(
                f"/api/medicoes-vibracao/{registro.pk}/", {"temperatura": "25.0"}, format="json",
            )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(
            (registro.zona_iso, registro.criticidade, registro.diagnostico_sugerido, registro.criterio_aplicado), historico,
        )

    def test_ods_e_estatica_registram_contexto_sem_aplicar_regra_dinamica(self):
        for subtipo in ("ODS", "MEC_ESTATICO"):
            with self.subTest(subtipo=subtipo):
                dados = self.criar(self.vibracao(
                    subtipo=subtipo, velocidade_rms="50", deslocamento_pp="125.50",
                    parametros={"frequencia_hz": "30.5", "fase_graus": "359.99"},
                ), "medicoes-vibracao")
                registro = MedicaoVibracao.objects.get(pk=dados["id"])
                self.assertEqual(registro.parametros, {"frequencia_hz": "30.5", "fase_graus": "359.99"})
                self.assertEqual(registro.deslocamento_pp, Decimal("125.50"))
                self.assertEqual((registro.zona_iso, registro.criticidade), ("", ""))
                self.assertEqual(registro.classificacao_status, "PENDENTE")
        self.assertFalse(OrdemServico.objects.exists())

    def test_fase_e_frequencia_rejeitam_fora_de_limites_e_tipos_invalidos(self):
        for campo, valor in (("fase_graus", "360"), ("fase_graus", "-0.01"),
                             ("frequencia_hz", "-1"), ("frequencia_hz", "NaN"),
                             ("fase_graus", "Infinity"), ("fase_graus", True), ("frequencia_hz", [])):
            with self.subTest(campo=campo, valor=valor):
                resposta = self.api.post("/api/medicoes-vibracao/", self.vibracao(
                    subtipo="ODS", parametros={campo: valor},
                ), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("parametros", resposta.data)
        self.criar(self.vibracao(subtipo="ODS", parametros={"frequencia_hz": 0, "fase_graus": 0}), "medicoes-vibracao")

    def test_alteracao_tecnica_arquiva_valores_e_classificacao_anteriores(self):
        criado = self.criar(self.payload(valor="12.25"))
        registro = MedicaoTecnica.objects.get(pk=criado["id"])
        criterio_anterior = registro.criterio_aplicado
        instante = registro.data_hora
        resposta = self.api.patch(
            f"/api/medicoes-tecnicas/{registro.pk}/", {"valor": "15.5"}, format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(len(registro.historico_classificacao), 1)
        anterior = registro.historico_classificacao[0]
        self.assertEqual(Decimal(anterior["dados"]["valor"]), Decimal("12.25"))
        self.assertEqual(anterior["criterio"], criterio_anterior)
        self.assertEqual(anterior["status"], "PENDENTE")
        self.assertTrue(anterior["registrado_em"])
        self.assertEqual(registro.data_hora, instante)
        self.assertEqual(registro.valor, Decimal("15.5"))

    def test_campos_de_classificacao_sao_somente_leitura(self):
        criado = self.criar(self.payload(
            criticidade="NORMAL", classificacao_status="CLASSIFICADA", criterio_aplicado={"fraude": True},
            historico_classificacao=[{"fraude": True}],
        ))
        registro = MedicaoTecnica.objects.get(pk=criado["id"])
        self.assertEqual(registro.criticidade, "")
        self.assertEqual(registro.classificacao_status, "PENDENTE")
        self.assertNotIn("fraude", registro.criterio_aplicado)
        self.assertEqual(registro.historico_classificacao, [])

    def test_ensaio_do_fluido_deve_ser_compativel_com_a_aplicacao(self):
        combinacoes = {
            "HIDRAULICO": ("FQ", "CR", "CP"),
            "LUBRIFICANTE": ("FQ", "CR", "CP"),
            "MINERAL_ISOLANTE": ("FQ", "CR", "PCB", "2FAL"),
        }
        for subtipo, permitidos in combinacoes.items():
            for ensaio in ("FQ", "CR", "CP", "PCB", "2FAL"):
                with self.subTest(subtipo=subtipo, ensaio=ensaio):
                    resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(
                        "FLUIDOS", subtipo, parametros={"ensaio": ensaio},
                    ), format="json")
                    self.assertEqual(resposta.status_code, 201 if ensaio in permitidos else 400, resposta.data)

    def test_espessura_e_resistencias_rejeitam_negativo_e_aceitam_zero(self):
        for tipo, subtipo in (("ESPESSURA", "ESPESSURA"), ("ENSAIO_ELETRICO", "MOTOR_RI"),
                              ("ENSAIO_ELETRICO", "TRANSFORMADOR_RI"), ("ENSAIO_ELETRICO", "TRANSFORMADOR_RO")):
            with self.subTest(tipo=tipo, subtipo=subtipo):
                resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(tipo, subtipo, valor="-0.0001"), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("valor", resposta.data)
                self.criar(self.payload(tipo, subtipo, valor="0"))

    def test_inspecao_com_medicoes_preserva_cliente_e_modalidade(self):
        criado = self.criar(self.payload())
        for mudanca in ({"tipo_analise": "ESPESSURA"}, {"cliente": self.outro_cliente.pk}):
            with self.subTest(mudanca=mudanca):
                resposta = self.api.patch(f"/api/inspecoes/{criado['inspecao']}/", mudanca, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        consulta = self.api.get(f"/api/inspecoes/{criado['inspecao']}/")
        self.assertEqual(consulta.data["qtd_medicoes"], 1)
        self.assertEqual(consulta.data["criticidade_maxima"], "")
        self.assertEqual(consulta.data["medicoes_tecnicas"][0]["subtipo"], "MECANICO")

    def test_unidades_incompativeis_sao_recusadas_por_modalidade(self):
        casos = (
            ("ULTRASSOM", "ELETRICO", "mm", {}), ("ESPESSURA", "ESPESSURA", "dB", {}),
            ("ENSAIO_ELETRICO", "MOTOR_RI", "%", {}), ("ENSAIO_ELETRICO", "TRANSFORMADOR_RO", "MΩ", {}),
            ("ENSAIO_ELETRICO", "TRANSFORMADOR_TTR", "%", {}),
            ("FLUIDOS", "MINERAL_ISOLANTE", "cSt", {"ensaio": "PCB"}),
            ("FLUIDOS", "HIDRAULICO", "ppm", {"ensaio": "CP"}),
        )
        for tipo, subtipo, unidade, parametros in casos:
            with self.subTest(tipo=tipo, subtipo=subtipo, unidade=unidade):
                resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(
                    tipo, subtipo, unidade=unidade, parametros=parametros,
                ), format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("unidade", resposta.data)

    def test_ttr_razao_e_desvio_nao_compartilham_unidade(self):
        for grandeza, unidade, valor in (("Relação TTR", "", "30"), ("Erro da relação", "%", "-0.5")):
            with self.subTest(grandeza=grandeza):
                criado = self.criar(self.payload(
                    "ENSAIO_ELETRICO", "TRANSFORMADOR_TTR", grandeza=grandeza, unidade=unidade, valor=valor,
                ))
                self.assertEqual(criado["unidade"], unidade)
                self.assertEqual(criado["classificacao_status"], "PENDENTE")
        resposta = self.api.post("/api/medicoes-tecnicas/", self.payload(
            "ENSAIO_ELETRICO", "TRANSFORMADOR_TTR", grandeza="Relação TTR", valor="-1",
        ), format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_termografia_exige_emissividade_explicita_e_preserva_em_patch(self):
        dados = self.termo()
        dados.pop("emissividade")
        resposta = self.api.post("/api/medicoes-termografia/", dados, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("emissividade", resposta.data)
        criado = self.criar(self.termo(emissividade="0.85"), "medicoes-termografia")
        resposta = self.api.patch(
            f"/api/medicoes-termografia/{criado['id']}/", {"ponto_medicao": "Conexão revisada"}, format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(MedicaoTermografia.objects.get(pk=criado["id"]).emissividade, Decimal("0.85"))

    def test_autoria_da_coleta_e_da_correcao_nao_pode_ser_falsificada(self):
        editor = get_user_model().objects.create_user(
            email="revisor@thermo.test", nome="Revisor", perfil="TECNICO",
        )
        criado = self.criar(self.payload(coletado_por=editor.pk))
        registro = MedicaoTecnica.objects.get(pk=criado["id"])
        self.assertEqual(registro.coletado_por_id, self.tecnico.pk)
        self.api.force_authenticate(editor)
        resposta = self.api.patch(
            f"/api/medicoes-tecnicas/{registro.pk}/", {"valor": "99", "coletado_por": editor.pk}, format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(registro.coletado_por_id, self.tecnico.pk)
        self.assertEqual(registro.historico_classificacao[0]["alterado_por"], editor.pk)
        self.assertEqual(registro.historico_classificacao[0]["coletado_por"], self.tecnico.pk)

    def test_historico_vibracao_exclui_medicoes_futuras_e_outras_modalidades(self):
        instante = timezone.now()
        contexto = {"instrumento": self.instrumento.pk, "rotacao_rpm": 1800}
        anterior = self.criar(self.vibracao(velocidade_rms="1", **contexto), "medicoes-vibracao")
        atual = self.criar(self.vibracao(velocidade_rms="2", **contexto), "medicoes-vibracao")
        futura = self.criar(self.vibracao(velocidade_rms="3", **contexto), "medicoes-vibracao")
        ods = self.criar(self.vibracao(subtipo="ODS", velocidade_rms="99", **contexto), "medicoes-vibracao")
        MedicaoVibracao.objects.filter(pk=anterior["id"]).update(data_hora=instante - timedelta(days=2))
        MedicaoVibracao.objects.filter(pk=atual["id"]).update(data_hora=instante - timedelta(days=1))
        MedicaoVibracao.objects.filter(pk=ods["id"]).update(data_hora=instante - timedelta(days=2))
        MedicaoVibracao.objects.filter(pk=futura["id"]).update(data_hora=instante)
        registro = MedicaoVibracao.objects.get(pk=atual["id"])
        self.assertEqual(registro._historico_vrms(), [Decimal("1")])

    def test_vibracao_sem_classe_ou_aplicabilidade_nao_adota_classe_generica(self):
        for classe in ("", "G1", "G2"):
            with self.subTest(classe=classe):
                Equipamento.objects.filter(pk=self.equipamento.pk).update(classe_iso=classe, tipo_base="")
                criado = self.criar(self.vibracao(velocidade_rms="30"), "medicoes-vibracao")
                self.assertEqual(criado["classificacao_status"], "PENDENTE")
                self.assertEqual(criado["zona_iso"], "")
                self.assertEqual(criado["criticidade"], "")

    def criterio_sintetico(self, **extras):
        dados = {
            "cliente": self.cliente, "classe": "II", "norma_codigo": "QA-Criterio", "norma_edicao": "1",
            "origem": "RESPONSAVEL_TECNICO", "fonte": "Apenas critério sintético de teste",
            "limite_ab": "1", "limite_bc": "2", "limite_cd": "3",
            "vigencia_inicio": date(2026, 1, 1), "vigencia_fim": date(2026, 10, 31),
        }
        dados.update(extras)
        return CriterioSeveridadeVibracao.objects.create(**dados)

    def test_criterio_vigente_na_data_da_inspecao_permanece_reproduzivel(self):
        criterio = self.criterio_sintetico()
        self.criterio_sintetico(
            norma_edicao="2", vigencia_inicio=date(2026, 11, 1), vigencia_fim=None,
            limite_ab="10", limite_bc="20", limite_cd="30",
        )
        criado = self.criar(self.vibracao(velocidade_rms="2.5"), "medicoes-vibracao")
        registro = MedicaoVibracao.objects.get(pk=criado["id"])
        snapshot = registro.criterio_aplicado
        self.assertEqual(registro.zona_iso, "C")
        self.assertEqual(snapshot["data_criterio"], "2026-10-21")
        self.assertEqual(snapshot["cadastro"]["id"], criterio.pk)
        self.assertEqual(snapshot["cadastro"]["fonte"], "Apenas critério sintético de teste")
        self.assertEqual(snapshot["cadastro"]["edicao"], "1")
        self.assertEqual(snapshot["cadastro"]["origem"], "RESPONSAVEL_TECNICO")
        self.assertEqual(snapshot["cadastro"]["vigencia_fim"], "2026-10-31")
        CriterioSeveridadeVibracao.objects.filter(pk=criterio.pk).update(
            limite_ab="10", limite_bc="20", limite_cd="30", fonte="Fonte revisada",
        )
        resposta = self.api.patch(
            f"/api/medicoes-vibracao/{registro.pk}/", {"temperatura": "25.0"}, format="json",
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        registro.refresh_from_db()
        self.assertEqual(registro.criterio_aplicado, snapshot)
        self.assertEqual(registro.zona_iso, "C")

    def test_fronteiras_de_zona_usam_apenas_criterio_especifico_do_teste(self):
        self.criterio_sintetico()
        for valor, zona in (("1", "A"), ("1.01", "B"), ("2", "B"), ("2.01", "C"), ("3", "C"), ("3.01", "D")):
            with self.subTest(valor=valor):
                criado = self.criar(self.vibracao(
                    velocidade_rms=valor, ponto_medicao=f"Ponto {valor}", fator_crista="99",
                ), "medicoes-vibracao")
                self.assertEqual(criado["zona_iso"], zona)
                self.assertFalse(criado["criterio_aplicado"]["fator_crista_avaliado"])
                if zona == "A":
                    self.assertEqual(criado["criticidade"], "NORMAL")

    def test_consulta_filtra_subtipo_e_status_de_classificacao(self):
        mecanico = self.criar(self.payload())
        self.criar(self.payload(subtipo="ELETRICO"))
        resposta = self.api.get("/api/medicoes-tecnicas/?subtipo=MECANICO&classificacao_status=PENDENTE")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual([d["id"] for d in resposta.data["results"]], [mecanico["id"]])
        self.assertEqual(self.api.get("/api/medicoes-tecnicas/?classificacao_status=CLASSIFICADA").data["results"], [])

    def test_sensitiva_qualitativa_sem_valor_nao_inventa_numero_no_laudo(self):
        dados = self.payload("SENSITIVA", "SENSITIVA", parametros={"criticidade": "ALERTA", "observacao": "Ruído observado"})
        dados.pop("valor")
        dados["unidade"] = ""
        criado = self.criar(dados)
        self.assertIsNone(MedicaoTecnica.objects.get(pk=criado["id"]).valor)
        laudo = self.api.post("/api/laudos/gerar/", {"inspecao": criado["inspecao"]}, format="json")
        self.assertEqual(laudo.status_code, 201, laudo.data)
        self.assertIn("Ruído observado", laudo.data["diagnostico"])
        self.assertNotIn("None", laudo.data["diagnostico"])

    def test_modalidade_quantitativa_exige_valor(self):
        for omitido in (True, False):
            with self.subTest(omitido=omitido):
                dados = self.payload(valor=None)
                if omitido:
                    dados.pop("valor")
                resposta = self.api.post("/api/medicoes-tecnicas/", dados, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertIn("valor", resposta.data)

    def test_medicao_nao_migra_para_outro_evento_de_inspecao(self):
        criado = self.criar(self.payload())
        outro_evento = self.inspecao("ULTRASSOM")
        resposta = self.api.patch(
            f"/api/medicoes-tecnicas/{criado['id']}/", {"inspecao": outro_evento.pk}, format="json",
        )
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertIn("inspecao", resposta.data)
        self.assertEqual(MedicaoTecnica.objects.get(pk=criado["id"]).inspecao_id, criado["inspecao"])

    def test_ods_e_estatica_aceitam_amplitude_real_sem_velocidade_ficticia(self):
        for subtipo, campo in (("ODS", "aceleracao_rms"), ("MEC_ESTATICO", "deslocamento_pp")):
            with self.subTest(subtipo=subtipo):
                dados = self.vibracao(subtipo=subtipo, **{campo: "0.25"})
                dados.pop("velocidade_rms")
                criado = self.criar(dados, "medicoes-vibracao")
                registro = MedicaoVibracao.objects.get(pk=criado["id"])
                self.assertIsNone(registro.velocidade_rms)
                self.assertEqual(getattr(registro, campo), Decimal("0.25"))
                self.assertEqual(registro.classificacao_status, "PENDENTE")

    def test_amplitude_ausente_nao_e_transformada_em_zero(self):
        for subtipo in ("MEC_DINAMICO", "ODS", "MEC_ESTATICO"):
            with self.subTest(subtipo=subtipo):
                dados = self.vibracao(subtipo=subtipo)
                dados.pop("velocidade_rms")
                resposta = self.api.post("/api/medicoes-vibracao/", dados, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        dados = self.vibracao(subtipo="MEC_DINAMICO", velocidade_rms=None, aceleracao_rms="1")
        resposta = self.api.post("/api/medicoes-vibracao/", dados, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)

    def test_exclusao_autorizada_de_medicao_preserva_historico_enquanto_retencao_pendente(self):
        master = get_user_model().objects.create_user(
            email="master-coleta@thermo.test", nome="Master", perfil="TECNICO", nivel="MASTER",
        )
        tecn = self.criar(self.payload())
        vib = self.criar(self.vibracao(), "medicoes-vibracao")
        termo = self.criar(self.termo(), "medicoes-termografia")
        self.api.force_authenticate(master)
        for endpoint, criado, modelo in (("medicoes-tecnicas", tecn, MedicaoTecnica),
                                         ("medicoes-vibracao", vib, MedicaoVibracao),
                                         ("medicoes-termografia", termo, MedicaoTermografia)):
            with self.subTest(endpoint=endpoint):
                resposta = self.api.delete(f"/api/{endpoint}/{criado['id']}/")
                self.assertEqual(resposta.status_code, 400, resposta.data)
                self.assertTrue(modelo.objects.filter(pk=criado["id"]).exists())
        resposta = self.api.delete(f"/api/inspecoes/{tecn['inspecao']}/")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertTrue(Inspecao.objects.filter(pk=tecn["inspecao"]).exists())

    def test_dashboard_e_portal_nao_apresentam_normalidade_com_pendencias(self):
        self.criterio_sintetico()
        self.criar(self.vibracao(velocidade_rms="0.1"), "medicoes-vibracao")
        self.criar(self.payload())
        dashboard = self.api.get("/api/dashboard/")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["medicoes_por_criticidade"]["PENDENTE"], 1)
        self.assertEqual(dashboard.data["medicoes_por_criticidade"]["NORMAL"], 1)
        self.api.force_authenticate(self.portal)
        portal = self.api.get("/api/portal/visao-geral/")
        self.assertEqual(portal.status_code, 200)
        self.assertEqual(portal.data["estado_equipamentos"][self.equipamento.tag]["criticidade"], "")
