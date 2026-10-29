"""Predição determinística: critérios sintéticos não representam normas oficiais."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Componente, CriterioSeveridadeVibracao, Equipamento, Instrumento, Setor
from apps.notificacoes.models import Notificacao
from apps.osp.models import OrdemServico

from .analise_preditiva import analisar_historico, numero_finito, replay_vibracao
from .models import Inspecao, MedicaoTecnica, MedicaoTermografia, MedicaoVibracao
from .rules import classificar_vibracao


class AnalisePreditivaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="QA Preditiva", cnpj="11.333.333/0001-33")
        cls.tecnico = get_user_model().objects.create_user(
            email="preditiva@thermo.test", nome="Analista", perfil="TECNICO", nivel="MASTER",
        )
        cls.portal = get_user_model().objects.create_user(
            email="portal-preditiva@thermo.test", nome="PCM", perfil="CLIENTE_PCM", cliente=cls.cliente,
        )
        cls.outro_cliente = Cliente.objects.create(nome="Outro QA", cnpj="22.444.444/0001-44")
        cls.outro_portal = get_user_model().objects.create_user(
            email="outro-preditiva@thermo.test", nome="Outro PCM", perfil="CLIENTE_PCM", cliente=cls.outro_cliente,
        )
        area = Area.objects.create(nome="QA", cliente=cls.cliente)
        setor = Setor.objects.create(nome="QA", area=area)
        cls.equipamento = Equipamento.objects.create(nome="Máquina QA", tag="PRED-01", setor=setor, classe_iso="II")
        cls.componente = Componente.objects.create(equipamento=cls.equipamento, nome="Ponto LA")
        cls.outro_componente = Componente.objects.create(equipamento=cls.equipamento, nome="Ponto LOA")
        cls.instrumento = Instrumento.objects.create(tipo="Coletor", modelo="QA", numero_serie="PRED-01")
        cls.outro_instrumento = Instrumento.objects.create(tipo="Coletor", modelo="QA", numero_serie="PRED-02")
        cls.inspecao = Inspecao.objects.create(cliente=cls.cliente, tecnico=cls.tecnico, data=date(2026, 10, 20))
        cls.criterio = CriterioSeveridadeVibracao.objects.create(
            cliente=cls.cliente, classe="II", norma_codigo="QA SEM VALOR NORMATIVO", norma_edicao="1",
            origem="RESPONSAVEL_TECNICO", fonte="Critério sintético de teste",
            limite_ab=10, limite_bc=20, limite_cd=30,
            vigencia_inicio=date(2026, 1, 1), vigencia_fim=date(2026, 12, 31),
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)
        self.instante = timezone.make_aware(timezone.datetime(2026, 10, 20, 12))

    def vibracao(self, valor=1, dias=0, **extras):
        dados = dict(inspecao=self.inspecao, equipamento=self.equipamento,
                     componente=self.componente, instrumento=self.instrumento,
                     ponto_medicao="LA", direcao="H", velocidade_rms=valor,
                     rotacao_rpm=1800, data_hora=self.instante + timedelta(days=dias))
        dados.update(extras)
        return MedicaoVibracao.objects.create(**dados)

    def habilitar(self, **extras):
        valores = dict(evolucao_habilitada=True, evolucao_validacao="VALIDADO",
                       evolucao_fonte="Homologação sintética QA", evolucao_fator=Decimal("2"), evolucao_janela=3)
        valores.update(extras)
        CriterioSeveridadeVibracao.objects.filter(pk=self.criterio.pk).update(**valores)

    def historico(self, valores=(1, 2, 3)):
        return [self.vibracao(v, dias=-len(valores) + i) for i, v in enumerate(valores)]

    def test_media_delta_e_inclinacao_usam_tempo_real_em_ordem_cronologica(self):
        # Inserção fora de ordem; 1, 3, 5, 7 em dias sucessivos é inclinação 2/dia.
        terceiro = self.vibracao(5, dias=-1)
        primeiro = self.vibracao(1, dias=-3)
        segundo = self.vibracao(3, dias=-2)
        atual = self.vibracao(7)
        analise = atual.criterio_aplicado["analise_preditiva"]
        self.assertEqual([p["id"] for p in analise["entradas"]], [primeiro.pk, segundo.pk, terceiro.pk])
        self.assertEqual(analise["status"], "COMPARAVEL")
        self.assertEqual(Decimal(analise["estatisticas"]["media_historica"]), 3)
        self.assertEqual(Decimal(analise["estatisticas"]["diferenca_anterior"]), 2)
        self.assertEqual(Decimal(analise["estatisticas"]["inclinacao_por_dia"]), 2)
        self.assertFalse(analise["diagnostico"])

    def test_apenas_janela_das_mais_recentes_anteriores_e_incluida(self):
        antigas = self.historico((1, 2, 3, 4, 5))
        atual = self.vibracao(6)
        ids = [p["id"] for p in atual.criterio_aplicado["analise_preditiva"]["entradas"]]
        self.assertEqual(ids, [m.pk for m in antigas[-3:]])

    def test_exclui_medicao_futura_e_mesmo_instante(self):
        anterior = self.vibracao(1, dias=-1)
        self.vibracao(999, dias=1)
        self.vibracao(888)
        atual = self.vibracao(2)
        self.assertEqual([p["id"] for p in atual.criterio_aplicado["analise_preditiva"]["entradas"]], [anterior.pk])

    def test_exclui_campanha_posterior_mesmo_com_timestamp_antigo(self):
        campanha = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=date(2026, 10, 21))
        self.vibracao(999, dias=-1, inspecao=campanha)
        self.assertEqual(self.vibracao(2).criterio_aplicado["analise_preditiva"]["entradas"], [])

    def test_contextos_distintos_nao_sao_misturados(self):
        distintos = [dict(instrumento=self.outro_instrumento), dict(componente=self.outro_componente),
                     dict(ponto_medicao="LOA"), dict(direcao="V"), dict(rotacao_rpm=1200),
                     dict(subtipo="ODS"), dict(parametro="A"), dict(numero_mancal=2),
                     dict(parametros={"carga": "parcial"})]
        for diferenca in distintos:
            self.vibracao(99, dias=-1, **diferenca)
        anterior = self.vibracao(1, dias=-2)
        atual = self.vibracao(2)
        self.assertEqual([p["id"] for p in atual.criterio_aplicado["analise_preditiva"]["entradas"]], [anterior.pk])

    def test_sem_historico_e_sem_instrumento_sao_inconclusivos(self):
        atual = self.vibracao(1)
        self.assertEqual(atual.criterio_aplicado["analise_preditiva"]["motivo"], "sem_historico_comparavel")
        sem_instrumento = self.vibracao(2, instrumento=None)
        analise = sem_instrumento.criterio_aplicado["analise_preditiva"]
        self.assertEqual(analise["status"], "INCONCLUSIVA")
        self.assertEqual(analise["motivo"], "instrumento_ou_contexto_operacional_ausente")

    def test_sem_contexto_operacional_nao_presume_comparabilidade(self):
        self.vibracao(1, dias=-1, rotacao_rpm=None)
        atual = self.vibracao(2, rotacao_rpm=None)
        self.assertEqual(atual.criterio_aplicado["analise_preditiva"]["status"], "INCONCLUSIVA")

    def test_media_zero_nao_gera_percentual_ou_elevacao(self):
        self.habilitar()
        self.historico((0, 0, 0))
        atual = self.vibracao(1)
        analise = atual.criterio_aplicado["analise_preditiva"]
        self.assertIsNone(analise["estatisticas"]["variacao_percentual_media"])
        self.assertEqual(atual.criticidade, "NORMAL")

    def test_evolucao_desabilitada_por_padrao_preserva_zona_mesmo_com_crescimento(self):
        self.historico((1, 1, 1))
        atual = self.vibracao(9)
        self.assertEqual(atual.criticidade, "NORMAL")
        self.assertFalse(atual.criterio_aplicado["evolucao_aplicavel"])

    def test_evolucao_usa_fronteira_estrita_e_janela_completa(self):
        self.habilitar()
        self.historico((1, 1, 1))
        igualdade = self.vibracao(2)
        acima = self.vibracao(Decimal("2.01"))
        self.assertEqual(igualdade.criticidade, "NORMAL")
        self.assertEqual(acima.criticidade, "ALERTA")
        self.assertTrue(acima.criterio_aplicado["evolucao_aplicavel"])

    def test_janela_incompleta_nao_eleva_criticidade(self):
        self.habilitar()
        self.historico((1, 1))
        atual = self.vibracao(9)
        self.assertFalse(atual.criterio_aplicado["evolucao_aplicavel"])
        self.assertEqual(atual.criticidade, "NORMAL")

    def test_configuracao_pendente_ou_sem_fonte_nao_eleva_mesmo_por_orm(self):
        self.historico((1, 1, 1))
        for valores in [dict(evolucao_validacao="PENDENTE"), dict(evolucao_fonte=" ")]:
            with self.subTest(valores=valores):
                self.habilitar(**valores)
                atual = self.vibracao(9)
                self.assertEqual(atual.criticidade, "NORMAL")
                self.assertFalse(atual.criterio_aplicado["evolucao_aplicavel"])

    def test_validacao_cadastro_exige_homologacao_e_fonte(self):
        self.criterio.evolucao_habilitada = True
        with self.assertRaises(ValidationError):
            self.criterio.full_clean()
        self.criterio.evolucao_validacao = "VALIDADO"
        with self.assertRaises(ValidationError):
            self.criterio.full_clean()
        self.criterio.evolucao_fonte = "Aprovação QA sintética"
        self.criterio.full_clean()

    def test_replay_independe_de_edicao_de_criterio_e_historico_posterior(self):
        self.habilitar()
        self.historico((1, 1, 1))
        atual = self.vibracao(9)
        snapshot = deepcopy(atual.criterio_aplicado)
        esperado = {k: snapshot["saida"][k] for k in ("zona_iso", "criticidade", "diagnostico_sugerido")}
        self.assertEqual(replay_vibracao(snapshot), esperado)
        CriterioSeveridadeVibracao.objects.filter(pk=self.criterio.pk).update(limite_ab=100, limite_bc=200, limite_cd=300)
        self.vibracao(999, dias=1)
        self.assertEqual(replay_vibracao(snapshot), esperado)
        atual.refresh_from_db()
        self.assertEqual(atual.criterio_aplicado, snapshot)

    def test_replay_legado_indisponivel_sem_inventar_entradas(self):
        with self.assertRaises(ValueError):
            replay_vibracao({"motor": "vibracao_v1"})

    def test_get_nao_grava_nem_gera_notificacoes_ou_osp(self):
        atual = self.vibracao(31)
        snapshot = deepcopy(atual.criterio_aplicado)
        contagens = (Notificacao.objects.count(), OrdemServico.objects.count())
        for _ in range(3):
            resposta = self.api.get(f"/api/medicoes-vibracao/{atual.pk}/analise-preditiva/")
            self.assertEqual(resposta.status_code, 200, resposta.data)
            self.assertEqual(resposta.data["snapshot"], snapshot)
            self.assertTrue(resposta.data["replay_disponivel"])
        atual.refresh_from_db()
        self.assertEqual(atual.criterio_aplicado, snapshot)
        self.assertEqual((Notificacao.objects.count(), OrdemServico.objects.count()), contagens)

    def test_consulta_respeita_permissao_e_escopo_do_cliente(self):
        atual = self.vibracao(1)
        url = f"/api/medicoes-vibracao/{atual.pk}/analise-preditiva/"
        self.api.force_authenticate(self.portal)
        self.assertEqual(self.api.get(url).status_code, 200)
        self.api.force_authenticate(self.outro_portal)
        self.assertEqual(self.api.get(url).status_code, 404)
        self.api.force_authenticate(user=None)
        self.assertIn(self.api.get(url).status_code, (401, 403))

    def test_edicao_instrumento_arquiva_base_anterior_e_interrompe_serie(self):
        self.historico()
        atual = self.vibracao(4)
        snapshot = deepcopy(atual.criterio_aplicado)
        atual.instrumento = self.outro_instrumento
        atual.save()
        self.assertEqual(atual.historico_classificacao[-1]["criterio"], snapshot)
        self.assertEqual(atual.criterio_aplicado["analise_preditiva"]["status"], "INCONCLUSIVA")

    def test_termografia_compara_delta_sem_concluir_severidade(self):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=self.inspecao.data,
                                           tipo_analise="TERMOGRAFIA")
        comum = dict(inspecao=inspecao, equipamento=self.equipamento, instrumento=self.instrumento,
                     ponto_medicao="Painel", sistema="ELETRICO", temperatura_referencia=20,
                     temperatura_ambiente=25, carga_percentual=80, emissividade=Decimal("0.90"))
        anterior = MedicaoTermografia.objects.create(**comum, temperatura_ponto=25, data_hora=self.instante-timedelta(days=1))
        atual = MedicaoTermografia.objects.create(**comum, temperatura_ponto=35, data_hora=self.instante)
        analise = atual.criterio_aplicado["analise_preditiva"]
        self.assertEqual([p["id"] for p in analise["entradas"]], [anterior.pk])
        self.assertEqual(Decimal(analise["estatisticas"]["diferenca_anterior"]), 10)
        self.assertEqual(atual.criticidade, "")
        self.assertEqual(atual.classificacao_status, "PENDENTE")

    def test_tecnica_com_contexto_compara_sem_limite_universal(self):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=self.inspecao.data,
                                           tipo_analise="ESPESSURA")
        comum = dict(inspecao=inspecao, equipamento=self.equipamento, instrumento=self.instrumento,
                     ponto_medicao="Tubo A", tipo="ESPESSURA", subtipo="ESPESSURA", grandeza="Espessura",
                     unidade="mm", parametros={"material": "QA", "malha": "A1", "contexto_operacional": "regime QA estável"})
        anterior = MedicaoTecnica.objects.create(**comum, valor=10, data_hora=self.instante-timedelta(days=1))
        atual = MedicaoTecnica.objects.create(**comum, valor=9, data_hora=self.instante)
        analise = atual.criterio_aplicado["analise_preditiva"]
        self.assertEqual([p["id"] for p in analise["entradas"]], [anterior.pk])
        self.assertEqual(Decimal(analise["estatisticas"]["diferenca_anterior"]), -1)
        self.assertEqual(atual.criticidade, "")

    def test_nan_infinito_ausente_booleano_e_texto_invalidos_nao_viram_zero(self):
        for valor in ("NaN", "Infinity", "-Infinity", None, True, "abc"):
            with self.subTest(valor=valor):
                self.assertIsNone(numero_finito(valor))
        atual = self.vibracao(1)
        for valor in (None, "NaN", -1):
            with self.subTest(valor=valor):
                atual.velocidade_rms = valor
                analise = analisar_historico(atual)
                self.assertEqual(analise["status"], "INCONCLUSIVA")
                self.assertEqual(analise["motivo"], "leitura_ausente_ou_invalida")

    def test_sensitiva_sem_numero_nao_ganha_tendencia_artificial(self):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=self.inspecao.data,
                                           tipo_analise="SENSITIVA")
        atual = MedicaoTecnica.objects.create(inspecao=inspecao, equipamento=self.equipamento,
            instrumento=self.instrumento, ponto_medicao="Carcaça", tipo="SENSITIVA", subtipo="SENSITIVA",
            grandeza="Parecer", valor=None, unidade="", parametros={"criticidade": "ALERTA", "observacao": "Ruído observado"})
        self.assertEqual(atual.criticidade, "ALERTA")
        self.assertEqual(atual.criterio_aplicado["analise_preditiva"]["status"], "INCONCLUSIVA")

    def test_classificador_recusa_valores_e_faixas_invalidas(self):
        faixas = {"A": Decimal(10), "B": Decimal(20), "C": Decimal(30)}
        for valor in (None, "NaN", "Infinity", -1, True):
            with self.subTest(valor=valor):
                resultado = classificar_vibracao("II", valor, faixas=faixas)
                self.assertEqual((resultado.zona_iso, resultado.criticidade), ("", ""))
        for alteracao in ({"B": Decimal(5)}, {"A": Decimal(-1)}, {"C": "Infinity"}, {"B": None}):
            with self.subTest(alteracao=alteracao):
                resultado = classificar_vibracao("II", 1, faixas={**faixas, **alteracao})
                self.assertEqual((resultado.zona_iso, resultado.criticidade), ("", ""))

    def test_evolucao_tem_teto_critico_sem_modificar_zona(self):
        self.habilitar()
        self.historico((1, 1, 1))
        atual = self.vibracao(31)
        self.assertEqual(atual.zona_iso, "D")
        self.assertEqual(atual.criticidade, "CRITICO")
        self.assertEqual(replay_vibracao(atual.criterio_aplicado)["criticidade"], "CRITICO")

    def test_contexto_tecnico_sem_regime_nao_e_declarado_comparavel(self):
        inspecao = Inspecao.objects.create(cliente=self.cliente, tecnico=self.tecnico, data=self.inspecao.data,
                                           tipo_analise="ULTRASSOM")
        comum = dict(inspecao=inspecao, equipamento=self.equipamento, instrumento=self.instrumento,
                     ponto_medicao="Mancal", tipo="ULTRASSOM", subtipo="MECANICO", grandeza="Nível",
                     unidade="dB", parametros={"frequencia_khz": 40})
        MedicaoTecnica.objects.create(**comum, valor=1, data_hora=self.instante-timedelta(days=1))
        atual = MedicaoTecnica.objects.create(**comum, valor=2, data_hora=self.instante)
        self.assertEqual(atual.criterio_aplicado["analise_preditiva"]["status"], "INCONCLUSIVA")

    def test_instante_do_snapshot_e_o_mesmo_instante_persistido(self):
        atual = self.vibracao(1)
        atual.refresh_from_db()
        self.assertEqual(timezone.datetime.fromisoformat(atual.criterio_aplicado["analise_preditiva"]["instante"]), atual.data_hora)
        instante_padrao = MedicaoVibracao.objects.create(
            inspecao=self.inspecao, equipamento=self.equipamento, instrumento=self.instrumento,
            ponto_medicao="Ponto automático", direcao="H", velocidade_rms=1, rotacao_rpm=1800,
        )
        instante_padrao.refresh_from_db()
        self.assertEqual(timezone.datetime.fromisoformat(instante_padrao.criterio_aplicado["analise_preditiva"]["instante"]), instante_padrao.data_hora)

    def test_metadado_nao_usado_na_regra_nao_reclassifica(self):
        atual = self.vibracao(1)
        snapshot = deepcopy(atual.criterio_aplicado)
        atual.temperatura = Decimal("30")
        atual.save(update_fields=["temperatura"])
        atual.refresh_from_db()
        self.assertEqual(atual.criterio_aplicado, snapshot)
        self.assertEqual(atual.historico_classificacao, [])
