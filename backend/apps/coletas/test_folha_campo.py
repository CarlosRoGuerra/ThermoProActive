"""
Lançamento em lote da folha de campo (`POST /carregamentos/{id}/definir-condicao/`).

É o atalho do "marcar estes 30 como OK": precisa gravar tudo de uma vez, mas
sem abrir brecha que o PATCH item a item não tem — rota encerrada, item de
outra rota e condição desativada continuam barrados.
"""
from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.cadastros.models import Area, Cliente, Condicao, Equipamento, Setor, TecnologiaAnalise
from apps.coletas.models import Carregamento, ItemInspecao, StatusCarregamento

User = get_user_model()


class DefinirCondicaoEmLote(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome="Indústria A", cnpj="11.111.111/0001-11")
        cls.tecnico = User.objects.create_user(
            email="tecnico@thermo.com", nome="Técnico", perfil="TECNICO", nivel="PLENO",
        )
        cls.leitor = User.objects.create_user(
            email="pcm@cliente.com", nome="PCM", perfil="CLIENTE_PCM", cliente=cls.cliente,
        )
        cls.tecnologia = TecnologiaAnalise.objects.create(nome="Vibração", sigla="VIB")
        setor = Setor.objects.create(area=Area.objects.create(cliente=cls.cliente, nome="Utilidades"), nome="Exaustores")
        cls.equipamentos = [
            Equipamento.objects.create(setor=setor, tag=f"EX-{i:02d}", nome=f"Exaustor {i}") for i in range(4)
        ]
        cls.ok = Condicao.objects.create(nome="Condição Normal de Operação", sigla="OK")
        cls.inativa = Condicao.objects.create(nome="Antiga", sigla="X", ativo=False)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.tecnico)
        self.rota = self.nova_rota()
        self.itens = list(self.rota.itens.order_by("ordem"))

    def nova_rota(self):
        c = Carregamento.objects.create(cliente=self.cliente, tecnologia=self.tecnologia, analista=self.tecnico)
        for ordem, eq in enumerate(self.equipamentos, start=1):
            ItemInspecao.objects.create(carregamento=c, equipamento=eq, ordem=ordem)
        return c

    def lancar(self, itens, condicao, rota=None):
        return self.api.post(
            f"/api/carregamentos/{(rota or self.rota).pk}/definir-condicao/",
            {"itens": [i.pk for i in itens], "condicao": condicao.pk},
            format="json",
        )

    def test_aplica_a_condicao_e_devolve_so_os_itens_alterados(self):
        antes = {i.pk: i.atualizado_em for i in self.itens}
        r = self.lancar(self.itens[:3], self.ok)
        self.assertEqual(r.status_code, 200, r.data)
        self.assertEqual({i["id"] for i in r.data}, {i.pk for i in self.itens[:3]})
        self.assertTrue(all(i["condicao"] == self.ok.pk and i["condicao_nome"] == self.ok.nome for i in r.data))
        for item in self.itens[:3]:
            item.refresh_from_db()
            self.assertEqual(item.condicao_id, self.ok.pk)
            self.assertGreater(item.atualizado_em, antes[item.pk])
        # O que não foi selecionado continua pendente — e segue travando a transferência.
        self.itens[3].refresh_from_db()
        self.assertIsNone(self.itens[3].condicao_id)
        self.assertFalse(self.rota.pode_transferir)

    def test_item_de_outra_rota_invalida_o_lote_inteiro(self):
        intruso = self.nova_rota().itens.first()
        r = self.lancar([self.itens[0], intruso], self.ok)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(ItemInspecao.objects.filter(condicao__isnull=False).exists())

    def test_rota_transferida_nao_aceita_lancamento(self):
        self.rota.status = StatusCarregamento.TRANSFERIDA
        self.rota.save(update_fields=["status"])
        self.assertEqual(self.lancar(self.itens, self.ok).status_code, 400)
        self.assertFalse(ItemInspecao.objects.filter(condicao__isnull=False).exists())

    def test_condicao_desativada_e_lista_vazia_sao_recusadas(self):
        self.assertEqual(self.lancar(self.itens, self.inativa).status_code, 400)
        self.assertEqual(self.lancar([], self.ok).status_code, 400)

    def test_cliente_so_le_a_folha(self):
        self.api.force_authenticate(self.leitor)
        self.assertEqual(self.lancar(self.itens, self.ok).status_code, 403)
        self.assertFalse(ItemInspecao.objects.filter(condicao__isnull=False).exists())

    def test_detalhe_da_rota_nao_cresce_uma_consulta_por_equipamento(self):
        # A folha relê a rota depois de adicionar linha, remover item e salvar
        # análise: o custo não pode escalar com o tamanho da rota.
        def consultas():
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.api.get(f"/api/carregamentos/{self.rota.pk}/").status_code, 200)
            return len(ctx.captured_queries)

        com_quatro = consultas()
        for eq in self.equipamentos:
            ItemInspecao.objects.create(carregamento=self.rota, equipamento=eq, ordem=99)
        self.assertEqual(consultas(), com_quatro)
