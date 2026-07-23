# Backend ThermoProActive — Django + DRF + gunicorn
# psycopg[binary] e Pillow usam wheels manylinux: sem necessidade de toolchain de build.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

WORKDIR /app

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
#   3) coleta estáticos, semeia dados de demonstração e entrega o processo ao gunicorn.
CMD ["sh", "-c", "n=0; until python manage.py showmigrations >/dev/null 2>&1 || [ $n -ge 30 ]; do n=$((n+1)); echo \"aguardando o banco de dados... ($n/30)\"; sleep 2; done; python manage.py migrate --noinput && python manage.py collectstatic --noinput && { python manage.py seed_demo || echo 'seed_demo ignorado'; } && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
