# 19 — Operação: implantação, backup, restauração e recuperação de falhas

Escopo: ambiente de produção/homologação em **VPS Linux com Docker Compose**
(PostgreSQL 16, Django/gunicorn, Next.js, nginx). Tudo aqui usa só ferramentas
open-source e funciona em qualquer provedor (Cláusula 12.4 — sem lock-in).

Arquivos relacionados: `docker-compose.prod.yml` (domínio + TLS), `docker-compose.http.yml`
(teste por IP, sem TLS — é o que a VPS usa hoje), `docker-compose.yml` (**só desenvolvimento**),
`.env.prod.example`, `deploy/backup/*`, `deploy/verificar-producao.sh`,
`deploy/testar-restauracao.sh`, `deploy/init-letsencrypt.sh`.

> Convenção dos comandos: `DC` abaixo é o compose em uso.
> `DC="docker compose --env-file .env.prod -f docker-compose.http.yml"` (hoje) ou
> `DC="docker compose --env-file .env.prod -f docker-compose.prod.yml"` (com domínio/TLS).

---

## 1. Implantação do zero

Pré-requisitos: VPS Linux (2 vCPU / 4 GB RAM / 40 GB de disco é o mínimo razoável — o
backend carrega o Chromium para gerar PDFs), Docker Engine + plugin Compose, `git`,
portas 22/80/443 liberadas **e mais nenhuma** (firewall do provedor ou `ufw`; lembre que o
Docker publica portas direto no iptables, ignorando o `ufw` — por isso só o nginx publica).

```bash
git clone <repositório> /root/ThermoProActive && cd /root/ThermoProActive
cp .env.prod.example .env.prod && chmod 600 .env.prod
nano .env.prod        # SECRET_KEY, POSTGRES_PASSWORD (+ DATABASE_URL igual), ALLOWED_HOSTS, domínio/IP
```

Pontos que derrubam o boot (de propósito, para falhar cedo):
* `SECRET_KEY` com menos de 32 caracteres, pouco variada ou de exemplo → o Django **recusa subir**
  (`ImproperlyConfigured`). Gere: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`.
* `ALLOWED_HOSTS` vazio ou com `*` → idem.
* `POSTGRES_PASSWORD` e a senha dentro de `DATABASE_URL` precisam ser a mesma.

**Com domínio (TLS):** aponte o DNS (registros `A` de `dominio` e `www`) para o IP da VPS e rode
```bash
bash deploy/init-letsencrypt.sh                       # emite o certificado (Let's Encrypt)
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build
```
**Teste por IP (sem TLS):** em `.env.prod` use `NEXT_PUBLIC_API_URL=http://SEU.IP/api`,
`ALLOWED_HOSTS=SEU.IP,backend`, `COOKIES_SECURE=False`, e suba com `docker-compose.http.yml`.
Risco registrado: sem TLS a sessão e as senhas trafegam em claro; só para homologação.

O backend, ao subir, **migra o banco, coleta estáticos e inicia o gunicorn** (o comando está no
compose). Ele **não** cria usuário nenhum: crie o primeiro administrador com
`$DC exec backend python manage.py createsuperuser` (o `seed_demo` só roda em desenvolvimento).

Configure o **backup antes de liberar o acesso** (seção 3). Depois rode
`bash deploy/verificar-producao.sh` e trate todo ALERTA.

---

## 2. Atualização (deploy) com migrações

```bash
cd /root/ThermoProActive
bash deploy/verificar-producao.sh                 # 1. estado antes (sem ALERTA = pode seguir)
$DC exec backup /backup/backup.sh                 # 2. backup de pré-deploy (OBRIGATÓRIO)
git fetch && git log --oneline HEAD..origin/main  # 3. o que vai mudar
git pull --ff-only
$DC build                                         # 4. constrói as imagens novas (sem derrubar nada)
$DC up -d                                         # 5. recria só o que mudou; o backend migra ao subir
$DC logs --tail=80 backend                        # 6. "Applying ... OK", "Listening at"
bash deploy/verificar-producao.sh                 # 7. estado depois (migrações pendentes = 0)
```
* Se o `git pull` mexeu em `deploy/nginx/`, no compose **http** o nginx monta um **arquivo único**:
  um `reload` não enxerga a versão nova — use `$DC up -d --force-recreate nginx`.
