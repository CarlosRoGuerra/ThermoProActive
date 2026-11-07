#!/bin/sh
# =============================================================================
# restore.sh — restaura um backup do ThermoProActive (banco e/ou mídia).
#
# Uso:
#   restore.sh --set <tpa_AAAAMMDDTHHMMSSZ | latest> [--tier daily|weekly|monthly]
#              [--from-dir DIR]                       (backup baixado do destino externo)
#              --db-host H --db-name N [--db-port 5432] [--db-user U]   (senha: RESTORE_PGPASSWORD)
#              --media-dir DIR
#              [--no-db] [--no-media] [--clean] [--yes] [--allow-production]
#
# SEGURANÇA
#  * Não há destino padrão: banco e diretório de destino são SEMPRE informados.
#  * Banco já com tabelas, ou diretório de mídia não vazio => recusa, a menos que
#    --clean (que apaga o conteúdo existente antes de restaurar).
#  * "Produção" = o par host/banco em RESTORE_PRODUCTION_DB (ex.: db/thermoproactive)
#    ou o diretório em RESTORE_PRODUCTION_MEDIA. Restaurar por cima exige
#    --allow-production E digitar a frase de confirmação (ou RESTORE_CONFIRM_PRODUCTION).
#  * Sem --yes, pede confirmação digitada; sem terminal e sem --yes => recusa.
#
# Código de saída: 0 ok | 1 falha | 2 uso/configuração | 3 recusado (produção)
#                  4 recusado (destino não vazio) | 5 checksum/descriptografia
# =============================================================================
set -eu
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"
LOG_TAG=restore
LOG_FILE=/dev/null

SET=""; TIER=daily; FROM_DIR=""
DB_HOST=""; DB_PORT=5432; DB_USER=""; DB_NAME=""; MEDIA_TARGET=""
DO_DB=1; DO_MEDIA=1; CLEAN=0; YES=0; ALLOW_PROD=0

usage() { sed -n '2,24p' "$0" | sed 's/^# \{0,1\}//'; exit 2; }

while [ $# -gt 0 ]; do
    case "$1" in
        --set) SET=${2:?}; shift 2 ;;
        --tier) TIER=${2:?}; shift 2 ;;
        --from-dir) FROM_DIR=${2:?}; shift 2 ;;
        --db-host) DB_HOST=${2:?}; shift 2 ;;
        --db-port) DB_PORT=${2:?}; shift 2 ;;
        --db-user) DB_USER=${2:?}; shift 2 ;;
        --db-name) DB_NAME=${2:?}; shift 2 ;;
        --media-dir) MEDIA_TARGET=${2:?}; shift 2 ;;
        --no-db) DO_DB=0; shift ;;
        --no-media) DO_MEDIA=0; shift ;;
        --clean) CLEAN=1; shift ;;
        --yes) YES=1; shift ;;
        --allow-production) ALLOW_PROD=1; shift ;;
        -h|--help) usage ;;
        *) echo "argumento desconhecido: $1" >&2; usage ;;
    esac
done

[ -n "$SET" ] || usage
case "$TIER" in daily|weekly|monthly) ;; *) die 2 "--tier inválido: $TIER" ;; esac
if [ "$DO_DB" = 1 ]; then
    [ -n "$DB_HOST" ] && [ -n "$DB_NAME" ] || die 2 "informe --db-host e --db-name (ou use --no-db)"
    DB_USER=${DB_USER:-${PGUSER:-}}
    [ -n "$DB_USER" ] || die 2 "informe --db-user (ou PGUSER)"
    : "${RESTORE_PGPASSWORD:?defina RESTORE_PGPASSWORD (senha do usuário do banco de destino)}"
    case "$DB_NAME$DB_USER" in *[!A-Za-z0-9_]*) die 2 "nome de banco/usuário só pode ter letras, números e _" ;; esac
fi
if [ "$DO_MEDIA" = 1 ]; then
    [ -n "$MEDIA_TARGET" ] || die 2 "informe --media-dir (ou use --no-media)"
fi

SRC=${FROM_DIR:-$BACKUP_DIR/$TIER}
[ -d "$SRC" ] || die 2 "diretório de backups inexistente: $SRC"
if [ "$SET" = latest ]; then
    SET=$(ls -1 "$SRC" | grep '^tpa_[0-9TZ]*\.sha256$' | sort | tail -n 1 | sed 's/\.sha256$//')
    [ -n "$SET" ] || die 2 "nenhum backup encontrado em $SRC"
