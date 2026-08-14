#!/bin/bash
set -e

# Azure Oryx extracts the build archive to /tmp/<hash>/ and runs this script
# from that directory. We use dirname to reliably find django_app/ next to us.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p /home/data/media

cd "$SCRIPT_DIR/django_app"

python manage.py migrate --noinput
python init_data.py
python manage.py collectstatic --noinput

exec gunicorn brueggen.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers 2 \
  --timeout 120 \
  --access-logfile '-' \
  --error-logfile '-'