* Migração que falha **derruba o backend** com o erro no log (não fica em loop). O banco continua
  íntegro (cada migração roda em transação no PostgreSQL). Corrija e suba de novo.
* O nginx resolve `backend`/`frontend` pelo DNS do Docker a cada requisição (`resolver 127.0.0.11`):
  recriar esses containers num deploy não exige reiniciar o nginx (antes dava 502 até o restart).
* **Rollback de código:** `git checkout <commit-anterior> && $DC build && $DC up -d`.
  Rollback de **migração** não é garantido: se uma migração já foi aplicada e o código antigo não a
  entende, restaure o backup de pré-deploy (seção 4.C). Por isso o passo 2 é obrigatório.
* Atualização de 29/10/2026 (Django 5.1 → 5.2 LTS, DRF 3.18, simplejwt 5.5, Pillow 13, cryptography 50,
  Next 15.5.28): aplica **1 migração nova** de terceiros (`token_blacklist.0013`, apenas opções de
  modelo, SQL vazio). Testado sobre cópia dos dados reais (seção 9.4).
* Disco: as imagens são construídas na própria VPS (a do backend tem ~2 GB). Após deploys,
  `docker image prune -f` e, se faltar espaço, `docker builder prune -f` (não toca em volumes).

---

## 3. Backup

### 3.1 O que é copiado, quando e onde
| Item | Como | Frequência |
| --- | --- | --- |
| Banco PostgreSQL (`thermoproactive`) | `pg_dump -Fc` pela rede interna do compose | diário às `BACKUP_AT` (03:15, fuso `BACKUP_TZ`) |
| Arquivos enviados (`media`: logos, assinaturas, fotos de placa, imagens de achados) | `tar.gz` do volume, montado **somente leitura** | idem |
| **NÃO coberto:** `.env.prod`, `deploy/`, código | `.env.prod` vai para o cofre de senhas da contratante; código está no Git | manual (ver 3.5) |

Cada execução gera, em `BACKUP_HOST_DIR` (padrão `/var/backups/thermoproactive`, **no host**,
fora dos volumes Docker — `docker compose down -v` não os apaga):
```
daily/ weekly/ monthly/    tpa_<AAAAMMDDTHHMMSSZ>_db.dump.gpg
                           tpa_<AAAAMMDDTHHMMSSZ>_media.tar.gz.gpg
                           tpa_<AAAAMMDDTHHMMSSZ>.sha256   (hashes dos 3 arquivos)
                           tpa_<AAAAMMDDTHHMMSSZ>.meta     (versão do PG, nº de migrações, nº de arquivos)
state/                     backup.log, last_success, last_failure, ...
```
**Retenção local em camadas** (padrão): 7 diários + 4 semanais (domingo) + 12 mensais (dia 1) —
`BACKUP_KEEP_DAILY/WEEKLY/MONTHLY`. Com a base atual (~2 MB por backup) são ~50 MB; cresce com a mídia.
**RPO** (perda máxima de dados): até 24 h. Para menos, rode `$DC exec backup /backup/backup.sh`
antes de operações de risco ou reduza o intervalo (futuro: arquivamento WAL).

### 3.2 Criptografia
* `gpg --symmetric --cipher-algo AES256` (S2K SHA-512, 65 milhões de iterações), em **streaming**:
  o dado nunca é gravado em claro no disco. Depois de criptografar, o script **descriptografa de
  volta** e lê o índice do dump e a lista do tar (se falhar, o backup é rejeitado) e grava SHA-256.
* A **frase-secreta** fica em `BACKUP_CONFIG_DIR/backup.passphrase` (padrão `/root/.thermoproactive/`,
  `chmod 700` na pasta e `600` no arquivo), **fora do repositório**, montada somente leitura no container.
* **Sem a frase-secreta não existe restauração.** Guarde uma cópia **fora da VPS** (cofre de senhas da
  contratante + cópia impressa em local seguro). Perder a VPS e a frase = perder todos os backups.

