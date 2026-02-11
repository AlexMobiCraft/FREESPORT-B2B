# Migration Runbook: Story 14.3 — Дедупликация атрибутов

Данный документ описывает процедуру миграции для Story 14.3 "Дедупликация атрибутов при импорте из 1С".

> [!IMPORTANT]
> Используется стратегия **Clean Slate** — все существующие атрибуты удаляются перед миграцией и импортируются заново с дедупликацией.

---

## Оглавление

1. [Pre-Migration Checklist](#pre-migration-checklist)
2. [Migration Steps](#migration-steps)
3. [Post-Migration Validation](#post-migration-validation)
4. [Rollback Plan](#rollback-plan)
5. [Troubleshooting](#troubleshooting)
6. [Timeline](#timeline)

---

## Pre-Migration Checklist

### Резервное копирование

- [ ] Создать полную резервную копию базы данных PostgreSQL
- [ ] Экспортировать текущие атрибуты в CSV для сравнения

```bash
# Создание резервной копии PostgreSQL
docker compose -f docker/docker-compose.yml exec db pg_dump -U freesport freesport > backup_$(date +%Y%m%d_%H%M%S).sql

# Экспорт атрибутов в CSV
docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
from apps.products.models import Attribute, AttributeValue
import csv
with open('/tmp/attributes_backup.csv', 'w') as f:
    writer = csv.writer(f)
    writer.writerow(['id', 'name', 'slug'])
    for attr in Attribute.objects.all():
        writer.writerow([attr.id, attr.name, attr.slug])
"
```

### Проверка системы

- [ ] Все тесты проходят
- [ ] Нет активных импорт-сессий
- [ ] Сервисы работают корректно (backend, db, redis)

```bash
# Проверка тестов
docker compose -f docker/docker-compose.yml run --rm backend pytest apps/products/tests/ -v

# Проверка статуса сервисов
docker compose -f docker/docker-compose.yml ps
```

---

## Migration Steps

### Шаг 1: Остановка импорта

Убедитесь что нет активных импорт-процессов:

```bash
# Проверка активных задач Celery
docker compose -f docker/docker-compose.yml exec backend celery -A freesport inspect active
```

### Шаг 2: Применение миграций

```bash
# Применение миграций для новых моделей (Attribute1CMapping, AttributeValue1CMapping)
docker compose -f docker/docker-compose.yml run --rm backend python manage.py migrate apps.products
```

### Шаг 3: Удаление существующих атрибутов (Clean Slate)

> [!CAUTION]
> Этот шаг удаляет ВСЕ существующие атрибуты и их значения! Убедитесь что резервная копия создана.

```bash
docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
from apps.products.models import Attribute, AttributeValue
count_attrs = Attribute.objects.count()
count_values = AttributeValue.objects.count()
print(f'Удаление {count_attrs} атрибутов и {count_values} значений...')
Attribute.objects.all().delete()
print('Удаление завершено.')
"
```

### Шаг 4: Импорт атрибутов

Запустите импорт атрибутов через Admin UI или командную строку:

```bash
# Через Django management command
docker compose -f docker/docker-compose.yml run --rm backend python manage.py import_attributes

# Или через Admin UI: 
# /admin/integrations/import-from-1c/ → "Загрузить атрибуты (справочники)"
```

### Шаг 5: Активация необходимых атрибутов

После импорта атрибуты имеют `is_active=False`. Активируйте нужные через Admin:

```bash
# Или массовая активация через shell:
docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
from apps.products.models import Attribute

# Активировать все атрибуты (или выборочно)
Attribute.objects.all().update(is_active=True)

# Или активировать только определенные:
# Attribute.objects.filter(name__in=['Цвет', 'Размер', 'Материал']).update(is_active=True)
"
```

---

## Post-Migration Validation

### Проверка количества объектов

```bash
docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
from apps.products.models import Attribute, AttributeValue, Attribute1CMapping, AttributeValue1CMapping

print('=== Post-Migration Statistics ===')
print(f'Атрибутов: {Attribute.objects.count()}')
print(f'Значений атрибутов: {AttributeValue.objects.count()}')
print(f'Маппингов атрибутов 1С: {Attribute1CMapping.objects.count()}')
print(f'Маппингов значений 1С: {AttributeValue1CMapping.objects.count()}')
print(f'Активных атрибутов: {Attribute.objects.filter(is_active=True).count()}')

# Проверка дубликатов
from django.db.models import Count
duplicates = Attribute.objects.values('normalized_name').annotate(count=Count('id')).filter(count__gt=1)
if duplicates.exists():
    print('ОШИБКА: Найдены дубликаты атрибутов!')
    for d in duplicates:
        print(f'  - {d}')
else:
    print('OK: Дубликатов атрибутов нет.')
"
```

### Проверка API endpoint

```bash
# Проверка /catalog/filters/
curl http://localhost:8001/api/v1/catalog/filters/ | python -m json.tool

# Ожидаемый результат: только активные атрибуты
```

### Проверка Admin UI

- [ ] Открыть `/admin/products/attribute/` — должны отображаться импортированные атрибуты
- [ ] Проверить inline маппинги `Attribute1CMapping` в каждом атрибуте
- [ ] Проверить bulk actions: `activate_attributes`, `deactivate_attributes`, `merge_attributes`

---

## Rollback Plan

Если миграция прошла неуспешно:

### Восстановление из резервной копии

```bash
# Восстановление PostgreSQL
docker compose -f docker/docker-compose.yml exec db psql -U freesport -d freesport < backup_YYYYMMDD_HHMMSS.sql
```

### Откат миграций (если применимо)

```bash
# Откат миграций
docker compose -f docker/docker-compose.yml run --rm backend python manage.py migrate apps.products <previous_migration_number>
```

---

## Troubleshooting

### Ошибка: "Duplicate key value violates unique constraint"

**Причина:** Попытка создания атрибута с уже существующим `normalized_name`.

**Решение:**

1. Убедитесь что шаг 3 (Clean Slate) выполнен
2. Проверьте что нет записей:

   ```bash
   docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
   from apps.products.models import Attribute
   print(Attribute.objects.count())
   "
   ```

### Ошибка: "IntegrityError on Attribute1CMapping"

**Причина:** Дублирующие `onec_id` в маппингах.

**Решение:** Удалите маппинги перед повторным импортом:

```bash
docker compose -f docker/docker-compose.yml run --rm backend python manage.py shell -c "
from apps.products.models import Attribute1CMapping, AttributeValue1CMapping
Attribute1CMapping.objects.all().delete()
AttributeValue1CMapping.objects.all().delete()
"
```

### Атрибуты не отображаются в API

**Причина:** `is_active=False` по умолчанию.

**Решение:** Активируйте атрибуты через Admin или shell (см. Шаг 5).

---

## Timeline

| Этап | Примерное время |
|------|-----------------|
| Pre-migration checklist | 15 мин |
| Резервное копирование | 5-10 мин |
| Миграции Django | 1-2 мин |
| Clean Slate (удаление) | 1 мин |
| Импорт атрибутов | 5-15 мин |
| Post-migration validation | 10 мин |
| **Итого** | **~45 мин** |

---

## Contacts

При возникновении проблем:

- **Dev Team:** <dev@freesport.com>
- **Database Admin:** <dba@freesport.com>
