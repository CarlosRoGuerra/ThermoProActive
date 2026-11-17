"""O dossiê congelado no laudo tem de ser o mesmo JSON que a API entrega à tela."""
from decimal import Decimal

from django.test import SimpleTestCase

from .snapshots import como_na_api, serializavel


class SnapshotNumerosTest(SimpleTestCase):
    def test_decimal_do_dossie_continua_numero(self):
        # Regressão: com o DjangoJSONEncoder o Decimal virava "51.700000" e as fichas de
        # ensaio (óleo, elétricos, fluidos, subestação) saíam com as células em branco no PDF.
        dossie = como_na_api({"fases": [{"medido": Decimal("51.700000"), "erro": None}]})
        self.assertEqual(dossie["fases"][0]["medido"], 51.7)
        self.assertIsInstance(dossie["fases"][0]["medido"], float)
        self.assertIsNone(dossie["fases"][0]["erro"])  # ausente não vira zero

    def test_snapshot_preserva_os_numeros_do_dossie(self):
        self.assertEqual(serializavel({"relatorio": como_na_api({"v": Decimal("0.5")})})["relatorio"]["v"], 0.5)
