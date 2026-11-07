#!/usr/bin/env bash
# =============================================================================
# testar-restauracao.sh — "simulado de restauração" em ambiente ISOLADO.
#
# Restaura o backup MAIS RECENTE num PostgreSQL descartável e num volume novo,
# e compara com a origem: contagem de linhas de TODAS as tabelas, lista de
# migrações e SHA-256 de cada arquivo de mídia. Não escreve na produção: a
# origem só é lida (psql SELECT e volume montado como somente leitura).
# Rode ao menos 1x por trimestre e após qualquer mudança no processo de backup.
#
# Uso (na VPS, a partir da raiz do projeto):
#   BACKUP_DIR=/var/backups/thermoproactive \
#   BACKUP_CONFIG_DIR=/root/.thermoproactive \
#   SRC_DB_CONTAINER=thermoproactive_db SRC_PGUSER=thermo SRC_PGDATABASE=thermoproactive \
#   SRC_MEDIA_VOLUME=thermoproactive_media \
#   bash deploy/testar-restauracao.sh
#
# Variáveis opcionais: DRILL_PREFIX (padrão tpa_drill_), BACKUP_TIER (daily),
# BACKUP_SET (latest), PG_IMAGE (postgres:16-alpine), KEEP=1 (não limpar ao final).
# Atenção: BACKUP_DIR e BACKUP_CONFIG_DIR podem ser caminhos do host OU nomes de volume.
# Se a origem estiver recebendo escritas, pequenas diferenças são esperadas
# (o backup é de um instante anterior); em banco parado devem ser ZERO.
# Código de saída: 0 = restauração íntegra | 1 = divergência/erro.
# =============================================================================
set -u

P=${DRILL_PREFIX:-tpa_drill_}
PG_IMAGE=${PG_IMAGE:-postgres:16-alpine}
TIER=${BACKUP_TIER:-daily}
SET_NAME=${BACKUP_SET:-latest}
: "${BACKUP_DIR:?defina BACKUP_DIR (pasta/volume dos backups)}"
: "${BACKUP_CONFIG_DIR:?defina BACKUP_CONFIG_DIR (pasta/volume com backup.passphrase)}"
: "${SRC_DB_CONTAINER:?defina SRC_DB_CONTAINER (container do banco de origem)}"
: "${SRC_PGUSER:?defina SRC_PGUSER}"
: "${SRC_PGDATABASE:?defina SRC_PGDATABASE}"
SRC_MEDIA_VOLUME=${SRC_MEDIA_VOLUME:-}
HERE=$(cd "$(dirname "$0")" && pwd)

NET=${P}net; PG=${P}pg; VOL=${P}media_restaurada; IMG=${P}backup_img
FAIL=0
say() { printf '\n== %s\n' "$*"; }
cleanup() {
    [ "${KEEP:-0}" = 1 ] && { echo "KEEP=1: mantendo $PG, $NET, $VOL, $IMG"; return; }
    docker rm -f "$PG" >/dev/null 2>&1
    docker volume rm "$VOL" >/dev/null 2>&1
    docker network rm "$NET" >/dev/null 2>&1
    docker rmi "$IMG" >/dev/null 2>&1
}
trap cleanup EXIT

say "1/6 imagem de backup + ambiente isolado ($PG, $NET, $VOL)"
( cd "$HERE/backup" && docker build -q -t "$IMG" . ) >/dev/null || { echo "falha ao construir a imagem"; exit 1; }
docker network create "$NET" >/dev/null || exit 1
docker volume create "$VOL" >/dev/null || exit 1
docker run -d --name "$PG" --network "$NET" -e POSTGRES_PASSWORD=drill -e POSTGRES_DB=postgres "$PG_IMAGE" >/dev/null || exit 1
for _ in $(seq 1 40); do
    docker exec "$PG" pg_isready -U postgres -d postgres >/dev/null 2>&1 && break
    sleep 1
done
docker exec "$PG" pg_isready -U postgres >/dev/null 2>&1 || { echo "postgres de teste não subiu"; exit 1; }
sleep 3  # o entrypoint reinicia o servidor uma vez após o initdb

say "2/6 restore.sh (--set $SET_NAME, camada $TIER) no banco 'restaurado' e no volume novo"
docker run --rm --network "$NET" \
    -v "$BACKUP_DIR:/backups:ro" -v "$BACKUP_CONFIG_DIR:/config:ro" -v "$VOL:/restore/media" \
    -e RESTORE_PGPASSWORD=drill "$IMG" \
    /backup/restore.sh --set "$SET_NAME" --tier "$TIER" \
        --db-host "$PG" --db-user postgres --db-name restaurado --media-dir /restore/media --yes \
    || { echo "FALHA no restore.sh"; exit 1; }