Criação (uma vez):
```bash
mkdir -p /root/.thermoproactive /var/backups/thermoproactive && chmod 700 /root/.thermoproactive
head -c 48 /dev/urandom | base64 -w0 > /root/.thermoproactive/backup.passphrase
chmod 600 /root/.thermoproactive/backup.passphrase
cat /root/.thermoproactive/backup.passphrase     # copie para o cofre AGORA
$DC up -d --build backup
$DC exec backup /backup/backup.sh                # primeiro backup + conferência
$DC ps backup                                    # healthy
```
**Rotação da frase-secreta:** trocar o arquivo vale só para os backups *novos*. Os antigos continuam
exigindo a frase antiga — **mantenha-a no cofre, datada, até o último backup antigo expirar**
(retenção mensal 12 meses; destino externo 400 dias). Se a frase antiga vazou, re-criptografe os
conjuntos que ainda importam (não exercitado no teste da seção 9):
`gpg --batch --pinentry-mode loopback --passphrase-file ANTIGA -d X.gpg | gpg --batch --pinentry-mode loopback --passphrase-file NOVA --symmetric --cipher-algo AES256 -o X.novo.gpg`
e depois refaça os `.sha256`. Rotacione ao menos 1x/ano e quando alguém com acesso sair da equipe.

### 3.3 Quem acessa
Quem tem `root` na VPS lê a frase e os backups; quem tem acesso ao cofre da contratante lê a frase.
Trate os dois grupos como equivalentes e mantenha a lista nominal atualizada (contratante).

### 3.4 Envio externo (obrigatório para produção real)
Backups só no mesmo servidor **não** protegem de perda da VPS, ransomware ou erro do provedor.
O envio usa **rclone** (open-source) e funciona com qualquer destino: S3-compatível (MinIO, Wasabi,
Backblaze B2, AWS...), SFTP/outro servidor, WebDAV, Google Drive, etc. — a escolha é da contratante.
```bash
# 1) na VPS, configure o destino (grava /root/.thermoproactive/rclone.conf; imagem oficial do rclone)
docker run --rm -it -v /root/.thermoproactive:/config/rclone rclone/rclone config
chmod 600 /root/.thermoproactive/rclone.conf
# 2) em .env.prod:
BACKUP_RCLONE_REMOTE=meuremoto:meu-bucket/thermoproactive
# 3) recrie o serviço e rode um backup
$DC up -d backup && $DC exec backup /backup/backup.sh
```
O script copia só o conjunto novo, confere tamanho no destino (`rclone check`) e apaga no destino o que
tem mais de `BACKUP_REMOTE_RETENTION_DAYS` (400). Falha no envio → **código de saída 6** (o backup local está
íntegro) e o serviço fica `unhealthy`. Como o rclone só *copia* (nunca espelha com `sync`), apagar o
local não apaga o remoto. Para proteção contra ransomware use um bucket com versionamento/object-lock.
**Pendência da contratante:** definir o destino e fornecer as credenciais (ainda não existem).

### 3.5 Agendamento (por que serviço no compose e não cron)
O serviço `backup` roda `deploy/backup/agendar.sh` (laço diário, mesmo padrão do `agendador`):
viaja com o repositório, sobe/desce com a stack, não depende de crontab do host (que se perde numa
VPS nova) e tem healthcheck (`unhealthy` se o último sucesso tiver mais de 30 h). Se o container estava
parado na hora marcada, roda assim que sobe; em falha, tenta de novo a cada 30 min, até 4 vezes por dia.
Alerta opcional: `BACKUP_ALERT_WEBHOOK` (POST JSON `{"text": "..."}`; Slack/Discord/Mattermost/n8n/ntfy).
Códigos de saída do `backup.sh`: 0 ok · 2 configuração (ex.: frase ausente) · 3 pg_dump · 4 mídia ·
5 verificação · 6 envio externo.
Backup manual: `$DC exec backup /backup/backup.sh`. Log: `/var/backups/thermoproactive/state/backup.log`.

---

## 4. Restauração (passo a passo)

`restore.sh` nunca tem destino padrão, confere SHA-256 e a descriptografia **antes** de tocar em
qualquer coisa, restaura o banco numa **transação única** (falhou = nada é aplicado), recusa destino
não vazio (a menos que `--clean`) e **recusa produção** sem `--allow-production` + frase digitada.

