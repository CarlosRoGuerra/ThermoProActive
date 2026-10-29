# -*- coding: utf-8 -*-
"""
Um relatório técnico COMPLETO de exemplo para cada tipo da Análise final:

  1. Análises e OSPs         → vibração (achados + OSPs), termografia e a corretiva de
                               balanceamento — gerados pelo `seed_relatorio_completo`.
  2. Ensaios de transformador → óleo isolante (FQ, CR, PCB, 2-FAL não coletado; duas
                               campanhas, umidade fora da referência) e ensaios
                               elétricos (R×T, R×I, R×O).
  3. Ensaios de fluidos       → redutor (lubrificante: FQ + EF) e unidade hidráulica
                               (FQ + EF + CP), duas campanhas trimestrais, boletim do
                               óleo novo e meta ISO 4406 do fabricante.

Tudo fica no cliente fictício do `seed_relatorio_completo` (CNPJ próprio) — nada de
outro cliente é tocado, e rodar de novo apaga e recria só esse cenário.

Fidelidade: os números do transformador são os dos relatórios de referência que os
testes de `apps/ensaios` já validam (TRF-001, laudos de 26/12/2025). Nenhum limite é
inventado: transformador usa as referências de norma do catálogo; fluidos usam as
referências gerais do responsável técnico (migrações) e a meta do fabricante cadastrada
aqui com a fonte. Os resultados são lançados como na tela: valores + `registrar_contexto`.

Uso:  python manage.py seed_relatorios_exemplo
"""
from datetime import timedelta
from decimal import Decimal as D

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import (
    Area,
    Cliente,
    DadosTecnicosTransformador,
    Equipamento,
    Instrumento,
    ModuloTecnico,
    Setor,
    TecnologiaAnalise,
    TipoEquipamento,
)
from apps.coletas.models import Carregamento, ItemInspecao, Relatorio, StatusCarregamento
from apps.ensaios.contexto import registrar_contexto
from apps.ensaios.models import (
    ColetaFluido,
    ColetaOleo,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    RegistroEnsaioEletrico,
    ResultadoEnsaio,
    TipoFluido,
    ValorOleoNovo,
    ValorParametro,
)

from .seed_relatorio_completo import CNPJ_DEMO, HOJE, obter_ou_criar

# --- Transformador: valores dos relatórios de referência (ver apps/ensaios/tests.py) ---
FQ_ANTERIOR = {"VISCOSIDADE": "40.00", "DENSIDADE": "0.85", "FATOR_POTENCIA": "1.20", "NEUTRALIZACAO": "0.02",
               "TEOR_AGUA": "12.00", "RIGIDEZ": "66.00", "TENSAO_INTERFACIAL": "26.00", "COR": "1.00"}
# Campanha atual: umidade acima da referência (o mesmo caso do teste de não conformidade).
FQ_ATUAL = {**FQ_ANTERIOR, "FATOR_POTENCIA": "1.50", "TEOR_AGUA": "41.00", "RIGIDEZ": "55.00",
            "TENSAO_INTERFACIAL": "24.00"}
CR = {"H2": "10", "O2": "4500", "N2": "50000", "CH4": "28", "CO": "480", "CO2": "5000", "C2H4": "15",
      "C2H6": "11.5", "C2H2": "0"}
RXI = {
    15: (250, 550, 150), 30: (900, 1000, 400), 45: (1790, 2500, 800), 60: (3000, 4000, 900),
    120: (3150, 4500, 950), 180: (3225, 5000, 1000), 240: (3300, 5000, 1040), 300: (3300, 5000, 1070),
    360: (3320, 5000, 1090), 420: (3310, 5000, 1100), 480: (3325, 5000, 1100), 540: (3330, 5000, 1125),
    600: (3325, 5000, 1100),
}
RXI_SERIES = (("AT-BT-Massa", 5000), ("AT-Massa-BT", 5000), ("BT-Massa-AT", 500))
RXT_FASES = {"Fase 1 (H1-H2/X0-X2)": "51.700", "Fase 2 (H2-H3/X0-X3)": "51.600", "Fase 3 (H3-H1/X0-X1)": "51.630"}
RXO = {"H1H2": "3.51", "H1H3": "3.60", "H2H3": "3.65", "X0X1": "1.46", "X0X2": "1.45", "X0X3": "1.47"}

