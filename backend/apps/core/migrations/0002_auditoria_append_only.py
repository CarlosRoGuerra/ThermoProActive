"""
V-03 / V-05 — trilha de auditoria: saneamento dos dados sensíveis já gravados e
append-only também no banco.

Ordem (importa):
1. vínculo com o usuário sem UPDATE automático ao apagar o usuário (DO_NOTHING, sem FK no banco);
2. tabela de controle de modo (0 bloqueado, 1 retenção, 2 saneamento);
3. saneamento dos registros antigos (única alteração permitida à trilha, em modo 2 — documentada);
4. triggers BEFORE UPDATE/DELETE: UPDATE só em modo 2, DELETE só em modo 1 (expurgo de retenção).

PostgreSQL usa função plpgsql; SQLite usa triggers com RAISE(ABORT). Outro banco: a migração para.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

TABELA_CONTROLE = "core_auditoria_controle"
TABELA_REGISTRO = "core_registroauditoria"
MENSAGEM = "registro de auditoria é append-only"


def _criar_controle_e_sanear(apps, schema_editor):
    from apps.core.auditoria import sanear_registros

    conexao = schema_editor.connection
    with conexao.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE IF NOT EXISTS {TABELA_CONTROLE} (id INTEGER PRIMARY KEY, modo INTEGER NOT NULL)"
        )
        cursor.execute(f"SELECT COUNT(*) FROM {TABELA_CONTROLE} WHERE id = 1")
        if cursor.fetchone()[0] == 0:
            cursor.execute(f"INSERT INTO {TABELA_CONTROLE} (id, modo) VALUES (1, 0)")
    Registro = apps.get_model("core", "RegistroAuditoria")
    sanear_registros(Registro)


def _criar_protecao(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(f"""
                CREATE OR REPLACE FUNCTION core_auditoria_protege() RETURNS trigger
                LANGUAGE plpgsql AS $$
                DECLARE m integer;
                BEGIN
                    SELECT modo INTO m FROM {TABELA_CONTROLE} WHERE id = 1;
                    IF TG_OP = 'UPDATE' AND m = 2 THEN RETURN NEW; END IF;
                    IF TG_OP = 'DELETE' AND m = 1 THEN RETURN OLD; END IF;
                    RAISE EXCEPTION '{MENSAGEM}';
                END;
                $$;
            """)
            cursor.execute(
                f"CREATE TRIGGER core_auditoria_protege BEFORE UPDATE OR DELETE ON {TABELA_REGISTRO} "
                "FOR EACH ROW EXECUTE FUNCTION core_auditoria_protege();"
            )
        elif vendor == "sqlite":
            cursor.execute(
                f"CREATE TRIGGER core_auditoria_nao_altera BEFORE UPDATE ON {TABELA_REGISTRO} "
                f"WHEN (SELECT modo FROM {TABELA_CONTROLE} WHERE id = 1) <> 2 "
                f"BEGIN SELECT RAISE(ABORT, '{MENSAGEM}'); END;"
            )
            cursor.execute(
                f"CREATE TRIGGER core_auditoria_nao_apaga BEFORE DELETE ON {TABELA_REGISTRO} "
                f"WHEN (SELECT modo FROM {TABELA_CONTROLE} WHERE id = 1) <> 1 "
                f"BEGIN SELECT RAISE(ABORT, '{MENSAGEM} (só o expurgo de retenção apaga)'); END;"
            )
        else:
            raise NotImplementedError(f"Banco '{vendor}' não suportado pela trilha append-only.")


def _remover_protecao(apps, schema_editor):
    vendor = schema_editor.connection.vendor
    with schema_editor.connection.cursor() as cursor:
        if vendor == "postgresql":
            cursor.execute(f"DROP TRIGGER IF EXISTS core_auditoria_protege ON {TABELA_REGISTRO};")
            cursor.execute("DROP FUNCTION IF EXISTS core_auditoria_protege();")
        elif vendor == "sqlite":
            cursor.execute("DROP TRIGGER IF EXISTS core_auditoria_nao_altera;")
            cursor.execute("DROP TRIGGER IF EXISTS core_auditoria_nao_apaga;")


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_registro_auditoria"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="registroauditoria",
            name="usuario",
            field=models.ForeignKey(
                blank=True, db_constraint=False, null=True,
                on_delete=django.db.models.deletion.DO_NOTHING, related_name="+",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(_criar_controle_e_sanear, migrations.RunPython.noop),
        migrations.RunPython(_criar_protecao, _remover_protecao),
    ]
