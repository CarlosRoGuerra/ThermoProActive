#!/bin/sh
# =============================================================================
# backup.sh — backup completo do ThermoProActive (banco + arquivos enviados).
#
#   1. pg_dump -Fc do PostgreSQL (rede interna do compose; o banco não é exposto)
#   2. tar.gz do diretório de mídia (logos, assinaturas, fotos, evidências)
#   3. cada artefato é CRIPTOGRAFADO (gpg --symmetric, AES-256) em streaming —
#      nenhum dado em claro toca o disco
#   4. verificação: descriptografa de volta e lê o índice do dump / a lista do tar
#   5. sha256 + metadados; retenção em camadas (diária/semanal/mensal)
#   6. envio opcional a um destino externo via rclone (qualquer provedor)
#
# Saída:  $BACKUP_DIR/{daily,weekly,monthly}/tpa_<UTC>_db.dump.gpg
#                                            tpa_<UTC>_media.tar.gz.gpg
#                                            tpa_<UTC>.sha256   tpa_<UTC>.meta
# Código de saída: 0 ok | 1 falha genérica | 2 configuração | 3 pg_dump | 4 mídia
#                  5 verificação | 6 envio externo (o backup LOCAL está íntegro)
# Variáveis: ver deploy/backup/common.sh e .env.prod.example (seção Backup).
# =============================================================================
set -eu
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

LOG_TAG=backup
STATE_DIR="$BACKUP_DIR/state"
mkdir -p "$STATE_DIR" "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly" "$BACKUP_DIR/monthly" "$BACKUP_DIR/.tmp"
LOG_FILE="$STATE_DIR/backup.log"
# rotação simples do log (5 MB)
if [ -f "$LOG_FILE" ] && [ "$(wc -c < "$LOG_FILE")" -gt 5242880 ]; then
    mv -f "$LOG_FILE" "$LOG_FILE.1"
fi

NAME="tpa_$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$BACKUP_DIR/.tmp/$NAME"
STAGE=inicio
LOCK="$STATE_DIR/lock"
HAVE_LOCK=0

alert() {
    [ -n "${BACKUP_ALERT_WEBHOOK:-}" ] || return 0
    _msg="ThermoProActive backup FALHOU em $(hostname) ($NAME, etapa: $STAGE). Veja $LOG_FILE"
    curl -fsS -m 15 -X POST -H 'Content-Type: application/json' \
        -d "{\"text\":\"$_msg\",\"content\":\"$_msg\"}" "$BACKUP_ALERT_WEBHOOK" >/dev/null 2>&1 \
        || log "aviso: não consegui notificar o webhook de alerta"
}

on_exit() {
    _rc=$?
    trap - EXIT
    cleanup_gpg
    rm -rf "$WORK"
    if [ "$_rc" -ne 0 ]; then
        printf '%s %s rc=%s etapa=%s\n' "$(date -u "$TS_FMT")" "$NAME" "$_rc" "$STAGE" > "$STATE_DIR/last_failure"
        log "FALHA (código $_rc, etapa '$STAGE') — nenhum backup novo foi marcado como bem-sucedido"
        alert
    fi
    if [ "$HAVE_LOCK" = 1 ]; then rm -rf "$LOCK"; fi
    exit "$_rc"
}
trap on_exit EXIT
trap 'exit 143' TERM INT

# --- 0. pré-requisitos --------------------------------------------------------
STAGE=configuracao
is_pos_int "$BACKUP_KEEP_DAILY" || die 2 "BACKUP_KEEP_DAILY deve ser inteiro >= 1 (recebido: '$BACKUP_KEEP_DAILY')"
is_pos_int "$BACKUP_KEEP_WEEKLY" || die 2 "BACKUP_KEEP_WEEKLY deve ser inteiro >= 1 (recebido: '$BACKUP_KEEP_WEEKLY')"
is_pos_int "$BACKUP_KEEP_MONTHLY" || die 2 "BACKUP_KEEP_MONTHLY deve ser inteiro >= 1 (recebido: '$BACKUP_KEEP_MONTHLY')"
: "${PGUSER:?PGUSER não definido}"
: "${PGDATABASE:?PGDATABASE não definido}"
: "${PGPASSWORD:?PGPASSWORD não definido}"
export PGUSER PGDATABASE PGPASSWORD
check_passphrase
if [ "${BACKUP_SKIP_MEDIA:-0}" != 1 ]; then
    [ -d "$MEDIA_DIR" ] || die 2 "diretório de mídia inexistente: $MEDIA_DIR (use BACKUP_SKIP_MEDIA=1 só em teste)"