### 4.A Simulado de restauração (sem risco) — faça no deploy inicial e a cada trimestre
```bash
BACKUP_DIR=/var/backups/thermoproactive BACKUP_CONFIG_DIR=/root/.thermoproactive \
SRC_DB_CONTAINER=thermoproactive_db SRC_PGUSER=thermo SRC_PGDATABASE=thermoproactive \
SRC_MEDIA_VOLUME=$(docker volume ls -q | grep -E '_media$' | head -1) \
bash deploy/testar-restauracao.sh
```
Sobe um PostgreSQL descartável, restaura o último backup nele e num volume novo, compara linha a
linha (contagem por tabela), a lista de migrações e o SHA-256 de cada arquivo de mídia, e remove tudo.
Termina com `RESULTADO: RESTAURAÇÃO ÍNTEGRA` (código 0) ou `FALHOU`. Em produção com escrita ativa,
diferenças pequenas são esperadas (o backup é de 03:15); no banco parado devem ser zero.

### 4.B Restaurar em outro banco/volume (inspecionar dados, recuperar um registro)
```bash
# só o banco, num banco novo ao lado do de produção:
$DC --profile restore run --rm backup-restore --set latest --tier daily \
    --db-host db --db-name thermo_recuperado --db-user thermo --no-media --yes
# a mídia, num volume novo (o caminho de destino precisa ser um volume montado):
$DC --profile restore run --rm -v recuperada_media:/restore/media-recuperada backup-restore \
    --set latest --no-db --media-dir /restore/media-recuperada --yes
```
(`--set` aceita `latest` ou o nome `tpa_AAAAMMDDTHHMMSSZ`; `--tier daily|weekly|monthly`; `--from-dir`
aponta para uma cópia baixada do destino externo.) Consulte o banco com
`$DC exec db psql -U thermo -d thermo_recuperado` e apague depois (`DROP DATABASE thermo_recuperado;`,
`docker volume rm recuperada_media`).

### 4.C Restaurar **sobre a produção** (corrupção de dados / migração ruim)
1. Decida o ponto no tempo (`ls /var/backups/thermoproactive/daily`) e **avise os usuários**.
2. `$DC stop backend agendador frontend nginx` (ninguém escreve durante a restauração).
3. Faça uma cópia de segurança do estado atual, mesmo corrompido:
   `$DC exec db pg_dump -U thermo -Fc thermoproactive > /root/pre-restore-$(date +%F-%H%M).dump`
4. Restaure (pede para digitar `SOBRESCREVER PRODUCAO`):
   ```bash
   $DC --profile restore run --rm backup-restore --set tpa_AAAAMMDDTHHMMSSZ \
       --db-host db --db-name thermoproactive --db-user thermo \
       --media-dir /restore/media-producao --clean --allow-production
   ```
   (`--clean` troca os objetos existentes do banco e **esvazia** a mídia antes de extrair.)
5. `$DC up -d`, entre no sistema, confira os registros mais recentes e rode
   `bash deploy/verificar-producao.sh`. Registre o incidente (data, causa, backup usado, perda estimada).

### 4.D VPS perdida (desastre)
1. Nova VPS Linux + Docker; DNS/IP (seção 8). `git clone` do repositório.
2. Recupere do cofre: `.env.prod` (**mesma `SECRET_KEY`**, senão sessões e MFA são invalidados) e a
   `backup.passphrase`. Recoloque em `/root/.thermoproactive/`.
3. Baixe os backups do destino externo para `/var/backups/thermoproactive/daily/` (`rclone copy`).
4. Suba só o banco: `$DC up -d db`. Restaure (banco novo é vazio, não precisa de `--clean`; o guard de
   produção ainda pede a frase). Suba o resto: `$DC up -d --build`.
5. Emita novo certificado (`init-letsencrypt.sh`) ou use o modo HTTP. Rode `verificar-producao.sh`.
**RTO** (tempo para voltar) estimado em 1–2 h com tudo à mão; **não medido numa VPS real** (ver Pendências).

