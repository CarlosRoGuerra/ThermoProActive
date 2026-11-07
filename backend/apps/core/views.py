from rest_framework import serializers, viewsets

from apps.accounts.permissions import IsMaster
from apps.core.models import RegistroAuditoria


class RegistroAuditoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegistroAuditoria
        fields = ["id", "criado_em", "usuario", "usuario_email", "ip", "metodo", "caminho",
                  "acao", "modelo", "objeto_id", "alteracoes"]


class RegistroAuditoriaViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Item 3.1.22 — consulta da trilha de auditoria. Só Master interno (nunca cliente).
    Filtros: modelo, acao, usuario, objeto_id, e intervalo `criado_em__gte/__lte`.
    Retenção: `manage.py purgar_auditoria` (AUDITORIA_RETENCAO_DIAS).
    """

    serializer_class = RegistroAuditoriaSerializer
    permission_classes = [IsMaster]
    filterset_fields = ["modelo", "acao", "usuario", "objeto_id", "criado_em"]
    ordering_fields = ["criado_em"]

    def get_queryset(self):
        return RegistroAuditoria.objects.select_related("usuario")


