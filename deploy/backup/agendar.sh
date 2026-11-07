#!/bin/sh
# =============================================================================
# agendar.sh — laço de agendamento do serviço `backup` (mesmo padrão do serviço
# `agendador`: viaja com o repositório, sobe/desce junto com o compose, sem cron
# no host e sem depender de configuração fora do repo).
#
# Roda backup.sh uma vez por dia a partir de BACKUP_AT (HH:MM, fuso TZ do
# container). Se o container estava parado na hora marcada, roda assim que
# subir (o laço não perde o dia). Em caso de falha, tenta de novo a cada
# BACKUP_RETRY_MINUTES, até BACKUP_MAX_TENTATIVAS por dia — o estado fica em
# $BACKUP_DIR/state e sobrevive a reinícios.
#
# Para um backup imediato:  docker compose ... exec backup /backup/backup.sh
# =============================================================================
set -u
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
# shellcheck source=common.sh
. "$SCRIPT_DIR/common.sh"

LOG_TAG=agendador-backup
: "${BACKUP_AT:=03:15}"
: "${BACKUP_RETRY_MINUTES:=30}"
: "${BACKUP_MAX_TENTATIVAS:=4}"
STATE_DIR="$BACKUP_DIR/state"
mkdir -p "$STATE_DIR"
LOG_FILE="$STATE_DIR/backup.log"

to_min() { echo $(( $(expr "${1%:*}" + 0) * 60 + $(expr "${1#*:}" + 0) )); }

case "$BACKUP_AT" in
    [01][0-9]:[0-5][0-9]|2[0-3]:[0-5][0-9]) ;;
    *) die 2 "BACKUP_AT inválido ('$BACKUP_AT'); use HH:MM" ;;
esac
AT_MIN=$(to_min "$BACKUP_AT")

trap 'log "encerrando"; exit 0' TERM INT

log "agendador de backup iniciado: diário às $BACKUP_AT (TZ=${TZ:-UTC}), até $BACKUP_MAX_TENTATIVAS tentativas/dia; retenção D${BACKUP_KEEP_DAILY}/S${BACKUP_KEEP_WEEKLY}/M${BACKUP_KEEP_MONTHLY}; destino externo: $( [ -n "${BACKUP_RCLONE_REMOTE:-}" ] && echo configurado || echo NÃO configurado )"
if [ ! -f "$BACKUP_PASSPHRASE_FILE" ]; then
    log "AVISO: frase-secreta ausente em $BACKUP_PASSPHRASE_FILE — os backups vão FALHAR até ela ser criada (docs/19, seção Backup)"
fi

while :; do
    today=$(date +%Y-%m-%d)
    now_min=$(to_min "$(date +%H:%M)")
    done_day=$(cat "$STATE_DIR/sched_done_day" 2>/dev/null || true)
    if [ "$done_day" != "$today" ] && [ "$now_min" -ge "$AT_MIN" ]; then
        # contador de tentativas do dia
        tries_day=$(cut -d' ' -f1 "$STATE_DIR/sched_tries" 2>/dev/null || true)
        tries=$(cut -d' ' -f2 "$STATE_DIR/sched_tries" 2>/dev/null || echo 0)
        [ "$tries_day" = "$today" ] || tries=0
        last_try=$(cat "$STATE_DIR/sched_last_try" 2>/dev/null || echo 0)
        now=$(date +%s)
        if [ "$tries" -lt "$BACKUP_MAX_TENTATIVAS" ] && [ $((now - last_try)) -ge $((BACKUP_RETRY_MINUTES * 60)) ]; then
            echo "$now" > "$STATE_DIR/sched_last_try"
            echo "$today $((tries + 1))" > "$STATE_DIR/sched_tries"
            log "disparando backup (tentativa $((tries + 1))/$BACKUP_MAX_TENTATIVAS do dia $today)"
            if "$SCRIPT_DIR/backup.sh"; then
                echo "$today" > "$STATE_DIR/sched_done_day"
            else
                rc=$?
                log "backup terminou com código $rc; nova tentativa em ${BACKUP_RETRY_MINUTES} min (se restarem tentativas)"
            fi
        fi
    fi
    sleep 30 &
    wait $!
done
