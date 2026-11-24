#!/usr/bin/env bash
# =============================================================================
# verificar-producao.sh — check-up SOMENTE LEITURA do ambiente ThermoProActive.
#
# Rode NA VPS (como root ou usuário do grupo docker), a partir da raiz do projeto:
#     bash deploy/verificar-producao.sh            # relatório legível
#     bash deploy/verificar-producao.sh --quiet    # só ALERTAs (bom para cron)
# Variáveis opcionais: BACKUP_HOST_DIR (padrão: do .env.prod ou /var/backups/thermoproactive),
#                      BACKUP_CONFIG_DIR, PROJECT_DIR (raiz do projeto; padrão: diretório atual).
#
# NÃO altera nada: só 'docker inspect/ps/port/exec' de leitura, 'ss', 'df', 'stat'.
# NUNCA imprime valores de segredos (SECRET_KEY, senhas): só tamanho/booleanos.
# Código de saída: 0 = nenhum ALERTA | 1 = há ao menos um ALERTA | 2 = docker indisponível.
# Cobertura: containers/restarts, DEBUG, ALLOWED_HOSTS, SECRET_KEY, COOKIES_SECURE,
# compose em uso, migrações pendentes, PostgreSQL, backup, disco, portas, certificado.
# =============================================================================
set -u
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1
PROJECT_DIR=${PROJECT_DIR:-$PWD}
ENV_FILE="$PROJECT_DIR/.env.prod"
ALERTAS=0; AVISOS=0

if [ -t 1 ]; then R=$'\e[31m'; G=$'\e[32m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'; else R=; G=; Y=; B=; N=; fi
ok()    { [ "$QUIET" = 1 ] || printf '  %s[ OK  ]%s %s\n' "$G" "$N" "$*"; }
info()  { [ "$QUIET" = 1 ] || printf '  [ info ] %s\n' "$*"; }
warn()  { AVISOS=$((AVISOS + 1)); printf '  %s[AVISO ]%s %s\n' "$Y" "$N" "$*"; }
alert() { ALERTAS=$((ALERTAS + 1)); printf '  %s[ALERTA]%s %s\n' "$R" "$N" "$*"; }
sec()   { [ "$QUIET" = 1 ] || printf '\n%s== %s%s\n' "$B" "$*" "$N"; }

command -v docker >/dev/null 2>&1 || { echo "docker não encontrado"; exit 2; }
docker info >/dev/null 2>&1 || { echo "sem acesso ao daemon do docker (rode como root ou do grupo docker)"; exit 2; }

env_get() { [ -f "$ENV_FILE" ] && grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed 's/^"//; s/"$//'; }
BACKEND=thermoproactive_backend; DB=thermoproactive_db

[ "$QUIET" = 1 ] || printf '%sThermoProActive — verificação de produção (somente leitura)%s\n%s em %s\n' "$B" "$N" "$(date '+%Y-%m-%d %H:%M:%S %Z')" "$(hostname)"

# ---------------------------------------------------------------- compose em uso
sec "1. Compose em uso"
cfg=$(docker inspect -f '{{ index .Config.Labels "com.docker.compose.project.config_files" }}' "$BACKEND" 2>/dev/null || true)
MODE=desconhecido
case "$cfg" in
    *docker-compose.http.yml*) MODE=http ;;
    *docker-compose.prod.yml*) MODE=prod ;;
    *docker-compose.yml*)      MODE=dev ;;
esac
case "$MODE" in
    http) warn "stack HTTP-only (docker-compose.http.yml): sem TLS — sessão/credenciais trafegam em claro. Aceitável só para homologação; migrar para docker-compose.prod.yml com domínio." ;;
    prod) ok "stack de produção com TLS (docker-compose.prod.yml)" ;;
    dev)  alert "o container está rodando o compose de DESENVOLVIMENTO (docker-compose.yml): DEBUG=True, senhas padrão, seed_demo" ;;
    *)    alert "não identifiquei o compose do container $BACKEND (existe? config_files='$cfg')" ;;
esac

# --------------------------------------------------------------------- containers
sec "2. Containers e reinícios"
for c in $(docker ps -a --filter 'name=^thermoproactive_' --format '{{.Names}}' | sort); do
    line=$(docker inspect -f '{{.State.Status}}|{{.RestartCount}}|{{if .State.Health}}{{.State.Health.Status}}{{else}}sem-healthcheck{{end}}|{{.State.OOMKilled}}|{{.HostConfig.RestartPolicy.Name}}|{{.HostConfig.LogConfig.Type}}:{{index .HostConfig.LogConfig.Config "max-size"}}x{{index .HostConfig.LogConfig.Config "max-file"}}' "$c")
    IFS='|' read -r st rc hl oom pol lg <<EOF