fi
case "$SET" in tpa_[0-9]*Z) ;; *) die 2 "nome de backup inválido: $SET" ;; esac
[ -f "$SRC/$SET.sha256" ] || die 2 "backup não encontrado: $SRC/$SET.sha256"

check_passphrase
init_gpg
trap 'cleanup_gpg' EXIT

log "backup escolhido: $SET (origem: $SRC)"
[ -f "$SRC/$SET.meta" ] && sed 's/^/    /' "$SRC/$SET.meta"

# --- integridade ---------------------------------------------------------------
( cd "$SRC" && sha256sum -c "$SET.sha256" ) || die 5 "checksum NÃO confere — backup corrompido ou adulterado; nada foi restaurado"
log "checksums sha256 conferem"
if [ "$DO_DB" = 1 ]; then
    gpg_decrypt "$SRC/${SET}_db.dump.gpg" 2>/dev/null | pg_restore --list >/dev/null 2>&1 \
        || die 5 "não consegui descriptografar o dump (frase-secreta errada?)"
    log "dump descriptografa e o índice é legível"
fi

# --- guarda de produção --------------------------------------------------------
IS_PROD=0
if [ "$DO_DB" = 1 ] && [ -n "${RESTORE_PRODUCTION_DB:-}" ] && [ "$DB_HOST/$DB_NAME" = "$RESTORE_PRODUCTION_DB" ]; then IS_PROD=1; fi
# Comparar só o texto deixava passar outro nome para o MESMO servidor (nome do
# container, IP, alias). Identidade real: system_identifier do cluster + nome do
# banco. Se não der para identificar o destino, trata como produção (falha fechada).
cluster_id() {
    PGPASSWORD="$RESTORE_PGPASSWORD" psql --no-password -h "$1" -p "$DB_PORT" -U "$DB_USER" -d postgres \
        -tAc 'select system_identifier from pg_control_system()' 2>/dev/null
}
if [ "$IS_PROD" = 0 ] && [ "$DO_DB" = 1 ] && [ -n "${RESTORE_PRODUCTION_DB:-}" ] && [ "$DB_NAME" = "${RESTORE_PRODUCTION_DB#*/}" ]; then
    _id_prod=$(cluster_id "${RESTORE_PRODUCTION_DB%%/*}" || true)
    _id_dest=$(cluster_id "$DB_HOST" || true)
    if [ -n "$_id_prod" ] && { [ -z "$_id_dest" ] || [ "$_id_prod" = "$_id_dest" ]; }; then IS_PROD=1; fi
fi
if [ "$DO_MEDIA" = 1 ] && [ -n "${RESTORE_PRODUCTION_MEDIA:-}" ]; then
    _alvo=$(readlink -f "$MEDIA_TARGET" 2>/dev/null || echo "$MEDIA_TARGET")
    _prod=$(readlink -f "$RESTORE_PRODUCTION_MEDIA" 2>/dev/null || echo "$RESTORE_PRODUCTION_MEDIA")
    if [ "$_alvo" = "$_prod" ]; then IS_PROD=1; fi
fi
if [ "$IS_PROD" = 1 ]; then
    [ "$ALLOW_PROD" = 1 ] || die 3 "o destino é PRODUÇÃO ($DB_HOST/$DB_NAME ${MEDIA_TARGET:+mídia $MEDIA_TARGET}). Recusado: restaure em um banco/volume de teste ou passe --allow-production (leia a seção de restauração em docs/19-OPERACAO-DEPLOY-BACKUP.md)."
    log "ATENÇÃO: restauração sobre PRODUÇÃO autorizada por --allow-production"
fi

# --- confirmação explícita -----------------------------------------------------
PHRASE="SOBRESCREVER PRODUCAO"
if [ "$IS_PROD" = 1 ]; then
    if [ "${RESTORE_CONFIRM_PRODUCTION:-}" != "$PHRASE" ]; then
        [ -t 0 ] || die 3 "produção exige terminal interativo (ou RESTORE_CONFIRM_PRODUCTION='$PHRASE')"
        printf 'Isto SUBSTITUI os dados de produção por %s.\nDigite exatamente "%s" para continuar: ' "$SET" "$PHRASE"
        read -r _ans
        [ "$_ans" = "$PHRASE" ] || die 3 "confirmação incorreta — nada foi alterado"
    fi