# --- Fluidos: (anterior, atual) por parâmetro. Desgaste ferroso subindo junto com sílica
# (poeira entrando pelo respiro) no redutor; contaminação por partículas na UH. ---
REDUTOR_FQ = {"VISC40": ("216.0", "205.0"), "IV": ("95", "94"), "AGUA": ("380", "450"),
              "TAN": ("0.30", "0.45"), "DENSIDADE": ("0.892", "0.893"), "OXIDACAO": ("6.0", "8.5"),
              "INSOLUVEIS": ("0.05", "0.08")}
REDUTOR_EF = {"FE": ("40", "95"), "CU": ("8", "12"), "CR": ("1", "2"), "AL": ("2", "4"), "PB": ("1", "1"),
              "SN": ("0", "1"), "NI": ("0", "1"), "AG": ("0", "0"), "MN": ("1", "1"), "TI": ("0", "0"),
              "V": ("0", "0"), "SI": ("8", "24"), "NA": ("2", "3"), "B": ("0", "0"), "K": ("1", "1"),
              "CA": ("10", "11"), "MG": ("2", "2"), "P": ("372", "360"), "ZN": ("15", "14"),
              "MO": ("0", "0"), "BA": ("0", "0")}
UH_FQ = {"VISC40": ("46.5", "47.5"), "IV": ("100", "99"), "AGUA": ("250", "300"), "TAN": ("0.55", "0.60"),
         "DENSIDADE": ("0.870", "0.871"), "OXIDACAO": ("5.0", "6.0"), "INSOLUVEIS": ("0.02", "0.03")}
UH_EF = {"FE": ("5", "6"), "CU": ("2", "2"), "CR": ("0", "0"), "AL": ("1", "1"), "PB": ("0", "0"),
         "SN": ("0", "0"), "NI": ("0", "0"), "AG": ("0", "0"), "MN": ("0", "0"), "TI": ("0", "0"),
         "V": ("0", "0"), "SI": ("4", "5"), "NA": ("1", "1"), "B": ("0", "0"), "K": ("0", "0"),
         "CA": ("30", "31"), "MG": ("1", "1"), "P": ("378", "370"), "ZN": ("445", "430"),
         "MO": ("0", "0"), "BA": ("0", "0")}
UH_CP = {"P4": ("2000", "4000"), "P6": ("600", "1200"), "P14": ("60", "100")}  # 18/16/13 → 19/17/14


