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
from .models import BalanceamentoPonto, EconomiaEnergetica, ServicoCampo, TipoServico


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

    def test_trim_fase_e_angulo_final_sao_grandezas_independentes(self):
        # `trim_fase` é o ângulo do vetor de vibração medido no Trim Run; `angulo_final`
        # é onde a massa de correção foi fixada no plano — origens e instrumentos
        # diferentes. O sistema nunca substitui um pelo outro nem os força a coincidir.
        self.montar_servico(trial_fase="0", trim_fase="185")  # angulo_final fica 210 (fixo em montar_servico)
        c = self.folha()["corretiva"]
        ponto = c["pontos"][0]
        self.assertEqual(ponto["trim"]["fase"], 185.0)
        self.assertEqual(c["planos"][0]["angulo_final"], 210.0)
        self.assertNotEqual(ponto["trim"]["fase"], c["planos"][0]["angulo_final"])

    def test_velocidade_referencia_vem_do_reference_do_ponto_de_foco(self):
        self.montar_servico()
        c = self.folha()["corretiva"]
        # Reference=12.31, Trial=23.95, Trim=1.70 — a velocidade inicial é o Reference,
        # nunca o Trial (ensaio) nem o Trim (resultado).
        self.assertEqual(c["velocidade_referencia"], 12.31)
        self.assertNotEqual(c["velocidade_referencia"], 23.95)
        self.assertNotEqual(c["velocidade_referencia"], 1.70)

    def test_velocidade_referencia_sem_foco_usa_primeiro_ponto_na_ordenacao_tecnica(self):
        self.salvar()
        BalanceamentoPonto.objects.create(
            servico_id=self.servico_id, numero_mancal=1, direcao="H", reference_mms="8.50",
        )
        c = self.folha()["corretiva"]
        self.assertIsNone(c["ponto_foco"])
        self.assertEqual(c["velocidade_referencia"], 8.5)

    def test_velocidade_referencia_sem_pontos_e_nula(self):
        self.salvar()
        c = self.folha()["corretiva"]
        self.assertEqual(c["pontos"], [])
        self.assertIsNone(c["velocidade_referencia"])

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

    def _osp_de_origem(self):
        """
        OSP de origem: nasce de uma análise PREDITIVA anterior (outro relatório),
        com sequencial real de cliente e global — é assim que `gerar_de_achado`
        sempre numera, ao contrário de uma OSP criada à mão sem essa chamada.
        Anexa a OSP a `self.servico_id` ANTES de salvar a análise técnica, como
        na execução de uma OSP preditiva já aberta.
        """
        from apps.coletas.models import Carregamento, ItemInspecao, Relatorio

        relatorio_pred = Relatorio.objects.create(
            cliente=self.cliente, tecnologia=self.vibracao,
            numero="RT-VIB-2020-01-10-00001", data_inicio="2020-01-10", data_termino="2020-01-10",
        )
        carregamento_pred = Carregamento.objects.create(
            cliente=self.cliente, tecnologia=self.vibracao, relatorio=relatorio_pred,
            analista=self.analista, instrumento=self.instrumento, data_coleta="2020-01-10",
        )
        item_pred = ItemInspecao.objects.create(
            carregamento=carregamento_pred, equipamento=self.equipamentos[0], condicao=self.condicao,
        )
        achado_pred = Achado.objects.create(
            item=item_pred, condicao=self.condicao, tipo_componente=self.componente_outro,
            componente_texto="Mancal 2", tipo_anomalia=self.anomalia_outra, anomalia_texto="Desbalanceamento",
        )
        origem = OrdemServico.gerar_de_achado(achado_pred)
        self.assertIsNotNone(origem.sequencial_cliente)
        ServicoCampo.objects.filter(pk=self.servico_id).update(osp=origem)
        return origem, achado_pred

    def test_osp_de_origem_aparece_na_folha_mesmo_sem_vinculo_direto_ao_achado(self):
        origem, achado_pred = self._osp_de_origem()
        self.assertEqual(self.salvar().status_code, 200)

        # Continua existindo só a OSP de origem — nenhuma segunda foi criada.
        self.assertEqual(OrdemServico.objects.count(), 1)
        servico = ServicoCampo.objects.get(pk=self.servico_id)
        self.assertEqual(servico.osp_id, origem.pk)
        # A OSP de origem não é "sequestrada": seu vínculo direto continua com a
        # análise ORIGINAL, não com a nova análise técnica desta intervenção.
        self.assertEqual(OrdemServico.objects.get(pk=origem.pk).achado_id, achado_pred.pk)

        # Mas a folha desta intervenção mostra o número da OSP de origem — não "—".
        folha = self.folha()
        self.assertEqual(folha["osp"], f"{origem.sequencial_cliente}/{origem.sequencial_global}")
        self.assertNotEqual(folha["osp"], "—")

    def test_osp_de_origem_tambem_aparece_na_analise_final_sem_copiar_o_numero(self):
        # A mesma regra (osp_da_intervencao) serve a tela de Análise final: o campo
        # somente leitura da API resolve a OSP de origem sem gravar nada no achado.
        origem, _ = self._osp_de_origem()
        self.assertEqual(self.salvar().status_code, 200)
        achado_id = ServicoCampo.objects.get(pk=self.servico_id).analise_tecnica_id

        resposta = self.api.get(f"/api/achados/{achado_id}/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(
            resposta.data["osp_intervencao_numero"],
            f"{origem.sequencial_cliente}/{origem.sequencial_global}",
        )
        # `numero_osp` (campo do modelo) continua vazio — não foi copiado
        # artificialmente só para a tela funcionar.
        self.assertEqual(resposta.data["numero_osp"], "")

    def test_osp_intervencao_numero_reflete_a_osp_gerada_normalmente(self):
        # Sem origem: a OSP nasceu desta própria análise — osp_intervencao_numero
        # bate com o vínculo direto (mesmo valor que numero_osp já mostrava).
        self.assertEqual(self.salvar().status_code, 200)
        achado_id = ServicoCampo.objects.get(pk=self.servico_id).analise_tecnica_id
        osp = OrdemServico.objects.get()
        resposta = self.api.get(f"/api/achados/{achado_id}/")
        esperado = f"{osp.sequencial_cliente}/{osp.sequencial_global}"
        self.assertEqual(resposta.data["osp_intervencao_numero"], esperado)
        self.assertEqual(resposta.data["numero_osp"], esperado)

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