---

## 5. Operação diária

| Quando | O quê | Comando |
| --- | --- | --- |
| Diário (automático) | backup 03:15 | `$DC ps` → `backup` deve estar `healthy` |
| Semanal | check-up | `bash deploy/verificar-producao.sh` (use `--quiet` em cron: só imprime ALERTA) |
| Semanal | logs de erro | `$DC logs --since 7d backend \| grep -iE "error|traceback"` |
| Mensal | atualizações de segurança do SO | `apt update && apt upgrade` + reboot programado; depois `$DC ps` |
| Trimestral | simulado de restauração | `bash deploy/testar-restauracao.sh` (seção 4.A) |
| Trimestral | dependências | `pip-audit -r backend/requirements.txt` e `npm audit --omit=dev` (em venv/pasta de trabalho) |
| Anual | rotação da frase do backup, revisão de acessos, renovação do domínio | seção 3.2 |

Comandos úteis: `$DC ps` · `$DC logs -f --tail=100 backend` · `$DC exec backend python manage.py showmigrations --plan | grep '\[ \]'`
· `$DC exec backend python manage.py verificar_canais` (diagnóstico de e-mail/WhatsApp sem revelar credenciais).

---

## 6. Logs, monitoramento e comportamento em falha

**Onde estão os logs**
* Containers: `docker logs <nome>` / `$DC logs`. Driver `json-file` com **rotação 10 MB × 5 arquivos por
  serviço** (máx. ~50 MB cada; sem isso o disco enche). Arquivos reais em `/var/lib/docker/containers/<id>/`.
* Backup: `/var/backups/thermoproactive/state/backup.log` (rotaciona em 5 MB).
* nginx: stdout/stderr do container `thermoproactive_nginx` (acesso e erro). Auditoria da aplicação
  (login, MFA, convites) fica no banco (`accounts_eventoseguranca`).
* SO: `journalctl -u docker`, `/var/log/syslog`, `dmesg` (OOM killer).

**Healthchecks** (`$DC ps` mostra `healthy`/`unhealthy`): `db` (pg_isready), `backend` (gunicorn responde HTTP
<500 em `/api/auth/me/`), `frontend` (GET `/`), `nginx` (processo vivo), `backup` (último sucesso < 30 h).
O `agendador` não tem healthcheck (limitação conhecida; a política de reinício cobre queda do processo).

**Reinício automático:** todos os serviços usam `restart: unless-stopped` — o Docker os sobe de novo após
queda do processo ou reboot da VPS (se o serviço `docker` estiver habilitado: `systemctl enable docker`).
Ele **não** reinicia container `unhealthy` por si só; o aviso vem do monitoramento abaixo.

**Monitoramento simples (open-source, sem conta em terceiros)**
1. De dentro: `crontab -e` →
   `*/15 * * * * cd /root/ThermoProActive && bash deploy/verificar-producao.sh --quiet > /tmp/tpa-check.txt 2>&1 || curl -fsS -m 15 -d @/tmp/tpa-check.txt https://ntfy.SEU-SERVIDOR/tpa-alertas`
   (o script sai com código 1 quando há ALERTA e, no modo `--quiet`, só imprime os alertas; o `curl` é um
   exemplo para o **ntfy** open-source auto-hospedado — troque por e-mail, Mattermost, n8n etc.).
2. De fora (a VPS inteira pode estar fora do ar): um **Uptime Kuma** (open-source) em outra máquina, ou
   `*/5 * * * * curl -fsS -m 20 -o /dev/null https://DOMINIO/login || <alerta>` num segundo servidor.
   Monitore também a expiração do certificado (o `verificar-producao.sh` avisa com 20/7 dias).
3. Disco: o mesmo script alerta a partir de 80%/90%.

---

## 7. Runbook de falhas