$line
EOF
    msg="$c: $st, reinícios=$rc, saúde=$hl, restart=$pol, log=$lg"
    if [ "$st" != running ]; then alert "$msg"
    elif [ "$oom" = true ]; then alert "$msg (OOM-killed: faltou memória)"
    elif [ "$hl" = unhealthy ]; then alert "$msg"
    elif [ "$rc" -ge 3 ]; then warn "$msg (reiniciou várias vezes — veja 'docker logs $c')"
    else ok "$msg"; fi
    [ "$lg" = "json-file:x" ] && warn "$c: rotação de log NÃO configurada (disco pode encher)"
done
PRECISA="thermoproactive_db thermoproactive_backend thermoproactive_frontend thermoproactive_nginx thermoproactive_agendador thermoproactive_backup"
[ "$MODE" = prod ] && PRECISA="$PRECISA thermoproactive_caddy"   # HTTPS da stack prod
for need in $PRECISA; do
    docker inspect "$need" >/dev/null 2>&1 || {
        if [ "$need" = thermoproactive_backup ]; then alert "serviço de BACKUP não existe (compose antigo?). Sem backup automático."; else alert "container ausente: $need"; fi
    }
done

# ------------------------------------------------------------ configuração Django
sec "3. Configuração efetiva do Django (lida de dentro do container; sem imprimir segredos)"
PYCODE=$(cat <<'PY'
import os, sys
try:
    from django.conf import settings
    s = settings
    k = s.SECRET_KEY or ""
    defaults = ("dev-insecure-change-me-em-producao", "docker-dev-secret-troque-em-producao", "TROQUE-POR-UMA-CHAVE-ALEATORIA-LONGA")
    print("DEBUG=%s" % s.DEBUG)
    print("ALLOWED_HOSTS=%s" % ",".join(s.ALLOWED_HOSTS))
    print("SECRET_KEY_LEN=%d" % len(k))
    print("SECRET_KEY_UNIQUE=%d" % len(set(k)))
    print("SECRET_KEY_DEFAULT=%s" % (k in defaults or "troque" in k.lower() or "insecure" in k.lower()))
    print("COOKIES_SECURE=%s" % getattr(s, "COOKIES_SECURE", "n/d"))
    print("SESSION_COOKIE_SECURE=%s" % getattr(s, "SESSION_COOKIE_SECURE", "n/d"))
    print("CSRF_COOKIE_SECURE=%s" % getattr(s, "CSRF_COOKIE_SECURE", "n/d"))
    print("HSTS=%s" % getattr(s, "SECURE_HSTS_SECONDS", 0))
    print("DB_ENGINE=%s" % s.DATABASES["default"]["ENGINE"].rsplit(".", 1)[-1])
    print("EMAIL_BACKEND=%s" % s.EMAIL_BACKEND.rsplit(".", 1)[-1])
    print("CSRF_TRUSTED=%s" % ",".join(s.CSRF_TRUSTED_ORIGINS))
except Exception as e:
    print("ERRO=%s" % type(e).__name__)
    sys.exit(1)
PY
)
out=$(docker exec -i "$BACKEND" python -c "$PYCODE" 2>&1) || out="ERRO=$out"
get() { printf '%s\n' "$out" | sed -n "s/^$1=//p" | head -n 1; }
if [ -z "$(get DEBUG)" ]; then
    alert "não consegui ler as settings do backend: $(printf '%s' "$out" | tail -n 1 | cut -c1-160)"
