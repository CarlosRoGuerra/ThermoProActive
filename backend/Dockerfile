# Backend ThermoProActive — Django + DRF + gunicorn
# psycopg[binary] e Pillow usam wheels manylinux: sem necessidade de toolchain de build.
FROM node:22-bookworm-slim AS node-runtime
FROM python:3.13-slim-bookworm

# Renderer local: imprime os mesmos layouts Next.js; sem serviço externo pago.
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm && \
    ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright
RUN npm install --no-save --package-lock=false playwright@1.63.0 && \
    npx playwright install --with-deps chromium && \
    rm -rf /var/lib/apt/lists/* /root/.npm

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Sobe em 3 etapas, nesta ordem:
#   1) espera o banco ACEITAR CONEXÃO (evita corrida no 1º boot do Postgres),
#      com limite de tentativas — não fica preso para sempre;
#   2) aplica as migrations. Se falhar, o container MORRE com o erro no log.
#      (Antes o migrate ficava em loop e o gunicorn nunca subia: o sintoma virava
#       um 502 no nginx, escondendo a mensagem real do banco.)
#   3) coleta estáticos, semeia dados de demonstração SOMENTE se SEED_DEMO=1 e
#      entrega o processo ao gunicorn.
# SEED_DEMO é opt-in (o docker-compose.yml de desenvolvimento liga). Antes, este CMD
# semeava SEMPRE — quem subisse a imagem sem sobrescrever o comando em produção
# criaria o superusuário de demonstração com senha pública. Os composes de
# produção (prod/http) já sobrescrevem o comando e nunca semeiam.
CMD ["sh", "-c", "n=0; until python manage.py showmigrations >/dev/null 2>&1 || [ $n -ge 30 ]; do n=$((n+1)); echo \"aguardando o banco de dados... ($n/30)\"; sleep 2; done; python manage.py migrate --noinput && python manage.py collectstatic --noinput && { if [ \"${SEED_DEMO:-0}\" = 1 ]; then python manage.py seed_demo || echo 'seed_demo ignorado'; else echo 'seed_demo desligado (defina SEED_DEMO=1 só em desenvolvimento)'; fi; } && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120"]