class Command(BaseCommand):
    help = "Cria um relatório completo de exemplo por tipo: Análises e OSPs, transformador e fluidos."

    def handle(self, *args, **options):
        w = self.stdout.write
        w(self.style.MIGRATE_HEADING("1/3 · Análises e OSPs (seed_relatorio_completo)"))
        call_command("seed_relatorio_completo", stdout=self.stdout)

        cliente = Cliente.objects.get(cnpj=CNPJ_DEMO)
        self.analista = (
            Carregamento.objects.filter(cliente=cliente).select_related("analista").order_by("id").first().analista
        )
        with transaction.atomic():
            w(self.style.MIGRATE_HEADING("2/3 · Ensaios de transformador"))
            oleo, eletrico = self.transformador(cliente)
            w(self.style.MIGRATE_HEADING("3/3 · Ensaios de fluidos"))
            fluidos = self.fluidos(cliente)

        w("")
        w(self.style.SUCCESS("Relatórios de exemplo criados (um por tipo de ensaio):"))
        for rotulo, rel in (("Óleo isolante", oleo), ("Ensaios elétricos", eletrico), ("Fluidos", fluidos)):
            w(f"  {rotulo:18}: {rel.numero}  →  /relatorios-inspecao/{rel.id}   (carta: /carta/{rel.id})")
        w("  Análises e OSPs   : ver o resumo do bloco 1/3 acima.")

    # ------------------------------------------------------------------ comum

    @staticmethod
    def tecnologia(modulo, nome, sigla):
        existente = TecnologiaAnalise.objects.filter(modulo_tecnico=modulo).order_by("id").first()
        return existente or TecnologiaAnalise.objects.create(nome=nome, sigla=sigla, modulo_tecnico=modulo)

    def rota(self, cliente, tecnologia, numero, data, equipamentos, consideracoes=""):
        rel = Relatorio.objects.create(
            cliente=cliente, tecnologia=tecnologia, numero=numero, data_inicio=data, data_termino=data,
            data_finalizacao=data + timedelta(days=10), consideracoes_finais=consideracoes,
        )
        carreg = Carregamento.objects.create(
            cliente=cliente, tecnologia=tecnologia, relatorio=rel, analista=self.analista, data_coleta=data,
            status=StatusCarregamento.TRANSFERIDA,
        )
        itens = [ItemInspecao.objects.create(carregamento=carreg, equipamento=eq, ordem=i)
                 for i, eq in enumerate(equipamentos, start=1)]
        return rel, itens

    def resultado(self, item, ensaio, valores=(), **campos):
        """`valores`: (parametro, valor, extras). Lança como a tela: valores e depois o contexto técnico."""
        campos.setdefault("situacao", "REALIZADO")
        r = ResultadoEnsaio.objects.create(item=item, ensaio=ensaio, **campos)
        ValorParametro.objects.bulk_create([
            ValorParametro(resultado=r, parametro=p, valor=D(v) if v is not None else None, **extras)
            for p, v, extras in valores
        ])
        registrar_contexto(r, autor=self.analista, origem="MANUAL")
        return r

    # ----------------------------------------------------------- transformador

    def transformador(self, cliente):
        modulos = (ModuloTecnico.OLEO_ISOLANTE, ModuloTecnico.ENSAIO_ELETRICO)
        ensaio = {e.sigla: e for e in Ensaio.objects.filter(modulo__in=modulos)}
        param = {(p.ensaio.sigla, p.codigo): p
                 for p in ParametroEnsaio.objects.select_related("ensaio").filter(ensaio__modulo__in=modulos)}

        setor = Setor.objects.create(
            area=Area.objects.create(cliente=cliente, nome="Subestações"), nome="SE-01 — Subestação Principal",
        )
        trafo = Equipamento.objects.create(
            setor=setor, tag="TRF-001", nome="Transformador Trifásico a Óleo", fabricante="Fabricante Exemplo",
            modelo="TFC-500", numero_serie="EX-91839", ano_fabricacao=1996,
        )
        DadosTecnicosTransformador.objects.create(
            equipamento=trafo, potencia_kva=D("500"), tensao_primaria_v=D("13800"), tensao_secundaria_v=D("380"),
            tensao_secundaria_fase_v=D("220"), impedancia_pct=D("4.49"), grupo_ligacao="DYn1",
            volume_oleo_l=D("540"), possui_tanque_expansao=False,
        )

        # Óleo isolante — campanha anterior (histórico) e atual.
        afim = self.tecnologia(ModuloTecnico.OLEO_ISOLANTE, "Análise de Fluídos Isolantes", "AFIM")
        data_ant, data_atual = HOJE - timedelta(days=380), HOJE - timedelta(days=20)
        for data, fq, numero, consid in (
            (data_ant, FQ_ANTERIOR, f"RT-AFIM-{data_ant:%Y-%m-%d}-00090", ""),
            (data_atual, FQ_ATUAL, f"RT-AFIM-{data_atual:%Y-%m-%d}-00104",
             "O teor de água subiu de 12 para 41 ppm em um ano e saiu da referência; a rigidez dielétrica caiu "
             "de 66 para 55 kV e segue conforme. Os gases dissolvidos não indicam falha ativa. Recomenda-se "
             "tratamento do óleo por termovácuo e nova coleta em 90 dias para confirmar a recuperação."),
        ):
            rel, (item,) = self.rota(cliente, afim, numero, data, [trafo], consid)
            coleta = ColetaOleo.objects.create(
                item=item, data_coleta=data, amostrador=self.analista.nome, temperatura_amostra_c=D("45.0"),
                temperatura_ambiente_c=D("31.0"), umidade_relativa_pct=D("58.0"),
                ponto_coleta=PontoColeta.objects.get(nome="Dreno Inferior Lado AT"),
                tipo_fluido=TipoFluido.objects.get(nome="Óleo Mineral B [Parafínico]"),
            )
            coleta.ensaios.set([ensaio[s] for s in ("FQ", "CR", "PCB")])
            InspecaoVisualColeta.objects.bulk_create([
                InspecaoVisualColeta(coleta=coleta, item_checklist=i, estado="OK" if i.grupo == "GERAL" else "NA")
                for i in ItemChecklistVisual.objects.all()
            ])
            atual = data == data_atual
            proxima = data + timedelta(days=90 if atual else 365)
            comum = {"data_analise": data + timedelta(days=12), "data_proxima": proxima}
            self.resultado(
                item, ensaio["FQ"],
                [(param[("FQ", k)], v, {}) for k, v in fq.items()]
                + [(param[("FQ", "APARENCIA")], None, {"valor_texto": "Límpido"})],
                numero_laudo=f"{data:%Y%m%d}001", criticidade="ALERTA" if atual else "ROTINA",
                recomendacao=("Tratamento do óleo por termovácuo e nova amostragem em 90 dias."
                              if atual else "Realizar nova amostragem dentro de 12 meses."), **comum,
            )
            self.resultado(item, ensaio["CR"], [(param[("CR", k)], v, {}) for k, v in CR.items()],
                           numero_laudo=f"{data:%Y%m%d}002", criticidade="ROTINA",
                           recomendacao="Manter o acompanhamento anual da cromatografia.", **comum)
            self.resultado(item, ensaio["PCB"], [(param[("PCB", "PCB")], "0.5", {})],
                           numero_laudo=f"{data:%Y%m%d}003", criticidade="ROTINA",
                           informacoes_adicionais="* Valor de PCB expresso em Somatória de Aroclor 1242 / 1254 / 1260",
                           **comum)
            if atual:
                self.resultado(item, ensaio["2FAL"], situacao="NAO_COLETADO", criticidade="ROTINA",
                               conclusao="Amostra não coletada!",
                               recomendacao="Recomenda-se realizar amostragem de equipamento com 10 anos ou mais de vida.")
                rel_oleo = rel
        self.stdout.write(f"  óleo isolante: {rel_oleo.numero} (+ campanha anterior para o histórico)")

        # Ensaios elétricos.
        ee = self.tecnologia(ModuloTecnico.ENSAIO_ELETRICO, "Ensaios Elétricos em Transformadores", "EE")
        data = HOJE - timedelta(days=20)
        rel_ee, (item,) = self.rota(
            cliente, ee, f"RT-EE-{data:%Y-%m-%d}-00105", data, [trafo],
            "Relação de transformação e resistência de isolamento conformes. A resistência ôhmica não tem "
            "critério de aceitação definido e fica registrada para comparação na próxima campanha.",
        )
        registro = RegistroEnsaioEletrico.objects.create(
            item=item, data_ensaio=data, analista=self.analista.nome, tap="5", tensao_tap_v=D("11400"),
            temperatura_oleo_c=D("45.0"), temperatura_ambiente_c=D("35.0"), umidade_relativa_pct=D("54.0"),
        )
        registro.ensaios.set([ensaio[s] for s in ("RXT", "RXI", "RXO")])
        instrumento = {
            modelo: obter_ou_criar(Instrumento, tipo=tipo, marca="Instrum", modelo=modelo,
                                                      numero_serie=serie)[0]
            for tipo, modelo, serie in (("TTR", "TTR-2000i", "IN-811721-24984"),
                                        ("Megôhmetro", "DMG-5Ki", "IN-811172-24990"),
                                        ("Microhmímetro", "MicroHM 10i", "IN-811172-24988"))
        }
        comum = {"criticidade": "ROTINA", "data_analise": data, "data_proxima": data + timedelta(days=362),
                 "recomendacao": "Realizar novo ensaio no prazo de 12 meses."}
        self.resultado(item, ensaio["RXT"], [(param[("RXT", "MEDIDA")], v, {"serie": f}) for f, v in RXT_FASES.items()],
                       numero_laudo=f"{data:%Y%m%d}011", instrumento=instrumento["TTR-2000i"], **comum)
        valores = [(param[("RXI", "TENSAO")], str(v), {"serie": s}) for s, v in RXI_SERIES]
        for tempo, leituras in RXI.items():
            valores += [(param[("RXI", "RESISTENCIA")], str(r), {"serie": s, "posicao": D(tempo)})
                        for (s, _), r in zip(RXI_SERIES, leituras)]
        self.resultado(item, ensaio["RXI"], valores, numero_laudo=f"{data:%Y%m%d}012",
                       instrumento=instrumento["DMG-5Ki"], **comum)
        self.resultado(item, ensaio["RXO"], [(param[("RXO", k)], v, {}) for k, v in RXO.items()],
                       numero_laudo=f"{data:%Y%m%d}013", instrumento=instrumento["MicroHM 10i"], **comum)
        self.stdout.write(f"  ensaios elétricos: {rel_ee.numero}")
        return rel_oleo, rel_ee

    # ----------------------------------------------------------------- fluidos

    def fluidos(self, cliente):
        modulo = ModuloTecnico.FLUIDO_LUBRIFICANTE
        ensaio = {e.sigla: e for e in Ensaio.objects.filter(modulo=modulo)}
        param = {(p.ensaio.sigla, p.codigo): p
                 for p in ParametroEnsaio.objects.select_related("ensaio").filter(ensaio__modulo=modulo)}
        aflh = self.tecnologia(modulo, "Análise de Fluídos Lubrificantes e Hidráulicos", "AFLH")

        setor = Setor.objects.create(
            area=Area.objects.create(cliente=cliente, nome="Acionamentos"), nome="Prensa de Sapata",
        )
        redutor = Equipamento.objects.create(
            setor=setor, tag="RED-01", nome="Redutor da Prensa de Sapata", fabricante="Fabricante Exemplo",
            tipo_equipamento=obter_ou_criar(TipoEquipamento, nome="Redutor")[0],
        )
        uh = Equipamento.objects.create(
            setor=setor, tag="UH-01", nome="Unidade Hidráulica da Prensa", fabricante="Fabricante Exemplo",
            tipo_equipamento=obter_ou_criar(TipoEquipamento, nome="Unidade Hidráulica")[0],
        )

        # Óleo novo cadastrado (base da variação de viscosidade e das quedas/aumentos da EF).
        engrenagem, _ = ProdutoFluido.objects.update_or_create(
            nome="Óleo de engrenagens ISO VG 220 (exemplo)",
            defaults={"fabricante": "Fornecedor Exemplo", "aplicacao": "LUBRIFICANTE",
                      "grau_viscosidade": "ISO VG 220", "viscosidade_40c_cst": D("220"),
                      "densidade_g_cm3": D("0.8900"), "densidade_temperatura_c": D("20.0"),
                      "indice_viscosidade": D("95")},
        )
        hidraulico, _ = ProdutoFluido.objects.update_or_create(
            nome="Óleo hidráulico HLP 46 (exemplo)",
            defaults={"fabricante": "Fornecedor Exemplo", "aplicacao": "HIDRAULICO",
                      "grau_viscosidade": "ISO VG 46", "viscosidade_40c_cst": D("46"),
                      "densidade_g_cm3": D("0.8700"), "densidade_temperatura_c": D("20.0"),
                      "indice_viscosidade": D("100")},
        )
        boletins = {engrenagem: {"SI": 2, "CA": 10, "MG": 2, "P": 380, "ZN": 15},
                    hidraulico: {"SI": 3, "CA": 30, "MG": 1, "P": 380, "ZN": 450}}
        for produto, valores in boletins.items():
            for codigo, valor in valores.items():
                ValorOleoNovo.objects.update_or_create(
                    produto=produto, parametro=param[("EF", codigo)],
                    defaults={"valor": D(valor), "fonte": "Boletim técnico do fornecedor (exemplo)", "data": HOJE},
                )
        # Meta de limpeza do fabricante da UH (com a fonte — nunca um limite genérico).
        ReferenciaParametro.objects.create(
            parametro=param[("CP", "ISO4406")], equipamento=uh, tipo="CODIGO_ISO", referencia_texto="17/15/12",
            origem="FABRICANTE_EQUIPAMENTO", fonte="Manual da unidade hidráulica (exemplo)",
        )
        laboratorio, _ = obter_ou_criar(Instrumento, 
            tipo="Laboratório de Fluídos", marca="LF01 - Laboratório de Fluídos", modelo="Exemplo",
        )

        data_ant, data_atual = HOJE - timedelta(days=110), HOJE - timedelta(days=15)
        rel_atual = None
        for indice, data in enumerate((data_ant, data_atual)):
            atual = indice == 1
            numero = f"RT-AFLH-{data:%Y-%m-%d}-{'00106' if atual else '00091'}"
            consid = (
                "Redutor RED-01: ferro subiu de 40 para 95 ppm junto com o silício (8 → 24 ppm, acima do óleo "
                "novo), indicando entrada de poeira pelo respiro e desgaste abrasivo das engrenagens. Trocar o "
                "respiro por um com filtro dessecante, filtrar ou trocar o óleo e recoletar em 30 dias. "
                "Unidade hidráulica UH-01: código ISO 4406 passou de 18/16/13 para 19/17/14, acima da meta "
                "17/15/12 do fabricante; substituir os elementos filtrantes e verificar a vedação do reservatório."
                if atual else ""
            )
            rel, (item_red, item_uh) = self.rota(cliente, aflh, numero, data, [redutor, uh], consid)
            for item, produto, aplicacao, siglas, ponto, horas in (
                (item_red, engrenagem, "LUBRIFICANTE", ("FQ", "EF"), "Bujão de dreno", 6200),
                (item_uh, hidraulico, "HIDRAULICO", ("FQ", "EF", "CP"), "Linha de retorno, antes do filtro", 4100),
            ):
                coleta = ColetaFluido.objects.create(
                    item=item, aplicacao=aplicacao, produto=produto, data_coleta=data, amostrador=self.analista.nome,
                    ponto_coleta=PontoColeta.objects.get(nome=ponto), temperatura_fluido_c=D("52.0"),
                    temperatura_ambiente_c=D("29.0"), condicao_operacional="EM_OPERACAO",
                    horas_equipamento=D(horas + (2200 if atual else 0)),
                    horas_fluido=D(1800 + (2200 if atual else 0)),
                    volume_reservatorio_l=D("180" if aplicacao == "LUBRIFICANTE" else "400"),
                    identificacao_amostra=f"{item.equipamento.tag}-{data:%Y%m}",
                )
                coleta.ensaios.set([ensaio[s] for s in siglas])

            def lancar(item, sigla, tabela, criticidade, recomendacao, sequencia):
                self.resultado(
                    item, ensaio[sigla],
                    [(param[(sigla, codigo)], par[indice], {}) for codigo, par in tabela.items()]
                    + ([(param[("FQ", "APARENCIA")], None, {"valor_texto": "Límpido"})] if sigla == "FQ" else []),
                    numero_laudo=f"LF01-{data:%Y%m%d}-{sequencia:02d}", criticidade=criticidade,
                    data_analise=data + timedelta(days=7), data_proxima=data + timedelta(days=90),
                    instrumento=laboratorio, laboratorio="LF01 - Laboratório de Fluídos",
                    recomendacao=recomendacao,
                )

            rotina = "Manter a periodicidade trimestral de coleta."
            lancar(item_red, "FQ", REDUTOR_FQ, "ROTINA", rotina, 1)
            lancar(item_red, "EF", REDUTOR_EF, "CRITICA" if atual else "ROTINA",
                   "Trocar o respiro (filtro dessecante), filtrar/trocar o óleo e recoletar em 30 dias."
                   if atual else rotina, 2)
            lancar(item_uh, "FQ", UH_FQ, "ROTINA", rotina, 3)
            lancar(item_uh, "EF", UH_EF, "ROTINA", rotina, 4)
            lancar(item_uh, "CP", UH_CP, "ALERTA" if atual else "ROTINA",
                   "Substituir os elementos filtrantes e revisar a vedação do reservatório." if atual else rotina, 5)
            if atual:
                rel_atual = rel
        self.stdout.write(f"  fluidos: {rel_atual.numero} (+ campanha anterior para o histórico)")
        return rel_atual
