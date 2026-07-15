#!/usr/bin/env bash
# =============================================================================
# ThermoProActive — bootstrap do certificado TLS (Let's Encrypt) na 1ª subida.
#
# Resolve o problema do ovo-e-galinha: o Nginx precisa de um certificado para
# iniciar o bloco :443, mas o certificado só é emitido depois que o Nginx está
# no ar respondendo o desafio ACME. A solução: cria um certificado "dummy"
# temporário, sobe o Nginx, troca pelo certificado real e recarrega o Nginx.
#
# Rode UMA vez, a partir da RAIZ do projeto, com o DNS do domínio já apontando
# para o IP da VPS:
#     bash deploy/init-letsencrypt.sh
# =============================================================================
set -euo pipefail

COMPOSE="docker compose --env-file .env.prod -f docker-compose.prod.yml"

# Carrega DOMAIN e CERTBOT_EMAIL do .env.prod.
set -a; source .env.prod; set +a
: "${DOMAIN:?defina DOMAIN no .env.prod}"
: "${CERTBOT_EMAIL:?defina CERTBOT_EMAIL no .env.prod}"

CERT_PATH="/etc/letsencrypt/live/${DOMAIN}"

echo "### 1/4 Criando certificado temporário (dummy) para ${DOMAIN}..."
$COMPOSE run --rm --entrypoint "sh -c '\
  mkdir -p ${CERT_PATH} && \
  openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
    -keyout ${CERT_PATH}/privkey.pem \
    -out ${CERT_PATH}/fullchain.pem \
    -subj \"/CN=${DOMAIN}\"'" certbot

echo "### 2/4 Subindo o Nginx com o certificado temporário..."
$COMPOSE up -d nginx

echo "### 3/4 Apagando o dummy e solicitando o certificado real..."
$COMPOSE run --rm --entrypoint "sh -c 'rm -rf /etc/letsencrypt/live/${DOMAIN} \
  /etc/letsencrypt/archive/${DOMAIN} /etc/letsencrypt/renewal/${DOMAIN}.conf'" certbot

$COMPOSE run --rm --entrypoint "certbot certonly --webroot -w /var/www/certbot \
  --email ${CERTBOT_EMAIL} -d ${DOMAIN} -d www.${DOMAIN} \
  --rsa-key-size 4096 --agree-tos --no-eff-email --non-interactive" certbot

echo "### 4/4 Recarregando o Nginx com o certificado real..."
$COMPOSE exec nginx nginx -s reload

echo "### Pronto! Certificado emitido para ${DOMAIN}."
echo "### Suba o restante da stack:  $COMPOSE up -d --build"
