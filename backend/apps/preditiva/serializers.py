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
