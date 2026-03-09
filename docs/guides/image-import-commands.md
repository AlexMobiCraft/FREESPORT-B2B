# Импорт и дедупликация изображений товаров

Документация по использованию management команд для работы с изображениями товаров из 1С.

## Команды

### 1. `import_products_from_1c` — Полный импорт из 1С

Основная команда импорта товаров, вариантов, цен и остатков.

```bash
# Полный импорт всех данных
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_products_from_1c --file-type=all

# Только товары (goods.xml)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_products_from_1c --file-type=goods

# Только цены (prices.xml)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_products_from_1c --file-type=prices

# Только остатки (rests.xml)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_products_from_1c --file-type=rests
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `--file-type` | Тип файла: `all`, `goods`, `prices`, `rests` |
| `--data-dir` | Путь к директории с данными 1С |
| `--skip-images` | Пропустить импорт изображений |

---

### 2. `import_images_from_1c` — Импорт только изображений

Импортирует изображения для существующих товаров без обновления других данных.

```bash
# Импорт всех изображений
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_images_from_1c

# Тестовый запуск (без записи)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_images_from_1c --dry-run

# С подробным выводом
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_images_from_1c --verbose

# Ограничить количество товаров
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_images_from_1c --limit 100
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `--data-dir` | Путь к директории с данными 1С |
| `--dry-run` | Тестовый запуск без записи |
| `--limit N` | Обработать только N товаров |
| `--verbose` | Подробный вывод |

**Важно:** При импорте автоматически пропускаются файлы меньше 100KB.

---

### 3. `deduplicate_images` — Очистка дублей и мелких файлов

Удаляет дублированные записи изображений и записи с файлами меньше указанного размера.

```bash
# Тестовый запуск (посмотреть что будет удалено)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images --dry-run --verbose

# Реальная очистка
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images

# С другим порогом размера (50KB)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images --min-size 50 --verbose

# Только дедупликация (без проверки размера)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images --skip-size-check

# Предпочитать новый формат путей (XX/... вместо import_files/...)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images --prefer-new-path
```

**Параметры:**

| Параметр | Описание |
|----------|----------|
| `--dry-run` | Тестовый запуск без сохранения |
| `--verbose` | Показать детали по каждому товару |
| `--min-size N` | Минимальный размер файла в KB (по умолчанию 100) |
| `--skip-size-check` | Пропустить проверку размера |
| `--prefer-new-path` | Предпочитать пути без `import_files/` |

**Что делает команда:**

1. **Product.base_images** — удаляет дублированные и мелкие изображения
2. **ProductVariant.gallery_images** — то же самое для вариантов
3. **Сохраняет минимум 1 изображение** — если все изображения мелкие, оставляет первое

---

## Рекомендуемый порядок действий

### После синхронизации данных из 1С

```bash
# 1. Полный импорт товаров
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_products_from_1c --file-type=all

# 2. Очистка дублей (сначала dry-run)
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images --dry-run --verbose

# 3. Если всё ОК, применить
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images
```

### Только обновить изображения

```bash
# 1. Импорт изображений
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py import_images_from_1c --verbose

# 2. Очистка дублей
docker compose --env-file .env -f docker/docker-compose.yml exec backend \
    python manage.py deduplicate_images
```

---

## Структура путей изображений

После импорта изображения сохраняются в:

```
media/
├── products/
│   ├── base/           # Базовые изображения товаров
│   │   ├── 41/         # Поддиректория по первым 2 символам ID
│   │   │   └── 41cae745-..._41cae746-....jpg
│   │   └── 8f/
│   │       └── 8f07c7e0-..._f15f3ce2-....jpg
│   └── variants/       # Изображения вариантов
│       └── XX/
│           └── *.jpg
```

**Формат имени файла:** `{product_onec_id}_{image_onec_id}.jpg`

---

## Проблемы и решения

### Дублирование изображений

**Проблема:** Изображения сохранялись с двумя путями:

- `products/base/import_files/41/filename.jpg`
- `products/base/41/filename.jpg`

**Причина:** В код передавался ненормализованный путь.

**Решение:** Исправлено в `variant_import.py`, запустите `deduplicate_images` для очистки.

### Мелкие изображения

**Проблема:** Импортировались файлы-заглушки размером 5-50KB.

**Решение:** Добавлена проверка минимального размера (100KB) при импорте. Существующие мелкие файлы можно удалить командой `deduplicate_images`.

---

## Локальный запуск (без Docker)

```bash
cd backend

# Импорт товаров
python manage.py import_products_from_1c --file-type=all

# Импорт изображений
python manage.py import_images_from_1c --verbose

# Дедупликация
python manage.py deduplicate_images --dry-run --verbose
```
