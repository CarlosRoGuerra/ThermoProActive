from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from rest_framework.response import Response

from .models import EventoPreditivo, Notificacao, PreferenciaNotificacao
from .serializers import EventoPreditivoSerializer, NotificacaoSerializer, PreferenciaNotificacaoSerializer


class NotificacaoViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Cada usuário enxerga apenas as próprias notificações (item 2.10.1.4)."""

    serializer_class = NotificacaoSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["lida", "evento", "nivel"]

    def get_queryset(self):
        from django.db.models import Q
        from apps.core.escopo import setores_restritos
        qs = Notificacao.objects.filter(destinatario=self.request.user).prefetch_related("entregas")
        # 2.1.1.6: cliente com restrição de setor não recebe aviso de equipamento de outro setor.
        # Aviso sem equipamento (ex.: sistema) continua visível.
        ids = setores_restritos(self.request.user)
        if ids is not None:
            qs = qs.filter(Q(evento_preditivo__isnull=True) | Q(evento_preditivo__equipamento__setor__in=ids))
        return qs

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


class EventoPreditivoViewSet(viewsets.ReadOnlyModelViewSet):
    """Evidência da transição, limitada ao cliente da inspeção; não reprocessa."""

    permission_classes = [IsAuthenticated]
    serializer_class = EventoPreditivoSerializer
    filterset_fields = ["inspecao", "equipamento", "medicao_tipo", "medicao_id", "criticidade"]

    def get_queryset(self):
        from apps.coletas.views import escopo_cliente
        from apps.core.escopo import restringe_setor
        qs = escopo_cliente(EventoPreditivo.objects.select_related("inspecao", "equipamento", "osp"),
                            self.request.user, "inspecao__cliente")
        return restringe_setor(qs, self.request.user, "equipamento__setor")


class PushChaveView(APIView):
    """Chave pública VAPID para o navegador assinar o push. `configurado` = o canal está pronto."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.conf import settings
        from .channels import push_configurado
        configurado, faltando = push_configurado()
        return Response({"chave": settings.VAPID_PUBLIC_KEY if configurado else "",
                         "configurado": configurado, "faltando": faltando})


class PushAssinaturaView(APIView):
    """
    Registra (POST) ou remove (DELETE) a assinatura de push do dispositivo ATUAL do usuário.
    POST: {"endpoint": ..., "keys": {"p256dh": ..., "auth": ...}}. Só para o próprio usuário.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from .models import AssinaturaPush
        endpoint = str(request.data.get("endpoint", ""))[:500]
        chaves = request.data.get("keys") or {}
        p256dh, auth = str(chaves.get("p256dh", ""))[:200], str(chaves.get("auth", ""))[:100]
        if not (p256dh and auth):
            return Response({"detail": "Assinatura de push incompleta."}, status=400)
        # V-01: só serviços de push conhecidos, sem IP literal, credenciais ou porta fora do padrão.
        from .seguranca_push import EndpointNaoPermitido, validar_endpoint
        try:
            validar_endpoint(endpoint)
        except EndpointNaoPermitido:
            return Response({"detail": "Endpoint de push não permitido."}, status=400)
        assinatura, _ = AssinaturaPush.objects.update_or_create(
            endpoint=endpoint,
            defaults={"usuario": request.user, "p256dh": p256dh, "auth": auth, "ativa": True,
                      "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]},
        )
        return Response({"id": assinatura.pk, "ativa": True}, status=201)

    def delete(self, request):
        from .models import AssinaturaPush
        endpoint = str(request.data.get("endpoint", ""))[:500]
        AssinaturaPush.objects.filter(usuario=request.user, endpoint=endpoint).delete()
        return Response(status=204)
