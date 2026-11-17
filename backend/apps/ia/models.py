"""
Inteligência artificial — credenciais dos provedores e ativação por recurso.

Dois cadastros, só do Master interno:

  * `ChaveApiIA` — a chave de API de um provedor (Anthropic, OpenAI, Google ou outro).
    Fica CIFRADA no banco; não volta pela API (só os 4 últimos caracteres, para
    reconhecer) e não entra na trilha de auditoria.
  * `AtivacaoIA` — liga ou desliga o uso de IA em cada recurso do sistema e diz qual
    chave (e qual modelo) ele usa.

O recurso aponta para uma chave, não para um provedor: trocar de provedor é escolher outra
chave, sem mexer em código (Cláusula 12.4 — sem aprisionamento a fornecedor).

Os recursos em si (apoio ao laudo de vibração, leitura do laudo do laboratório) ainda não
existem: este app guarda a configuração que eles vão consultar por
`servico.credencial_do_recurso`.
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import TimeStampedModel

from . import cifra


class ProvedorIA(models.TextChoices):
    ANTHROPIC = "ANTHROPIC", "Anthropic (Claude)"
    OPENAI = "OPENAI", "OpenAI (GPT)"
    GOOGLE = "GOOGLE", "Google (Gemini)"
    OUTRO = "OUTRO", "Outro provedor (endereço próprio)"


class RecursoIA(models.TextChoices):
    """Onde o sistema pode usar IA. Um recurso novo entra aqui e em `DESCRICAO_RECURSO`."""

    LAUDO_VIBRACAO = "LAUDO_VIBRACAO", "Apoio ao laudo de vibração"
    LEITURA_LAUDO_FLUIDOS = "LEITURA_LAUDO_FLUIDOS", "Leitura do laudo do laboratório (fluidos)"


DESCRICAO_RECURSO = {
    RecursoIA.LAUDO_VIBRACAO: (
        "Lê em conjunto os gráficos de um ponto (espectros de velocidade, aceleração e envelope) e "
        "propõe um fechamento para o analista revisar."
    ),
    RecursoIA.LEITURA_LAUDO_FLUIDOS: (
        "Lê o laudo enviado pelo laboratório (lubrificantes, hidráulicos e isolantes) e preenche os "
        "campos do ensaio, para o analista conferir em vez de redigitar."
    ),
}

# Recursos cuja função já está no sistema. Enquanto o recurso não está aqui, a ativação
# fica gravada, mas nada é enviado a provedor nenhum.
RECURSOS_IMPLEMENTADOS: frozenset = frozenset()


class ChaveApiIA(TimeStampedModel):
    provedor = models.CharField("Provedor", max_length=20, choices=ProvedorIA.choices)
    rotulo = models.CharField(
        "Identificação", max_length=80, help_text="Como reconhecer esta chave (ex.: Conta principal).",
    )
    # Nomes com "chave": a trilha de auditoria registra só que mudaram, nunca o valor.
    chave_cifrada = models.TextField("Chave cifrada", editable=False)
    chave_final = models.CharField("Final da chave", max_length=8, editable=False, blank=True)
    modelo_padrao = models.CharField(
        "Modelo padrão", max_length=120, blank=True,
        help_text="Identificador do modelo no provedor. O recurso pode usar outro.",
    )
    url_base = models.URLField(
        "Endereço da API", blank=True,
        help_text="Só para outro provedor ou servidor próprio. Vazio = endereço oficial do provedor.",
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Chave de API de IA"
        verbose_name_plural = "Chaves de API de IA"
        ordering = ["provedor", "rotulo"]
        constraints = [
            models.UniqueConstraint(fields=["provedor", "rotulo"], name="uniq_chave_ia_provedor_rotulo"),
        ]

    def __str__(self):
        return f"{self.get_provedor_display()} — {self.rotulo}"

    def definir_chave(self, texto: str) -> None:
        texto = texto.strip()
        self.chave_cifrada = cifra.cifrar(texto)
        self.chave_final = texto[-4:]

    def revelar(self) -> str:
        """A chave em texto, para chamar o provedor. Nunca devolver em resposta de API nem em log."""
        return cifra.decifrar(self.chave_cifrada)

    @property
    def mascarada(self) -> str:
        return f"••••{self.chave_final}"

    @property
    def legivel(self) -> bool:
        try:
            self.revelar()
        except cifra.ChaveIlegivel:
            return False
        return True


class AtivacaoIA(TimeStampedModel):
    """Um registro por recurso. Sem registro = recurso desligado."""

    recurso = models.CharField("Recurso", max_length=40, choices=RecursoIA.choices, unique=True)
    habilitado = models.BooleanField("Uso de IA habilitado", default=False)
    credencial = models.ForeignKey(
        ChaveApiIA, on_delete=models.SET_NULL, null=True, blank=True, related_name="ativacoes",
        verbose_name="Chave de API usada",
    )
    modelo = models.CharField(
        "Modelo", max_length=120, blank=True, help_text="Vazio = o modelo padrão da chave.",
    )
    atualizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )

    class Meta(TimeStampedModel.Meta):
        verbose_name = "Ativação de IA"
        verbose_name_plural = "Ativações de IA"
        ordering = ["recurso"]

    def __str__(self):
        return f"{self.get_recurso_display()}: {'ligado' if self.habilitado else 'desligado'}"

    def clean(self):
        if self.habilitado and self.credencial_id is None:
            raise ValidationError({"credencial": "Escolha a chave de API antes de habilitar o recurso."})

    @property
    def modelo_efetivo(self) -> str:
        return self.modelo or (self.credencial.modelo_padrao if self.credencial_id else "")
