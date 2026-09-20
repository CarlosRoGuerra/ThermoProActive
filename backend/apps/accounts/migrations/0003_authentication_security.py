import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_user_nivel"),
        ("cadastros", "0025_tipoequipamento_categoria_tecnica_dadostecnicosmotor_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="user", name="bloqueado_ate",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Bloqueado até"),
        ),
        migrations.AddField(
            model_name="user", name="email_verificado_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="E-mail verificado em"),
        ),
        migrations.AddField(
            model_name="user", name="estado",
            field=models.CharField(
                choices=[
                    ("PENDING_EMAIL_VERIFICATION", "Aguardando confirmação de e-mail"),
                    ("PENDING_APPROVAL", "Aguardando aprovação"),
                    ("ACTIVE", "Ativa"), ("SUSPENDED", "Suspensa"),
                    ("BLOCKED", "Bloqueada"), ("INACTIVE", "Inativa"),
                ], default="ACTIVE", max_length=32, verbose_name="Estado da conta",
            ),
        ),
        migrations.AddField(
            model_name="user", name="exigir_troca_senha",
            field=models.BooleanField(default=False, verbose_name="Exigir troca de senha"),
        ),
        migrations.AddField(
            model_name="user", name="mfa_obrigatorio",
            field=models.BooleanField(default=False, verbose_name="MFA obrigatório"),
        ),
        migrations.AddField(
            model_name="user", name="senha_alterada_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Senha alterada em"),
        ),
        migrations.AddField(
            model_name="user", name="tentativas_login",
            field=models.PositiveSmallIntegerField(default=0, verbose_name="Tentativas de login"),
        ),
        migrations.AddField(
            model_name="user", name="termos_aceitos_em",
            field=models.DateTimeField(blank=True, null=True, verbose_name="Termos aceitos em"),
        ),
        migrations.CreateModel(
            name="SolicitacaoAcesso",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("nome", models.CharField(max_length=160)),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("telefone", models.CharField(max_length=20)),
                ("razao_social", models.CharField(max_length=160)),
                ("nome_fantasia", models.CharField(blank=True, max_length=160)),
                ("cnpj", models.CharField(db_index=True, max_length=18)),
                ("segmento", models.CharField(blank=True, max_length=120)),
                ("telefone_empresa", models.CharField(blank=True, max_length=20)),
                ("email_empresa", models.EmailField(blank=True, max_length=254)),
                ("quantidade_equipamentos", models.PositiveIntegerField(blank=True, null=True)),
                ("cargo", models.CharField(blank=True, max_length=80)),
                ("aceitou_termos", models.BooleanField(default=False)),
                ("aceita_marketing", models.BooleanField(default=False)),
                ("status", models.CharField(choices=[("PENDING", "Pendente"), ("APPROVED", "Aprovada"), ("REJECTED", "Recusada")], default="PENDING", max_length=16)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
            ],
            options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="TokenUsoUnico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("finalidade", models.CharField(choices=[("RESET_PASSWORD", "Redefinição de senha"), ("VERIFY_EMAIL", "Confirmação de e-mail"), ("CHANGE_EMAIL", "Alteração de e-mail")], max_length=32)),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("contexto", models.CharField(choices=[("portal", "Portal"), ("admin", "Admin")], max_length=16)),
                ("expira_em", models.DateTimeField(db_index=True)),
                ("usado_em", models.DateTimeField(blank=True, null=True)),
                ("tentativas", models.PositiveSmallIntegerField(default=0)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="tokens_uso_unico", to="accounts.user")),
            ], options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="SessaoAutenticacao",
            fields=[
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("refresh_jti", models.CharField(max_length=255, unique=True)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("lembrar", models.BooleanField(default=False)),
                ("ultimo_uso_em", models.DateTimeField()),
                ("expira_em", models.DateTimeField(db_index=True)),
                ("revogada_em", models.DateTimeField(blank=True, null=True)),
                ("usuario", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sessoes_auth", to="accounts.user")),
            ], options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="EventoSeguranca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("evento", models.CharField(db_index=True, max_length=64)),
                ("sucesso", models.BooleanField(default=True)),
                ("ip_hash", models.CharField(blank=True, max_length=64)),
                ("user_agent", models.CharField(blank=True, max_length=300)),
                ("detalhes", models.JSONField(blank=True, default=dict)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="eventos_seguranca", to="accounts.user")),
            ], options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="DispositivoMFA",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("segredo_criptografado", models.TextField()),
                ("confirmado_em", models.DateTimeField(blank=True, null=True)),
                ("ultimo_passo_usado", models.BigIntegerField(blank=True, null=True)),
                ("usuario", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mfa", to="accounts.user")),
            ], options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="Convite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("email", models.EmailField(db_index=True, max_length=254)),
                ("nome", models.CharField(max_length=160)),
                ("tipo", models.CharField(choices=[("portal", "Portal do cliente"), ("admin", "Área administrativa")], max_length=16)),
                ("perfil", models.CharField(choices=[("ADMIN", "Administrador"), ("GESTOR", "Gestor/Supervisor"), ("TECNICO", "Técnico/Analista"), ("CLIENTE_CORP", "Cliente — Gestor Corporativo"), ("CLIENTE_LOCAL", "Cliente — Gestor Local"), ("CLIENTE_PCM", "Cliente — PCM"), ("CLIENTE_MANUT", "Cliente — Manutentor")], max_length=20)),
                ("nivel", models.CharField(choices=[("MASTER", "Master"), ("SENIOR", "Sênior"), ("PLENO", "Pleno"), ("JUNIOR", "Júnior")], max_length=10)),
                ("token_hash", models.CharField(db_index=True, max_length=64, unique=True)),
                ("expira_em", models.DateTimeField(db_index=True)),
                ("aceito_em", models.DateTimeField(blank=True, null=True)),
                ("revogado_em", models.DateTimeField(blank=True, null=True)),
                ("cliente", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="convites_acesso", to="cadastros.cliente")),
                ("criado_por", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="convites_criados", to="accounts.user")),
                ("empresa", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="convites_acesso", to="cadastros.empresa")),
            ], options={"ordering": ["-criado_em"]},
        ),
        migrations.CreateModel(
            name="CodigoRecuperacaoMFA",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("criado_em", models.DateTimeField(auto_now_add=True, verbose_name="Criado em")),
                ("atualizado_em", models.DateTimeField(auto_now=True, verbose_name="Atualizado em")),
                ("codigo_hash", models.CharField(max_length=128)),
                ("usado_em", models.DateTimeField(blank=True, null=True)),
                ("dispositivo", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codigos_recuperacao", to="accounts.dispositivomfa")),
            ], options={"ordering": ["-criado_em"]},
        ),
    ]
