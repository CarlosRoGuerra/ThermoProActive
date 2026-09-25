from collections import defaultdict

from django.db import transaction
from django.db.models import Count, Max, Q, Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
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
    CondicaoEmLoteSerializer,
    InspecaoListSerializer,
    InspecaoSerializer,
    ItemInspecaoSerializer,
    MedicaoTecnicaSerializer,
    MedicaoTermografiaSerializer,
    MedicaoVibracaoSerializer,
    RelatorioSerializer,
)


def escopo_cliente(qs, user, campo_cliente="cliente"):
    """
    Perfis cliente só enxergam dados do próprio cliente (Portal — item 2.7).
    Falha fechada: cliente sem `cliente_id` (conta mal configurada) não vê nada,
    em vez de cair no `qs` inteiro sem filtro — mesma regra do multi-tenant em
    `apps.cadastros.views.BaseCadastroViewSet`.
    """
    if user.is_cliente:
        if not user.cliente_id:
            return qs.none()
        return qs.filter(**{campo_cliente: user.cliente_id})
    return qs


def recorte_cliente(qs, request, campo_cliente="cliente"):
    """
    `escopo_cliente` (segurança) + recorte opcional pelo CLIENTE ATIVO (UX).

    O painel da equipe interna trabalha "dentro" de um cliente quando o analista
    ativa um na barra lateral; sem nenhum ativado, ele mostra a operação inteira.
    O front manda essa escolha em `?cliente=<id>`.

    A ordem importa: o escopo de segurança vem PRIMEIRO e o recorte só estreita
    o que sobrou. Assim um usuário do Portal que mande `?cliente=<de outro>` não
    amplia nada — recebe conjunto vazio, nunca dado alheio.
    """
    qs = escopo_cliente(qs, request.user, campo_cliente)
    escolhido = request.query_params.get("cliente")
    if escolhido and str(escolhido).isdigit():
        qs = qs.filter(**{campo_cliente: int(escolhido)})
    return qs


def impedir_cross_tenant(user, validated_data, campo, resto=None):
    """
    Contraparte de `escopo_cliente` para escrita: `get_queryset()` só protege
    ler/editar um registro que já existe — nada impede o Master de um cliente
    CRIAR um novo apontando um campo-âncora (`campo`) de OUTRO cliente (ex.:
    uma Inspeção com `cliente` alheio, ou uma Medição com `inspecao` alheia).

    `campo` é a chave em `validated_data`; `resto` é o caminho ORM daquele
    valor até `cliente_id`, igual ao segundo argumento de `escopo_cliente`
    (`None` quando o próprio campo já É o cliente, ex.: Inspecao.cliente).
    Não faz nada para interno — ele pode apontar para qualquer cliente.
    """
    if not (user.is_cliente and user.cliente_id):
        return
    if campo not in validated_data:
        return
    valor = validated_data[campo]
    pk_valor = getattr(valor, "pk", valor)
    if resto:
        ok = valor.__class__.objects.filter(pk=pk_valor, **{resto: user.cliente_id}).exists()
    else:
        ok = pk_valor == user.cliente_id
    if not ok:
        raise ValidationError({campo: "Isso não pertence à sua empresa."})


class InspecaoViewSet(viewsets.ModelViewSet):
    # Lançar medição é trabalho técnico da CONTRATADA; o cliente consulta o
    # resultado (decisão de 2026-09-21). As guardas de escrita cross-tenant
    # abaixo continuam valendo para o caso de a regra voltar a afrouxar.
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

    def perform_create(self, serializer):
        impedir_cross_tenant(self.request.user, serializer.validated_data, "cliente")
        serializer.save()

    def perform_update(self, serializer):
        impedir_cross_tenant(self.request.user, serializer.validated_data, "cliente")
        serializer.save()


