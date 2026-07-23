from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    perfil_display = serializers.CharField(source="get_perfil_display", read_only=True)
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)
    is_interno = serializers.BooleanField(read_only=True)
    is_cliente = serializers.BooleanField(read_only=True)
    # Hierarquia definida com o cliente: ambiente (BackEnd/FrontEnd) × nível.
    ambiente = serializers.CharField(read_only=True)
    grupo_acesso = serializers.CharField(read_only=True)
    is_master = serializers.BooleanField(read_only=True)
    pode_excluir = serializers.BooleanField(read_only=True)
    pode_curar_dados_sistema = serializers.BooleanField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "nome", "perfil", "perfil_display",
            "nivel", "nivel_display", "ambiente", "grupo_acesso",
            "is_interno", "is_cliente", "is_master", "pode_excluir",
            "pode_curar_dados_sistema", "empresa", "cliente",
            "celular", "cargo", "conselho_classe", "is_active",
        ]
        read_only_fields = ["id"]


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=6)

    class Meta:
        model = User
        fields = [
            "id", "email", "nome", "perfil", "nivel", "password",
            "empresa", "cliente", "celular", "cpf", "cargo",
            "conselho_classe", "is_active",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        user = User(**validated_data)
        user.set_password(password or get_random_string(12))
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class LoginSerializer(TokenObtainPairSerializer):
    """JWT (item 2.1.1.3) que retorna também os dados do usuário autenticado."""

    username_field = User.USERNAME_FIELD

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
