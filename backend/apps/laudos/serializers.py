from rest_framework import serializers

from .models import Laudo


class LaudoSerializer(serializers.ModelSerializer):
    inspecao_id = serializers.IntegerField(source="inspecao.id", read_only=True)
    cliente_nome = serializers.CharField(source="inspecao.cliente.nome", read_only=True)
    responsavel_nome = serializers.CharField(source="responsavel.nome", read_only=True)
    responsavel_conselho = serializers.CharField(source="responsavel.conselho_classe", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Laudo
        fields = [
            "id", "numero", "versao", "inspecao", "inspecao_id", "cliente_nome",
            "titulo", "criticidade_geral", "diagnostico", "recomendacoes",
            "conclusao", "responsavel", "responsavel_nome", "responsavel_conselho",
            "status", "status_display", "data_emissao", "criado_em",
        ]
        read_only_fields = ["numero", "data_emissao"]


class GerarLaudoSerializer(serializers.Serializer):
    inspecao = serializers.IntegerField(help_text="ID da inspeção de origem.")
