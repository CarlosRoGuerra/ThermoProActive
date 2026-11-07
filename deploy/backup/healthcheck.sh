#!/bin/sh
# healthcheck.sh — saudável = existe um backup COMPLETO bem-sucedido recente.
# (Depois do deploy inicial fica "unhealthy" até o primeiro backup — é proposital:
#  sem backup validado não há motivo para o painel mostrar verde.)
BACKUP_DIR=${BACKUP_DIR:-/backups}
MAX_H=${BACKUP_MAX_AGE_HOURS:-30}
f="$BACKUP_DIR/state/last_success"
[ -f "$f" ] || { echo "nenhum backup bem-sucedido registrado"; exit 1; }
ts=$(cut -d' ' -f1 "$f")
age=$(( $(date +%s) - ts ))
if [ "$age" -gt $((MAX_H * 3600)) ]; then
    echo "último backup bem-sucedido há $((age / 3600)) h (limite ${MAX_H} h): $(cut -d' ' -f2 "$f")"
    exit 1
fi
echo "ok: $(cut -d' ' -f2 "$f") há $((age / 60)) min"
