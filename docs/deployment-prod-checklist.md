# Чек-лист Деплоя на продакшн сервер

Выполните эти шаги на сервере по порядку:

## 1. Обновление кода
Убедитесь, что сервер находится на ветке `develop` (или той, куда мы вносили изменения) и скачайте обновления.

```bash
cd /home/freesport/freesport/
git status
# Если ветка не develop - переключитесь: git checkout develop
git pull
```

## 2. Пересборка Backend
Так как мы добавили новые библиотеки и файлы, контейнер нужно пересобрать.

```bash
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml down backend
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml build backend
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml up -d backend
```

## 3. Применение миграций
Это создаст нужные права в базе данных.

```bash
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend python manage.py migrate
```

## 4. Перезапуск Nginx
Чтобы Nginx увидел обновленный контейнер (если IP сменился).

```bash
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml restart nginx
```
