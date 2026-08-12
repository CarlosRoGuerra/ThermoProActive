from collections import defaultdict

from django.db.models import Count, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import InternoEditaClienteVisualiza

from .models import (
    Achado,
    AchadoImagem,
    Carregamento,
    Inspecao,
    ItemInspecao,
    MedicaoTecnica,
    MedicaoTermografia,
    MedicaoVibracao,
    Relatorio,
    StatusCarregamento,
)
from .serializers import (
    AchadoImagemSerializer,
    AchadoSerializer,
    CarregamentoListSerializer,
    CarregamentoSerializer,
    InspecaoListSerializer,
    InspecaoSerializer,
    ItemInspecaoSerializer,
    MedicaoTecnicaSerializer,
    MedicaoTermografiaSerializer,
    MedicaoVibracaoSerializer,
    RelatorioSerializer,
)


def escopo_cliente(qs, user, campo_cliente="cliente"):
    """Perfis cliente só enxergam dados do próprio cliente (Portal — item 2.7)."""
    if user.is_cliente and user.cliente_id:
        return qs.filter(**{campo_cliente: user.cliente_id})
    return qs


class InspecaoViewSet(viewsets.ModelViewSet):
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["cliente", "tipo_analise", "status", "tecnico"]
    search_fields = ["observacoes"]
    ordering_fields = ["data", "criado_em"]

    def get_queryset(self):
        qs = (
            Inspecao.objects.ativos()
            .select_related("cliente", "tecnico")
            .prefetch_related(
                "medicoes_vibracao__equipamento", "medicoes_vibracao__componente",
                "medicoes_termografia__equipamento", "medicoes_termografia__componente",
                "medicoes_tecnicas__equipamento", "medicoes_tecnicas__componente",
            )
        )
        return escopo_cliente(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return InspecaoListSerializer
        return InspecaoSerializer


class MedicaoVibracaoViewSet(viewsets.ModelViewSet):
    serializer_class = MedicaoVibracaoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["inspecao", "equipamento", "criticidade", "zona_iso", "direcao"]
    ordering_fields = ["data_hora", "velocidade_rms"]

    def get_queryset(self):
        qs = MedicaoVibracao.objects.select_related(
            "equipamento", "componente", "instrumento", "inspecao"
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")


class MedicaoTermografiaViewSet(viewsets.ModelViewSet):
    serializer_class = MedicaoTermografiaSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["inspecao", "equipamento", "criticidade", "sistema"]
    ordering_fields = ["data_hora", "delta_t"]

    def get_queryset(self):
        qs = MedicaoTermografia.objects.select_related(
            "equipamento", "componente", "instrumento", "inspecao"
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")


class MedicaoTecnicaViewSet(viewsets.ModelViewSet):
    serializer_class = MedicaoTecnicaSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["inspecao", "equipamento", "criticidade", "tipo"]
    ordering_fields = ["data_hora"]

    def get_queryset(self):
        qs = MedicaoTecnica.objects.select_related(
            "equipamento", "componente", "instrumento", "inspecao"
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")


# =============================================================================
# Fluxo de inspeção campo → escritório
# =============================================================================


class RelatorioViewSet(viewsets.ModelViewSet):
    """Relatórios (laudos) — usado na janela "Utilizar outro número"."""

    serializer_class = RelatorioSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["cliente", "tecnologia"]
    search_fields = ["numero"]
    ordering_fields = ["data_termino", "numero", "criado_em"]

    def get_queryset(self):
        qs = Relatorio.objects.ativos().select_related("cliente", "tecnologia").order_by(
            "-data_termino", "-numero"
        )
        return escopo_cliente(qs, self.request.user)

    @action(detail=True, methods=["get"], url_path="secao-c")
    def secao_c(self, request, pk=None):
        """
        Seção C do relatório — Relação de Equipamentos Contemplados.
        Uma linha por análise (com o GR de cada), agrupada por Área → Setor;
        equipamentos sem análise entram com a condição do item (OK/PDP/PDM…).
        """
        relatorio = self.get_object()
        itens = (
            ItemInspecao.objects.filter(carregamento__relatorio=relatorio)
            .select_related("equipamento__setor__area", "condicao")
            .prefetch_related("achados__condicao", "achados__tipo_componente")
            .order_by(
                "equipamento__setor__area__nome", "equipamento__setor__nome",
                "equipamento__tag", "ordem",
            )
        )

        def rotulo(cond):
            if not cond:
                return "—"
            return cond.sigla or cond.nome

        grupos: dict = {}
        total = 0
        for item in itens:
            eq = item.equipamento
            setor = eq.setor
            area = setor.area if setor else None
            chave = (area.nome if area else "—", setor.nome if setor else "—")
            linhas = grupos.setdefault(chave, [])
            achados = list(item.achados.all())
            if achados:
                for a in achados:
                    comp = a.tipo_componente.nome if a.tipo_componente_id else a.componente_texto
                    nome = f"{eq.nome} - {comp}" if comp else eq.nome
                    linhas.append({"tag": eq.tag, "equipamento": nome, "condicao": rotulo(a.condicao)})
                    total += 1
            else:
                linhas.append({"tag": eq.tag, "equipamento": eq.nome, "condicao": rotulo(item.condicao)})
                total += 1

        return Response({
            "empresa": relatorio.cliente.nome,
            "numero": relatorio.numero,
            "data_inicio": relatorio.data_inicio,
            "data_termino": relatorio.data_termino,
            "total": total,
            "grupos": [{"area": a, "setor": s, "linhas": linhas} for (a, s), linhas in grupos.items()],
        })

    @action(detail=True, methods=["get"])
    def dossie(self, request, pk=None):
        """Relatório técnico completo — Capa + Seções A, B, C e D (folhas de OSP)."""
        from apps.cadastros.models import Norma

        rel = self.get_object()
        cliente = rel.cliente
        carregs = list(rel.carregamentos.select_related("instrumento", "analista"))
        analistas = sorted({c.analista.nome for c in carregs if c.analista_id})

        # Instrumentação com dados de calibração (atrelados ao ID do instrumento).
        instrumentos, vistos = [], set()
        for c in carregs:
            ins = c.instrumento
            if ins and ins.id not in vistos:
                vistos.add(ins.id)
                instrumentos.append({
                    "tipo": ins.tipo, "marca": ins.marca, "modelo": ins.modelo,
                    "numero_serie": ins.numero_serie,
                    "data_ultima_calibracao": ins.data_ultima_calibracao,
                    "proxima_calibracao": ins.proxima_calibracao,
                    "periodicidade": ins.get_periodicidade_calibracao_display(),
                    "entidade_calibracao": ins.entidade_calibracao,
                    "software_analise": ins.software_analise,
                })

        # Normas ligadas à tecnologia do relatório.
        normas = [
            {"codigo": n.codigo, "nome": n.nome, "orgao": n.orgao}
            for n in Norma.objects.ativos().filter(tecnologias=rel.tecnologia).order_by("codigo")
        ]

        # Concatenação: [valor do dropdown] + " " + [texto livre]  (regra do cliente).
        def concat(categoria, texto):
            return " ".join(p for p in [(categoria or "").strip(), (texto or "").strip()] if p)

        def rotulo(cond):
            return (cond.sigla or cond.nome) if cond else "—"

        condicoes_usadas = {}  # id -> Condicao, para o glossário dinâmico

        # --- Seção C (por área/setor) + apuração das condições (Seção B) ---
        itens = (
            ItemInspecao.objects.filter(carregamento__relatorio=rel)
            .select_related("equipamento__setor__area", "condicao")
            .prefetch_related("achados__condicao", "achados__tipo_componente")
            .order_by("equipamento__setor__area__nome", "equipamento__setor__nome",
                      "equipamento__tag", "ordem")
        )
        grupos, cond_tally, equipamentos_ids = {}, {}, set()
        total_linhas = 0
        for item in itens:
            eq = item.equipamento
            equipamentos_ids.add(eq.id)
            setor = eq.setor
            area = setor.area if setor else None
            chave = (area.nome if area else "—", setor.nome if setor else "—")
            linhas = grupos.setdefault(chave, [])
            achados = list(item.achados.all())
            if achados:
                for a in achados:
                    cat = a.tipo_componente.nome if a.tipo_componente_id else ""
                    comp = concat(cat, a.componente_texto)
                    nome = f"{eq.nome} - {comp}" if comp else eq.nome
                    r = rotulo(a.condicao)
                    linhas.append({"tag": eq.tag, "equipamento": nome, "condicao": r})
                    cond_tally[r] = cond_tally.get(r, 0) + 1
                    total_linhas += 1
                    if a.condicao_id:
                        condicoes_usadas[a.condicao_id] = a.condicao
            else:
                r = rotulo(item.condicao)
                linhas.append({"tag": eq.tag, "equipamento": eq.nome, "condicao": r})
                cond_tally[r] = cond_tally.get(r, 0) + 1
                total_linhas += 1
                if item.condicao_id:
                    condicoes_usadas[item.condicao_id] = item.condicao

        # Avaliação de Resultados (tabela verde da Seção D) — compara preditiva
        # × emergencial e o retorno (ROI). Campos já existem na OrdemServico.
        def avaliacao_osp(o):
            if o is None:
                return None
            return {
                "linhas": [
                    {"rotulo": "Mão de obra (h)", "pred_q": o.pred_mao_obra_h, "pred_v": o.pred_mao_obra_valor,
                     "emerg_q": o.emerg_mao_obra_h, "emerg_v": o.emerg_mao_obra_valor},
                    {"rotulo": "Serv. terceirizado (h)", "pred_q": o.pred_terceirizado_h, "pred_v": o.pred_terceirizado_valor,
                     "emerg_q": o.emerg_terceirizado_h, "emerg_v": o.emerg_terceirizado_valor},
                    {"rotulo": "Material de reparo ($)", "pred_q": None, "pred_v": o.pred_material_valor,
                     "emerg_q": None, "emerg_v": o.emerg_material_valor},
                    {"rotulo": "Produção (h/ton)", "pred_q": o.pred_producao_h, "pred_v": o.pred_producao_valor,
                     "emerg_q": o.emerg_producao_h, "emerg_v": o.emerg_producao_valor},
                    {"rotulo": "Outros ($)", "pred_q": None, "pred_v": o.pred_outros_valor,
                     "emerg_q": None, "emerg_v": o.emerg_outros_valor},
                ],
                "total_preditiva": o.total_preditiva,
                "total_emergencial": o.total_emergencial,
                "retorno": o.retorno_investimento,
            }

        # --- Achados: apuração (Seção B) E folhas (Seção D) da MESMA lista —
        #     itera TODOS os achados, garantindo que a contagem bata com as folhas.
        achados_qs = (
            Achado.objects.filter(item__carregamento__relatorio=rel)
            .select_related(
                "tipo_componente", "tipo_anomalia", "recomendacao", "condicao",
                "item__equipamento__setor__area", "item__carregamento__analista", "osp",
            )
            .prefetch_related("imagens")
            .order_by("item__equipamento__setor__area__nome", "item__equipamento__setor__nome",
                      "item__equipamento__tag", "id")
        )
        comp_tally, anom_tally = {}, {}
        secao_d = []
        for a in achados_qs:
            comp_cat = a.tipo_componente.nome if a.tipo_componente_id else (a.componente_texto or "Outros")
            anom_cat = a.tipo_anomalia.nome if a.tipo_anomalia_id else (a.anomalia_texto or "Outros")
            comp_tally[comp_cat] = comp_tally.get(comp_cat, 0) + 1
            anom_tally[anom_cat] = anom_tally.get(anom_cat, 0) + 1

            eq = a.item.equipamento
            setor = eq.setor
            area = setor.area if setor else None
            osp = getattr(a, "osp", None)
            osp_num = (
                f"{osp.sequencial_cliente:04d} | {osp.id}"
                if osp and osp.sequencial_cliente else (a.numero_osp or "—")
            )
            imagens = [
                {"tipo": img.get_tipo_display(), "arquivo": request.build_absolute_uri(img.arquivo.url),
                 "legenda": img.legenda}
                for img in a.imagens.all()
            ]
            secao_d.append({
                "osp": osp_num,
                "area": area.nome if area else "—",
                "setor": setor.nome if setor else "—",
                "tag": eq.tag,
                "equipamento": eq.nome,
                "componente": concat(a.tipo_componente.nome if a.tipo_componente_id else "", a.componente_texto),
                "anomalia": concat(a.tipo_anomalia.nome if a.tipo_anomalia_id else "", a.anomalia_texto),
                "recomendacao": concat(a.recomendacao.nome if a.recomendacao_id else "", a.recomendacao_texto),
                "observacao": a.observacoes,
                "grau_risco": rotulo(a.condicao),
                "grau_risco_descricao": a.condicao.nome if a.condicao_id else "",
                # Bloco de vibração
                "amplitude_velocidade": a.velocidade_global,
                "amplitude_aceleracao": a.aceleracao_global,
                # Bloco de termografia
                "temperatura_medida": a.temperatura_medida,
                "temperatura_referencia": a.temperatura_referencia,
                "delta_t": a.delta_t,
                "carga_percentual": a.carga_percentual,
                "corrente": [a.corrente_nominal, a.corrente_a, a.corrente_b, a.corrente_c],
                "tensao": [a.tensao_nominal, a.tensao_a, a.tensao_b, a.tensao_c],
                "analista": a.item.carregamento.analista.nome if a.item.carregamento.analista_id else "",
                "imagens": imagens,
                "avaliacao": avaliacao_osp(osp),
            })

        def distribuicao(tally):
            return [{"rotulo": k, "total": v} for k, v in sorted(tally.items(), key=lambda x: -x[1])]

        # Glossário dinâmico: só os termos (condições) presentes no relatório, com a
        # descrição vinda do cadastro "Condição do Equipamento".
        glossario = [
            {"sigla": c.sigla or c.nome, "termo": c.nome, "descricao": c.descricao or c.nome}
            for c in sorted(condicoes_usadas.values(), key=lambda x: (x.nivel, x.nome))
        ]

        return Response({
            "cabecalho": {
                "empresa": cliente.nome,
                "cnpj": cliente.cnpj,
                "endereco": cliente.endereco_formatado,
                "cidade_uf": cliente.cidade_uf,
                "contato": cliente.contato_gestor,
                "departamento": cliente.departamento,
                "logomarca": request.build_absolute_uri(cliente.logomarca.url) if cliente.logomarca else None,
                "numero": rel.numero,
                "tecnologia": rel.tecnologia.nome,
                "analistas": analistas,
                "data_inicio": rel.data_inicio,
                "data_termino": rel.data_termino,
                "data_finalizacao": rel.data_finalizacao,
                "instrumentos": instrumentos,
                "normas": normas,
                "glossario": glossario,
                "consideracoes_finais": rel.consideracoes_finais,
            },
            "secao_b": {
                "condicoes": distribuicao(cond_tally),
                "componentes": distribuicao(comp_tally),
                "anomalias": distribuicao(anom_tally),
                "equip_monitorados": len(equipamentos_ids),
                # Bate exatamente com o nº de folhas da Seção D.
                "anomalias_diagnosticadas": len(secao_d),
            },
            "secao_c": {
                "total": total_linhas,
                "grupos": [{"area": a, "setor": s, "linhas": linhas} for (a, s), linhas in grupos.items()],
            },
            "secao_d": secao_d,
        })


class CarregamentoViewSet(viewsets.ModelViewSet):
    """Análise de campo: "carregar rota", listar itens e transferir."""

    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["cliente", "tecnologia", "status", "analista", "rota", "relatorio"]
    search_fields = ["relatorio__numero"]
    ordering_fields = ["data_coleta", "criado_em"]

    def get_queryset(self):
        qs = (
            Carregamento.objects.ativos()
            .select_related("cliente", "tecnologia", "relatorio", "rota", "instrumento", "analista")
            .prefetch_related(
                "itens__equipamento__setor__area", "itens__condicao", "itens__achados__imagens",
            )
        )
        return escopo_cliente(qs, self.request.user)

    def get_serializer_class(self):
        if self.action == "list":
            return CarregamentoListSerializer
        return CarregamentoSerializer

    @action(detail=True, methods=["post"])
    def transferir(self, request, pk=None):
        """Encerra a rota: exige condição em TODOS os itens; envia à Análise final."""
        carregamento = self.get_object()
        if carregamento.status != StatusCarregamento.EM_CAMPO:
            return Response(
                {"detail": "Esta rota já foi transferida ou descartada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        pendentes = carregamento.itens_pendentes.count()
        if pendentes:
            return Response(
                {"detail": f"Há {pendentes} equipamento(s) sem condição. "
                           "Preencha a condição de todos antes de transferir."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        carregamento.status = StatusCarregamento.TRANSFERIDA
        carregamento.transferido_em = timezone.now()
        carregamento.save(update_fields=["status", "transferido_em", "atualizado_em"])
        return Response(self.get_serializer(carregamento).data)

    @action(detail=True, methods=["post"])
    def descartar(self, request, pk=None):
        """"Apagar tudo": marca o carregamento como descartado (sai da tela de campo)."""
        carregamento = self.get_object()
        carregamento.status = StatusCarregamento.DESCARTADA
        carregamento.save(update_fields=["status", "atualizado_em"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ItemInspecaoViewSet(viewsets.ModelViewSet):
    """Itens da folha de campo: definir condição e "adicionar/remover linha"."""

    serializer_class = ItemInspecaoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["carregamento", "equipamento", "condicao"]

    def get_queryset(self):
        qs = (
            ItemInspecao.objects.ativos()
            .select_related("equipamento__setor__area", "condicao", "carregamento")
            .prefetch_related("achados__imagens")
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="carregamento__cliente")


class AchadoViewSet(viewsets.ModelViewSet):
    """
    Análises (achados). Serve tanto o formulário de campo quanto a Análise final.
    Filtros de escritório: `item__carregamento__status=TRANSFERIDA`, `confirmada`,
    `visivel_cliente`, `item__carregamento__tecnologia`.
    """

    serializer_class = AchadoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = [
        "item", "item__carregamento", "item__carregamento__cliente",
        "item__carregamento__status", "item__carregamento__tecnologia",
        "confirmada", "visivel_cliente",
    ]
    ordering_fields = ["criado_em", "numero_osp"]

    def get_queryset(self):
        qs = (
            Achado.objects.ativos()
            .select_related(
                "item__equipamento__setor__area", "item__carregamento__tecnologia",
                "item__carregamento__relatorio", "item__carregamento__analista",
                "tipo_componente", "tipo_anomalia", "recomendacao", "condicao",
            )
            .prefetch_related("imagens")
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="item__carregamento__cliente")


class AchadoImagemViewSet(viewsets.ModelViewSet):
    """Upload das evidências (800×600) na Análise final."""

    serializer_class = AchadoImagemSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["achado", "tipo"]

    def get_queryset(self):
        qs = AchadoImagem.objects.select_related("achado__item__carregamento")
        return escopo_cliente(
            qs, self.request.user, campo_cliente="achado__item__carregamento__cliente"
        )


def _conta_criticidade(queryset) -> dict:
    return {
        item["criticidade"]: item["total"]
        for item in queryset.values("criticidade").annotate(total=Count("id"))
    }


class DashboardView(APIView):
    """Indicadores operacionais — Anexo I 2.8.1.1 (vibração + termografia)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        inspecoes = escopo_cliente(Inspecao.objects.ativos(), request.user)
        vib = escopo_cliente(
            MedicaoVibracao.objects.all(), request.user, campo_cliente="inspecao__cliente"
        )
        termo = escopo_cliente(
            MedicaoTermografia.objects.all(), request.user, campo_cliente="inspecao__cliente"
        )
        tec = escopo_cliente(
            MedicaoTecnica.objects.all(), request.user, campo_cliente="inspecao__cliente"
        )

        c_vib, c_termo, c_tec = _conta_criticidade(vib), _conta_criticidade(termo), _conta_criticidade(tec)
        por_criticidade = {
            nivel: c_vib.get(nivel, 0) + c_termo.get(nivel, 0) + c_tec.get(nivel, 0)
            for nivel in ("NORMAL", "ALERTA", "CRITICO")
        }

        # Equipamentos críticos consolidando todos os tipos de medição.
        criticos: dict = {}
        for qs in (vib, termo, tec):
            for row in (
                qs.filter(criticidade="CRITICO")
                .values("equipamento__tag", "equipamento__nome")
                .annotate(ocorrencias=Count("id"))
            ):
                chave = row["equipamento__tag"]
                if chave not in criticos:
                    criticos[chave] = {**row}
                else:
                    criticos[chave]["ocorrencias"] += row["ocorrencias"]
        equipamentos_criticos = sorted(
            criticos.values(), key=lambda r: r["ocorrencias"], reverse=True
        )[:10]

        # Import tardio evita dependência circular coletas <-> osp.
        from apps.osp.models import STATUS_ABERTOS, OrdemServico

        osps = escopo_cliente(OrdemServico.objects.all(), request.user)

        return Response({
            "total_inspecoes": inspecoes.count(),
            "inspecoes_abertas": inspecoes.filter(status="ABERTA").count(),
            "total_medicoes": vib.count() + termo.count() + tec.count(),
            "medicoes_por_criticidade": por_criticidade,
            "equipamentos_criticos": equipamentos_criticos,
            "osps_abertas": osps.filter(status__in=STATUS_ABERTOS).count(),
            "osps_total": osps.count(),
        })


def _ultimos_meses(n=6):
    hoje = timezone.now()
    ano, mes = hoje.year, hoje.month
    saida = []
    for _ in range(n):
        saida.append((ano, mes))
        mes -= 1
        if mes == 0:
            mes, ano = 12, ano - 1
    return list(reversed(saida))


class DashboardExecutivoView(APIView):
    """Dashboard executivo — Anexo I 2.8.1.2 (KPIs, custos, MTBF, MTTR, evolução)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.cadastros.models import Cliente
        from apps.osp.models import OrdemServico

        user = request.user
        osps = escopo_cliente(OrdemServico.objects.all(), user)
        vib = escopo_cliente(MedicaoVibracao.objects.all(), user, "inspecao__cliente")
        termo = escopo_cliente(MedicaoTermografia.objects.all(), user, "inspecao__cliente")
        tec = escopo_cliente(MedicaoTecnica.objects.all(), user, "inspecao__cliente")

        total_osp = osps.count()
        finalizadas = osps.filter(status="FINALIZADA", finalizada_em__isnull=False)

        # MTTR — tempo médio de reparo (horas) — item 2.8.1.2.4
        duracoes = [
            (o.finalizada_em - o.criado_em).total_seconds() / 3600
            for o in finalizadas.only("finalizada_em", "criado_em")
        ]
        mttr = round(sum(duracoes) / len(duracoes), 1) if duracoes else None

        # MTBF — tempo médio entre falhas (dias) — item 2.8.1.2.3
        por_equip = defaultdict(list)
        for o in osps.order_by("criado_em").values("equipamento_id", "criado_em"):
            por_equip[o["equipamento_id"]].append(o["criado_em"])
        gaps = [
            (ts[i] - ts[i - 1]).total_seconds() / 86400
            for ts in por_equip.values()
            for i in range(1, len(ts))
        ]
        mtbf = round(sum(gaps) / len(gaps), 1) if gaps else None

        # Custos de manutenção — item 2.8.1.2.2
        custos = osps.aggregate(real=Sum("custo_real"), estimado=Sum("custo_estimado"))

        # Evolução histórica (6 meses) — item 2.8.1.2.6
        evolucao = []
        for ano, mes in _ultimos_meses(6):
            criticas = sum(
                q.filter(data_hora__year=ano, data_hora__month=mes, criticidade="CRITICO").count()
                for q in (vib, termo, tec)
            )
            evolucao.append({
                "mes": f"{mes:02d}/{ano}",
                "criticas": criticas,
                "osps": osps.filter(criado_em__year=ano, criado_em__month=mes).count(),
            })

        # Performance por unidade — item 2.8.1.2.5
        performance = []
        for c in escopo_cliente(Cliente.objects.ativos(), user, "id"):
            cosps = osps.filter(cliente=c)
            criticas = sum(
                q.filter(inspecao__cliente=c, criticidade="CRITICO").count()
                for q in (vib, termo, tec)
            )
            performance.append({
                "cliente": c.nome,
                "osps": cosps.count(),
                "finalizadas": cosps.filter(status="FINALIZADA").count(),
                "criticas": criticas,
                "custo_real": float(cosps.aggregate(s=Sum("custo_real"))["s"] or 0),
            })

        return Response({
            "kpis": {
                "osps_total": total_osp,
                "osps_finalizadas": finalizadas.count(),
                "taxa_conclusao": round(finalizadas.count() / total_osp * 100) if total_osp else 0,
                "mttr_horas": mttr,
                "mtbf_dias": mtbf,
            },
            "custos": {
                "real": float(custos["real"] or 0),
                "estimado": float(custos["estimado"] or 0),
            },
            "evolucao": evolucao,
            "performance": performance,
        })


class PortalVisaoGeralView(APIView):
    """
    Visão geral do Portal do Cliente — Anexo I 2.7.

    Entrega, em linguagem voltada ao cliente, o dashboard personalizado (2.7.1.1.6),
    os indicadores de desempenho do parque (2.7.1.1.7 — incluindo índice de
    disponibilidade, item 2.8.1.1.6) e o histórico de serviços (2.7.1.1.5),
    sempre restrito ao próprio cliente via `escopo_cliente` (somente leitura).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.cadastros.models import Cliente, Equipamento
        from apps.laudos.models import Laudo, StatusLaudo
        from apps.osp.models import STATUS_ABERTOS, OrdemServico

        user = request.user

        # --- Identificação do cliente (cabeçalho do portal) ---
        cliente = (
            Cliente.objects.filter(pk=user.cliente_id).first()
            if user.is_cliente and user.cliente_id
            else None
        )

        # --- Escopos (cliente vê apenas o próprio parque) ---
        equipamentos = escopo_cliente(Equipamento.objects.ativos(), user, "setor__area__cliente")
        inspecoes = escopo_cliente(Inspecao.objects.ativos(), user)
        vib = escopo_cliente(MedicaoVibracao.objects.all(), user, "inspecao__cliente")
        termo = escopo_cliente(MedicaoTermografia.objects.all(), user, "inspecao__cliente")
        tec = escopo_cliente(MedicaoTecnica.objects.all(), user, "inspecao__cliente")
        osps = escopo_cliente(OrdemServico.objects.all(), user)
        laudos = escopo_cliente(
            Laudo.objects.filter(status=StatusLaudo.EMITIDO).select_related("inspecao__cliente"),
            user, "inspecao__cliente",
        )

        # --- Equipamentos que requerem atenção (com medição crítica) ---
        atencao: dict = {}
        for qs in (vib, termo, tec):
            for row in (
                qs.filter(criticidade="CRITICO")
                .values("equipamento__tag", "equipamento__nome")
                .annotate(ocorrencias=Count("id"))
            ):
                chave = row["equipamento__tag"]
                if chave not in atencao:
                    atencao[chave] = {**row}
                else:
                    atencao[chave]["ocorrencias"] += row["ocorrencias"]
        equipamentos_atencao = sorted(
            atencao.values(), key=lambda r: r["ocorrencias"], reverse=True
        )

        total_equip = equipamentos.count()
        em_atencao = len(equipamentos_atencao)
        # Índice de disponibilidade (item 2.8.1.1.6): % do parque sem ocorrência crítica.
        disponibilidade = (
            round((total_equip - em_atencao) / total_equip * 100, 1) if total_equip else 100.0
        )

        # --- Histórico de serviços (item 2.7.1.1.5) — consolidado e ordenado ---
        historico: list = []
        for laudo in laudos.order_by("-data_emissao")[:10]:
            historico.append({
                "tipo": "laudo",
                "titulo": f"Laudo {laudo.numero}",
                "descricao": laudo.titulo,
                "data": laudo.data_emissao,
                "status": laudo.get_status_display(),
                "criticidade": laudo.criticidade_geral or "",
                "url": f"/laudos/{laudo.id}",
            })
        for insp in inspecoes.order_by("-data")[:10]:
            historico.append({
                "tipo": "inspecao",
                "titulo": f"Inspeção — {insp.get_tipo_analise_display()}",
                "descricao": insp.observacoes[:120],
                "data": insp.data,
                "status": insp.get_status_display(),
                "criticidade": "",
                "url": f"/inspecoes/{insp.id}",
            })
        for osp in osps.select_related("equipamento").order_by("-criado_em")[:10]:
            historico.append({
                "tipo": "osp",
                "titulo": f"OSP {osp.numero}",
                "descricao": f"{osp.equipamento.tag} — {osp.titulo}",
                "data": osp.criado_em,
                "status": osp.get_status_display(),
                "criticidade": osp.criticidade_origem or "",
                "url": "/osps",
            })

        # Datas e datetimes coexistem; normaliza para `date` apenas na ordenação.
        def _chave_data(item):
            d = item["data"]
            return d.date() if hasattr(d, "date") else d

        historico.sort(key=_chave_data, reverse=True)

        return Response({
            "cliente": (
                {
                    "nome": cliente.nome,
                    "unidade_negocio": cliente.unidade_negocio,
                    "cidade_uf": cliente.cidade_uf,
                }
                if cliente
                else None
            ),
            "indicadores": {
                "equipamentos_monitorados": total_equip,
                "equipamentos_atencao": em_atencao,
                "indice_disponibilidade": disponibilidade,
                "inspecoes": inspecoes.count(),
                "osps_abertas": osps.filter(status__in=STATUS_ABERTOS).count(),
                "laudos_disponiveis": laudos.count(),
            },
            "equipamentos_atencao": equipamentos_atencao[:8],
            "historico": historico[:12],
        })