fi

# lock (mkdir é atômico); lock órfão com mais de 6 h é descartado
if ! mkdir "$LOCK" 2>/dev/null; then
    if [ -n "$(find "$LOCK" -maxdepth 0 -mmin +360 2>/dev/null)" ]; then
        log "lock antigo (>6h) removido"; rm -rf "$LOCK"; mkdir "$LOCK"
    else
        die 1 "outro backup está em andamento ($LOCK)"
    fi
fi
HAVE_LOCK=1
# Com o lock na mão, nenhum outro backup roda: sobras em .tmp são de execução
# interrompida (kill -9, queda do host) que o trap EXIT não limpou.
find "$BACKUP_DIR/.tmp" -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
init_gpg
mkdir -p "$WORK"

log "=== início $NAME (banco $PGUSER@$PGHOST:$PGPORT/$PGDATABASE; mídia ${MEDIA_DIR}) ==="
_free_kb=$(df -Pk "$BACKUP_DIR" | awk 'NR==2{print $4}')
log "espaço livre em $BACKUP_DIR: $((_free_kb / 1024)) MB"
[ "$_free_kb" -gt 262144 ] || die 1 "menos de 256 MB livres em $BACKUP_DIR"

# --- 1. banco -----------------------------------------------------------------
STAGE=pg_dump
DB_FILE="$WORK/${NAME}_db.dump.gpg"
{ pg_dump --format=custom --no-password || : > "$WORK/dump.failed"; } | gpg_encrypt > "$DB_FILE"
[ ! -e "$WORK/dump.failed" ] || die 3 "pg_dump falhou"
[ -s "$DB_FILE" ] || die 3 "dump criptografado vazio"
PG_VERSION=$(psql --no-password -tAc 'show server_version' 2>/dev/null || echo desconhecida)
MIGRATIONS=$(psql --no-password -tAc 'select count(*) from django_migrations' 2>/dev/null || echo n/d)
log "banco: $(wc -c < "$DB_FILE") bytes criptografados (PostgreSQL $PG_VERSION, $MIGRATIONS migrações aplicadas)"

# --- 2. mídia -----------------------------------------------------------------
MEDIA_FILE="$WORK/${NAME}_media.tar.gz.gpg"
MEDIA_COUNT=0
STAGE=midia
if [ "${BACKUP_SKIP_MEDIA:-0}" = 1 ]; then
    log "AVISO: mídia ignorada (BACKUP_SKIP_MEDIA=1)"
else
    # tar sai com 1 quando um arquivo muda durante a leitura: é aviso, não falha.
    {
        _trc=0
        tar -C "$MEDIA_DIR" -czf - . || _trc=$?
        if [ "$_trc" -gt 1 ]; then : > "$WORK/tar.failed"; fi
        # (stdout deste bloco é o fluxo criptografado: o log vai para stderr)
        if [ "$_trc" -eq 1 ]; then log "aviso: arquivos mudaram durante a leitura da mídia (tar rc=1)" >&2; fi
    } | gpg_encrypt > "$MEDIA_FILE"
    [ ! -e "$WORK/tar.failed" ] || die 4 "tar da mídia falhou"
    [ -s "$MEDIA_FILE" ] || die 4 "arquivo de mídia criptografado vazio"
    MEDIA_COUNT=$(find "$MEDIA_DIR" -type f | wc -l)
    log "mídia: $MEDIA_COUNT arquivos, $(wc -c < "$MEDIA_FILE") bytes criptografados"
fi

# --- 3. verificação (descriptografa e lê de volta) -----------------------------
STAGE=verificacao
_toc=$(gpg_decrypt "$DB_FILE" 2>/dev/null | pg_restore --list 2>/dev/null | grep -c '^[0-9][0-9]*;' || true)
[ "$_toc" -gt 0 ] || die 5 "não consegui descriptografar/ler o índice do dump"
log "verificação do dump: descriptografa e lista $_toc itens"
if [ "${BACKUP_SKIP_MEDIA:-0}" != 1 ]; then
    _tarn=$(gpg_decrypt "$MEDIA_FILE" | tar -tzf - 2>/dev/null | grep -vc '/$' || true)
    if [ "$MEDIA_COUNT" -gt 0 ] && [ "$_tarn" -eq 0 ]; then die 5 "tar da mídia não lista arquivos"; fi
    log "verificação da mídia: $_tarn arquivos no tar (origem: $MEDIA_COUNT)"
