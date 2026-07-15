from rest_framework import serializers

from .models import OrdemServico


class OrdemServicoSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True)
    equipamento_tag = serializers.CharField(source="equipamento.tag", read_only=True)
    responsavel_nome = serializers.CharField(source="responsavel.nome", read_only=True, default=None)
    prioridade_display = serializers.CharField(source="get_prioridade_display", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    sla_vencido = serializers.BooleanField(read_only=True)

    class Meta:
        model = OrdemServico
        fields = [
            "id", "numero", "cliente", "cliente_nome", "equipamento", "equipamento_tag",
            "inspecao", "titulo", "descricao", "prioridade", "prioridade_display",
            "status", "status_display", "criticidade_origem", "gerada_automaticamente",
            "responsavel", "responsavel_nome", "sla_data", "sla_vencido",
            "custo_estimado", "custo_real", "finalizada_em", "criado_em",
        ]
        read_only_fields = ["numero", "gerada_automaticamente", "criticidade_origem", "finalizada_em"]


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrdemServico._meta.get_field("status").choices)
