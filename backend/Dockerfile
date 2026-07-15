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

# Espera o banco aceitar conexões TCP (migrate em loop — evita corrida no 1º boot do
# Postgres em volume novo), aplica migrations, coleta estáticos, semeia e sobe o gunicorn.
CMD ["sh", "-c", "until python manage.py migrate --noinput; do echo 'aguardando o banco de dados...'; sleep 2; done; python manage.py collectstatic --noinput && python manage.py seed_demo; gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3"]
