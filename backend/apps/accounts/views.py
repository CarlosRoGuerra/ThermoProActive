from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .permissions import IsAdmin
from .serializers import LoginSerializer, UserSerializer, UserWriteSerializer

User = get_user_model()


class LoginView(TokenObtainPairView):
    """POST e-mail+senha → access/refresh + dados do usuário (item 2.1.1.3)."""

    serializer_class = LoginSerializer


class MeView(APIView):
    """Dados do usuário autenticado (para o front montar menu por perfil)."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    """CRUD de usuários — somente Administrador (item 2.1.1.4 / 2.1.2.1)."""

    queryset = User.objects.all().order_by("nome")
    permission_classes = [IsAdmin]
    filterset_fields = ["perfil", "is_active", "empresa", "cliente"]
    search_fields = ["nome", "email", "cpf"]

    def get_serializer_class(self):
        if self.action in ("list", "retrieve"):
            return UserSerializer
        return UserWriteSerializer