class RelatorioAlinhamentoTest(base.AnaliseBalanceamentoTest):
    """
    Alinhamento a laser: reconhecido como manutenção corretiva desde já, mesmo sem
    layout técnico próprio definido — nunca cai de volta no layout preditivo, e
    nunca inventa tolerância/offset/angularidade/calços/resultado de laser.

    Não existe ainda um endpoint de análise técnica de alinhamento (só balanceamento
    tem `/atividades-corretivas/.../balanceamento/`) — o cenário é montado
    diretamente pelos modelos, como o domínio ficará quando esse endpoint existir.
    """

    for _nome in [n for n in vars(base.AnaliseBalanceamentoTest) if n.startswith("test_")]:
        locals()[_nome] = None
    del _nome

    def _montar_alinhamento(self):
        from apps.coletas.models import Carregamento, ItemInspecao, Relatorio

        relatorio = Relatorio.objects.create(
            cliente=self.cliente, tecnologia=self.tecnologia,
            numero="RT-ALI-2020-06-01-00001", data_inicio="2020-06-01", data_termino="2020-06-01",
        )
        carregamento = Carregamento.objects.create(
            cliente=self.cliente, tecnologia=self.tecnologia, relatorio=relatorio,
            analista=self.analista, instrumento=self.instrumento, data_coleta="2020-06-01",
            tipo_corretiva=TipoServico.ALINHAMENTO,
        )
        item = ItemInspecao.objects.create(
            carregamento=carregamento, equipamento=self.equipamentos[0], condicao=self.condicao,
        )
        achado = Achado.objects.create(
            item=item, condicao=self.condicao, tipo_componente=self.componente,
            componente_texto="Acoplamento", tipo_anomalia=self.anomalia,
            anomalia_texto="Desalinhamento angular",
        )
        servico = ServicoCampo.objects.create(
            item=item, analise_tecnica=achado, cliente=self.cliente, equipamento=item.equipamento,
            tipo=TipoServico.ALINHAMENTO, analista=self.analista, instrumento=self.instrumento,
            relatorio=relatorio, data_execucao="2020-06-01",
        )
        resposta = self.api.get(f"/api/relatorios-inspecao/{relatorio.pk}/dossie/")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        folha = resposta.data["secao_d"][0]
        return servico, folha

    def test_alinhamento_e_reconhecido_como_corretiva_sem_campos_inventados(self):
        servico, folha = self._montar_alinhamento()

        # Nunca confundida com preditiva nem com balanceamento.
        self.assertEqual(folha["tipo_corretiva"], "ALINHAMENTO")
        self.assertEqual(folha["tipo_corretiva_display"], "Alinhamento a laser")

        c = folha["corretiva"]
        self.assertIsNotNone(c)  # reconhecida como corretiva — não cai em None.
        self.assertEqual(c["servico_id"], servico.pk)
        self.assertEqual(c["tipo"], "ALINHAMENTO")
        self.assertNotEqual(c["tipo"], "BALANCEAMENTO")

        # Nenhum campo técnico é inventado: sem medições reais de balanceamento
        # (que não se aplicam ao alinhamento), os blocos saem vazios/nulos.
        self.assertEqual(c["pontos"], [])
        self.assertEqual(c["planos"], [])
        self.assertIsNone(c["ponto_foco"])
        self.assertIsNone(c["velocidade_referencia"])
        self.assertIsNone(c["resultado"]["criticidade_final"])
        self.assertIsNone(c["resultado"]["reducao_media_pct"])
        self.assertIsNone(c["economia"])

        # Sem OSP ainda (não há endpoint de análise técnica de alinhamento que a
        # gere) — estado de ausência, não um erro.
        self.assertEqual(folha["osp"], "—")

    def test_alinhamento_reaproveita_o_bloco_de_economia_quando_existir(self):
        # A Economia energética vale para balanceamento E alinhamento (mesmo
        # modelo, sem restrição de tipo) — quando já estiver cadastrada, o bloco
        # comum é reaproveitado em vez de reimplementado por tipo.
        servico, _ = self._montar_alinhamento()
        EconomiaEnergetica.objects.create(
            servico=servico, tensao_v="220", corrente_antes_a="12", corrente_apos_a="10",
            fator_potencia="0.900", horas_dia="8", dias_ano=250, custo_kwh="0.6500",
            investimento="500.00",
        )
        resposta = self.api.get(f"/api/relatorios-inspecao/{servico.relatorio_id}/dossie/")
        c = resposta.data["secao_d"][0]["corretiva"]
        self.assertIsNotNone(c["economia"])
        self.assertEqual(c["economia"]["corrente_antes_a"], "12.00")
        self.assertEqual(c["economia"]["corrente_apos_a"], "10.00")
        self.assertIsNotNone(c["economia"]["economia_kwh_ano"])
