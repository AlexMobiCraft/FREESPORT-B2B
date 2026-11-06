#!/bin/bash
set -e

# Очистка pyc файлов для гарантии применения настроек
find . -name "*.pyc" -delete
find . -name "__pycache__" -delete

# Применение миграций
python manage.py migrate --noinput

# Сборка статики (если нужно, но обычно в build phase)
# python manage.py collectstatic --noinput

# Запуск Gunicorn
exec gunicorn freesport.wsgi:application \
    --name freesport-backend \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --timeout 60 \
    --log-level=info \
    --access-logfile=- \
    --error-logfile=-
