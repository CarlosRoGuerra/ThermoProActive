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

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.cadastros.models import (
    Area,
    Cliente,
    Condicao,
    DadosTecnicosTransformador,
    Equipamento,
    Instrumento,
    ModuloTecnico,
    OrigemCriterio,
    Sensor,
    Setor,
    TecnologiaAnalise,
    TipoAnomalia,
    TipoComponente,
    TipoEquipamento,
    TipoRecomendacao,
)
from apps.preditiva.models import LimiteAlarmeSerie, Validacao
from apps.coletas.models import (
    Achado,
    AchadoImagem,
    Carregamento,
    Inspecao,
    ItemInspecao,
    MedicaoTecnica,
    MedicaoTermografia,
    Relatorio,
    StatusCarregamento,
    SistemaTermografia,
    TipoAnalise,
)
from apps.ensaios.contexto import registrar_contexto
from apps.notificacoes.models import EventoPreditivo, Notificacao
from apps.ensaios.models import (
    MODULOS_SUBESTACAO,
    ColetaFluido,
    ColetaOleo,
    DadosPlacaSubestacao,
    Ensaio,
    InspecaoVisualColeta,
    ItemChecklistVisual,
    ParametroEnsaio,
    PontoColeta,
    ProdutoFluido,
    ReferenciaParametro,
    RegistroEnsaioEletrico,
    RegistroEnsaioSubestacao,
    ResultadoEnsaio,
    TipoFluido,
    ValorOleoNovo,
    ValorParametro,
)

from .seed_relatorio_completo import CNPJ_DEMO, HOJE, img_real, img_termica, obter_ou_criar

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


# Critérios de DEMONSTRAÇÃO: restritos ao cliente fictício e sempre identificados como tal.
# Não são tolerâncias de fabricante nem normativas; o responsável técnico substitui antes de uso real.
FONTE_DEMO = "DEMONSTRAÇÃO — valor fictício do seed de exemplo, sem validade técnica"


