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

## 5. Разовые шаги конкретных релизов

### Story 36.1 — вынос каталогов обмена 1С из публичного MEDIA_ROOT

Выполнить **один раз** при первом деплое Story 36.1.

1. Создать на хосте каталог под приватный обмен (монтируется в `backend` и `celery`)
   **и отдать его runtime-пользователю контейнера**. Оба сервиса объявлены как
   `user: "1000:1000"`, а `mkdir` от root создаёт каталог `root:root` c `0755` —
   тогда первый же `mode=file` падает с `PermissionError` при создании
   `1c_temp/<sessid>`, и обмен с 1С не стартует вовсе:

   ```bash
   mkdir -p /home/freesport/freesport/data/prod/onec_private/1c_temp \
            /home/freesport/freesport/data/prod/onec_private/1c_import
   chown -R 1000:1000 /home/freesport/freesport/data/prod/onec_private
   chmod -R u+rwX,g+rwX /home/freesport/freesport/data/prod/onec_private
   ```

   Проверить, что запись действительно доступна изнутри контейнера:

   ```bash
   docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend \
     python manage.py shell -c "
from pathlib import Path
from django.conf import settings
probe = Path(str(settings.ONEC_EXCHANGE['TEMP_DIR'])) / '.write_probe'
probe.parent.mkdir(parents=True, exist_ok=True)
probe.write_text('ok')
probe.unlink()
print('private dir writable:', probe.parent)
"
   ```

   Ту же проверку нужно повторить для `celery` (`exec celery ...`) — контейнеры
   разные, а каталог общий.

   > `scripts/deploy/deploy.sh` (шаг 3.5) делает то же самое автоматически —
   > ручные команды нужны, только если деплой выполняется без него.

2. Удалить остатки старых обменов из публичного `media/`. Media-том переживает
   деплой, поэтому XML с прайсами, остатками и реквизитами контрагентов,
   записанные до переезда, физически остаются под `MEDIA_ROOT`. Сначала — сухой
   прогон:

   ```bash
   docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend \
     python manage.py purge_legacy_1c_media --dry-run
   docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend \
     python manage.py purge_legacy_1c_media
   ```

   Команда идемпотентна и отказывается работать, если `ONEC_EXCHANGE["IMPORT_DIR"]`
   всё ещё указывает внутрь `MEDIA_ROOT` (признак отката или сбитого
   `ONEC_PRIVATE_DIR`).

3. Проверить, что публичный доступ закрыт (ожидается `404`):

   ```bash
   curl -o /dev/null -s -w "%{http_code}\n" https://optisport.ru/media/1c_import/
   curl -o /dev/null -s -w "%{http_code}\n" https://optisport.ru/media/1c_temp/
   ```
