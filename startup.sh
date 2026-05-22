#!/bin/bash
set -e

export PYTHONPATH="/home/site/wwwroot/django_app:$PYTHONPATH"

cd /home/site/wwwroot/django_app

# Persistent storage on Azure lives under /home
mkdir -p /home/data

python manage.py migrate --noinput
python init_data.py
python manage.py collectstatic --noinput

exec gunicorn brueggen.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 2 \
  --timeout 120 \
  --access-logfile '-' \
  --error-logfile '-'