class _MedicaoViewSetBase(viewsets.ModelViewSet):
    """
    As três medições (Vibração/Termografia/Técnica) compartilham a mesma regra
    de tenant: a âncora é `inspecao`, e o `equipamento` referenciado também
    precisa ser do mesmo cliente (senão a resposta vazaria TAG/nome de
    equipamento alheio numa Inspeção legítima do cliente).
    """

    def perform_create(self, serializer):
        self._impedir_cross_tenant(serializer.validated_data)
        serializer.save()

    def perform_update(self, serializer):
        self._impedir_cross_tenant(serializer.validated_data)
        serializer.save()

    def _impedir_cross_tenant(self, validated_data):
        user = self.request.user
        impedir_cross_tenant(user, validated_data, "inspecao", resto="cliente")
        impedir_cross_tenant(user, validated_data, "equipamento", resto="setor__area__cliente")


class MedicaoVibracaoViewSet(_MedicaoViewSetBase):
    serializer_class = MedicaoVibracaoSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["inspecao", "equipamento", "criticidade", "zona_iso", "direcao"]
    ordering_fields = ["data_hora", "velocidade_rms"]

    def get_queryset(self):
        qs = MedicaoVibracao.objects.select_related(
            "equipamento", "componente", "instrumento", "inspecao"
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")


class MedicaoTermografiaViewSet(_MedicaoViewSetBase):
    serializer_class = MedicaoTermografiaSerializer
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["inspecao", "equipamento", "criticidade", "sistema"]
    ordering_fields = ["data_hora", "delta_t"]

    def get_queryset(self):
        qs = MedicaoTermografia.objects.select_related(
            "equipamento", "componente", "instrumento", "inspecao"
        )
        return escopo_cliente(qs, self.request.user, campo_cliente="inspecao__cliente")


class MedicaoTecnicaViewSet(_MedicaoViewSetBase):
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
        """
        Relatório técnico completo: shell comum (capa, carta, relação de
        equipamentos) + a parte do módulo técnico da tecnologia (KPIs e fichas).
        Montagem em `apps.coletas.relatorio_tecnico`.
        """
        from .relatorio_tecnico import montar_dossie

        return Response(montar_dossie(self.get_object(), request))

    @action(detail=True, methods=["get"], url_path="carta-docx")
    def carta_docx(self, request, pk=None):
        """Carta ao Cliente (Seção A) como .docx — documento independente do relatório."""
        from io import BytesIO

        from django.http import HttpResponse

        from apps.cadastros.models import Empresa

        from .carta_docx import construir_carta_docx

        rel = self.get_object()
        prestador = Empresa.objects.ativos().order_by("id").first()
        doc = construir_carta_docx(rel, prestador)
        buf = BytesIO()
        doc.save(buf)
        buf.seek(0)

        base = f"Carta_{rel.numero}_{rel.cliente.nome}"
        seguro = "".join(c if c.isalnum() or c in "-_." else "_" for c in base)
        resp = HttpResponse(
            buf.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        resp["Content-Disposition"] = f'attachment; filename="{seguro}.docx"'
        return resp


class CarregamentoViewSet(viewsets.ModelViewSet):
    """Análise de campo: "carregar rota", listar itens e transferir."""

    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = ["cliente", "tecnologia", "status", "analista", "rota", "relatorio"]
    search_fields = ["relatorio__numero"]
    ordering_fields = ["data_coleta", "criado_em"]

    def get_queryset(self):
        # Inclui carregamentos de manutenção corretiva (tipo_corretiva preenchido) — a
        # Análise de campo é o único ponto de entrada para os dois fluxos.
        qs = (
            Carregamento.objects.ativos()
            .select_related("cliente", "tecnologia", "relatorio", "rota", "instrumento", "analista")
        )

        if self.action == "list":
            # A listagem só precisa de CONTAGENS. Carregar itens, condições,
            # achados e imagens para depois contá-los em Python custava uma
            # consulta por linha (e trazia as imagens de toda a rota à toa).
            # Com anotação, é uma consulta só para a página inteira.
            qs = qs.annotate(
                _qtd_itens=Count("itens", distinct=True),
                _qtd_pendentes=Count(
                    "itens", filter=Q(itens__condicao__isnull=True), distinct=True
                ),
                _qtd_achados=Count("itens__achados", distinct=True),
            )
        else:
            # No detalhe a folha de campo precisa da árvore inteira. Tipo do
            # equipamento e serviço corretivo entram aqui porque o
            # ItemInspecaoSerializer lê os dois — fora do prefetch eram duas
            # consultas POR equipamento (N+1), e esta é a leitura que a folha
            # de campo refaz depois de cada alteração.
            qs = qs.prefetch_related(
                "itens__equipamento__setor__area", "itens__equipamento__tipo_equipamento",
                "itens__condicao", "itens__achados__imagens", "itens__servico_corretivo",
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

    @action(detail=True, methods=["post"], url_path="definir-condicao")
    @transaction.atomic
    def definir_condicao(self, request, pk=None):
        """
        Lançamento em lote da folha de campo: UMA condição para vários itens.

        É o "marcar estes 30 como OK" — uma requisição e uma escrita, em vez de
        30 PATCH em /itens-inspecao/. Devolve os itens no mesmo formato de
        `CarregamentoSerializer.itens`, para a tela trocar só essas linhas.
        """
        carregamento = self.get_object()
        if carregamento.status != StatusCarregamento.EM_CAMPO:
            return Response(
                {"detail": "Esta rota já foi transferida ou descartada."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entrada = CondicaoEmLoteSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        ids = set(entrada.validated_data["itens"])
        alvo = ItemInspecao.objects.ativos().filter(carregamento=carregamento, pk__in=ids)
        if alvo.count() != len(ids):
            raise ValidationError({"itens": "Há equipamentos que não pertencem a esta rota."})
        # update() não passa por save(): o auto_now de `atualizado_em` vai à mão.
        alvo.update(condicao=entrada.validated_data["condicao"], atualizado_em=timezone.now())
        itens = (
            ItemInspecao.objects.filter(pk__in=ids)
            .select_related(
                "equipamento__setor__area", "equipamento__tipo_equipamento",
                "condicao", "carregamento", "servico_corretivo",
            )
            .prefetch_related("achados__imagens")
        )
        return Response(ItemInspecaoSerializer(itens, many=True).data)

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
            .select_related(
                "equipamento__setor__area", "equipamento__tipo_equipamento",
                "condicao", "carregamento", "servico_corretivo",
            )
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
    # Diagnosticar e confirmar a análise é responsabilidade técnica da
    # CONTRATADA; o cliente lê o que foi diagnosticado (decisão de 2026-09-21).
    # Achados de manutenção corretiva continuam fora do alcance deste endpoint
    # genérico — ver `AchadoSerializer.validate_item` e `perform_destroy`
    # abaixo, que já bloqueiam isso independente de quem pede.
    permission_classes = [InternoEditaClienteVisualiza]
    filterset_fields = [
        "item", "item__carregamento", "item__carregamento__cliente",
        "item__carregamento__status", "item__carregamento__tecnologia",
        "confirmada", "visivel_cliente",
    ]
    ordering_fields = ["criado_em", "numero_osp"]

    def get_queryset(self):
        # Inclui achados de manutenção corretiva (ex.: análise técnica de balanceamento)
        # para que apareçam na Análise final — a criação/edição dos campos técnicos
        # especializados continua restrita a /atividades-corretivas/.../balanceamento
        # (AchadoSerializer.validate_item bloqueia criar/realocar achados corretivos
        # por este endpoint genérico).
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

    def perform_destroy(self, instance):
        # Achado de manutenção corretiva é a análise técnica de um ServicoCampo
        # (OneToOne, on_delete=PROTECT) — remover por aqui derrubaria a exclusão com um
        # erro de integridade. Mesmo estilo de guarda de ServicoCampoViewSet.perform_destroy.
        if getattr(instance, "balanceamento_tecnico", None) is not None:
            raise ValidationError(
                "Esta análise está vinculada a uma atividade de manutenção corretiva; "
                "não pode ser removida por aqui."
            )
        super().perform_destroy(instance)


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
    """
    Indicadores operacionais — Anexo I 2.8.1.1 (vibração + termografia).

    Aceita `?cliente=<id>`: com um cliente ativado na barra lateral, o painel
    mostra só a operação dele; sem nenhum, mostra o todo (ver `recorte_cliente`).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        inspecoes = recorte_cliente(Inspecao.objects.ativos(), request)
        vib = recorte_cliente(
            MedicaoVibracao.objects.all(), request, campo_cliente="inspecao__cliente"
        )
        termo = recorte_cliente(
            MedicaoTermografia.objects.all(), request, campo_cliente="inspecao__cliente"
        )
        tec = recorte_cliente(
            MedicaoTecnica.objects.all(), request, campo_cliente="inspecao__cliente"
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

        osps = recorte_cliente(OrdemServico.objects.all(), request)

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
    """
    Dashboard executivo — Anexo I 2.8.1.2 (KPIs, custos, MTBF, MTTR, evolução).

    Aceita `?cliente=<id>` igual ao painel operacional: com cliente ativado, os
    KPIs e a "performance por unidade" falam só dele; sem nenhum, falam do todo.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.cadastros.models import Cliente
        from apps.osp.models import OrdemServico

        osps = recorte_cliente(OrdemServico.objects.all(), request)
        vib = recorte_cliente(MedicaoVibracao.objects.all(), request, "inspecao__cliente")
        termo = recorte_cliente(MedicaoTermografia.objects.all(), request, "inspecao__cliente")
        tec = recorte_cliente(MedicaoTecnica.objects.all(), request, "inspecao__cliente")

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
        # Com cliente ativado a tabela fica com uma linha só (a dele); sem
        # nenhum, compara todas as unidades.
        performance = []
        for c in recorte_cliente(Cliente.objects.ativos(), request, "id"):
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

        # --- Estado atual por equipamento (para a lista do Portal) ---
        # O Portal precisa dizer COMO está cada máquina, não só quais estão
        # críticas. Sem isto a tela teria de inventar um estado (ou mostrar
        # "normal" para equipamento nunca medido, o que é falso).
        # Uma agregação por (tag, criticidade) nas três origens de medição, e a
        # pior criticidade é resolvida em Python — `Max` num CharField ordenaria
        # alfabeticamente e "NORMAL" venceria "CRITICO".
        RANK = {"CRITICO": 3, "ALERTA": 2, "NORMAL": 1, "": 0}
        estado_por_tag: dict = {}
        for qs in (vib, termo, tec):
            for row in (
                qs.values("equipamento__tag", "criticidade")
                .annotate(total=Count("id"), ultima=Max("data_hora"))
            ):
                tag = row["equipamento__tag"]
                atual = estado_por_tag.setdefault(
                    tag, {"criticidade": "", "medicoes": 0, "ultima_medicao": None}
                )
                atual["medicoes"] += row["total"]
                if RANK.get(row["criticidade"], 0) > RANK.get(atual["criticidade"], 0):
                    atual["criticidade"] = row["criticidade"]
                if row["ultima"] and (
                    atual["ultima_medicao"] is None or row["ultima"] > atual["ultima_medicao"]
                ):
                    atual["ultima_medicao"] = row["ultima"]

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
            # Mapa TAG → estado atual, consumido pela lista de equipamentos do
            # Portal. Campo aditivo: nada que já existia mudou de forma.
            "estado_equipamentos": estado_por_tag,
            "historico": historico[:12],
        })