else
    [ "$(get DEBUG)" = False ] && ok "DEBUG=False" || alert "DEBUG=$(get DEBUG) em produção (vaza código/variáveis em páginas de erro)"
    ah=$(get ALLOWED_HOSTS)
    case ",$ah," in
        *,\*,*) alert "ALLOWED_HOSTS contém '*' ($ah)" ;;
        ,,)     alert "ALLOWED_HOSTS vazio" ;;
        *)      ok "ALLOWED_HOSTS=$ah" ;;
    esac
    kl=$(get SECRET_KEY_LEN); ku=$(get SECRET_KEY_UNIQUE)
    if [ "$(get SECRET_KEY_DEFAULT)" = True ]; then alert "SECRET_KEY é um valor PADRÃO/de exemplo — qualquer um forja sessões e tokens. Gere outra e reinicie (todos farão login de novo)."
    elif [ "${kl:-0}" -lt 50 ] || [ "${ku:-0}" -lt 15 ]; then warn "SECRET_KEY curta ou pouco variada (tamanho=$kl, caracteres distintos=$ku). Recomendado >= 50 e token_urlsafe(64)."
    else ok "SECRET_KEY: tamanho=$kl, caracteres distintos=$ku (valor não exibido)"; fi
    cs=$(get COOKIES_SECURE)
    if [ "$cs" = True ]; then ok "COOKIES_SECURE=True (SESSION=$(get SESSION_COOKIE_SECURE), CSRF=$(get CSRF_COOKIE_SECURE), HSTS=$(get HSTS)s)"
    else
        if [ "$MODE" = http ]; then warn "COOKIES_SECURE=$cs — necessário no modo HTTP, mas cookies de sessão/CSRF trafegam em claro (risco aceito até haver HTTPS)"
        else alert "COOKIES_SECURE=$cs em ambiente com TLS: cookies sem flag Secure"; fi
    fi
    [ "$(get DB_ENGINE)" = postgresql ] && ok "banco: PostgreSQL" || alert "banco NÃO é PostgreSQL: $(get DB_ENGINE) (SQLite em produção?)"
    case "$(get EMAIL_BACKEND)" in
        console*|*Console*) warn "e-mails saem só no log (EMAIL_BACKEND console): convites/redefinição de senha não chegam ao usuário" ;;
        *) info "EMAIL_BACKEND=$(get EMAIL_BACKEND)" ;;
    esac
fi
u=$(docker exec "$BACKEND" id -u 2>/dev/null || echo "?")
[ "$u" = 0 ] && warn "backend roda como root dentro do container (uid 0) — ver recomendação I-04 em docs/19" || ok "backend roda como uid $u"

# ------------------------------------------------------------- migrações pendentes
sec "4. Migrações"
pend=$(docker exec "$BACKEND" python manage.py showmigrations --plan 2>/dev/null | grep -c '\[ \]' || true)
tot=$(docker exec "$BACKEND" python manage.py showmigrations --plan 2>/dev/null | grep -c '^\[' || true)
if [ -z "$tot" ] || [ "$tot" = 0 ]; then alert "não consegui consultar as migrações"
elif [ "$pend" = 0 ]; then ok "nenhuma migração pendente ($tot aplicadas)"
else alert "$pend migração(ões) PENDENTE(S) de $tot — rode: docker compose ... exec backend python manage.py migrate"
     docker exec "$BACKEND" python manage.py showmigrations --plan 2>/dev/null | grep '\[ \]' | head -n 8 | sed 's/^/           /'; fi

