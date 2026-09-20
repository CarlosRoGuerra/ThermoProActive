from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Convite, SolicitacaoAcesso

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
    mfa_ativo = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "nome", "perfil", "perfil_display",
            "nivel", "nivel_display", "ambiente", "grupo_acesso",
            "is_interno", "is_cliente", "is_master", "pode_excluir",
            "pode_curar_dados_sistema", "empresa", "cliente",
            "celular", "cargo", "conselho_classe", "is_active",
            "estado", "email_verificado_em", "exigir_troca_senha",
            "mfa_obrigatorio", "mfa_ativo",
        ]
        read_only_fields = ["id"]

    def get_mfa_ativo(self, obj):
        dispositivo = getattr(obj, "mfa", None)
        return bool(dispositivo and dispositivo.ativo)


class UserWriteSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False, min_length=15)

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


class ConvitePendenteSerializer(serializers.ModelSerializer):
    """Convite ainda não aceito — pra quem convidou acompanhar quem falta criar a senha."""

    perfil_display = serializers.CharField(source="get_perfil_display", read_only=True)
    nivel_display = serializers.CharField(source="get_nivel_display", read_only=True)
    expirado = serializers.SerializerMethodField()

    class Meta:
        model = Convite
        fields = ["id", "nome", "email", "perfil", "perfil_display", "nivel", "nivel_display",
                   "criado_em", "expira_em", "expirado"]

    def get_expirado(self, obj) -> bool:
        from django.utils import timezone
        return obj.expira_em <= timezone.now()


class SolicitacaoAcessoListSerializer(serializers.ModelSerializer):
    """
    Leitura, para o Master revisar o pedido comercial (formulário público
    /portal/cadastro). Aprovar/recusar aqui NUNCA cria cliente ou usuário —
    é só a decisão de negócio; o cadastro em si continua sendo feito à mão em
    Clientes → Novo cliente, e o acesso por um convite, do jeito que já existia.
    """

    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = SolicitacaoAcesso
        fields = [
            "id", "nome", "email", "telefone", "razao_social", "nome_fantasia", "cnpj",
            "segmento", "telefone_empresa", "email_empresa", "quantidade_equipamentos",
            "cargo", "aceitou_termos", "aceita_marketing", "status", "status_display",
            "criado_em",
        ]
        read_only_fields = fields
