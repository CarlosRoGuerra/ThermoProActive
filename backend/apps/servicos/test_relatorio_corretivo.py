"""
Relatório de manutenção corretiva — payload do dossiê e do endpoint do serviço.

Foco dos testes: os números que saem no documento são os que estão no banco. O caso
crítico é o ângulo — o Trial Run é o ensaio, o Trim Run é a correção que ficou na
máquina. Um relatório que mostrasse o ângulo do Trial diria ao cliente que a massa
está num lugar onde ela não está.
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.coletas.models import Achado
from apps.osp.models import OrdemServico

from . import test_analise_balanceamento as base
from .models import BalanceamentoPonto, ServicoCampo


class RelatorioCorretivoTest(base.AnaliseBalanceamentoTest):
    """Reaproveita a atividade/rota/catálogos já montados para a análise técnica."""

    # Os testes herdados já rodam na classe de origem — aqui interessam só os novos.
    for _nome in [n for n in vars(base.AnaliseBalanceamentoTest) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def montar_servico(self, *, trim_fase="210", trial_fase="0", com_economia=True):
        """Serviço completo: análise salva, plano, ponto de foco e as três corridas."""
        self.salvar()
        plano = self.api.post("/api/balanceamento-planos/", {
            "servico": self.servico_id, "numero": 1, "descricao": "Lado acoplamento",
            "massa_teste_g": "30", "angulo_teste": trial_fase,
            "massa_final_g": "100", "angulo_final": "210",
        }, format="json")
        self.assertEqual(plano.status_code, 201, plano.data)
        ponto = self.api.post("/api/balanceamento-pontos/", {
            "servico": self.servico_id, "plano": plano.data["id"],
            "numero_mancal": 2, "direcao": "H", "reference_mms": "12.31",
        }, format="json")
        self.assertEqual(ponto.status_code, 201, ponto.data)
        foco = self.api.patch(
            f"/api/servicos/{self.servico_id}/", {"ponto_foco": ponto.data["id"]}, format="json"
        )
        self.assertEqual(foco.status_code, 200, foco.data)
        corridas = {"trial_mms": "23.95", "trial_fase": trial_fase, "trim_mms": "1.70"}
        if trim_fase is not None:
            corridas["trim_fase"] = trim_fase
        resposta = self.api.patch(
            f'/api/balanceamento-pontos/{ponto.data["id"]}/', corridas, format="json"
        )
        self.assertEqual(resposta.status_code, 200, resposta.data)
        if com_economia:
            economia = self.api.post("/api/economias/", {
                "servico": self.servico_id, "tensao_v": "440", "corrente_antes_a": "120",
                "corrente_apos_a": "110", "fator_potencia": "0.850", "horas_dia": "24",
                "dias_ano": 365, "custo_kwh": "0.6500", "investimento": "3500.00",
            }, format="json")
            self.assertEqual(economia.status_code, 201, economia.data)
        return plano.data, ponto.data

    def dossie(self):
        relatorio_id = ServicoCampo.objects.get(pk=self.servico_id).relatorio_id
        resposta = self.api.get(f"/api/relatorios-inspecao/{relatorio_id}/dossie/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        return resposta.data

    def folha(self):
        """A folha da Seção D desta análise técnica."""
        achado = Achado.objects.get(pk=ServicoCampo.objects.get(pk=self.servico_id).analise_tecnica_id)
        folhas = [f for f in self.dossie()["secao_d"] if f["tag"] == achado.item.equipamento.tag]
        self.assertEqual(len(folhas), 1)
        return folhas[0]

    def test_dossie_traz_o_balanceamento_completo_numa_unica_carga(self):
        self.montar_servico()
        folha = self.folha()
        self.assertEqual(folha["tipo_corretiva"], "BALANCEAMENTO")
        c = folha["corretiva"]
        self.assertEqual(c["servico_id"], self.servico_id)
        self.assertEqual(c["tipo"], "BALANCEAMENTO")
        self.assertEqual(c["rotacao_hz"], 29.74)
        self.assertEqual(c["rotacao_rpm"], 1784)
        self.assertEqual(c["classe_iso"], "II")

        plano = c["planos"][0]
        self.assertEqual(plano["numero"], 1)
        self.assertEqual(plano["massa_final_g"], 100.0)
        self.assertEqual(plano["angulo_final"], 210.0)

        ponto = c["pontos"][0]
        self.assertEqual(ponto["codigo_ponto"], "2H")
        self.assertEqual(ponto["plano"], plano["id"])
        self.assertEqual(ponto["reference"]["mms"], 12.31)
        self.assertEqual(ponto["trial"]["mms"], 23.95)
        self.assertEqual(ponto["trim"]["mms"], 1.70)
        self.assertTrue(ponto["completo"])
        self.assertAlmostEqual(ponto["reducao_pct"], 86.2, delta=0.1)
        self.assertEqual(ponto["zona_iso"], "B")
        self.assertEqual(ponto["criticidade"], "NORMAL")
        self.assertTrue(ponto["diagnostico"])

        self.assertEqual(c["resultado"]["pontos_completos"], 1)
        self.assertAlmostEqual(c["resultado"]["reducao_media_pct"], 86.2, delta=0.1)
        self.assertEqual(c["resultado"]["criticidade_final"], "NORMAL")

        economia = c["economia"]
        self.assertEqual(economia["corrente_antes_a"], "120.00")
        self.assertEqual(economia["corrente_apos_a"], "110.00")
        self.assertEqual(economia["reducao_corrente_a"], "10.00")
        for campo in (
            "reducao_kw", "economia_kwh_ano", "economia_rs_ano",
            "payback_meses", "payback_dias", "retorno_ano", "investimento",
        ):
            self.assertIsNotNone(economia[campo], campo)
        self.assertTrue(economia["premissas"])

        # A folha também traz o número da OSP gerada pela análise técnica.
        osp = OrdemServico.objects.get()
        self.assertEqual(folha["osp"], f"{osp.sequencial_cliente}/{osp.sequencial_global}")

    def test_resultado_final_usa_o_angulo_do_trim_e_nunca_o_do_trial(self):
        # Caso relatado pelo cliente: Trial a 0°, Trim a 210°. O documento final
        # precisa dizer 210° — o 0° é o ensaio, não a correção que ficou na máquina.
        self.montar_servico(trial_fase="0", trim_fase="210")
        c = self.folha()["corretiva"]
        ponto = c["pontos"][0]
        self.assertEqual(ponto["trial"]["fase"], 0.0)
        self.assertEqual(ponto["trim"]["fase"], 210.0)
        self.assertEqual(c["planos"][0]["angulo_final"], 210.0)
        self.assertEqual(c["planos"][0]["angulo_teste"], 0.0)
        # O mostrador desenhado no relatório é o do Trim, no ângulo do Trim.
        self.assertEqual(ponto["mostrador"]["trim"]["fase"], 210.0)
        self.assertEqual(ponto["mostrador"]["trial"]["fase"], 0.0)
        self.assertNotEqual(ponto["mostrador"]["trim"], ponto["mostrador"]["trial"])

    def test_trim_sem_fase_nao_herda_a_fase_do_trial(self):
        self.montar_servico(trial_fase="133", trim_fase=None)
        ponto = self.folha()["corretiva"]["pontos"][0]
        # O trim existe (amplitude medida) e vale como resultado; a fase é ausente.
        self.assertEqual(ponto["trim"]["mms"], 1.70)
        self.assertIsNone(ponto["trim"]["fase"])
        self.assertEqual(ponto["trial"]["fase"], 133.0)
        # Sem fase não há agulha: o mostrador fica vazio em vez de apontar o Trial.
        self.assertIsNone(ponto["mostrador"]["trim"])
        self.assertIsNotNone(ponto["mostrador"]["trial"])

    def test_servico_sem_trim_nao_declara_resultado(self):
        self.salvar()
        BalanceamentoPonto.objects.create(
            servico_id=self.servico_id, numero_mancal=2, direcao="H", reference_mms="12.31",
        )
        c = self.folha()["corretiva"]
        ponto = c["pontos"][0]
        self.assertIsNone(ponto["trim"])
        self.assertIsNone(ponto["reducao_pct"])
        self.assertEqual(ponto["zona_iso"], "")
        self.assertEqual(c["resultado"]["pontos_completos"], 0)
        # Nenhum ponto medido não vira veredito "NORMAL" por omissão.
        self.assertIsNone(c["resultado"]["criticidade_final"])
        self.assertIsNone(c["resultado"]["reducao_media_pct"])

    def test_economia_ausente_sai_nula_em_vez_de_zerada(self):
        self.montar_servico(com_economia=False)
        self.assertIsNone(self.folha()["corretiva"]["economia"])

    def test_endpoint_do_servico_e_o_dossie_usam_a_mesma_montagem(self):
        self.montar_servico()
        do_servico = self.api.get(f"/api/servicos/{self.servico_id}/relatorio/")
        self.assertEqual(do_servico.status_code, 200, do_servico.data)
        c = self.folha()["corretiva"]
        self.assertEqual(do_servico.data["pontos"], c["pontos"])
        self.assertEqual(do_servico.data["planos"], c["planos"])
        self.assertEqual(do_servico.data["economia"], c["economia"])
        # O contrato anterior do endpoint continua valendo.
        for chave in ("servico", "mostrador", "pontos", "economia"):
            self.assertIn(chave, do_servico.data)

    def test_dossie_carrega_os_servicos_de_uma_vez(self):
        """Mais folhas corretivas não podem significar uma consulta por folha."""
        def consultas_do_dossie():
            relatorio_id = ServicoCampo.objects.get(pk=self.servico_id).relatorio_id
            with CaptureQueriesContext(connection) as ctx:
                resposta = self.api.get(f"/api/relatorios-inspecao/{relatorio_id}/dossie/")
            self.assertEqual(resposta.status_code, 200, resposta.data)
            return len(ctx.captured_queries), resposta.data

        self.montar_servico()
        uma_folha, _ = consultas_do_dossie()
        for item in self.atividade["itens"][1:4]:
            url = f'/api/atividades-corretivas/{self.atividade["id"]}/itens/{item["id"]}'
            self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json")
            self.api.post(url + "/analise/", {}, format="json")
            resposta = self.api.patch(url + "/balanceamento/", {"tecnica": self.tecnica}, format="json")
            self.assertEqual(resposta.status_code, 200, resposta.data)
        quatro_folhas, dados = consultas_do_dossie()
        self.assertEqual(len([f for f in dados["secao_d"] if f["corretiva"]]), 4)
        self.assertEqual(quatro_folhas, uma_folha)


class RelatorioPreditivoTest(base.AnaliseBalanceamentoTest):
    """Regressão: nada do balanceamento pode contaminar o relatório preditivo."""

    for _nome in [n for n in vars(base.AnaliseBalanceamentoTest) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def test_folha_preditiva_segue_sem_bloco_corretivo(self):
        from apps.coletas.models import Carregamento, ItemInspecao, Relatorio, TipoImagem
        from apps.coletas.models import AchadoImagem

        relatorio = Relatorio.objects.create(
            cliente=self.cliente, tecnologia=self.vibracao,
            numero="RT-VIB-2020-05-20-00001", data_inicio="2020-05-20", data_termino="2020-05-20",
        )
        carregamento = Carregamento.objects.create(
            cliente=self.cliente, tecnologia=self.vibracao, relatorio=relatorio,
            analista=self.analista, instrumento=self.instrumento, data_coleta="2020-05-20",
        )
        item = ItemInspecao.objects.create(
            carregamento=carregamento, equipamento=self.equipamentos[0], condicao=self.condicao,
        )
        achado = Achado.objects.create(
            item=item, condicao=self.condicao, tipo_componente=self.componente_outro,
            componente_texto="Mancal 2", tipo_anomalia=self.anomalia_outra,
            anomalia_texto="Desalinhamento", recomendacao_texto="Alinhar",
            aceleracao_global="3.200", velocidade_global="7.450",
        )
        for tipo in (TipoImagem.REAL, TipoImagem.TENDENCIA, TipoImagem.ESPECTRO):
            AchadoImagem.objects.create(achado=achado, tipo=tipo, arquivo=f"achados/{tipo}.png")

        resposta = self.api.get(f"/api/relatorios-inspecao/{relatorio.pk}/dossie/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        folha = resposta.data["secao_d"][0]
        # Layout preditivo: sem tipo_corretiva e sem bloco técnico da corretiva.
        self.assertEqual(folha["tipo_corretiva"], "")
        self.assertIsNone(folha["corretiva"])
        # E tudo que a preditiva já mostrava continua no payload.
        self.assertEqual(str(folha["amplitude_aceleracao"]), "3.200")
        self.assertEqual(str(folha["amplitude_velocidade"]), "7.450")
        self.assertIn("avaliacao", folha)
        self.assertEqual(
            {img["tipo"] for img in folha["imagens"]},
            {"Foto real", "Linha de tendência", "Espectro"},
        )