# --------------------------------------------------------------------- PostgreSQL
sec "5. PostgreSQL"
pgv=$(docker exec "$DB" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "show server_version"' 2>/dev/null || true)
if [ -n "$pgv" ]; then
    case "$pgv" in 16.*|17.*|18.*) ok "PostgreSQL $pgv" ;; *) warn "PostgreSQL $pgv (versão fora de suporte ou desconhecida)" ;; esac
    sz=$(docker exec "$DB" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select pg_size_pretty(pg_database_size(current_database()))"' 2>/dev/null || true)
    nc=$(docker exec "$DB" sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tAc "select count(*) from pg_stat_activity where datname=current_database()"' 2>/dev/null || true)
    info "tamanho do banco: ${sz:-?}; conexões ativas: ${nc:-?}"
else alert "não consegui consultar o PostgreSQL em $DB"; fi
pub=$(docker port "$DB" 2>/dev/null || true)
[ -z "$pub" ] && ok "banco NÃO está publicado no host (só rede interna)" || alert "banco PUBLICADO no host: $pub"

# ------------------------------------------------------------------------- backup
sec "6. Backup"
BHD=${BACKUP_HOST_DIR:-$(env_get BACKUP_HOST_DIR)}; BHD=${BHD:-/var/backups/thermoproactive}
BCD=${BACKUP_CONFIG_DIR:-$(env_get BACKUP_CONFIG_DIR)}; BCD=${BCD:-/root/.thermoproactive}
if [ -f "$BHD/state/last_success" ]; then
    ts=$(cut -d' ' -f1 "$BHD/state/last_success"); nm=$(cut -d' ' -f2 "$BHD/state/last_success")
    age_h=$(( ($(date +%s) - ts) / 3600 ))
    if [ "$age_h" -gt 36 ]; then alert "último backup bem-sucedido há ${age_h} h ($nm) — esperado < 30 h"
    else ok "último backup bem-sucedido há ${age_h} h ($nm)"; fi
    [ -f "$BHD/state/last_failure" ] && warn "houve falha registrada: $(cat "$BHD/state/last_failure")"
    for t in daily weekly monthly; do info "$t: $(ls "$BHD/$t" 2>/dev/null | grep -c '\.sha256$') conjunto(s)"; done
    info "ocupação de $BHD: $(du -sh "$BHD" 2>/dev/null | cut -f1)"
else
    alert "nenhum backup bem-sucedido encontrado em $BHD/state/last_success"
fi
if [ -f "$BCD/backup.passphrase" ]; then
    perm=$(stat -c '%a' "$BCD/backup.passphrase" 2>/dev/null || echo ?)
    [ "$perm" = 600 ] || [ "$perm" = 400 ] && ok "frase-secreta presente (modo $perm)" || warn "frase-secreta com permissão $perm (esperado 600)"
else
    alert "frase-secreta do backup ausente em $BCD/backup.passphrase"
fi
rem=$(docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' thermoproactive_backup 2>/dev/null | sed -n 's/^BACKUP_RCLONE_REMOTE=//p' | head -n 1)
[ -n "$rem" ] && ok "destino EXTERNO configurado (${rem%%:*}:...)" || alert "destino externo de backup NÃO configurado — os backups estão só nesta VPS (perda da VPS = perda dos dados e dos backups)"
bh=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{end}}' thermoproactive_backup 2>/dev/null || true)
[ -n "$bh" ] && info "healthcheck do serviço backup: $bh"

# --------------------------------------------------------------------------- disco
sec "7. Disco e Docker"
while read -r pct avail mnt; do
    n=${pct%\%}
    case "$n" in ''|*[!0-9]*) continue ;; esac
    if [ "$n" -ge 90 ]; then alert "disco $mnt em ${pct} (livre $avail)"
    elif [ "$n" -ge 80 ]; then warn "disco $mnt em ${pct} (livre $avail)"
    else ok "disco $mnt em ${pct} (livre $avail)"; fi
done <<EOF
$(df -hP / /var/lib/docker "$BHD" 2>/dev/null | awk 'NR>1 && !seen[$NF]++ {print $(NF-1), $(NF-2), $NF}')
EOF
info "uso do Docker: $(docker system df --format '{{.Type}}={{.Size}}' 2>/dev/null | tr '\n' ' ')"

# --------------------------------------------------------------------------- portas
sec "8. Portas abertas para fora (esperado: 22, 80, 443)"
if command -v ss >/dev/null 2>&1; then
    extra=""
    for p in $(ss -H -tln 2>/dev/null | awk '{print $4}' | grep -vE '^(127\.|\[::1\]|::1)' | sed 's/.*://' | sort -un); do
        case "$p" in 22|80|443) ok "porta $p aberta (esperada)" ;; *) extra="$extra $p" ;; esac
    done
    [ -z "$extra" ] && ok "nenhuma porta inesperada em escuta" || alert "portas INESPERADAS em escuta fora do loopback:$extra — confira 'ss -tlnp' e o firewall"
else warn "'ss' indisponível — não verifiquei portas"; fi
pubs=$(docker ps --format '{{.Names}} {{.Ports}}' --filter 'name=^thermoproactive_' | grep -E '0\.0\.0\.0|\[::\]' || true)
[ -n "$pubs" ] && printf '%s\n' "$pubs" | sed 's/^/           publicado: /'
if command -v ufw >/dev/null 2>&1; then info "ufw: $(ufw status 2>/dev/null | head -n 1)"; else warn "ufw não encontrado — confirme que há firewall (no provedor ou no host)"; fi
info "lembrete: o Docker publica portas direto no iptables, ignorando o ufw; por isso só o proxy da frente publica portas (Caddy na stack prod, nginx na http)."

# ------------------------------------------------------------------- certificado TLS
if [ "$MODE" = prod ]; then
    sec "9. Certificado TLS"
    dom=$(env_get DOMAIN)
    if [ -n "$dom" ] && command -v openssl >/dev/null 2>&1; then
        end=$(echo | openssl s_client -connect "$dom:443" -servername "$dom" 2>/dev/null | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2)
        if [ -n "$end" ]; then
            dias=$(( ($(date -d "$end" +%s) - $(date +%s)) / 86400 ))
            if [ "$dias" -lt 7 ]; then alert "certificado de $dom expira em $dias dia(s) ($end)"
            elif [ "$dias" -lt 20 ]; then warn "certificado de $dom expira em $dias dias — a renovação automática deveria ter ocorrido"
            else ok "certificado de $dom válido por mais $dias dias"; fi
        else alert "não consegui obter o certificado de $dom:443"; fi
    else info "DOMAIN/openssl indisponível — verificação de certificado pulada"; fi
fi

sec "Resumo"
printf '  %s ALERTA(s), %s AVISO(s)\n' "$ALERTAS" "$AVISOS"
[ "$ALERTAS" -eq 0 ]
