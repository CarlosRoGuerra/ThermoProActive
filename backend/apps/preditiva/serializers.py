from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import (
    AceitacaoSugestao,
    ConfiguracaoTendencia,
    LimiteAlarmeSerie,
    MatrizRisco,
    RegraSugestao,
)

CAMPOS_AUDITORIA = ["ativo", "criado_em", "atualizado_em"]


class CadastroPreditivoSerializer(serializers.ModelSerializer):
    """Roda `Model.clean()` sobre o estado resultante, para as mesmas regras valerem na API e no admin."""

    def validate(self, attrs):
        instancia = self.instance or self.Meta.model()
        for campo, valor in attrs.items():
            setattr(instancia, campo, valor)
        try:
            instancia.clean()
        except DjangoValidationError as erro:
            if hasattr(erro, "error_dict"):
                raise serializers.ValidationError(erro.message_dict)
            raise serializers.ValidationError(erro.messages)
        return attrs


class ConfiguracaoTendenciaSerializer(CadastroPreditivoSerializer):
    class Meta:
        model = ConfiguracaoTendencia
        exclude = CAMPOS_AUDITORIA


class LimiteAlarmeSerieSerializer(CadastroPreditivoSerializer):
    # Rótulos e nome do cliente para a tabela de cadastro (a tela lista esses campos).
    modalidade_display = serializers.CharField(source="get_modalidade_display", read_only=True)
    sistema_display = serializers.CharField(source="get_sistema_display", read_only=True)
    sentido_display = serializers.CharField(source="get_sentido_display", read_only=True)
    origem_display = serializers.CharField(source="get_origem_display", read_only=True)
    validacao_display = serializers.CharField(source="get_validacao_display", read_only=True)
    cliente_nome = serializers.CharField(source="cliente.nome", read_only=True, default=None)

    class Meta:
        model = LimiteAlarmeSerie
        exclude = CAMPOS_AUDITORIA


class MatrizRiscoSerializer(CadastroPreditivoSerializer):
    class Meta:
        model = MatrizRisco
        exclude = CAMPOS_AUDITORIA


class RegraSugestaoSerializer(CadastroPreditivoSerializer):
    class Meta:
        model = RegraSugestao
        exclude = CAMPOS_AUDITORIA


class AceitacaoSugestaoSerializer(serializers.ModelSerializer):
    """Decisão do analista. A validação de existência da sugestão é feita em `sugestoes.registrar_decisao`."""

    class Meta:
        model = AceitacaoSugestao
        fields = ["id", "achado", "recomendacao_sugerida", "origem", "regra", "decisao",
                  "recomendacao_final", "justificativa", "evidencia", "usuario", "criado_em"]
        read_only_fields = ["id", "regra", "evidencia", "usuario", "criado_em"]