class Command(BaseCommand):
    help = "Cria um relatório completo de exemplo por tipo: Análises e OSPs, transformador, fluidos e alinhamento/termografia mecânica."

    def handle(self, *args, **options):
        w = self.stdout.write
        # Inspeções (medições) do cenário são protegidas contra a exclusão do cliente: saem antes da
        # limpeza do seed_relatorio_completo, senão a segunda execução para no PROTECT.
        # Eventos preditivos nascem ao salvar as medições e seguram Inspecao/Equipamento com PROTECT;
        # as notificações deles seguram o evento com PROTECT. Saem nesta ordem.
        Notificacao.objects.filter(evento_preditivo__inspecao__cliente__cnpj=CNPJ_DEMO).delete()
        EventoPreditivo.objects.filter(inspecao__cliente__cnpj=CNPJ_DEMO).delete()
        Inspecao.objects.filter(cliente__cnpj=CNPJ_DEMO).delete()
        # Sensores do cliente demo (PROTECT no equipamento): dado do cenário, apagado com ele.
        Sensor.objects.filter(equipamento__setor__area__cliente__cnpj=CNPJ_DEMO).delete()
        w(self.style.MIGRATE_HEADING("1/4 · Análises e OSPs (seed_relatorio_completo)"))
        call_command("seed_relatorio_completo", stdout=self.stdout)

        cliente = Cliente.objects.get(cnpj=CNPJ_DEMO)
        self.analista = (
            Carregamento.objects.filter(cliente=cliente).select_related("analista").order_by("id").first().analista
        )
        with transaction.atomic():
            w(self.style.MIGRATE_HEADING("2/4 · Ensaios de transformador"))
            oleo, eletrico = self.transformador(cliente)
            w(self.style.MIGRATE_HEADING("3/4 · Ensaios de fluidos"))
            fluidos = self.fluidos(cliente)
            w(self.style.MIGRATE_HEADING("4/4 · Alinhamento a laser e termografia mecânica"))
            alinhamentos = self.alinhamento_e_termografia(cliente)
            w(self.style.MIGRATE_HEADING("5/5 · Ensaios elétricos de subestação (TC, TP, DJ, CS, RP)"))
            subestacao = self.subestacao(cliente)

        w("")
        w(self.style.SUCCESS("Relatórios de exemplo criados (um por tipo de ensaio):"))
        for rotulo, rel in (("Óleo isolante", oleo), ("Ensaios elétricos", eletrico), ("Fluidos", fluidos),
                            *alinhamentos, *subestacao.items()):
            w(f"  {rotulo:18}: {rel.numero}  →  /relatorios-inspecao/{rel.id}   (carta: /carta/{rel.id})")
        w("  Análises e OSPs   : ver o resumo do bloco 1/4 acima.")

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

    # ------------------------------------------- alinhamento e termografia mecânica

    def alinhamento_e_termografia(self, cliente):
        """Alinhamento de eixos, de polias (ficha antes/depois) e termografia mecânica dinâmica.

        Os relatórios ficam no cliente fictício. Os critérios de classificação são de demonstração
        (`FONTE_DEMO`), validados só para este cliente; sem eles o relatório sairia PENDENTE.
        """
        # Garante os módulos do catálogo (TI-SMD/TI-SME/TI-PI e a tecnologia de polias) antes de usá-los.
        # A de eixos vem antes: o comando copia dela a análise corretiva da de polias e, num banco
        # vazio (testes), ela ainda não existe.
        eixos = self.tecnologia(ModuloTecnico.ALINHAMENTO_EIXOS, "Alinhamento à Laser Entre Eixos", "ALEE")
        call_command("ajustar_catalogo_termo_alinhamento", stdout=self.stdout)
        polias = self.tecnologia(ModuloTecnico.ALINHAMENTO_POLIAS, "Alinhamento à Laser Entre Polias", "ALEP")
        termo_mec = self.tecnologia(
            ModuloTecnico.TERMOGRAFIA_MECANICA, "Termografia Infravermelha em Sistemas Mecânicos Dinâmicos", "TI-SMD",
        )

        for modalidade, grandeza, unidade, sistema, alerta, critico in (
            ("CORRETIVA", "Desalinhamento angular", "mm/100mm", "", D("0.05"), D("0.10")),
            ("CORRETIVA", "Desalinhamento paralelo", "mm", "", D("0.05"), D("0.10")),
            ("TERMOGRAFIA", "delta_t", "°C", SistemaTermografia.MEC_DINAMICO, D("10"), D("20")),
        ):
            obter_ou_criar(
                LimiteAlarmeSerie, modalidade=modalidade, grandeza=grandeza, unidade=unidade, sistema=sistema,
                sentido="SUPERIOR", cliente=cliente,
                defaults={"valor_alerta": alerta, "valor_critico": critico, "origem": OrigemCriterio.RESPONSAVEL_TECNICO,
                          "fonte": FONTE_DEMO, "validacao": Validacao.VALIDADA},
            )

        setor = Setor.objects.create(
            area=Area.objects.create(cliente=cliente, nome="Utilidades e Processo"), nome="Casa de Máquinas",
        )
        bomba = Equipamento.objects.create(
            setor=setor, tag="BMB-01", nome="Conjunto motor-bomba de água de resfriamento",
            fabricante="Fabricante Exemplo", modelo="BMC-40",
        )
        ventilador = Equipamento.objects.create(
            setor=setor, tag="VEN-02", nome="Ventilador com transmissão por polias", fabricante="Fabricante Exemplo",
            modelo="VXP-20",
        )
        redutor = Equipamento.objects.create(
            setor=setor, tag="RED-03", nome="Redutor de transmissão do misturador", fabricante="Fabricante Exemplo",
            modelo="RTM-200",
        )
        laser = obter_ou_criar(Instrumento, tipo="Alinhador a laser", marca="Instrum", modelo="ALX-DEMO",
                               numero_serie="DEMO-LASER-01")[0]
        termovisor = obter_ou_criar(Instrumento, tipo="Termovisor", marca="Instrum", modelo="TMV-DEMO",
                                    numero_serie="DEMO-TERMO-01")[0]

        # Alinhamento de eixos: motor-bomba. Antes fora de tolerância; depois dentro (condição NORMAL).
        data_eixos = HOJE - timedelta(days=20)
        rel_eixos, (item,) = self.rota(
            cliente, eixos, f"RT-ALEE-{data_eixos:%Y-%m-%d}-00120", data_eixos, [bomba],
            "Alinhamento a laser do conjunto motor-bomba: o desalinhamento angular caiu de 0,45 para 0,04 mm/100 mm "
            "com correção de calços nos pés. Recomenda-se reverificar o alinhamento após 6 meses de operação.",
        )
        self.alinhamento(
            item, data_eixos, eixos, bomba, "Acoplamento motor-bomba", "ALINHAMENTO_EIXOS", laser,
            antes={"vertical_paralelo_mm": "0.30", "vertical_angular_mm_100mm": "0.45",
                   "horizontal_paralelo_mm": "0.18", "horizontal_angular_mm_100mm": "0.22", "rpm": "1780"},
            depois={"vertical_paralelo_mm": "0.03", "vertical_angular_mm_100mm": "0.04",
                    "horizontal_paralelo_mm": "0.02", "horizontal_angular_mm_100mm": "-0.03", "rpm": "1780",
                    "correcao_pe_vertical_mm": "0.25", "correcao_pe_horizontal_mm": "-0.10",
                    "distancia_pes_mm": "250"},
            componente="Acoplamento", anomalia="Desalinhamento",
            recomendacao="Realinhar o conjunto motor-bomba", condicao="GR-0",
            detalhe="Acoplamento motor-bomba — alinhamento a laser",
            observacao="Desalinhamento corrigido com calços nos pés do motor. Equipamento liberado para operação.",
        )

        # Alinhamento de polias: ventilador. Depois da correção ainda em alerta pelo critério cadastrado.
        data_polias = HOJE - timedelta(days=18)
        rel_polias, (item,) = self.rota(
            cliente, polias, f"RT-ALEP-{data_polias:%Y-%m-%d}-00122", data_polias, [ventilador],
            "Alinhamento de polias da transmissão do ventilador: desalinhamento angular reduzido de 0,60 para "
            "0,06 mm/100 mm. Permanece em alerta pelo critério cadastrado; programar nova verificação.",
        )
        self.alinhamento(
            item, data_polias, polias, ventilador, "Polia do motor × polia do ventilador", "ALINHAMENTO_POLIAS", laser,
            antes={"vertical_paralelo_mm": "0.90", "vertical_angular_mm_100mm": "0.60",
                   "horizontal_paralelo_mm": "0.40", "horizontal_angular_mm_100mm": "-0.35", "rpm": "1190"},
            depois={"vertical_paralelo_mm": "0.06", "vertical_angular_mm_100mm": "0.06",
                    "horizontal_paralelo_mm": "0.04", "horizontal_angular_mm_100mm": "0.04", "rpm": "1190"},
            componente="Correias e polias", anomalia="Desalinhamento",
            recomendacao="Realinhar as polias e as correias", condicao="GR-3",
            detalhe="Transmissão por polias e correias do ventilador",
            observacao="Alinhamento entre as faces das polias melhorado. Ainda em alerta: reajustar as "
                       "polias e verificar a tensão das correias.",
        )

        # Termografia mecânica dinâmica: mancais do redutor. Dois pontos, com critérios diferentes.
        data_termo = HOJE - timedelta(days=15)
        rel_termo, (item,) = self.rota(
            cliente, termo_mec, f"RT-TMEC-{data_termo:%Y-%m-%d}-00121", data_termo, [redutor],
            "Inspeção termográfica dos mancais do redutor de transmissão. O mancal do lado do acionamento "
            "apresentou ΔT acima do critério de demonstração e foi encaminhado para lubrificação e inspeção.",
        )
        inspecao_termo = Inspecao.objects.create(
            cliente=cliente, tipo_analise=TipoAnalise.TERMOGRAFIA, tecnico=self.analista, data=data_termo,
        )
        pontos = (
            ("Mancal lado acionamento (LA)", D("62.0"), D("28.0"), "GR-2",
             "Lubrificar e inspecionar o mancal", "Aquecimento anormal de mancal",
             "ΔT de 34,0 °C acima da referência do mesmo ponto em operação comparável."),
            ("Mancal lado oposto ao acionamento (LOA)", D("41.0"), D("29.0"), "GR-3",
             "Monitorar na próxima rota", "Aquecimento anormal de mancal",
             "ΔT de 12,0 °C. Dentro da faixa de alerta; acompanhar na próxima rota."),
        )
        for ponto, tmed, tref, grau, recomendacao, anomalia, obs in pontos:
            MedicaoTermografia.objects.create(
                inspecao=inspecao_termo, equipamento=redutor, instrumento=termovisor, ponto_medicao=ponto,
                sistema=SistemaTermografia.MEC_DINAMICO, temperatura_ponto=tmed, temperatura_referencia=tref,
            )
            achado = Achado.objects.create(
                item=item, tipo_componente=self.catalogo(TipoComponente, "Mancal", termo_mec),
                detalhe=ponto, tipo_anomalia=self.catalogo(TipoAnomalia, anomalia, termo_mec),
                recomendacao=self.catalogo(TipoRecomendacao, recomendacao, termo_mec),
                observacoes=obs, condicao=self.condicao(grau), temperatura_medida=tmed,
                temperatura_referencia=tref, confirmada=True, visivel_cliente=True,
            )
            termica = img_termica(float(tmed), float(tref), f"{redutor.tag} — {ponto}")
            if termica:
                AchadoImagem.objects.create(
                    achado=achado, tipo="TERMICA", legenda=f"Termograma — {redutor.tag} ({ponto})",
                    arquivo=ContentFile(termica, name=f"termica_{redutor.tag}_{tmed}.png"),
                )
        self.stdout.write(f"  alinhamento e termografia: {rel_eixos.numero}, {rel_polias.numero}, {rel_termo.numero}")
        return [("Alinhamento eixos", rel_eixos), ("Alinhamento polias", rel_polias),
                ("Termografia mecânica", rel_termo)]

    def alinhamento(self, item, data, tecnologia, equipamento, ponto, subtipo, laser, *, antes, depois,
                    componente, anomalia, recomendacao, condicao, detalhe, observacao):
        """Uma análise de alinhamento: ficha antes e depois na mesma inspeção, e o Achado do relatório."""
        inspecao = Inspecao.objects.create(
            cliente=item.carregamento.cliente, tipo_analise=TipoAnalise.CORRETIVA, tecnico=self.analista, data=data,
        )
        for fase, ficha in (("antes", antes), ("depois", depois)):
            # `valor` = maior desalinhamento angular dos dois planos (mesma regra da ficha da tela).
            angular = max(abs(D(ficha["vertical_angular_mm_100mm"])), abs(D(ficha["horizontal_angular_mm_100mm"])))
            MedicaoTecnica.objects.create(
                inspecao=inspecao, equipamento=equipamento, tipo=TipoAnalise.CORRETIVA, subtipo=subtipo,
                ponto_medicao=ponto, grandeza="Desalinhamento angular", valor=angular, unidade="mm/100mm",
                parametros={"fase": fase, **ficha}, instrumento=laser,
            )
        Achado.objects.create(
            item=item, tipo_componente=self.catalogo(TipoComponente, componente, tecnologia),
            detalhe=detalhe, tipo_anomalia=self.catalogo(TipoAnomalia, anomalia, tecnologia),
            recomendacao=self.catalogo(TipoRecomendacao, recomendacao, tecnologia),
            observacoes=observacao, condicao=self.condicao(condicao), confirmada=True, visivel_cliente=True,
        )

    @staticmethod
    def catalogo(modelo, nome, tecnologia):
        """Item de catálogo ligado à tecnologia (sem duplicar por nome: `obter_ou_criar`)."""
        obj, _ = obter_ou_criar(modelo, nome=nome)
        obj.tecnologias.add(tecnologia)
        return obj

    @staticmethod
    def condicao(sigla):
        """Grau de risco do catálogo base (criado por `seed_relatorio_completo`)."""
        return Condicao.objects.filter(sigla=sigla).order_by("id").first()

    # ------------------------------------------------------------- subestação

    def subestacao(self, cliente):
        """
        Um relatório de exemplo por tipo de equipamento de subestação (docs/25): TC, TP, DJ, CS e RP.
        Os dados são de exemplo, não de um cliente real. Cada ensaio é lançado como na tela: valores
        por série e depois o contexto técnico (placa e registro do momento).
        """
        ensaio = {(e.modulo, e.sigla): e for e in Ensaio.objects.filter(modulo__in=MODULOS_SUBESTACAO)}
        param = {(p.ensaio.modulo, p.ensaio.sigla, p.codigo): p
                 for p in ParametroEnsaio.objects.select_related("ensaio").filter(ensaio__modulo__in=MODULOS_SUBESTACAO)}
        setor = Setor.objects.create(area=Area.objects.create(cliente=cliente, nome="Subestação de Distribuição"),
                                     nome="SE-02 — Pátio de Manobras")
        analista = self.analista.nome
        ttr = obter_ou_criar(Instrumento, tipo="TTR", marca="Instrum", modelo="TTR-2000i",
                             numero_serie="IN-811721-24984")[0]
        megometro = obter_ou_criar(Instrumento, tipo="Megôhmetro", marca="Instrum", modelo="DMG-5Ki",
                                   numero_serie="IN-811172-24990")[0]
        micro = obter_ou_criar(Instrumento, tipo="Microhmímetro", marca="Instrum", modelo="MicroHM 10i",
                               numero_serie="IN-811172-24988")[0]
        data = HOJE - timedelta(days=20)
        rels = {}

        def equipamento(tag, nome, tipo, **placa):
            eq = Equipamento.objects.create(
                setor=setor, tag=tag, nome=nome, fabricante="Fabricante Exemplo", numero_serie=f"EX-{tag}",
                tipo_equipamento=obter_ou_criar(TipoEquipamento, nome=tipo)[0],
            )
            DadosPlacaSubestacao.objects.create(equipamento=eq, **placa)
            return eq

        def rota(modulo, nome, sigla, eq, consideracoes):
            tec = self.tecnologia(modulo, nome, sigla)
            rel, (item,) = self.rota(cliente, tec, f"RT-{sigla}-{data:%Y-%m-%d}-00120", data, [eq], consideracoes)
            rels[nome] = rel
            return item

        def registro(item, ensaios, **campos):
            reg = RegistroEnsaioSubestacao.objects.create(item=item, data_ensaio=data, analista=analista, **campos)
            reg.ensaios.set([ensaio[(item.carregamento.tecnologia.modulo_tecnico, s)] for s in ensaios])

        def lancar(item, sigla, valores, **campos):
            modulo = item.carregamento.tecnologia.modulo_tecnico
            r = ResultadoEnsaio.objects.create(
                item=item, ensaio=ensaio[(modulo, sigla)], situacao="REALIZADO", criticidade="ROTINA",
                data_analise=data + timedelta(days=7), data_proxima=data + timedelta(days=365), **campos,
            )
            for codigo, serie, posicao, valor in valores:
                numero = D(valor) if valor.replace(".", "", 1).isdigit() else None
                ValorParametro.objects.create(
                    resultado=r, parametro=param[(modulo, sigla, codigo)], serie=serie,
                    posicao=None if posicao is None else D(posicao), valor=numero,
                    valor_texto="" if numero is not None else valor,
                )
            registrar_contexto(r, autor=self.analista, origem="MANUAL")
            return r

        # TC: relação com polaridade, curva de excitação, isolação e ôhmica (2 núcleos).
        tc = equipamento("TC-01", "Transformador de corrente 600/5 A", "Transformador de corrente",
                         tensao_nominal_kv=D("13.8"), corrente_nominal_a=D("600"), relacao_texto="600/5 A",
                         relacao_transformacao=D("120"), classe_exatidao="0,5", polaridade="Subtrativa",
                         numero_nucleos=2, carga_nominal_va=D("15"))
        item = rota(ModuloTecnico.ENSAIO_ELETRICO_TC, "Ensaios de TC", "ETC", tc,
                    "Relação do Núcleo 2 acima da classe 0,5 da placa; a curva de excitação do Núcleo 1 está "
                    "normal. Repetir a relação do Núcleo 2 após verificar as conexões do secundário.")
        registro(item, ("RELA", "EXC", "ISO", "OHM"), temperatura_equipamento_c=D("35.0"),
                 temperatura_ambiente_c=D("30.0"), umidade_relativa_pct=D("60.0"))
        lancar(item, "RELA", [
            ("RELACAO_MEDIDA", "Núcleo 1", None, "120.40"), ("POLARIDADE", "Núcleo 1", None, "Subtrativa"),
            ("RELACAO_MEDIDA", "Núcleo 2", None, "121.00"), ("POLARIDADE", "Núcleo 2", None, "Subtrativa"),
        ], numero_laudo=f"{data:%Y%m%d}021", instrumento=ttr,
            recomendacao="Relação do Núcleo 2 fora da classe 0,5: verificar as conexões e repetir o ensaio.")
        lancar(item, "EXC", [
            ("CORRENTE_EXCITACAO", "Núcleo 1", t, i) for t, i in
            (("50", "0.9"), ("100", "1.8"), ("150", "3.0"), ("200", "5.2"), ("250", "12.5"), ("300", "40.0"))
        ], numero_laudo=f"{data:%Y%m%d}022", instrumento=ttr)
        lancar(item, "ISO", [
            ("TENSAO_ENSAIO", "Primário – massa", None, "5000"), ("RESISTENCIA", "Primário – massa", None, "2500"),
            ("TENSAO_ENSAIO", "Secundário – massa", None, "1000"), ("RESISTENCIA", "Secundário – massa", None, "1800"),
        ], numero_laudo=f"{data:%Y%m%d}023", instrumento=megometro)
        lancar(item, "OHM", [
            ("RESISTENCIA", "Secundário Núcleo 1", None, "0.5732"),
            ("RESISTENCIA", "Secundário Núcleo 2", None, "0.5810"),
        ], numero_laudo=f"{data:%Y%m%d}024", instrumento=micro)

        # TP: relação com polaridade, isolação e ôhmica.
        tp = equipamento("TP-01", "Transformador de potencial 13,8 kV", "Transformador de potencial",
                         tensao_nominal_kv=D("13.8"), relacao_texto="13800/115 V", relacao_transformacao=D("120"),
                         classe_exatidao="0,5", polaridade="Subtrativa", carga_nominal_va=D("100"))
        item = rota(ModuloTecnico.ENSAIO_ELETRICO_TP, "Ensaios de TP", "ETP", tp,
                    "Transformador de potencial dentro da classe 0,5 em todas as medições lançadas.")
        registro(item, ("RELA", "ISO", "OHM"), temperatura_equipamento_c=D("33.0"),
                 temperatura_ambiente_c=D("30.0"), umidade_relativa_pct=D("60.0"))
        lancar(item, "RELA", [
            ("RELACAO_MEDIDA", "Fase A", None, "120.05"), ("POLARIDADE", "Fase A", None, "Subtrativa"),
        ], numero_laudo=f"{data:%Y%m%d}031", instrumento=ttr)
        lancar(item, "ISO", [
            ("TENSAO_ENSAIO", "Primário – massa", None, "5000"), ("RESISTENCIA", "Primário – massa", None, "3100"),
        ], numero_laudo=f"{data:%Y%m%d}032", instrumento=megometro)
        lancar(item, "OHM", [("RESISTENCIA", "Primário", None, "41.2300")],
               numero_laudo=f"{data:%Y%m%d}033", instrumento=micro)

        # DJ: resistência de contatos, isolação e tempos por polo (simultaneidade entre polos).
        dj = equipamento("DJ-01", "Disjuntor 15 kV 1250 A", "Disjuntor",
                         tensao_nominal_kv=D("15"), corrente_nominal_a=D("1250"),
                         capacidade_interrupcao_ka=D("25"), numero_polos=3, mecanismo="Mola")
        item = rota(ModuloTecnico.ENSAIO_ELETRICO_DJ, "Ensaios de DJ", "EDJ", dj,
                    "Resistência de contatos e isolação dentro do esperado para o equipamento. Tempos de operação "
                    "com simultaneidade de 0,8 ms entre os polos na abertura.")
        registro(item, ("RCON", "ISO", "TEMP"), temperatura_equipamento_c=D("30.0"),
                 temperatura_ambiente_c=D("29.0"), umidade_relativa_pct=D("62.0"))
        lancar(item, "RCON", [
            ("RESISTENCIA", "Polo A", None, "38"), ("RESISTENCIA", "Polo B", None, "41"),
            ("RESISTENCIA", "Polo C", None, "39"),
        ], numero_laudo=f"{data:%Y%m%d}041", instrumento=micro)
        lancar(item, "ISO", [
            ("TENSAO_ENSAIO", "Polo A", None, "5000"), ("RESISTENCIA", "Polo A", None, "3200"),
            ("TENSAO_ENSAIO", "Polo B", None, "5000"), ("RESISTENCIA", "Polo B", None, "3050"),
            ("TENSAO_ENSAIO", "Polo C", None, "5000"), ("RESISTENCIA", "Polo C", None, "3300"),
        ], numero_laudo=f"{data:%Y%m%d}042", instrumento=megometro)
        lancar(item, "TEMP", [
            ("TEMPO_ABERTURA", "Polo A", None, "31.2"), ("TEMPO_ABERTURA", "Polo B", None, "31.8"),
            ("TEMPO_ABERTURA", "Polo C", None, "31.0"),
            ("TEMPO_FECHAMENTO", "Polo A", None, "62.1"), ("TEMPO_FECHAMENTO", "Polo B", None, "62.4"),
            ("TEMPO_FECHAMENTO", "Polo C", None, "62.0"),
        ], numero_laudo=f"{data:%Y%m%d}043", instrumento=ttr)

        # CS: resistência de contatos e isolação por fase.
        cs_eq = equipamento("CS-01", "Chave seccionadora 13,8 kV 600 A", "Chave seccionadora",
                            tensao_nominal_kv=D("13.8"), corrente_nominal_a=D("600"), numero_polos=3,
                            mecanismo="Manual com motor")
        item = rota(ModuloTecnico.ENSAIO_ELETRICO_CS, "Ensaios de CS", "ECS", cs_eq,
                    "Contatos e isolação das três fases, sem limite universal: valores para comparação nas próximas "
                    "campanhas.")
        registro(item, ("RCON", "ISO"), temperatura_equipamento_c=D("31.0"),
                 temperatura_ambiente_c=D("29.0"), umidade_relativa_pct=D("62.0"))
        lancar(item, "RCON", [
            ("RESISTENCIA", "Fase A", None, "210"), ("RESISTENCIA", "Fase B", None, "215"),
            ("RESISTENCIA", "Fase C", None, "208"),
        ], numero_laudo=f"{data:%Y%m%d}051", instrumento=micro)
        lancar(item, "ISO", [
            ("TENSAO_ENSAIO", "Fase A", None, "5000"), ("RESISTENCIA", "Fase A", None, "4200"),
            ("TENSAO_ENSAIO", "Fase B", None, "5000"), ("RESISTENCIA", "Fase B", None, "4000"),
            ("TENSAO_ENSAIO", "Fase C", None, "5000"), ("RESISTENCIA", "Fase C", None, "4400"),
        ], numero_laudo=f"{data:%Y%m%d}052", instrumento=megometro)

        # RP: pickup e tempo por função; a tolerância de cada linha é a informada no lançamento.
        rele = equipamento("RL-01", "Relé de proteção do alimentador", "Relé de proteção",
                           funcoes_protecao="50/51 — fase A\n50/51 — fase B\n50N/51N — neutro")
        item = rota(ModuloTecnico.ENSAIO_ELETRICO_RP, "Ensaios de relé", "ERP", rele,
                    "Pickup e tempo de atuação das funções 50/51 e 50N/51N. A função 51 da fase B está fora da "
                    "tolerância informada no lançamento.")
        registro(item, ("PICK", "TEMP"), temperatura_ambiente_c=D("28.0"), umidade_relativa_pct=D("58.0"))
        lancar(item, "PICK", [
            ("ESPERADO", "50 — fase A", None, "500"), ("MEDIDO", "50 — fase A", None, "507"),
            ("TOLERANCIA", "50 — fase A", None, "5"),
            ("ESPERADO", "51 — fase B", None, "500"), ("MEDIDO", "51 — fase B", None, "530"),
            ("TOLERANCIA", "51 — fase B", None, "5"),
            ("ESPERADO", "50N — neutro", None, "100"), ("MEDIDO", "50N — neutro", None, "101"),
            ("TOLERANCIA", "50N — neutro", None, "5"),
        ], numero_laudo=f"{data:%Y%m%d}061", instrumento=ttr,
            recomendacao="Função 51 da fase B fora da tolerância: revisar o ajuste e repetir o ensaio.")
        lancar(item, "TEMP", [
            ("ESPERADO", "51 — fase A", None, "1.20"), ("MEDIDO", "51 — fase A", None, "1.24"),
            ("TOLERANCIA", "51 — fase A", None, "10"),
            ("ESPERADO", "51 — fase B", None, "1.20"), ("MEDIDO", "51 — fase B", None, "1.46"),
            ("TOLERANCIA", "51 — fase B", None, "10"),
        ], numero_laudo=f"{data:%Y%m%d}062", instrumento=ttr)
        return rels
