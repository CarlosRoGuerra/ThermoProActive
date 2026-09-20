"""
Usuário e perfis de acesso — Anexo I, item 2.1 (Login e Controle de Acesso).

Os 7 perfis do item 2.1.2 são modelados como choices; permissões finas por módulo
ficam em `apps.accounts.permissions`. Campos da equipe técnica seguem o item 3.1.2.
"""
import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.core.models import TimeStampedModel

from .managers import UserManager


class EstadoConta(models.TextChoices):
    PENDING_EMAIL_VERIFICATION = "PENDING_EMAIL_VERIFICATION", "Aguardando confirmação de e-mail"
    PENDING_APPROVAL = "PENDING_APPROVAL", "Aguardando aprovação"
    ACTIVE = "ACTIVE", "Ativa"
    SUSPENDED = "SUSPENDED", "Suspensa"
    BLOCKED = "BLOCKED", "Bloqueada"
    INACTIVE = "INACTIVE", "Inativa"


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


class Nivel(models.TextChoices):
    """
    Nível hierárquico de acesso (reunião 22/07/2026).

    Aplica-se aos DOIS ambientes: BackEnd (equipe interna que alimenta o sistema)
    e FrontEnd (cliente que consome/complementa). Combinado com o ambiente,
    reproduz os grupos definidos pelo cliente: BackEnd-Master, FrontEnd-Pleno etc.
    """

    MASTER = "MASTER", "Master"
    SENIOR = "SENIOR", "Sênior"
    PLENO = "PLENO", "Pleno"
    JUNIOR = "JUNIOR", "Júnior"


#: Níveis autorizados a excluir registros. Júnior/Pleno alimentam mas não apagam.
NIVEIS_PODEM_EXCLUIR = {Nivel.MASTER, Nivel.SENIOR}


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    """Usuário do sistema. Login por e-mail (multiusuário — item 2.1.1.5)."""

    email = models.EmailField("E-mail", unique=True)
    nome = models.CharField("Nome completo", max_length=160)
    perfil = models.CharField(
        "Perfil de acesso", max_length=20, choices=Perfil.choices, default=Perfil.TECNICO
    )
    nivel = models.CharField(
        "Nível de acesso", max_length=10, choices=Nivel.choices, default=Nivel.PLENO,
        help_text="Master cura os dados de sistema e concede acessos; Júnior/Pleno não excluem.",
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
    estado = models.CharField(
        "Estado da conta", max_length=32, choices=EstadoConta.choices,
        default=EstadoConta.ACTIVE,
    )
    email_verificado_em = models.DateTimeField("E-mail verificado em", null=True, blank=True)
    termos_aceitos_em = models.DateTimeField("Termos aceitos em", null=True, blank=True)
    senha_alterada_em = models.DateTimeField("Senha alterada em", null=True, blank=True)
    exigir_troca_senha = models.BooleanField("Exigir troca de senha", default=False)
    mfa_obrigatorio = models.BooleanField("MFA obrigatório", default=False)
    tentativas_login = models.PositiveSmallIntegerField("Tentativas de login", default=0)
    bloqueado_ate = models.DateTimeField("Bloqueado até", null=True, blank=True)

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

    # --- Hierarquia de acesso (reunião 22/07/2026) -------------------------
    @property
    def ambiente(self) -> str:
        """BackEnd = equipe interna que alimenta; FrontEnd = cliente."""
        return "BackEnd" if self.is_interno else "FrontEnd"

    @property
    def grupo_acesso(self) -> str:
        """Rótulo no formato usado pelo cliente: 'BackEnd-Master'."""
        return f"{self.ambiente}-{self.get_nivel_display()}"

    @property
    def is_master(self) -> bool:
        return self.nivel == Nivel.MASTER

    @property
    def pode_excluir(self) -> bool:
        return self.nivel in NIVEIS_PODEM_EXCLUIR

    @property
    def pode_curar_dados_sistema(self) -> bool:
        """Só o Master interno cria/edita as tabelas de referência do sistema."""
        return self.is_interno and self.is_master


class FinalidadeToken(models.TextChoices):
    RESET_PASSWORD = "RESET_PASSWORD", "Redefinição de senha"
    VERIFY_EMAIL = "VERIFY_EMAIL", "Confirmação de e-mail"
    CHANGE_EMAIL = "CHANGE_EMAIL", "Alteração de e-mail"


class TokenUsoUnico(TimeStampedModel):
    """Token opaco; somente o SHA-256 é persistido no banco."""

    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="tokens_uso_unico")
    finalidade = models.CharField(max_length=32, choices=FinalidadeToken.choices)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.EmailField(blank=True)
    contexto = models.CharField(max_length=16, choices=[("portal", "Portal"), ("admin", "Admin")])
    expira_em = models.DateTimeField(db_index=True)
    usado_em = models.DateTimeField(null=True, blank=True)
    tentativas = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-criado_em"]