| Sintoma | Diagnóstico | Ação |
| --- | --- | --- |
| **Site fora / 502** | `$DC ps`; `$DC logs --tail=100 backend nginx` | Container caído: `$DC up -d` (o `restart` já tenta). Backend em loop de erro de configuração: leia a mensagem (`SECRET_KEY fraca`, `ALLOWED_HOSTS`) e corrija o `.env.prod`. |
| **Container reinicia sem parar** | `docker inspect -f '{{.RestartCount}}' thermoproactive_backend`; `docker logs` | Migração falhando → corrija; OOM (`dmesg \| grep -i kill`, `OOMKilled` no `inspect`) → mais RAM/swap ou reduza `--workers`; PDF pesado derruba o backend (Chromium no mesmo container). |
| **Banco não sobe / corrompido** | `$DC logs db`; `pg_isready` | 1) tente `$DC restart db`; PostgreSQL faz recuperação de WAL sozinho após queda. 2) Se o volume `pgdata` estiver danificado (`invalid checkpoint`, `could not read block`): **não** apague o volume ainda — `docker run --rm -v <pgdata>:/v alpine tar czf - /v > pgdata-corrompido.tgz` para forense; depois restaure o último backup (4.C, banco novo). |
| **Dados apagados/alterados por engano** | quando aconteceu? | 4.B: restaure o backup anterior ao incidente num banco ao lado e recupere só os registros; ou 4.C se for geral. |
| **VPS perdida / sem acesso** | provedor | 4.D. |
| **Disco cheio** | `df -h`; `docker system df`; `du -sh /var/lib/docker/containers/*` | `docker image prune -f; docker builder prune -f` (seguro); logs de container já são rotacionados; apague backups locais muito antigos fora da retenção; `journalctl --vacuum-size=200M`. **Não** rode `docker system prune --volumes` (apaga volumes sem container, inclusive dados). Com disco 100% o PostgreSQL pára: libere espaço e `$DC restart db backend`. |
| **Certificado expirado / HTTPS quebrado** (stack prod) | `$DC logs certbot`; `echo \| openssl s_client -connect DOMINIO:443 2>/dev/null \| openssl x509 -noout -dates` | Cheque DNS e porta 80 abertos (o desafio é http-01). Renove à mão: `$DC run --rm certbot renew --webroot -w /var/www/certbot` e `$DC exec nginx nginx -s reload`. Se o `live/` sumiu, rode `deploy/init-letsencrypt.sh` de novo. |
| **Backup `unhealthy`** | `tail -50 /var/backups/thermoproactive/state/backup.log`; `cat state/last_failure` | Código 2: frase-secreta ausente/curta (ou pasta criada no lugar do arquivo — apague a pasta e crie o arquivo). 3: senha/rede do banco. 6: credenciais do destino externo. Corrija e rode `$DC exec backup /backup/backup.sh`. |
| **Usuários não conseguem entrar após deploy** | `$DC logs backend \| grep -i csrf` | `CSRF_TRUSTED_ORIGINS`/`ALLOWED_HOSTS`/`COOKIES_SECURE` incompatíveis com HTTP/HTTPS em uso; se a `SECRET_KEY` mudou, sessões antigas caem (novo login) e **MFA precisa ser recadastrado**. |
| **E-mails/convites não chegam** | `$DC exec backend python manage.py verificar_canais` | Sem `EMAIL_BACKEND` SMTP o e-mail só vai para o log. Credenciais SMTP são da contratante. |

---

## 8. Portabilidade e transferência para outro provedor (Cláusula 12)

**Dependências de terceiros verificadas** (nenhuma é proprietária nem obrigatória):
* Imagens base públicas: `postgres:16-alpine`, `nginx:1.27-alpine`, `python:3.13-slim-bookworm`,
  `node:22*`, `certbot/certbot` (tag fixa). Não há registry privado nem imagem pré-construída: tudo é
  construído a partir do repositório (`docker compose build`).
* Pacotes: PyPI, npm, apt (Debian), Playwright/Chromium — todos públicos; o *build* precisa de internet.
* **Google Fonts no build** (`next/font/google` em `frontend/src/app/layout.tsx`): o Next baixa Inter e
  JetBrains Mono ao construir e as serve do próprio domínio; o navegador do usuário **não** fala com o
  Google. Dependência só de build; para build 100% offline, trocar por `next/font/local` (fontes OFL).
* **ViaCEP** (`viacep.com.br`): o navegador consulta CEP nos formulários de cliente/prestador; é serviço
  público gratuito sem chave. Se cair, o preenchimento automático falha e o usuário digita o endereço.
