"""Fluxo corretivo sobre o carregamento de rotas já usado pelas inspeções."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.permissions import InternoEditaClienteVisualiza
from apps.cadastros.models import Condicao
from apps.coletas.models import Carregamento, ItemInspecao, StatusCarregamento
from apps.coletas.serializers import CarregamentoSerializer, ItemInspecaoSerializer
from .models import ServicoCampo


class ItemCorretivoSerializer(ItemInspecaoSerializer):
    analise = serializers.IntegerField(source="servico_corretivo.pk", read_only=True, default=None)
    observacoes_analise = serializers.CharField(
        source="servico_corretivo.observacoes", read_only=True, default="",
    )


class AtividadeCorretivaSerializer(CarregamentoSerializer):
    itens = ItemCorretivoSerializer(many=True, read_only=True)

    class Meta(CarregamentoSerializer.Meta):
        read_only_fields = [
            "tipo_corretiva", "analista", "cliente", "relatorio", "status", "transferido_em",
        ]
        extra_kwargs = {
            **CarregamentoSerializer.Meta.extra_kwargs,
            "rota": {"required": True, "allow_null": False},
            "instrumento": {"required": True, "allow_null": False},
        }

    def validate(self, attrs):
        rota = attrs["rota"]
        tecnologia = attrs.get("tecnologia")
        instrumento = attrs["instrumento"]
        data = attrs.get("data_termino_novo")
        if not tecnologia or not tecnologia.ativo or not tecnologia.tipo_corretiva:
            raise serializers.ValidationError({"tecnologia": "Selecione uma tecnologia corretiva cadastrada."})
        if not rota.ativo or not rota.cliente.ativo:
            raise serializers.ValidationError({"rota": "A rota e o cliente devem estar ativos."})
        if rota.tecnologia_id and rota.tecnologia_id != tecnologia.pk:
            raise serializers.ValidationError({"rota": "Rota incompatível com a tecnologia."})
        if not rota.equipamentos.exists():
            raise serializers.ValidationError({"rota": "A rota não possui equipamentos."})
        if rota.equipamentos.exclude(setor__area__cliente=rota.cliente).exists():
            raise serializers.ValidationError({"rota": "Há equipamentos de outro cliente nesta rota."})
        if not instrumento.ativo or not instrumento.tecnologias.filter(pk=tecnologia.pk).exists():
            raise serializers.ValidationError({"instrumento": "Instrumento incompatível com a tecnologia."})
        if data is None or data > timezone.localdate():
            raise serializers.ValidationError({"data_termino_novo": "Informe a data real do ensaio, até hoje."})
        attrs["cliente"] = rota.cliente
        attrs["tipo_corretiva"] = tecnologia.tipo_corretiva
        attrs["data_coleta"] = data
        return super().validate(attrs)

    @transaction.atomic
    def create(self, validated_data):
        # Serializa a geração para o mesmo cliente; o número continua sendo gerado
        # exclusivamente por Relatorio.proximo_numero no serializer compartilhado.
        cliente = validated_data["cliente"]
        type(cliente).objects.select_for_update().get(pk=cliente.pk)
        return super().create(validated_data)


class CondicaoCorretivaSerializer(serializers.Serializer):
    condicao = serializers.PrimaryKeyRelatedField(queryset=Condicao.objects.ativos())


class PreparacaoAnaliseSerializer(serializers.Serializer):
    observacoes = serializers.CharField(allow_blank=True)


class AtividadeCorretivaViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [InternoEditaClienteVisualiza]
    serializer_class = AtividadeCorretivaSerializer
    filterset_fields = ["cliente", "tecnologia", "rota", "analista"]
    ordering_fields = ["data_coleta", "criado_em"]

    def get_queryset(self):
        qs = Carregamento.objects.ativos().exclude(tipo_corretiva="").select_related(
            "cliente", "tecnologia", "relatorio", "rota", "instrumento", "analista",
        ).prefetch_related(
            "itens__equipamento__setor__area", "itens__condicao", "itens__achados",
            "itens__servico_corretivo",
        )
        if self.request.user.is_cliente:
            qs = qs.filter(cliente_id=self.request.user.cliente_id)
        return qs

    def item_da_atividade(self, item_id, *, editar=False):
        atividade = self.get_object()
        if editar and atividade.status != StatusCarregamento.EM_CAMPO:
            raise serializers.ValidationError("Esta atividade não está aberta para edição.")
        # Bloqueio da linha serializa condição e abertura, inclusive cliques concorrentes.
        return get_object_or_404(
            ItemInspecao.objects.select_for_update() if editar else ItemInspecao.objects,
            pk=item_id, carregamento=atividade, ativo=True,
        )

    @action(detail=True, methods=["patch"], url_path=r"itens/(?P<item_id>\d+)/condicao")
    @transaction.atomic
    def condicao(self, request, pk=None, item_id=None):
        item = self.item_da_atividade(item_id, editar=True)
        entrada = CondicaoCorretivaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        item.condicao = entrada.validated_data["condicao"]
        item.save(update_fields=["condicao", "atualizado_em"])
        return Response(ItemCorretivoSerializer(item).data)

    @action(detail=True, methods=["get", "post", "patch"], url_path=r"itens/(?P<item_id>\d+)/analise")
    @transaction.atomic
    def analise(self, request, pk=None, item_id=None):
        item = self.item_da_atividade(item_id, editar=request.method != "GET")
        atividade = item.carregamento
        if request.method == "POST":
            if item.condicao_id is None:
                raise serializers.ValidationError("Selecione a condição do equipamento antes de analisar.")
            servico, _ = ServicoCampo.objects.get_or_create(item=item, defaults={
                "cliente": atividade.cliente, "equipamento": item.equipamento,
                "tipo": atividade.tipo_corretiva, "analista": atividade.analista,
                "instrumento": atividade.instrumento, "relatorio": atividade.relatorio,
                "data_execucao": atividade.data_coleta,
            })
        else:
            servico = get_object_or_404(ServicoCampo, item=item)
        if request.method == "PATCH":
            entrada = PreparacaoAnaliseSerializer(data=request.data)
            entrada.is_valid(raise_exception=True)
            servico.observacoes = entrada.validated_data["observacoes"]
            servico.save(update_fields=["observacoes", "atualizado_em"])
        return Response({
            "id": servico.pk, "atividade": atividade.pk, "item": item.pk,
            "equipamento": item.equipamento_id, "tipo": servico.tipo,
            "observacoes": servico.observacoes,
        })
