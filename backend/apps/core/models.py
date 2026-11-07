"""Modelos base reutilizados por todas as apps (arquitetura modular — Cláusula 4.2)."""
from contextlib import contextmanager

from django.db import models


class TimeStampedModel(models.Model):
    """Auditoria mínima de criação/atualização (apoio à LGPD — Cláusula 13.2)."""

    criado_em = models.DateTimeField("Criado em", auto_now_add=True)
    atualizado_em = models.DateTimeField("Atualizado em", auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-criado_em"]


class AtivoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True)


class BaseModel(TimeStampedModel):
    """Base com soft-delete lógico (não apaga histórico técnico/laudos)."""

    ativo = models.BooleanField("Ativo", default=True)

    objects = AtivoQuerySet.as_manager()

    class Meta:
        abstract = True
        ordering = ["-criado_em"]


# --- Trilha de auditoria (V-05): append-only também no banco -----------------------
# Dois modos de manutenção são o ÚNICO caminho que relaxa o bloqueio, e o trigger do banco
# confere o mesmo modo (migração core/0002). Cada caminho tem um só uso:
#   MODO_RETENCAO   -> permite DELETE (expurgo por AUDITORIA_RETENCAO_DIAS, `purgar_auditoria`);
#   MODO_SANEAMENTO -> permite UPDATE (correção de dados sensíveis gravados antes do V-03).
TABELA_CONTROLE = "core_auditoria_controle"
MODO_BLOQUEADO, MODO_RETENCAO, MODO_SANEAMENTO = 0, 1, 2


def _gravar_modo(conexao, modo):
    with conexao.cursor() as cursor:
        cursor.execute(f"UPDATE {TABELA_CONTROLE} SET modo = %s WHERE id = 1", [modo])


@contextmanager
def modo_manutencao(modo):
    """Abre um modo de manutenção da trilha na transação atual e fecha ao sair."""
    from django.db import connection, transaction
    with transaction.atomic():
        _gravar_modo(connection, modo)
        try:
            yield
        finally:
            _gravar_modo(connection, MODO_BLOQUEADO)


class RegistroAuditoriaQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise PermissionError("Registro de auditoria é append-only: alteração por consulta não é permitida.")

    def delete(self):
        # Trilha append-only: apagar só pela retenção (`purgar_antigos`).
        raise PermissionError("Registros de auditoria não podem ser apagados por consulta.")

    def purgar_antigos(self, dias):
        from datetime import timedelta
        from django.utils import timezone
        corte = timezone.now() - timedelta(days=dias)
        with modo_manutencao(MODO_RETENCAO):
            return models.QuerySet.delete(self.filter(criado_em__lt=corte))

    def sanear_campos(self, **kwargs):
        """Saneamento (correção de dado sensível já gravado). Único UPDATE permitido, com modo."""
        with modo_manutencao(MODO_SANEAMENTO):
            return models.QuerySet.update(self, **kwargs)


class RegistroAuditoria(models.Model):
    """
    Item 3.1.22 — trilha de auditoria de criação, alteração e exclusão de dados de negócio.
    Quem (usuário + e-mail no momento), quando, IP, modelo, id, campos alterados (antes/depois).
    Senhas, segredos, tokens e dados pessoais sensíveis NÃO são gravados (ver `apps.core.auditoria`).
    Append-only no ORM E no banco (trigger): update/delete só nos modos de manutenção acima.
    """

    class Acao(models.TextChoices):
        CRIAR = "CRIAR", "Criação"
        ALTERAR = "ALTERAR", "Alteração"
        EXCLUIR = "EXCLUIR", "Exclusão"

    criado_em = models.DateTimeField("Quando", auto_now_add=True, db_index=True)
    # DO_NOTHING + db_constraint=False: apagar um usuário NÃO altera a trilha (o SET_NULL do
    # Django faria um UPDATE, que o banco bloqueia). O id e o e-mail mascarado ficam.
    usuario = models.ForeignKey(
        "accounts.User", on_delete=models.DO_NOTHING, null=True, blank=True, related_name="+",
        db_constraint=False,
    )
    usuario_email = models.CharField("E-mail do usuário", max_length=254, blank=True)
    ip = models.CharField("IP", max_length=45, blank=True)
    metodo = models.CharField("Método HTTP", max_length=10, blank=True)
    caminho = models.CharField("Rota", max_length=255, blank=True)
    acao = models.CharField("Ação", max_length=8, choices=Acao.choices)
    modelo = models.CharField("Modelo (app.Modelo)", max_length=120, db_index=True)
    objeto_id = models.CharField("Id do registro", max_length=64, db_index=True)
    alteracoes = models.JSONField("Campos (antes/depois)", default=dict, blank=True)

    objects = RegistroAuditoriaQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name = "registro de auditoria"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise PermissionError("Registro de auditoria é append-only.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionError("Registro de auditoria é append-only.")