* **Let's Encrypt** (TLS): gratuito, padrão ACME, qualquer outro CA ACME serve.
* E-mail (SMTP) e WhatsApp (gateway HTTP) são **da contratante**; nada é fixo no código.
  Push não está implementado. Não há CDN, analytics, APIs pagas, nem chave amarrada à contratada.
* Contas em nome da contratada a transferir: repositório GitHub (`CarlosRoGuerra/ThermoProActive`, conta
  pessoal), a própria VPS, e — quando existir — domínio/DNS e o e-mail dos avisos do Let's Encrypt.
  O `.env.prod.example` não carrega mais o e-mail da contratada (placeholder).

**Procedimento de transferência**
1. **Código:** transferir o repositório para a organização da contratante (GitHub: *Settings → Transfer*)
   ou `git clone --mirror` + `git push --mirror` para outro Git (GitLab/Gitea/servidor próprio). O
   histórico contém e-mails de autoria (`git shortlog -sne`) e dois documentos de clientes versionados
   por engano (ver relatório de segredos) — a contratante decide se os remove do rastreamento.
2. **Banco:** `$DC exec -T db pg_dump -U thermo -Fc thermoproactive > thermoproactive.dump` (ou o último
   backup desta seção) → restaurar com `restore.sh` ou `pg_restore --no-owner -d novo_banco` no destino.
3. **Mídia:** `docker run --rm -v <volume_media>:/m:ro -v $PWD:/o alpine tar czf /o/media.tgz -C /m .` e
   extrair no volume `media` do destino.
4. **Segredos a regenerar no destino:** `SECRET_KEY` (nova → derruba sessões; **MFA recadastrar**, a menos
   que se use `MFA_ENCRYPTION_KEY` fixa desde o início), `POSTGRES_PASSWORD`, credenciais SMTP/WhatsApp
   (da contratante), nova frase-secreta de backup, chaves SSH. Revogue as antigas no ambiente anterior.
5. **DNS:** reduzir o TTL do registro `A` para 300 s com antecedência; apontar `dominio` e `www` para o
   novo IP depois de validar o novo ambiente por IP; manter o ambiente antigo até a propagação.
6. **TLS:** no destino, `deploy/init-letsencrypt.sh` emite certificado novo (não copie chaves privadas
   entre servidores). Atualize `DOMAIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`,
   `FRONTEND_URL` e **`NEXT_PUBLIC_API_URL`** — esta última é embutida no bundle: exige `$DC build frontend`.
7. **Validação:** `verificar-producao.sh`, login de um usuário de cada perfil, abrir um laudo com imagem
   (prova que mídia + PDF funcionam), um backup manual e o simulado de restauração (4.A).
8. **Desligamento do ambiente antigo** só depois de 1 backup completo do novo ambiente enviado ao destino
   externo; apagar dados e chaves do provedor anterior (LGPD).

---

## 9. Evidências do teste de restauração e das migrações (29/10/2026)

Executado em ambiente isolado (containers/volumes `tpa_homolog_*`, removidos ao final), a partir do banco
local (cópia dos dados de produção, **somente leitura**) e do volume de mídia local montado `:ro`.

