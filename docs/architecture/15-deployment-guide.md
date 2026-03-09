# Production Deployment Guide

## Обзор

Данное руководство описывает развертывание FREESPORT в production, дополняя существующую Docker структуру проекта.

## Существующая Инфраструктура

Проект уже имеет:
- ✅ `docker-compose.yml` - development среда
- ✅ `docker-compose.test.yml` - тестовая среда  
- ✅ `backend/Dockerfile` и `frontend/Dockerfile`
- ✅ `Makefile` с командами разработки
- ✅ `docker/nginx/` - конфигурация Nginx

## Production Configuration

### 1. Создание docker-compose.prod.yml

Дополняем существующую структуру production конфигурацией:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  # Наследуем Nginx из существующей структуры
  nginx:
    build:
      context: ./docker/nginx
      dockerfile: Dockerfile.prod  # Создадим отдельно
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./docker/nginx/conf.d:/etc/nginx/conf.d
      - ./ssl:/etc/nginx/ssl
      - static_volume:/var/www/static
      - media_volume:/var/www/media
    depends_on:
      - backend
      - frontend
    restart: unless-stopped
    networks:
      - freesport-network

  # Production Backend (расширяем существующий Dockerfile)
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production  # Multi-stage build
      args:
        DJANGO_SETTINGS_MODULE: freesport.settings.production
    expose:
      - "8001"  # Изменим порт для production
    environment:
      - DJANGO_SETTINGS_MODULE=freesport.settings.production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
      - SECRET_KEY=${SECRET_KEY}
      - DEBUG=False
    volumes:
      - static_volume:/app/static
      - media_volume:/app/media
      - ./logs:/app/logs
    depends_on:
      - db
      - redis
    restart: unless-stopped
    deploy:
      replicas: 2
    networks:
      - freesport-network

  # Production Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
      target: production
    expose:
      - "3000"
    environment:
      - NODE_ENV=production
      - NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
    depends_on:
      - backend
    restart: unless-stopped
    deploy:
      replicas: 2
    networks:
      - freesport-network

  # Используем существующую конфигурацию БД
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init-db.sql:/docker-entrypoint-initdb.d/init.sql
    restart: unless-stopped
    networks:
      - freesport-network
    # В production не открываем порт наружу

  # Используем существующую конфигурацию Redis
  redis:
    image: redis:7-alpine
    command: redis-server --appendonly yes --requirepass ${REDIS_PASSWORD}
    volumes:
      - redis_data:/data
    restart: unless-stopped
    networks:
      - freesport-network

  # Production Celery Workers
  celery:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    command: celery -A freesport worker --loglevel=info --concurrency=4
    environment:
      - DJANGO_SETTINGS_MODULE=freesport.settings.production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    restart: unless-stopped
    deploy:
      replicas: 2
    networks:
      - freesport-network

  # Production Celery Beat
  celery-beat:
    build:
      context: ./backend
      dockerfile: Dockerfile
      target: production
    command: celery -A freesport beat --loglevel=info
    environment:
      - DJANGO_SETTINGS_MODULE=freesport.settings.production
      - DATABASE_URL=${DATABASE_URL}
      - REDIS_URL=${REDIS_URL}
    depends_on:
      - db
      - redis
    restart: unless-stopped
    networks:
      - freesport-network

volumes:
  postgres_data:
  redis_data:
  static_volume:
  media_volume:

networks:
  freesport-network:
    driver: bridge
```

### 2. Модификация backend/Dockerfile для Production

Дополняем существующий Dockerfile production стадией:

```dockerfile
# Добавляем в конец существующего backend/Dockerfile

# Production стадия (добавляем к существующему multi-stage)
FROM production as production-final

# Production настройки
ENV DJANGO_SETTINGS_MODULE=freesport.settings.production
ENV DEBUG=False
ENV PYTHONUNBUFFERED=1

# Создаем пользователя для безопасности
RUN adduser --disabled-password --gecos '' appuser
RUN chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8001

# Production команда запуска
CMD ["gunicorn", "freesport.wsgi:application", "--bind", "0.0.0.0:8001", "--workers", "4", "--worker-class", "sync", "--worker-connections", "1000", "--max-requests", "1200", "--max-requests-jitter", "50", "--access-logfile", "-", "--error-logfile", "-"]
```

### 3. Модификация frontend/Dockerfile для Production

```dockerfile
# Добавляем в конец существующего frontend/Dockerfile

