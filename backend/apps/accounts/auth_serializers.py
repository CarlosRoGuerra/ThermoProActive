import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Convite,
    EstadoConta,
    FinalidadeToken,
    Perfil,
    PERFIS_CLIENTE,
    PERFIS_INTERNOS,
    SolicitacaoAcesso,
)
from .security import hash_opaco, localizar_token
from .serializers import UserSerializer

User = get_user_model()


def validar_senha_forte(senha: str, usuario=None):
    if len(senha) < 15:
        raise serializers.ValidationError("Use pelo menos 15 caracteres.")
    if len(senha) > 128:
        raise serializers.ValidationError("Use no máximo 128 caracteres.")
    try:
        validate_password(senha, user=usuario)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return senha


def cnpj_valido(valor: str) -> bool:
    numeros = re.sub(r"\D", "", valor or "")
    if len(numeros) != 14 or numeros == numeros[0] * 14:
        return False
    for tamanho in (12, 13):
        pesos = list(range(tamanho - 7, 1, -1)) + list(range(9, 1, -1))
        soma = sum(int(n) * p for n, p in zip(numeros[:tamanho], pesos))
        digito = 11 - (soma % 11)
        digito = 0 if digito >= 10 else digito
        if int(numeros[tamanho]) != digito:
            return False
    return True


class LoginContextualSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)
    lembrar = serializers.BooleanField(default=False)
    codigo_mfa = serializers.CharField(required=False, allow_blank=True, max_length=24)

    def validate(self, attrs):
        request = self.context["request"]
        usuario = authenticate(request=request, email=attrs["email"].lower(), password=attrs["password"])
        if not usuario:
            raise serializers.ValidationError("E-mail ou senha incorretos.", code="invalid_credentials")
        if usuario.estado != EstadoConta.ACTIVE or not usuario.is_active:
            raise serializers.ValidationError("E-mail ou senha incorretos.", code="invalid_credentials")
        attrs["usuario"] = usuario
        return attrs


class EsqueciSenhaSerializer(serializers.Serializer):
    email = serializers.EmailField()


class RedefinirSenhaSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=256)
    nova_senha = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        registro = localizar_token(attrs["token"], FinalidadeToken.RESET_PASSWORD)
        if not registro or registro.usado_em or registro.expira_em <= timezone.now():
            raise serializers.ValidationError({"token": "Este link não é mais válido."})
        attrs["registro"] = registro
        attrs["nova_senha"] = validar_senha_forte(attrs["nova_senha"], registro.usuario)
        return attrs


class AlterarSenhaSerializer(serializers.Serializer):
    senha_atual = serializers.CharField(trim_whitespace=False)
    nova_senha = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        usuario = self.context["request"].user
        if not usuario.check_password(attrs["senha_atual"]):
            raise serializers.ValidationError({"senha_atual": "A senha atual está incorreta."})
        attrs["nova_senha"] = validar_senha_forte(attrs["nova_senha"], usuario)
        return attrs


class SolicitacaoAcessoSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitacaoAcesso
        fields = [
            "nome", "email", "telefone", "razao_social", "nome_fantasia", "cnpj",
            "segmento", "telefone_empresa", "email_empresa", "quantidade_equipamentos",
            "cargo", "aceitou_termos", "aceita_marketing",
        ]

    def validate_cnpj(self, valor):
        if not cnpj_valido(valor):
            raise serializers.ValidationError("Informe um CNPJ válido.")
        return valor

    def validate_aceitou_termos(self, valor):
        if not valor:
            raise serializers.ValidationError("Você precisa aceitar os Termos de Uso.")
        return valor

    def validate(self, attrs):
        email = attrs.get("email", "").lower()
        if SolicitacaoAcesso.objects.filter(email=email, status=SolicitacaoAcesso.Status.PENDING).exists():
            raise serializers.ValidationError({"email": "Já existe uma solicitação em análise para este e-mail."})
        attrs["email"] = email
        return attrs


class CriarConviteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Convite
        fields = ["nome", "email", "tipo", "perfil", "nivel", "empresa", "cliente"]

    def validate(self, attrs):
        tipo = attrs.get("tipo")
        perfil = attrs.get("perfil")
        if tipo == Convite.Tipo.ADMIN and perfil not in PERFIS_INTERNOS:
            raise serializers.ValidationError({"perfil": "Selecione um perfil interno."})
        if tipo == Convite.Tipo.PORTAL and perfil not in PERFIS_CLIENTE:
            raise serializers.ValidationError({"perfil": "Selecione um perfil de cliente."})
        if tipo == Convite.Tipo.ADMIN and attrs.get("cliente"):
            raise serializers.ValidationError({"cliente": "Convites administrativos não vinculam um cliente."})
        if tipo == Convite.Tipo.PORTAL and not attrs.get("cliente"):
            raise serializers.ValidationError({"cliente": "Selecione a organização do convidado."})
        email = attrs.get("email", "").lower()
        if User.objects.filter(email=email).exists():
            raise serializers.ValidationError({"email": "Já existe uma conta com este e-mail."})
        attrs["email"] = email
        return attrs


class AceitarConviteSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=256)
    senha = serializers.CharField(trim_whitespace=False)
    aceitou_termos = serializers.BooleanField()

    def validate(self, attrs):
        convite = Convite.objects.select_related("empresa", "cliente").filter(
            token_hash=hash_opaco(attrs["token"])
        ).first()
        if not convite or convite.aceito_em or convite.revogado_em or convite.expira_em <= timezone.now():
            raise serializers.ValidationError({"token": "Este convite não é mais válido."})
        if not attrs["aceitou_termos"]:
            raise serializers.ValidationError({"aceitou_termos": "Aceite os Termos de Uso para continuar."})
        attrs["senha"] = validar_senha_forte(attrs["senha"])
        attrs["convite"] = convite
        return attrs


class ConfirmarEmailSerializer(serializers.Serializer):
    token = serializers.CharField(min_length=32, max_length=256)


class ConfirmarMFASerializer(serializers.Serializer):
    codigo = serializers.CharField(min_length=6, max_length=24)
    senha = serializers.CharField(required=False, trim_whitespace=False)