### 9.1 Backup real com `backup.sh` (imagem construída de `deploy/backup/`)
```
[backup] === início tpa_20261029T073632Z (banco thermo@db:5432/thermoproactive; mídia /data/media) ===
[backup] banco: 487082 bytes criptografados (PostgreSQL 16.14, 128 migrações aplicadas)
[backup] mídia: 74 arquivos, 1432154 bytes criptografados
[backup] verificação do dump: descriptografa e lista 856 itens
[backup] verificação da mídia: 74 arquivos no tar (origem: 74)
[backup] === SUCESSO tpa_20261029T073632Z ===
```
### 9.2 Restauração + comparação (`deploy/testar-restauracao.sh`)
```
restore.sh: sha256 dos 3 arquivos OK; dump descriptografa; banco 'restaurado' criado; django_migrations 128 (no backup: 128); mídia 74 arquivos
tabelas (origem/restaurado): 94 / 94
linhas somadas (origem/restaurado): 3375 / 3375        -> OK: todas as tabelas com contagem idêntica
accounts_user 6|6 · cadastros_cliente 26|26 · cadastros_equipamento 53|53 · coletas_inspecao 8|8
coletas_achado 37|37 · coletas_carregamento 34|34 · coletas_relatorio 32|32 · laudos_laudo 2|2
osp_ordemservico 30|30 · osp_historicoosp 30|30        (todas as tabelas coletas_*/osp_*/laudos_* idênticas)
django_migrations: d562f6962551ee1ab88fda65b9c73302 128 | d562f6962551ee1ab88fda65b9c73302 128  -> idênticas
mídia: 74 / 74 arquivos; SHA-256 de cada arquivo idêntico   -> RESULTADO: RESTAURAÇÃO ÍNTEGRA (exit 0)
```
### 9.3 Testes negativos (salvaguardas)
| Teste | Esperado | Obtido |
| --- | --- | --- |
| Restaurar sobre `db/thermoproactive` sem `--allow-production` | recusa | exit 3 |
| Idem com `--allow-production` mas sem terminal/frase | recusa | exit 3 |
| Frase-secreta errada | falha na descriptografia | exit 5 |
| 1 byte do dump alterado | checksum acusa; nada restaurado | exit 5 |
| Diretório de mídia não vazio, sem `--clean` | recusa | exit 4 |
| Backup sem frase-secreta | falha de configuração | exit 2 |
| Backup com senha do banco errada | falha; `last_failure` gravado; sem resíduo em `.tmp` | exit 3 |
| Retenção (`KEEP_DAILY=1`) e promoção semanal | apaga o excedente; copia p/ `weekly/` | ok |
| Envio rclone (destino `:local:`) + `rclone check` | 4 arquivos no destino | ok |
| Agendador (`BACKUP_AT=00:00`) | dispara 1 backup e marca o dia | ok |

### 9.4 Migrações em banco descartável (PostgreSQL 16, porta aleatória em 127.0.0.1)
`migrate` do zero (Django 5.2.18): exit 0, 129 migrações aplicadas, 0 pendentes; `makemigrations --check --dry-run`:
*No changes detected*; segundo `migrate`: *No migrations to apply*; `check`: sem problemas. A cópia dos dados reais, vinda
de Django 5.1.4 (128 migrações), recebeu apenas `token_blacklist.0013` ao rodar a stack nova, sem perda
(smoke ORM: 6 usuários, 53 equipamentos).

---

## 10. Pendências (dependem da VPS ou da contratante)

**Da VPS (não verificável daqui — SSH negado):** rodar `bash deploy/verificar-producao.sh` e tratar cada
ALERTA; conferir `SECRET_KEY` atual (o Django agora recusa chave fraca no boot — verificar **antes** do
próximo deploy); confirmar `DEBUG`, `ALLOWED_HOSTS`, firewall e portas (só 22/80/443); criar a pasta
`/root/.thermoproactive` e a frase-secreta; subir o serviço `backup`; executar o primeiro backup e o
simulado de restauração **na VPS real** (medir RTO); `systemctl enable docker`; atualizações do SO.
**Da contratante:** (1) destino externo do backup e suas credenciais; (2) cofre de senhas com `.env.prod` e
a frase-secreta (e quem acessa); (3) domínio + DNS e decisão de migrar de HTTP para HTTPS (hoje a sessão
trafega em claro); (4) SMTP/WhatsApp reais; (5) webhook/canal para alertas e quem recebe; (6) política de
retenção formal (LGPD) e o RPO desejado; (7) transferência do repositório para a organização; (8) decidir
sobre documentos de clientes versionados no Git.
**Técnicas recomendadas (não feitas aqui):** rodar o backend sem root (hoje o Chromium exige
`--no-sandbox` como root; sem root ele falha neste container — avaliar `seccomp`/userns); limites de
memória/CPU e separar a geração de PDF do gunicorn; healthcheck/heartbeat do `agendador`; fixar as imagens base por digest; build em CI
com registry em vez de construir na VPS; fontes locais (`next/font/local`); arquivamento WAL se o RPO de
24 h não for aceitável.
