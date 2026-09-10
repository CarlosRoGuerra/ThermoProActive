from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Condicao, Equipamento, Instrumento, Rota, Setor, TecnologiaAnalise
from apps.coletas.models import Carregamento, ItemInspecao, Relatorio
from .models import ServicoCampo, TipoServico


class AtividadeCorretivaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Exemplo Indústria Têxtil", cnpj="11.111.111/0001-11")
        cls.outro = Cliente.objects.create(nome="Outro cliente", cnpj="22.222.222/0001-22")
        cls.analista = get_user_model().objects.create_user(email="analista@example.com", nome="Analista", perfil="TECNICO")
        cls.leitor = get_user_model().objects.create_user(email="cliente@example.com", nome="Cliente", perfil="CLIENTE_PCM", cliente=cls.cliente)
        cls.tecnologia = TecnologiaAnalise.objects.create(nome="Balanceamento", sigla="BAL", tipo_corretiva=TipoServico.BALANCEAMENTO)
        cls.vibracao = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB")
        cls.instrumento = Instrumento.objects.create(tipo="Coletor", numero_serie="IN-1")
        cls.instrumento.tecnologias.add(cls.tecnologia)
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Área"), nome="Setor")
        cls.equipamentos = [Equipamento.objects.create(setor=setor, tag=f"EX-{i}", nome=f"Exaustor {i}") for i in range(5)]
        cls.rota = Rota.objects.create(cliente=cls.cliente, nome="Bal Exaustores", tecnologia=cls.tecnologia)
        cls.rota.equipamentos.add(*cls.equipamentos)
        cls.condicao = Condicao.objects.create(nome="Normal", sigla="N")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.analista)
        self.payload = {
            "rota": self.rota.pk, "tecnologia": self.tecnologia.pk,
            "instrumento": self.instrumento.pk, "data_termino_novo": "2020-05-20",
        }

    def abrir(self, **kwargs):
        resposta = self.api.post("/api/atividades-corretivas/", {**self.payload, **kwargs}, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        return resposta.data

    def urls_item(self, atividade):
        return f'/api/atividades-corretivas/{atividade["id"]}/itens/{atividade["itens"][0]["id"]}'

    def test_carrega_cinco_equipamentos_e_rastreabilidade(self):
        a = self.abrir(analista=self.leitor.pk, cliente=self.outro.pk, data_coleta="2020-01-01")
        self.assertEqual(len(a["itens"]), 5)
        self.assertSetEqual({i["equipamento"] for i in a["itens"]}, {e.pk for e in self.equipamentos})
        self.assertEqual(a["cliente"], self.cliente.pk)
        self.assertEqual(a["analista"], self.analista.pk)
        self.assertEqual(a["instrumento"], self.instrumento.pk)
        self.assertEqual(a["data_coleta"], "2020-05-20")
        self.assertEqual(a["data_termino"], "2020-05-20")
        self.assertRegex(a["numero"], r"^RT-BAL-2020-05-20-\d{5}$")
        self.assertFalse(ServicoCampo.objects.exists())
        self.assertTrue(all(i["analise"] is None for i in a["itens"]))
        self.rota.equipamentos.clear()
        self.assertEqual(Carregamento.objects.get(pk=a["id"]).itens.count(), 5)

    def test_analisar_reutiliza_registro_e_permita_continuar(self):
        a = self.abrir()
        url = self.urls_item(a)
        self.assertEqual(self.api.post(url + "/analise/", {}, format="json").status_code, 400)
        self.assertEqual(self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json").status_code, 200)
        primeira = self.api.post(url + "/analise/", {}, format="json")
        segunda = self.api.post(url + "/analise/", {}, format="json")
        self.assertEqual(primeira.status_code, 200, primeira.data)
        self.assertEqual(primeira.data, segunda.data)
        self.assertEqual(ServicoCampo.objects.count(), 1)
        self.assertEqual(Carregamento.objects.count(), 1)
        self.assertEqual(Relatorio.objects.count(), 1)
        servico = ServicoCampo.objects.get()
        self.assertEqual(servico.equipamento_id, a["itens"][0]["equipamento"])
        self.assertEqual(servico.item.carregamento_id, a["id"])
        self.assertEqual(servico.relatorio_id, a["relatorio"])
        self.assertEqual(servico.analista_id, self.analista.pk)
        self.assertEqual(servico.instrumento_id, self.instrumento.pk)
        self.assertEqual(str(servico.data_execucao), "2020-05-20")
        self.assertEqual(servico.tipo, TipoServico.BALANCEAMENTO)
        self.assertEqual(self.api.patch(url + "/analise/", {"observacoes": "Retomar ensaio"}, format="json").status_code, 200)
        detalhe = self.api.get(f'/api/atividades-corretivas/{a["id"]}/').data
        self.assertEqual(detalhe["itens"][0]["observacoes_analise"], "Retomar ensaio")
        self.assertEqual(detalhe["itens"][0]["analise"], servico.pk)
        self.assertEqual(self.api.patch(f"/api/servicos/{servico.pk}/", {"equipamento": self.equipamentos[-1].pk}, format="json").status_code, 400)

    def test_carrega_rota_com_um_unico_equipamento(self):
        unica = Rota.objects.create(cliente=self.cliente, nome="Só um exaustor", tecnologia=self.tecnologia)
        unica.equipamentos.add(self.equipamentos[0])
        a = self.abrir(rota=unica.pk)
        self.assertEqual(len(a["itens"]), 1)
        self.assertEqual(a["itens"][0]["equipamento"], self.equipamentos[0].pk)
        url = self.urls_item(a)
        self.assertEqual(self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json").status_code, 200)
        resposta = self.api.post(url + "/analise/", {}, format="json")
        self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(ServicoCampo.objects.count(), 1)

    def test_rejeita_rota_inativa_ou_inexistente(self):
        self.rota.ativo = False
        self.rota.save()
        resposta = self.api.post("/api/atividades-corretivas/", self.payload, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.rota.ativo = True
        self.rota.save()
        resposta = self.api.post("/api/atividades-corretivas/", {**self.payload, "rota": 999999}, format="json")
        self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertFalse(Carregamento.objects.exists())

    def test_mesmo_equipamento_em_outra_atividade_tem_analise_propria(self):
        ids = []
        for _ in range(2):
            a = self.abrir()
            url = self.urls_item(a)
            self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json")
            ids.append(self.api.post(url + "/analise/", {}, format="json").data["id"])
        self.assertEqual(len(set(ids)), 2)
        self.assertEqual(len(set(Relatorio.objects.values_list("numero", flat=True))), 2)

    def test_item_de_outra_atividade_nao_pode_ser_usado(self):
        a, b = self.abrir(), self.abrir()
        url = f'/api/atividades-corretivas/{a["id"]}/itens/{b["itens"][0]["id"]}'
        self.assertEqual(self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json").status_code, 404)
        self.assertEqual(self.api.post(url + "/analise/", {}, format="json").status_code, 404)

    def test_rejeita_entradas_incompativeis_sem_criar_relatorio(self):
        for dados in [
            {"tecnologia": self.vibracao.pk}, {"rota": None}, {"instrumento": None},
            {"data_termino_novo": str(timezone.localdate() + timedelta(days=1))},
        ]:
            with self.subTest(dados=dados):
                resposta = self.api.post("/api/atividades-corretivas/", {**self.payload, **dados}, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        self.instrumento.tecnologias.clear()
        self.assertEqual(self.api.post("/api/atividades-corretivas/", self.payload, format="json").status_code, 400)
        self.assertFalse(Relatorio.objects.exists())

    def test_rejeita_rota_vazia_de_outra_tecnologia_ou_com_equipamento_de_outro_cliente(self):
        vazia = Rota.objects.create(nome="Vazia", cliente=self.cliente)
        outra = Rota.objects.create(nome="Outra", cliente=self.outro)
        outra.equipamentos.add(self.equipamentos[0])
        self.rota.tecnologia = self.vibracao
        self.rota.save()
        for rota in [vazia, outra, self.rota]:
            with self.subTest(rota=rota.pk):
                resposta = self.api.post("/api/atividades-corretivas/", {**self.payload, "rota": rota.pk}, format="json")
                self.assertEqual(resposta.status_code, 400, resposta.data)
        self.assertFalse(Carregamento.objects.exists())

    def test_cliente_apenas_le_propria_atividade(self):
        a = self.abrir()
        self.api.force_authenticate(self.leitor)
        self.assertEqual(self.api.get(f'/api/atividades-corretivas/{a["id"]}/').status_code, 200)
        self.assertEqual(self.api.post("/api/atividades-corretivas/", self.payload, format="json").status_code, 403)
        self.assertEqual(self.api.patch(self.urls_item(a) + "/condicao/", {"condicao": self.condicao.pk}, format="json").status_code, 403)
        self.assertEqual(self.api.post(self.urls_item(a) + "/analise/", {}, format="json").status_code, 403)
        self.leitor.cliente = self.outro
        self.leitor.save()
        self.assertEqual(self.api.get(f'/api/atividades-corretivas/{a["id"]}/').status_code, 404)
        self.assertEqual(self.api.get("/api/atividades-corretivas/").data["count"], 0)
        self.leitor.cliente = None
        self.leitor.save()
        self.assertEqual(self.api.get("/api/atividades-corretivas/").data["count"], 0)

    def test_fluxo_preditivo_preservado_e_analise_de_campo_unificada(self):
        # A Análise de campo (Inspeções) é o ponto de entrada único para os dois fluxos:
        # /carregamentos/ e /itens-inspecao/ agora enxergam preditivo E corretivo juntos
        # (é a mesma "atividade" = Carregamento com tipo_corretiva preenchido). Mas
        # /atividades-corretivas/ continua sendo a visão especializada, só das corretivas,
        # e não dá pra criar itens soltos apontando pra uma atividade corretiva pelo
        # endpoint genérico.
        a = self.abrir()
        resposta = self.api.post("/api/carregamentos/", {
            "cliente": self.cliente.pk, "tecnologia": self.vibracao.pk,
            "rota": self.rota.pk, "data_termino_novo": "2020-05-20",
        }, format="json")
        self.assertEqual(resposta.status_code, 201, resposta.data)
        preditiva = resposta.data
        self.assertEqual(len(preditiva["itens"]), 5)
        self.assertEqual(preditiva["tipo_corretiva"], "")
        listagem = self.api.get("/api/carregamentos/").data
        self.assertEqual(
            sorted(c["id"] for c in listagem["results"]), sorted([preditiva["id"], a["id"]]),
        )
        self.assertEqual(self.api.get(f'/api/carregamentos/{a["id"]}/').status_code, 200)
        self.assertEqual(self.api.get(f'/api/atividades-corretivas/{preditiva["id"]}/').status_code, 404)
        self.assertEqual(self.api.get(f'/api/atividades-corretivas/{a["id"]}/').status_code, 200)
        for item in preditiva["itens"]:
            resposta = self.api.patch(f'/api/itens-inspecao/{item["id"]}/', {"condicao": self.condicao.pk}, format="json")
            self.assertEqual(resposta.status_code, 200, resposta.data)
        self.assertEqual(self.api.post(f'/api/carregamentos/{preditiva["id"]}/transferir/').status_code, 200)
        self.assertEqual(self.api.post("/api/itens-inspecao/", {
            "carregamento": a["id"], "equipamento": self.equipamentos[0].pk,
        }, format="json").status_code, 400)

    def test_falha_ao_copiar_equipamentos_reverte_atividade_e_relatorio(self):
        with patch("apps.coletas.serializers.ItemInspecao.objects.bulk_create", side_effect=RuntimeError("falha")):
            with self.assertRaises(RuntimeError):
                self.abrir()
        self.assertFalse(Carregamento.objects.exists())
        self.assertFalse(Relatorio.objects.exists())
        self.assertFalse(ItemInspecao.objects.exists())

    def test_tecnologia_determina_alinhamento(self):
        self.tecnologia.tipo_corretiva = TipoServico.ALINHAMENTO
        self.tecnologia.save()
        a = self.abrir()
        self.assertEqual(a["tipo_corretiva"], TipoServico.ALINHAMENTO)
        # Alteração posterior no catálogo não reclassifica uma atividade existente.
        self.tecnologia.tipo_corretiva = TipoServico.BALANCEAMENTO
        self.tecnologia.save()
        url = self.urls_item(a)
        self.api.patch(url + "/condicao/", {"condicao": self.condicao.pk}, format="json")
        self.assertEqual(self.api.post(url + "/analise/", {}, format="json").data["tipo"], TipoServico.ALINHAMENTO)
