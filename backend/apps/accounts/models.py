"""
Usuário e perfis de acesso — Anexo I, item 2.1 (Login e Controle de Acesso).

Os 7 perfis do item 2.1.2 são modelados como choices; permissões finas por módulo
ficam em `apps.accounts.permissions`. Campos da equipe técnica seguem o item 3.1.2.
"""
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import TimeStampedModel

from .managers import UserManager


class Perfil(models.TextChoices):
    # Internos (CONTRATADA)
    ADMIN = "ADMIN", "Administrador"
    GESTOR = "GESTOR", "Gestor/Supervisor"
    TECNICO = "TECNICO", "Técnico/Analista"
    # Clientes (CONTRATANTE) — item 2.1.2.4 a 2.1.2.7
    CLIENTE_CORP = "CLIENTE_CORP", "Cliente — Gestor Corporativo"
    CLIENTE_LOCAL = "CLIENTE_LOCAL", "Cliente — Gestor Local"
    CLIENTE_PCM = "CLIENTE_PCM", "Cliente — PCM"
    CLIENTE_MANUT = "CLIENTE_MANUT", "Cliente — Manutentor"


#: Perfis internos da CONTRATADA (podem registrar coletas/laudos)
PERFIS_INTERNOS = {Perfil.ADMIN, Perfil.GESTOR, Perfil.TECNICO}
#: Perfis do lado do cliente (acesso restrito ao Portal — item 2.7)
PERFIS_CLIENTE = {
    Perfil.CLIENTE_CORP,
    Perfil.CLIENTE_LOCAL,
    Perfil.CLIENTE_PCM,
    Perfil.CLIENTE_MANUT,
}


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Usuário do sistema. Login por e-mail (multiusuário — item 2.1.1.5)."""

    email = models.EmailField("E-mail", unique=True)
    nome = models.CharField("Nome completo", max_length=160)
    perfil = models.CharField(
        "Perfil de acesso", max_length=20, choices=Perfil.choices, default=Perfil.TECNICO
    )

    # Vínculo organizacional (multi-tenant) — escopo de dados por empresa/cliente
    empresa = models.ForeignKey(
        "cadastros.Empresa",
        verbose_name="Empresa contratada",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usuarios",
    )
    cliente = models.ForeignKey(
        "cadastros.Cliente",
        verbose_name="Cliente vinculado",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="usuarios",
        help_text="Preenchido para perfis do tipo Cliente (Portal do Cliente).",
    )

    # Dados da equipe técnica — Anexo I 3.1.2
    celular = models.CharField("Celular", max_length=20, blank=True)
    cpf = models.CharField("CPF", max_length=14, blank=True)
    cargo = models.CharField("Cargo/Função", max_length=80, blank=True)
    conselho_classe = models.CharField(
        "Conselho de Classe", max_length=60, blank=True,
        help_text="Ex.: CREA — necessário para assinar laudos.",
    )
    assinatura_digital = models.ImageField(
        "Assinatura digital", upload_to="assinaturas/", null=True, blank=True
    )

    is_active = models.BooleanField("Ativo", default=True)
    is_staff = models.BooleanField("Acesso ao admin", default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome"]

    class Meta:
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.get_perfil_display()})"

    @property
    def is_interno(self) -> bool:
        return self.perfil in PERFIS_INTERNOS

    @property
    def is_cliente(self) -> bool:
        return self.perfil in PERFIS_CLIENTE