fi

# --- 4. checksums e metadados --------------------------------------------------
STAGE=metadados
{
    echo "name=$NAME"
    echo "created_utc=$(date -u "$TS_FMT")"
    echo "host=$(hostname)"
    echo "postgres_server=$PG_VERSION"
    echo "django_migrations=$MIGRATIONS"
    echo "dump_toc_items=$_toc"
    echo "media_files=$MEDIA_COUNT"
    echo "cipher=gpg-symmetric-AES256"
} > "$WORK/$NAME.meta"
(
    cd "$WORK"
    _files="${NAME}_db.dump.gpg"
    if [ -s "${NAME}_media.tar.gz.gpg" ]; then _files="$_files ${NAME}_media.tar.gz.gpg"; fi
    # shellcheck disable=SC2086
    sha256sum $_files "$NAME.meta" > "$NAME.sha256"
)
rm -f "$WORK/dump.failed" "$WORK/tar.failed"

# --- 5. publicação local + retenção em camadas ---------------------------------
STAGE=retencao
_publish() { # <camada>
    for _f in "$WORK/$NAME".* "$WORK/${NAME}_"*; do
        [ -e "$_f" ] || continue
        ln -f "$_f" "$BACKUP_DIR/$1/$(basename "$_f")" 2>/dev/null || cp -p "$_f" "$BACKUP_DIR/$1/$(basename "$_f")"
    done
}
_prune() { # <camada> <manter>
    ls -1 "$BACKUP_DIR/$1" | grep '^tpa_[0-9TZ]*\.sha256$' | sort -r | tail -n "+$(($2 + 1))" | while read -r _m; do
        _n=${_m%.sha256}
        log "retenção ($1): removendo $_n"
        rm -f "$BACKUP_DIR/$1/$_n".* "$BACKUP_DIR/$1/${_n}_"*
    done
}
_publish daily
TIERS="daily"
if [ "$(date -u +%u)" = "$BACKUP_WEEKLY_DOW" ]; then _publish weekly; TIERS="$TIERS weekly"; fi
if [ "$(date -u +%d)" = "01" ]; then _publish monthly; TIERS="$TIERS monthly"; fi
_prune daily "$BACKUP_KEEP_DAILY"
_prune weekly "$BACKUP_KEEP_WEEKLY"
_prune monthly "$BACKUP_KEEP_MONTHLY"
printf '%s %s\n' "$(date -u +%s)" "$NAME" > "$STATE_DIR/last_local_ok"
log "backup local concluído: $NAME (camadas: $TIERS). Ocupação total: $(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)"

# --- 6. envio externo (opcional) -----------------------------------------------
if [ -n "${BACKUP_RCLONE_REMOTE:-}" ]; then
    STAGE=envio-externo
    command -v rclone >/dev/null 2>&1 || die 6 "rclone não instalado"
    export RCLONE_CONFIG="${RCLONE_CONFIG:-/config/rclone.conf}"
    for _t in $TIERS; do
        log "rclone: enviando $NAME ($_t) para ${BACKUP_RCLONE_REMOTE%%:*}:..."
        rclone copy "$BACKUP_DIR/$_t" "$BACKUP_RCLONE_REMOTE/$_t" \
            --include "$NAME.*" --include "${NAME}_*" --retries 3 --low-level-retries 5 \
            || die 6 "rclone copy falhou ($_t) — backup local íntegro, envio externo NÃO concluído"
        rclone check "$BACKUP_DIR/$_t" "$BACKUP_RCLONE_REMOTE/$_t" \
            --include "$NAME.*" --include "${NAME}_*" --one-way --size-only \
            || die 6 "rclone check falhou ($_t): destino não confere com a origem"
    done
    if [ "$BACKUP_REMOTE_RETENTION_DAYS" != 0 ]; then
        rclone delete "$BACKUP_RCLONE_REMOTE" --min-age "${BACKUP_REMOTE_RETENTION_DAYS}d" --include "tpa_*" \
            || log "aviso: limpeza de retenção no destino externo falhou (não crítico)"
    fi
    log "envio externo concluído e conferido"
else
    log "envio externo: NÃO configurado (BACKUP_RCLONE_REMOTE vazio) — cópias só neste servidor"
fi

STAGE=fim
printf '%s %s\n' "$(date -u +%s)" "$NAME" > "$STATE_DIR/last_success"
rm -f "$STATE_DIR/last_failure"
log "=== SUCESSO $NAME ==="