# Production стадия
FROM node:18-alpine as production

WORKDIR /app

# Копируем package files
COPY package*.json ./
RUN npm ci --only=production

# Копируем built app из предыдущей стадии
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY next.config.js ./

# Создаем пользователя
RUN addgroup -g 1001 -S nodejs
RUN adduser -S nextjs -u 1001
RUN chown -R nextjs:nodejs /app
USER nextjs

EXPOSE 3000

CMD ["npm", "start"]
```

### 4. Production Nginx Configuration

Создаем `docker/nginx/Dockerfile.prod`:

```dockerfile
FROM nginx:alpine

# Копируем существующую конфигурацию
COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

# Создаем директории для логов
RUN mkdir -p /var/log/nginx

# Права на файлы
RUN chown -R nginx:nginx /var/cache/nginx /var/run /var/log/nginx

# Non-root пользователь
USER nginx

EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
```

Обновляем `docker/nginx/conf.d/default.conf`:

```nginx
# Production configuration для FREESPORT

upstream backend {
    server backend:8001;
}

upstream frontend {
    server frontend:3000;
}

# HTTP to HTTPS redirect
server {
    listen 80;
    server_name _;
    return 301 https://$server_name$request_uri;
}

# HTTPS Server
server {
    listen 443 ssl http2;
    server_name _;
    
    # SSL Configuration (будет настроено через Let's Encrypt)
    ssl_certificate /etc/nginx/ssl/fullchain.pem;
    ssl_certificate_key /etc/nginx/ssl/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256;
    
    # Security Headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    
    # Static Files
    location /static/ {
        alias /var/www/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    location /media/ {
        alias /var/www/media/;
        expires 1M;
        add_header Cache-Control "public";
    }
    
    # API Routes
    location /api/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    location /admin/ {
        proxy_pass http://backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Frontend
    location / {
        proxy_pass http://frontend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 5. Environment Configuration

Создаем `.env.production`:

```bash
# Production Environment Variables
# Database
POSTGRES_DB=freesport
POSTGRES_USER=postgres
POSTGRES_PASSWORD=secure_password_change_me

# Redis
REDIS_PASSWORD=secure_redis_password_change_me
REDIS_URL=redis://:secure_redis_password_change_me@redis:6379/0

# Django
SECRET_KEY=your_secret_key_50_chars_minimum_change_me
DATABASE_URL=postgresql://postgres:secure_password_change_me@db:5432/freesport
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Frontend
NEXT_PUBLIC_API_URL=https://yourdomain.com

# Integrations
YUKASSA_ACCOUNT_ID=your_yukassa_account
YUKASSA_SECRET_KEY=your_yukassa_secret
ONEC_API_URL=https://your-1c-server.com/api
ONEC_USERNAME=1c_user
ONEC_PASSWORD=1c_password

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=noreply@yourdomain.com
EMAIL_HOST_PASSWORD=app_password

# Monitoring
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project
```

### 6. Расширение Makefile для Production

Добавляем в существующий `Makefile`:

```makefile
# === PRODUCTION COMMANDS ===

# Production сборка
build-prod:
	@echo "Сборка production образов..."
	docker-compose -f docker-compose.prod.yml build --no-cache

# Production запуск
up-prod:
	@echo "Запуск production среды..."
	docker-compose -f docker-compose.prod.yml up -d

# Production остановка
down-prod:
	@echo "Остановка production среды..."
	docker-compose -f docker-compose.prod.yml down

# Production логи
logs-prod:
	docker-compose -f docker-compose.prod.yml logs -f

# Health check
health-check:
	@echo "Проверка состояния сервисов..."
	curl -f http://localhost/api/health/ || echo "❌ API недоступно"
	curl -f http://localhost/ || echo "❌ Frontend недоступно"

# Database backup
backup-db:
	@echo "Создание backup базы данных..."
	docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U $(POSTGRES_USER) $(POSTGRES_DB) | gzip > backups/db_backup_$(shell date +%Y%m%d_%H%M%S).sql.gz

# Deploy (полный цикл)
deploy:
	@echo "🚀 Запуск production deployment..."
	make backup-db
	git pull origin main
	make build-prod
	docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate
	docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput
	make up-prod
	sleep 30
	make health-check
	@echo "✅ Deployment завершен"

# Rollback
rollback:
	@echo "🔄 Откат к предыдущей версии..."
	git reset --hard HEAD~1
	make build-prod
	make up-prod
	make health-check
	@echo "✅ Rollback завершен"
```

### 7. SSL Setup Script

Создаем `scripts/ssl-setup.sh`:

```bash
#!/bin/bash
# scripts/ssl-setup.sh - SSL сертификаты

set -e

DOMAIN=${1:-"yourdomain.com"}
EMAIL=${2:-"admin@yourdomain.com"}

echo "🔐 Настройка SSL для домена: $DOMAIN"

# Установка Certbot
sudo apt update
sudo apt install -y certbot

# Создание директории для SSL
mkdir -p ./ssl

# Получение сертификата (при остановленном Nginx)
docker-compose -f docker-compose.prod.yml stop nginx

sudo certbot certonly --standalone \
  -d $DOMAIN \
  -d www.$DOMAIN \
  --email $EMAIL \
  --agree-tos \
  --non-interactive

# Копирование сертификатов
sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem ./ssl/
sudo chmod 644 ./ssl/*.pem

# Настройка автообновления
echo "0 12 * * * /usr/bin/certbot renew --quiet --post-hook 'docker-compose -f $(pwd)/docker-compose.prod.yml restart nginx'" | sudo crontab -

docker-compose -f docker-compose.prod.yml start nginx

echo "✅ SSL сертификаты настроены"
```

### 8. Deployment Script

Создаем `scripts/deploy.sh`:

```bash
#!/bin/bash
# scripts/deploy.sh - Production Deployment

set -e

DEPLOY_DIR="/opt/freesport"
BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)

echo "🚀 FREESPORT Production Deployment"

# Создание директории для backups
mkdir -p $BACKUP_DIR

# Загрузка переменных окружения
if [ -f ".env.production" ]; then
    source .env.production
else
    echo "❌ Файл .env.production не найден"
    exit 1
fi

# Backup базы данных
echo "📦 Создание backup..."
make backup-db

# Обновление кода
echo "📥 Обновление кода..."
git pull origin main

# Сборка новых образов
echo "🔨 Сборка образов..."
make build-prod

# Миграции БД
echo "🗄️ Применение миграций..."
docker-compose -f docker-compose.prod.yml exec backend python manage.py migrate --noinput

# Сбор статических файлов
echo "📎 Сбор статических файлов..."
docker-compose -f docker-compose.prod.yml exec backend python manage.py collectstatic --noinput

# Rolling restart
echo "♻️ Перезапуск сервисов..."
docker-compose -f docker-compose.prod.yml up -d --no-deps backend celery
sleep 15
docker-compose -f docker-compose.prod.yml up -d --no-deps frontend
sleep 10
docker-compose -f docker-compose.prod.yml up -d --no-deps nginx

# Health check
echo "🏥 Проверка состояния..."
sleep 30
make health-check

# Очистка старых образов
echo "🧹 Очистка..."
docker image prune -f

echo "🎉 Deployment завершен успешно!"
```

## Production Checklist

### Перед развертыванием:
- [ ] Сервер настроен и доступен
- [ ] Домен настроен и указывает на сервер
- [ ] SSL сертификаты получены
- [ ] `.env.production` настроен с реальными значениями
- [ ] Firewall настроен (порты 80, 443, SSH)
- [ ] Backup стратегия настроена

### После развертывания:
- [ ] Все сервисы запущены (`docker-compose -f docker-compose.prod.yml ps`)
- [ ] Health check проходит (`make health-check`)
- [ ] SSL работает (проверить в браузере)
- [ ] Статические файлы загружаются
- [ ] API отвечает корректно
- [ ] Мониторинг настроен

## Мониторинг

Добавляем health check endpoint в Django:

```python
# backend/apps/common/views.py
from django.http import JsonResponse
from django.db import connection

def health_check(request):
    """Production health check"""
    try:
        # Database check
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        
        # Redis check (если используется)
        from django.core.cache import cache
        cache.set('health_check', 'ok', 10)
        
        return JsonResponse({
            'status': 'healthy',
            'database': 'ok',
            'cache': 'ok'
        })
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'error': str(e)
        }, status=503)
```

## Команды для работы с Production

Расширенные команды через существующий Makefile:

```bash
# Запуск production среды
make up-prod

# Просмотр логов
make logs-prod

# Проверка состояния
make health-check

# Полный deployment
make deploy

# Backup базы данных
make backup-db

# Откат изменений
make rollback
```

Этот deployment guide полностью интегрируется с существующей структурой проекта и расширяет её production возможностями!