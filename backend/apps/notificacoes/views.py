from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notificacao, PreferenciaNotificacao
from .serializers import NotificacaoSerializer, PreferenciaNotificacaoSerializer


class NotificacaoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cada usuário enxerga apenas as próprias notificações (item 2.10.1.4)."""

    serializer_class = NotificacaoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["lida", "evento", "nivel"]

    def get_queryset(self):
        return Notificacao.objects.filter(destinatario=self.request.user)

    @action(detail=False, methods=["get"])
    def resumo(self, request):
        """Contador de não lidas — para o badge do frontend."""
        return Response({"nao_lidas": self.get_queryset().filter(lida=False).count()})

    @action(detail=True, methods=["post"])
    def lida(self, request, pk=None):
        notif = self.get_object()
        notif.marcar_lida()
        return Response(NotificacaoSerializer(notif).data)

    @action(detail=False, methods=["post"], url_path="marcar-todas")
    def marcar_todas(self, request):
        atualizadas = self.get_queryset().filter(lida=False).update(
            lida=True, lida_em=timezone.now()
        )
        return Response({"marcadas": atualizadas})

    @action(detail=False, methods=["get", "put"], url_path="preferencias")
    def preferencias(self, request):
        pref, _ = PreferenciaNotificacao.objects.get_or_create(user=request.user)
        if request.method == "PUT":
            serializer = PreferenciaNotificacaoSerializer(pref, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data)
        return Response(PreferenciaNotificacaoSerializer(pref).data)