COUNT_SQL="select table_name||' '||(xpath('/row/c/text()', query_to_xml(format('select count(*) as c from %I.%I', table_schema, table_name), false, true, '')))[1]::text from information_schema.tables where table_schema='public' and table_type='BASE TABLE' order by 1"
MIG_SQL="select md5(string_agg(app||'/'||name, ',' order by app, name)) || ' ' || count(*) from django_migrations"

say "3/6 contagem de linhas por tabela: origem x restauração"
docker exec "$SRC_DB_CONTAINER" psql -U "$SRC_PGUSER" -d "$SRC_PGDATABASE" -tA -c "$COUNT_SQL" > "${TMPDIR:-/tmp}/${P}origem.txt" || FAIL=1
docker exec "$PG" psql -U postgres -d restaurado -tA -c "$COUNT_SQL" > "${TMPDIR:-/tmp}/${P}restaurado.txt" || FAIL=1
echo "tabelas (origem/restaurado): $(wc -l < "${TMPDIR:-/tmp}/${P}origem.txt") / $(wc -l < "${TMPDIR:-/tmp}/${P}restaurado.txt")"
echo "linhas somadas (origem/restaurado): $(awk '{s+=$2} END{print s}' "${TMPDIR:-/tmp}/${P}origem.txt") / $(awk '{s+=$2} END{print s}' "${TMPDIR:-/tmp}/${P}restaurado.txt")"
if diff "${TMPDIR:-/tmp}/${P}origem.txt" "${TMPDIR:-/tmp}/${P}restaurado.txt" > "${TMPDIR:-/tmp}/${P}diff.txt"; then
    echo "OK: todas as tabelas com contagem idêntica"
else
    echo "DIVERGÊNCIA (< origem, > restaurado):"; cat "${TMPDIR:-/tmp}/${P}diff.txt"; FAIL=1
fi
echo "--- tabelas-chave (origem | restaurado)"
for t in accounts_user cadastros_cliente cadastros_equipamento; do
    printf '%-28s %s | %s\n' "$t" "$(grep "^$t " "${TMPDIR:-/tmp}/${P}origem.txt" | cut -d' ' -f2)" "$(grep "^$t " "${TMPDIR:-/tmp}/${P}restaurado.txt" | cut -d' ' -f2)"
done
grep -E '^(coletas_|osp_|laudos_)' "${TMPDIR:-/tmp}/${P}origem.txt" | while read -r t n; do
    printf '%-28s %s | %s\n' "$t" "$n" "$(grep "^$t " "${TMPDIR:-/tmp}/${P}restaurado.txt" | cut -d' ' -f2)"
done

say "4/6 django_migrations (hash da lista + total)"
A=$(docker exec "$SRC_DB_CONTAINER" psql -U "$SRC_PGUSER" -d "$SRC_PGDATABASE" -tA -c "$MIG_SQL")
B=$(docker exec "$PG" psql -U postgres -d restaurado -tA -c "$MIG_SQL")
echo "origem:     $A"; echo "restaurado: $B"
[ "$A" = "$B" ] && echo "OK: migrações idênticas" || { echo "DIVERGÊNCIA nas migrações"; FAIL=1; }

say "5/6 SHA-256 dos arquivos de mídia: origem x restauração"
if [ -n "$SRC_MEDIA_VOLUME" ]; then
    SUM='cd /m && find . -type f -exec sha256sum {} + | sort -k2'
    docker run --rm -v "$SRC_MEDIA_VOLUME:/m:ro" alpine sh -c "$SUM" > "${TMPDIR:-/tmp}/${P}media_origem.txt" || FAIL=1
    docker run --rm -v "$VOL:/m:ro" alpine sh -c "$SUM" > "${TMPDIR:-/tmp}/${P}media_rest.txt" || FAIL=1
    echo "arquivos (origem/restaurado): $(wc -l < "${TMPDIR:-/tmp}/${P}media_origem.txt") / $(wc -l < "${TMPDIR:-/tmp}/${P}media_rest.txt")"
    echo "hash dos hashes (origem):     $(sha256sum < "${TMPDIR:-/tmp}/${P}media_origem.txt" | cut -c1-16)"
    echo "hash dos hashes (restaurado): $(sha256sum < "${TMPDIR:-/tmp}/${P}media_rest.txt" | cut -c1-16)"
    diff -q "${TMPDIR:-/tmp}/${P}media_origem.txt" "${TMPDIR:-/tmp}/${P}media_rest.txt" >/dev/null \
        && echo "OK: todos os arquivos de mídia com SHA-256 idêntico" || { echo "DIVERGÊNCIA na mídia"; FAIL=1; }
else
    echo "SRC_MEDIA_VOLUME não informado: comparação de mídia pulada"
fi

say "6/6 resultado"
rm -f "${TMPDIR:-/tmp}/${P}"*.txt
if [ "$FAIL" = 0 ]; then echo "RESULTADO: RESTAURAÇÃO ÍNTEGRA"; else echo "RESULTADO: FALHOU"; fi
exit "$FAIL"
