#!/bin/sh
# =============================================================================
# common.sh — funções e padrões compartilhados por backup.sh / restore.sh /
# agendar.sh / healthcheck.sh. POSIX sh (roda em alpine/busybox e em Debian).
# Não é executado diretamente: é "sourced" pelos outros scripts.
# =============================================================================

: "${PGHOST:=db}"
: "${PGPORT:=5432}"
: "${BACKUP_DIR:=/backups}"
: "${MEDIA_DIR:=/data/media}"
: "${BACKUP_PASSPHRASE_FILE:=/config/backup.passphrase}"
: "${BACKUP_KEEP_DAILY:=7}"
: "${BACKUP_KEEP_WEEKLY:=4}"
: "${BACKUP_KEEP_MONTHLY:=12}"
: "${BACKUP_WEEKLY_DOW:=7}"            # dia da semana (1=seg ... 7=dom) promovido a "semanal"
: "${BACKUP_REMOTE_RETENTION_DAYS:=400}" # 0 = nunca apagar no destino externo
: "${BACKUP_MAX_AGE_HOURS:=30}"        # idade máxima do último sucesso p/ healthcheck
export PGHOST PGPORT

TS_FMT='+%Y-%m-%dT%H:%M:%SZ'

log() {
    printf '%s [%s] %s\n' "$(date -u "$TS_FMT")" "${LOG_TAG:-backup}" "$*" | tee -a "${LOG_FILE:-/dev/null}"
}

die() {
    # die <código> <mensagem...>
    _code=$1; shift
    log "ERRO: $*"
    exit "$_code"
}

is_pos_int() {
    case "$1" in
        ''|*[!0-9]*) return 1 ;;
        0) return 1 ;;
    esac
    return 0
}

# Valida o arquivo da frase-secreta: precisa existir, ser ARQUIVO REGULAR e ter
# pelo menos 16 caracteres. (Se o bind mount apontar para um arquivo que não
# existe, o Docker cria um DIRETÓRIO no lugar — detectamos isso aqui.)
check_passphrase() {
    [ -f "$BACKUP_PASSPHRASE_FILE" ] || die 2 "frase-secreta ausente (ou é um diretório): $BACKUP_PASSPHRASE_FILE — veja docs/19-OPERACAO-DEPLOY-BACKUP.md, seção Backup"
    _n=$(head -n 1 "$BACKUP_PASSPHRASE_FILE" | tr -d '\r\n' | wc -c)
    [ "$_n" -ge 16 ] || die 2 "frase-secreta curta demais ($_n caracteres; mínimo 16): $BACKUP_PASSPHRASE_FILE"
}

# GNUPGHOME descartável: não toca em ~/.gnupg e some junto com o diretório temporário.
init_gpg() {
    GNUPGHOME=$(mktemp -d "${TMPDIR:-/tmp}/gnupg.XXXXXX")
    chmod 700 "$GNUPGHOME"
    export GNUPGHOME
}

cleanup_gpg() {
    if [ -n "${GNUPGHOME:-}" ] && [ -d "$GNUPGHOME" ]; then
        gpgconf --kill gpg-agent >/dev/null 2>&1 || true
        rm -rf "$GNUPGHOME"
    fi
}

# stdin -> stdout, AES-256, frase lida de arquivo (nunca aparece em argv/env).
gpg_encrypt() {
    gpg --batch --yes --quiet --no-tty --pinentry-mode loopback \
        --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
        --symmetric --cipher-algo AES256 \
        --s2k-mode 3 --s2k-digest-algo SHA512 --s2k-count 65011712 \
        --compress-algo none -o -
}

# arquivo -> stdout
gpg_decrypt() {
    gpg --batch --yes --quiet --no-tty --pinentry-mode loopback \
        --passphrase-file "$BACKUP_PASSPHRASE_FILE" \
        --decrypt "$1"
}