elif [ "$YES" != 1 ]; then
    [ -t 0 ] || die 2 "sem terminal: use --yes para confirmar a restauração em destino não-produção"
    printf 'Restaurar %s em banco "%s" (%s) / mídia "%s"? Digite "sim": ' "$SET" "${DB_NAME:--}" "${DB_HOST:--}" "${MEDIA_TARGET:--}"
    read -r _ans
    [ "$_ans" = "sim" ] || die 2 "cancelado — nada foi alterado"
fi

# --- banco ---------------------------------------------------------------------
if [ "$DO_DB" = 1 ]; then
    export PGPASSWORD="$RESTORE_PGPASSWORD"
    PSQL="psql --no-password -h $DB_HOST -p $DB_PORT -U $DB_USER"
    $PSQL -d postgres -tAc 'select 1' >/dev/null || die 1 "não consegui conectar em $DB_USER@$DB_HOST:$DB_PORT"
    if [ "$($PSQL -d postgres -tAc "select count(*) from pg_database where datname='$DB_NAME'")" = 0 ]; then
        log "criando banco $DB_NAME"
        $PSQL -d postgres -c "create database \"$DB_NAME\"" >/dev/null
    fi
    _tabs=$($PSQL -d "$DB_NAME" -tAc "select count(*) from information_schema.tables where table_schema='public'")
    RESTORE_OPTS=""
    if [ "$_tabs" -gt 0 ]; then
        [ "$CLEAN" = 1 ] || die 4 "o banco $DB_NAME já tem $_tabs tabelas. Recusado. Use um banco vazio ou --clean (apaga os objetos existentes)."
        RESTORE_OPTS="--clean --if-exists"
        log "--clean: objetos existentes em $DB_NAME serão substituídos"
    fi
    log "restaurando banco em $DB_USER@$DB_HOST:$DB_PORT/$DB_NAME (transação única; falha = nada é aplicado)"
    # shellcheck disable=SC2086
    gpg_decrypt "$SRC/${SET}_db.dump.gpg" | pg_restore --no-password -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
        --no-owner --no-privileges --single-transaction --exit-on-error $RESTORE_OPTS \
        || die 1 "pg_restore falhou — a transação foi desfeita"
    $PSQL -d "$DB_NAME" -qc 'analyze' >/dev/null 2>&1 || true
    _mig=$($PSQL -d "$DB_NAME" -tAc 'select count(*) from django_migrations' 2>/dev/null || echo n/d)
    _expected=$(sed -n 's/^django_migrations=//p' "$SRC/$SET.meta" 2>/dev/null || true)
    log "banco restaurado. django_migrations: $_mig (no backup: ${_expected:-n/d})"
    if [ -n "$_expected" ] && [ "$_mig" != "$_expected" ]; then log "AVISO: contagem de migrações difere do metadado do backup"; fi
fi

# --- mídia ---------------------------------------------------------------------
if [ "$DO_MEDIA" = 1 ]; then
    if [ ! -f "$SRC/${SET}_media.tar.gz.gpg" ]; then
        log "AVISO: este backup não tem arquivo de mídia — nada a restaurar"
    else
        # Valida o tar ANTES de apagar qualquer coisa do destino.
        _lista=$(gpg_decrypt "$SRC/${SET}_media.tar.gz.gpg" | tar -tzf -) || die 5 "não consegui ler o tar da mídia — nada foi apagado"
        _bad=$(printf '%s\n' "$_lista" | grep -cE '(^/|(^|/)\.\.(/|$))' || true)
        [ "$_bad" -eq 0 ] || die 5 "o tar da mídia contém caminhos absolutos ou com '..' — recusado"
        mkdir -p "$MEDIA_TARGET"
        if [ -n "$(ls -A "$MEDIA_TARGET" 2>/dev/null)" ]; then
            [ "$CLEAN" = 1 ] || die 4 "diretório de mídia $MEDIA_TARGET não está vazio. Recusado. Use um diretório vazio ou --clean."
            log "--clean: esvaziando $MEDIA_TARGET"
            find "$MEDIA_TARGET" -mindepth 1 -delete
        fi
        gpg_decrypt "$SRC/${SET}_media.tar.gz.gpg" | tar -xzf - -C "$MEDIA_TARGET" --no-same-owner \
            || die 1 "extração da mídia falhou"
        _n=$(find "$MEDIA_TARGET" -type f | wc -l)
        _exp=$(sed -n 's/^media_files=//p' "$SRC/$SET.meta" 2>/dev/null || true)
        log "mídia restaurada em $MEDIA_TARGET: $_n arquivos (no backup: ${_exp:-n/d})"
    fi
fi

log "=== restauração concluída ($SET) ==="