class SolicitacaoAcesso(TimeStampedModel):
    """Pedido comercial; nunca cria organização ou conta ativa automaticamente."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pendente"
        APPROVED = "APPROVED", "Aprovada"
        REJECTED = "REJECTED", "Recusada"

    nome = models.CharField(max_length=160)
    email = models.EmailField(db_index=True)
    telefone = models.CharField(max_length=20)
    razao_social = models.CharField(max_length=160)
    nome_fantasia = models.CharField(max_length=160, blank=True)
    cnpj = models.CharField(max_length=18, db_index=True)
    segmento = models.CharField(max_length=120, blank=True)
    telefone_empresa = models.CharField(max_length=20, blank=True)
    email_empresa = models.EmailField(blank=True)
    quantidade_equipamentos = models.PositiveIntegerField(null=True, blank=True)
    cargo = models.CharField(max_length=80, blank=True)
    aceitou_termos = models.BooleanField(default=False)
    aceita_marketing = models.BooleanField(default=False)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    ip_hash = models.CharField(max_length=64, blank=True)


class Convite(TimeStampedModel):
    class Tipo(models.TextChoices):
        PORTAL = "portal", "Portal do cliente"
        ADMIN = "admin", "Área administrativa"

    email = models.EmailField(db_index=True)
    nome = models.CharField(max_length=160)
    tipo = models.CharField(max_length=16, choices=Tipo.choices)
    perfil = models.CharField(max_length=20, choices=Perfil.choices)
    nivel = models.CharField(max_length=10, choices=Nivel.choices)
    empresa = models.ForeignKey(
        "cadastros.Empresa", on_delete=models.PROTECT, null=True, blank=True,
        related_name="convites_acesso",
    )
    cliente = models.ForeignKey(
        "cadastros.Cliente", on_delete=models.PROTECT, null=True, blank=True,
        related_name="convites_acesso",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    expira_em = models.DateTimeField(db_index=True)
    aceito_em = models.DateTimeField(null=True, blank=True)
    revogado_em = models.DateTimeField(null=True, blank=True)
    criado_por = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="convites_criados"
    )


class SessaoAutenticacao(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessoes_auth")
    refresh_jti = models.CharField(max_length=255, unique=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    lembrar = models.BooleanField(default=False)
    ultimo_uso_em = models.DateTimeField()
    expira_em = models.DateTimeField(db_index=True)
    revogada_em = models.DateTimeField(null=True, blank=True)

    @property
    def ativa(self):
        from django.utils import timezone
        return self.revogada_em is None and self.expira_em > timezone.now()


class EventoSeguranca(TimeStampedModel):
    usuario = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="eventos_seguranca",
    )
    evento = models.CharField(max_length=64, db_index=True)
    sucesso = models.BooleanField(default=True)
    ip_hash = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    detalhes = models.JSONField(default=dict, blank=True)


class DispositivoMFA(TimeStampedModel):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name="mfa")
    segredo_criptografado = models.TextField()
    confirmado_em = models.DateTimeField(null=True, blank=True)
    ultimo_passo_usado = models.BigIntegerField(null=True, blank=True)

    @property
    def ativo(self):
        return self.confirmado_em is not None


class CodigoRecuperacaoMFA(TimeStampedModel):
    dispositivo = models.ForeignKey(
        DispositivoMFA, on_delete=models.CASCADE, related_name="codigos_recuperacao"
    )
    codigo_hash = models.CharField(max_length=128)
    usado_em = models.DateTimeField(null=True, blank=True)
