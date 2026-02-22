# Руководство по запуску тестов FREESPORT

## Быстрый старт

### Запуск через Docker (рекомендуется)

**Преимущества:**
- Изолированная среда тестирования
- Автоматическая настройка PostgreSQL и Redis
- Соответствие окружению CI/CD на GitHub Actions

**Требования:**
- Docker Desktop должен быть запущен

**Команды:**

```powershell
# Из корневой директории проекта
.\run-tests-docker.ps1
```

Или вручную:

```powershell
# Запуск всех тестов
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Очистка после тестов
docker-compose -f docker-compose.test.yml down -v
```

### Запуск конкретных тестов через Docker

```powershell
# Только unit тесты
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit -v

# Только integration тесты
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/integration -v

# Конкретный файл
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit/test_models/test_product_models.py -v

# Конкретный тест
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit/test_models/test_product_models.py::TestProductModel1CFields::test_last_sync_at_field -v
```

### Запуск локально (без Docker)

**Требования:**
- PostgreSQL запущен локально или через Docker
- Redis запущен локально или через Docker
- Виртуальное окружение Python активировано

**Настройка переменных окружения:**

```powershell
# В PowerShell
$env:DJANGO_SETTINGS_MODULE="freesport.settings.test"
$env:DB_NAME="test_db"
$env:DB_USER="postgres"
$env:DB_PASSWORD="postgres"
$env:DB_HOST="localhost"
$env:DB_PORT="5432"
$env:REDIS_URL="redis://localhost:6379/0"
```

**Команды:**

```powershell
cd backend

# Все тесты
python -m pytest -v

# С покрытием кода
python -m pytest --cov=apps --cov-report=html --cov-report=term -v

# Только unit тесты
python -m pytest tests/unit -v

# Только integration тесты
python -m pytest tests/integration -v

# Конкретный файл
python -m pytest tests/unit/test_models/test_product_models.py -v

# С подробным выводом ошибок
python -m pytest tests/unit -v --tb=long
```

## Проверка исправлений после коммита

### 1. Проверка naive datetime warnings

```powershell
# Запустить тесты, которые используют datetime
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit/test_models/test_product_models.py::TestProductModel1CFields -v
```

**Ожидаемый результат:** Нет предупреждений "DateTimeField received a naive datetime"

### 2. Проверка Database access not allowed

```powershell
# Запустить тесты сериализаторов
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit/test_serializers -v
```

**Ожидаемый результат:** Нет ошибок "RuntimeError: Database access not allowed"

### 3. Проверка уникальности ключей

```powershell
# Запустить все тесты моделей
docker-compose -f docker-compose.test.yml run --rm backend pytest tests/unit/test_models -v
```

**Ожидаемый результат:** Нет ошибок "duplicate key value violates unique constraint"

## Полезные опции pytest

```powershell
# Остановиться на первой ошибке
pytest -x

# Показать локальные переменные при ошибке
pytest -l

# Запустить последние упавшие тесты
pytest --lf

# Запустить тесты параллельно (требует pytest-xdist)
pytest -n auto

# Показать самые медленные тесты
pytest --durations=10

# Запустить только тесты с определенным маркером
pytest -m django_db

# Подробный вывод (показывает print statements)
pytest -s -v
```

## Отладка тестов

### Просмотр логов Docker контейнеров

```powershell
# Логи backend контейнера
docker-compose -f docker-compose.test.yml logs backend

# Логи PostgreSQL
docker-compose -f docker-compose.test.yml logs db

# Логи Redis
docker-compose -f docker-compose.test.yml logs redis

# Следить за логами в реальном времени
docker-compose -f docker-compose.test.yml logs -f backend
```

### Подключение к контейнеру для отладки

```powershell
# Запустить bash в backend контейнере
docker-compose -f docker-compose.test.yml run --rm backend bash

# Внутри контейнера можно запускать команды:
# python manage.py shell
# pytest tests/unit -v
# python manage.py check
```

### Проверка подключения к БД

```powershell
# Подключиться к PostgreSQL контейнеру
docker-compose -f docker-compose.test.yml exec db psql -U postgres -d freesport_test

# Внутри psql:
# \dt - показать таблицы
# \d products_product - описание таблицы
# SELECT COUNT(*) FROM products_product;
```

## CI/CD на GitHub Actions

Тесты на GitHub Actions используют те же настройки, что и `docker-compose.test.yml`:

- PostgreSQL 15
- Redis 7
- Python 3.12
- Django settings: `freesport.settings.test`

**Просмотр логов CI:**

1. Перейдите в GitHub репозиторий
2. Вкладка "Actions"
3. Выберите последний workflow run
4. Кликните на "Run tests" для просмотра логов

## Структура тестов

```text
backend/tests/
├── unit/                    # Unit тесты (изолированные)
│   ├── test_models/        # Тесты моделей
│   ├── test_serializers/   # Тесты сериализаторов
│   └── test_*.py           # Другие unit тесты
├── integration/            # Integration тесты (API, workflows)
├── performance/            # Performance тесты
├── fixtures/               # Общие фикстуры
├── conftest.py            # Глобальные фикстуры pytest
└── factories.py           # Factory Boy фабрики

```

## Покрытие кода

```powershell
# Генерация HTML отчета о покрытии
docker-compose -f docker-compose.test.yml run --rm backend pytest --cov=apps --cov-report=html

# Отчет будет в backend/htmlcov/index.html
# Откройте в браузере для просмотра
```

## Чеклист перед коммитом

- [ ] Все тесты проходят локально через Docker
- [ ] Нет предупреждений о naive datetime
- [ ] Нет ошибок "Database access not allowed"
- [ ] Нет ошибок уникальности ключей
- [ ] Покрытие кода не упало
- [ ] Новые тесты добавлены для новой функциональности
- [ ] Документация обновлена при необходимости

## Troubleshooting

### Docker не запускается

```powershell
# Проверить статус Docker
docker ps

# Если ошибка - запустите Docker Desktop
```

### Ошибка "port is already allocated"

```powershell
# Остановить все контейнеры
docker-compose -f docker-compose.test.yml down

# Проверить занятые порты
netstat -ano | findstr :5433
netstat -ano | findstr :6380

# Убить процесс по PID (последний столбец)
taskkill /PID <PID> /F
```

### Тесты зависают

```powershell
# Остановить все контейнеры
docker-compose -f docker-compose.test.yml down -v

# Очистить Docker кеш
docker system prune -f

# Запустить заново
docker-compose -f docker-compose.test.yml up --build
```

### Ошибки миграций

```powershell
# Сбросить БД и применить миграции заново
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d db redis
docker-compose -f docker-compose.test.yml run --rm backend python manage.py migrate
docker-compose -f docker-compose.test.yml run --rm backend pytest
```
