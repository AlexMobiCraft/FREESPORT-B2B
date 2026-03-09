# Руководство по командам импорта данных из 1С

## Обзор

Этот документ описывает использование команд Django management для импорта данных каталога из 1С:Предприятие в систему FREESPORT.

## Содержание

- [Команда import_products_from_1c](#команда-import_products_from_1c)
- [Команда load_product_stocks](#команда-load_product_stocks)
- [Команда fix_variant_sizes](#команда-fix_variant_sizes)
- [Команда backup_db](#команда-backup_db)
- [Команда restore_db](#команда-restore_db)
- [Команда rotate_backups](#команда-rotate_backups)
- [Примеры использования](#примеры-использования)
- [Troubleshooting](#troubleshooting)

---

## Команда import_products_from_1c

### Описание

Импортирует данные каталога товаров из XML файлов формата CommerceML 3.1, экспортированных из 1С:Предприятие.

### Синтаксис

```bash
python manage.py import_products_from_1c --data-dir=<path> [OPTIONS]
```

### Обязательные параметры

- `--data-dir` - Путь к директории с XML файлами экспорта 1С

### Опциональные параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `--chunk-size` | integer | 1000 | Размер пакета для bulk операций |
| `--skip-validation` | flag | false | Пропустить валидацию данных для ускорения |
| `--file-type` | choice | all | Тип файлов для импорта: goods, offers, prices, rests, all |
| `--clear-existing` | flag | false | Очистить существующие данные перед импортом |
| `--dry-run` | flag | false | Тестовый запуск без записи в БД |

### Структура директории данных

Директория `--data-dir` должна содержать следующую структуру:

```
data-dir/
├── goods/
│   ├── goods.xml           # Основные данные товаров
│   ├── goods_*.xml         # Сегментированные файлы (опционально)
│   └── import_files/
│        ├── image1.jpg
│        └── image2.png
├── offers/
│   ├── offers.xml          # SKU и предложения
│   └── offers_*.xml
├── prices/
│   ├── prices.xml          # Цены товаров
│   └── prices_*.xml
├── rests/
│   ├── rests.xml           # Остатки на складах
│   └── rests_*.xml
└── priceLists/
    └── priceLists.xml      # Типы цен
```

### Процесс импорта

1. **Проверка прав** - Команда требует superuser привилегий
2. **Автоматический backup** - Создается резервная копия БД перед импортом
3. **Создание ImportSession** - Создается запись для отслеживания процесса
4. **Парсинг XML файлов** - Последовательная обработка: goods → offers → prices → rests
5. **Bulk операции** - Данные записываются пакетами для производительности
6. **Обновление статистики** - Финальный отчет в ImportSession

### Примеры использования

#### Базовый импорт

```bash
python manage.py import_products_from_1c --data-dir=/var/data/1c/export/
```

#### Импорт с увеличенным chunk-size для больших каталогов

```bash
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    --chunk-size=2000
```

#### Быстрый импорт без валидации

```bash
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    --skip-validation
```

#### Импорт только цен

```bash
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    --file-type=prices
```

#### Полная перезагрузка каталога

```bash
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    --clear-existing
```

#### Тестовый запуск (dry-run)

```bash
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    --dry-run
```

### Производительность

- **100 товаров**: ~30-60 секунд
- **1000 товаров**: <5 минут (DoD requirement)
- **10000+ товаров**: используйте `--chunk-size=2000` и `--skip-validation`

### Безопасность

- ✅ Требуется superuser доступ
- ✅ Автоматическое создание backup перед импортом
- ✅ Защита от XML injection (defusedxml)
- ✅ Валидация путей (path traversal prevention)
- ✅ Audit logging всех операций

---

## Команда load_product_stocks

### Описание

Обновляет только остатки товаров из файла `rests.xml`. Эта команда является легковесной альтернативой `import_products_from_1c --file-type=rests` и рекомендуется для частых запусков (например, через cron).

### Синтаксис

```bash
python manage.py load_product_stocks --file=<path> [OPTIONS]
```

### Обязательные параметры

- `--file` - Путь к файлу `rests.xml` с данными об остатках.

### Опциональные параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `--batch-size` | integer | 1000 | Размер пакета для `bulk_update` операций |
| `--dry-run` | flag | false | Тестовый запуск без записи в БД |

### Примеры использования

#### Базовое обновление остатков

```bash
python manage.py load_product_stocks --file=/var/data/1c/export/rests.xml
```

#### Тестовый запуск (dry-run)

```bash
python manage.py load_product_stocks --file=/var/data/1c/export/rests.xml --dry-run
```

#### Регулярное обновление через cron (каждые 15 минут)

```bash
*/15 * * * * cd /app && python manage.py load_product_stocks --file=/var/data/1c/export/rests.xml >> /var/log/stocks_import.log 2>&1
```

---

## Команда fix_variant_sizes

### Описание

Очищает некорректные значения `size_value` в модели `ProductVariant`. Эта команда используется для исправления данных, когда поле размера содержит булевые значения вместо реального размера (например, "Да" вместо "42").

**Причина проблемы**: При импорте из 1С поле "Детский размер" (булевый флаг с значением "Да"/"Нет") ошибочно записывалось в `size_value` вместо реального размера из поля "Размер_...".

### Синтаксис

```bash
python manage.py fix_variant_sizes [OPTIONS]
```

### Опциональные параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `--dry-run` | flag | false | Тестовый запуск без записи в БД |

### Невалидные значения, которые очищаются

- `Да`, `да`
- `Нет`, `нет`  
- `Yes`, `yes`
- `No`, `no`
- `True`, `true`
- `False`, `false`
- `-`

### Примеры использования

#### Тестовый запуск (рекомендуется всегда начинать с него)

```bash
python manage.py fix_variant_sizes --dry-run
```

Вывод:

```
=== ТЕСТОВЫЙ ЗАПУСК (dry-run) ===

Найдено вариантов с невалидным size_value: 742

Будет очищено: 742 вариантов
```

#### Применение очистки

```bash
python manage.py fix_variant_sizes
```

Вывод:

```
Найдено вариантов с невалидным size_value: 742

Очищено вариантов: 742

Теперь запустите повторный импорт:
  python manage.py import_products_from_1c --file-type=offers --data-dir=data/import_1c
```

### Рабочий процесс исправления данных

После очистки некорректных значений необходимо повторно импортировать данные из `offers.xml`, чтобы правильно заполнить поле `size_value`:

```bash
# 1. Очистка невалидных значений
python manage.py fix_variant_sizes

# 2. Повторный импорт из offers.xml
python manage.py import_products_from_1c --file-type=offers --data-dir=data/import_1c
```

### Docker команды

```bash
# Локальное окружение
docker compose --env-file .env -f docker/docker-compose.yml exec backend python manage.py fix_variant_sizes --dry-run
docker compose --env-file .env -f docker/docker-compose.yml exec backend python manage.py fix_variant_sizes

# Production
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend python manage.py fix_variant_sizes --dry-run
docker compose --env-file .env.prod -f docker/docker-compose.prod.yml exec backend python manage.py fix_variant_sizes
```

### Связанные исправления в коде

Вместе с этой командой было исправлено в `variant_import.py`:

1. Удалён "детский размер" из списка `size_names` (это булевый флаг, не размер)
2. Добавлен паттерн `name.startswith("размер_")` для полей вроде "Размер_Обувь для гимнастики..."
3. Добавлена фильтрация невалидных булевых значений ("да", "нет", etc.)

---

## Команда backup_db

### Описание

Создает резервную копию базы данных PostgreSQL в SQL формате.

### Синтаксис

```bash
python manage.py backup_db [OPTIONS]
```

### Опциональные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `--output` | string | Путь к файлу backup (по умолчанию: `BACKUP_DIR/backup_YYYY-MM-DD_HHMMSS.sql`) |
| `--encrypt` | flag | Зашифровать backup с использованием GPG |

### Примеры использования

#### Создать backup с автоматическим именем

```bash
python manage.py backup_db
```

Результат: `backend/backup_db/backup_2025-10-19_143000.sql`

#### Создать backup с указанным именем

```bash
python manage.py backup_db --output=/tmp/my_backup.sql
```

#### Создать зашифрованный backup

```bash
python manage.py backup_db --encrypt
```

Результат: `backend/backup_db/backup_2025-10-19_143000.sql.gpg`

### Автоматическая ротация

Команда автоматически удаляет старые backup файлы, оставляя последние 3 копии.

### Расположение backup файлов

По умолчанию backup файлы сохраняются в:

```
backend/backup_db/
├── backup_2025-10-19_143000.sql
├── backup_2025-10-18_120000.sql
└── backup_2025-10-17_090000.sql
```

---

## Команда restore_db

### Описание

Восстанавливает базу данных из резервной копии.

⚠️ **ВНИМАНИЕ**: Эта операция ПЕРЕЗАПИШЕТ текущую базу данных!

### Синтаксис

```bash
python manage.py restore_db --backup-file=<path> [OPTIONS]
```

### Обязательные параметры

- `--backup-file` - Путь к файлу backup для восстановления

### Опциональные параметры

| Параметр | Тип | Описание |
|----------|-----|----------|
| `--confirm` | flag | Пропустить подтверждение (для автоматизации) |

### Примеры использования

#### Восстановление с подтверждением

```bash
python manage.py restore_db --backup-file=/path/to/backup_2025-10-19_143000.sql
```

Система запросит подтверждение:

```
This will OVERWRITE the current database. Continue? (yes/no):
```

#### Восстановление без подтверждения (для скриптов)

```bash
python manage.py restore_db \
    --backup-file=/path/to/backup_2025-10-19_143000.sql \
    --confirm
```

### Требования

- ✅ Требуется superuser доступ
- ✅ Файл backup должен существовать
- ✅ PostgreSQL должен быть доступен

### Процесс восстановления

1. Проверка прав superuser
2. Валидация существования файла backup
3. Запрос подтверждения (если не указан `--confirm`)
4. Восстановление через `psql`
5. Проверка успешности операции

---

## Команда rotate_backups

### Описание

Управляет ротацией backup файлов, удаляя старые копии.

### Синтаксис

```bash
python manage.py rotate_backups [OPTIONS]
```

### Опциональные параметры

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|--------------|----------|
| `--keep` | integer | 3 | Количество backup файлов для сохранения |
| `--dry-run` | flag | false | Показать что будет удалено без фактического удаления |

### Примеры использования

#### Оставить последние 3 копии (по умолчанию)

```bash
python manage.py rotate_backups
```

#### Оставить последние 5 копий

```bash
python manage.py rotate_backups --keep=5
```

#### Предпросмотр без удаления

```bash
python manage.py rotate_backups --dry-run
```

Вывод:

```
[DRY RUN] Would delete: backup_2025-10-15_120000.sql
[DRY RUN] Would delete: backup_2025-10-14_120000.sql
[DRY RUN] Would keep: backup_2025-10-19_143000.sql
[DRY RUN] Would keep: backup_2025-10-18_120000.sql
[DRY RUN] Would keep: backup_2025-10-17_090000.sql
```

### Автоматизация через cron

Добавьте в crontab для автоматической ротации:

```bash
# Ротация backup файлов каждый день в 2:00
0 2 * * * cd /app && python manage.py rotate_backups --keep=3
```

---

## Примеры использования

### Полный цикл импорта с backup

```bash
# 1. Создать backup перед импортом (автоматически)
python manage.py import_products_from_1c --data-dir=/var/data/1c/export/

# 2. Если что-то пошло не так, восстановить из backup
python manage.py restore_db --backup-file=/path/to/backup_2025-10-19_143000.sql

# 3. Очистить старые backup файлы
python manage.py rotate_backups --keep=3
```

### Регулярный импорт через cron

```bash
# Импорт каталога каждый день в 3:00
0 3 * * * cd /app && python manage.py import_products_from_1c --data-dir=/var/data/1c/export/ >> /var/log/import.log 2>&1

# Ротация backup файлов каждый день в 4:00
0 4 * * * cd /app && python manage.py rotate_backups --keep=5 >> /var/log/backup.log 2>&1
```

### Импорт с мониторингом

```bash
# Запуск с логированием
python manage.py import_products_from_1c \
    --data-dir=/var/data/1c/export/ \
    2>&1 | tee /var/log/import_$(date +%Y%m%d_%H%M%S).log

# Проверка статуса последнего импорта
python manage.py shell -c "
from apps.products.models import ImportSession
session = ImportSession.objects.latest('started_at')
print(f'Status: {session.status}')
print(f'Created: {session.report_details.get(\"created\", 0)}')
print(f'Updated: {session.report_details.get(\"updated\", 0)}')
print(f'Failed: {session.report_details.get(\"failed\", 0)}')
"
```

---

## Troubleshooting

### Ошибка: "This command requires superuser privileges"

**Проблема**: Недостаточно прав для выполнения команды.

**Решение**:

```bash
# Проверить права пользователя
python manage.py shell
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()
>>> user = User.objects.get(username='admin')
>>> user.is_superuser = True
>>> user.save()
```

### Ошибка: "Директория не найдена"

**Проблема**: Указанная директория не существует.

**Решение**:

```bash
# Проверить путь
ls -la /var/data/1c/export/

# Создать директорию если нужно
mkdir -p /var/data/1c/export/{goods,offers,prices,rests,priceLists}
```

### Ошибка: "File size exceeds limit"

**Проблема**: XML файл слишком большой (>100MB).

**Решение**:

```bash
# Разбить файл на части
split -b 50M large_file.xml part_

# Или увеличить лимит в settings.py
IMPORT_MAX_FILE_SIZE = 200  # MB
```

### Импорт зависает

**Проблема**: Импорт не завершается более 10 минут.

**Решение**:

```bash
# Использовать меньший chunk-size
python manage.py import_products_from_1c \
    --data-dir=/path \
    --chunk-size=500

# Проверить логи
tail -f /var/log/freesport/import.log

# Проверить процессы
ps aux | grep import_products
```

### Дубликаты товаров после импорта

**Проблема**: Появились дубликаты с одинаковым onec_id.

**Решение**:

```python
# Найти и удалить дубликаты
python manage.py shell
>>> from django.db.models import Count
>>> from apps.products.models import Product
>>> duplicates = Product.objects.values('onec_id').annotate(
...     count=Count('id')
... ).filter(count__gt=1)
>>> for dup in duplicates:
...     products = Product.objects.filter(onec_id=dup['onec_id']).order_by('created_at')
...     products.exclude(id=products.last().id).delete()
```

### Backup не создается

**Проблема**: Ошибка при создании backup.

**Решение**:

```bash
# Проверить подключение к БД
python manage.py dbshell

# Проверить права на запись
ls -la /path/to/backup/
chmod 700 /path/to/backup/

# Проверить переменные окружения
echo $BACKUP_DIR
```

---

## Переменные окружения

Для работы команд импорта требуются следующие переменные в `.env`:

```bash
# Пути к директориям
ONEC_DATA_DIR=/var/data/1c/export/
BACKUP_DIR=/var/backups/freesport/

# Настройки импорта
IMPORT_CHUNK_SIZE=1000
IMPORT_TIMEOUT=300
IMPORT_MAX_RETRIES=3

# Настройки бэкапов
BACKUP_RETENTION_DAYS=30
BACKUP_COMPRESSION=true

# Логирование
IMPORT_LOG_LEVEL=INFO
IMPORT_LOG_FILE=/var/log/freesport/import.log
```

---

## Дополнительные ресурсы

- [Story 3.1.2: loading-scripts](../stories/epic-3/3.1.2.loading-scripts.md)
- [Архитектура интеграции с 1С](../architecture/20-1c-integration.md)
- [Стандарты кодирования](../architecture/coding-standards.md)

---

## Поддержка

При возникновении проблем:

1. Проверьте логи: `/var/log/freesport/import.log`
2. Проверьте статус ImportSession в Django Admin
3. Обратитесь к разделу [Troubleshooting](#troubleshooting)
4. Создайте issue в репозитории проекта
