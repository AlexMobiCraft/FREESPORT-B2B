# 19. Development Environment Guide

## Обзор

Полное руководство по настройке среды разработки FREESPORT Platform на основе существующей инфраструктуры проекта.

## Существующая Инфраструктура

### Структура проекта (Monorepo)

```
freesport/
├── backend/                    # Django + DRF API
│   ├── apps/                   # Django приложения
│   ├── freesport/              # Settings и конфигурация
│   ├── tests/                  # Comprehensive test suite
│   │   ├── unit/               # Unit тесты
│   │   ├── integration/        # Integration тесты
│   │   └── performance/        # Performance тесты
│   ├── requirements.txt        # Python зависимости
│   ├── manage.py               # Django CLI
│   ├── pytest.ini             # Pytest конфигурация
│   └── .env.example            # Environment template
├── frontend/                   # Next.js 15+ App
│   ├── src/app/                # Next.js App Router
│   ├── src/components/         # React компоненты
│   ├── package.json            # Node.js зависимости
│   └── .env.example            # Frontend environment
├── docker-compose.yml          # Development environment
├── docker-compose.test.yml     # Testing environment
├── Makefile                    # Development commands
└── scripts/                    # Automation scripts
    ├── test.sh                 # Linux/macOS test runner
    └── test.bat                # Windows test runner
```

### Technology Stack

**Backend (Django 4.2 LTS):**
- ✅ Django REST Framework 3.14+
- ✅ PostgreSQL 15+ (production)
- ✅ Redis 7.0+ for caching
- ✅ JWT authentication with refresh tokens
- ✅ drf-spectacular for OpenAPI documentation

**Frontend (Next.js 15+):**
- ✅ React 19.1.0 with App Router
- ✅ TypeScript 5.0+
- ✅ Tailwind CSS 4.0
- ✅ Zustand for state management
- ✅ React Hook Form for forms
- ✅ Jest + Testing Library for testing

## Быстрый Старт

### Вариант 1: Docker (Рекомендуемый)

```bash
# 1. Клонировать репозиторий
git clone <repository-url>
cd freesport

# 2. Запустить среду разработки
make up

# 3. Открыть в браузере
# Frontend: http://localhost:3000
# Backend API: http://localhost:8001/api/v1/
# Admin Panel: http://localhost:8001/admin/
```

**Доступные команды:**
```bash
make help          # Показать все команды
make build         # Собрать Docker образы
make up            # Запустить среду разработки
make down          # Остановить среду
make logs          # Показать логи
make shell         # Shell в backend контейнере
make test          # Запустить все тесты
make clean         # Очистить volumes и образы
```

### Вариант 2: Локальная разработка

#### Backend Setup

```bash
cd backend

# 1. Создать виртуальное окружение
python -m venv venv

# 2. Активировать venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Настроить окружение
cp .env.example .env
# Отредактировать .env файл

# 5. Применить миграции
python manage.py migrate

# 6. Создать суперпользователя
python manage.py createsuperuser

# 7. Запустить сервер
python manage.py runserver 8001
```

#### Frontend Setup

```bash
cd frontend

# 1. Установить Node.js зависимости
npm install

# 2. Настроить окружение
cp .env.example .env.local
# Отредактировать .env.local файл

# 3. Запустить dev сервер
npm run dev

# 4. Открыть http://localhost:3000
```

## Конфигурация Окружения

### Backend Environment (.env)

**Основанные на backend/.env.example:**

```bash
# === РЕЖИМ РАЗРАБОТКИ ===
DJANGO_ENVIRONMENT=development
SECRET_KEY=your-super-secret-key-change-this-in-production

# === DATABASE (локальная разработка через PostgreSQL Docker) ===
DB_NAME=freesport
DB_USER=postgres
DB_PASSWORD=password123
DB_HOST=localhost
DB_PORT=5432

# === REDIS CACHE ===
REDIS_URL=redis://localhost:6379/0

# === EMAIL (разработка - console backend) ===
EMAIL_HOST=localhost
EMAIL_PORT=587
DEFAULT_FROM_EMAIL=dev@freesport.local
```

### Frontend Environment (.env.local)

**Основанные на frontend/.env.example:**

```bash
# === API CONNECTION ===
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1

# === DEVELOPMENT MODE ===
NODE_ENV=development

# === ANALYTICS (опционально) ===
NEXT_PUBLIC_GA_MEASUREMENT_ID=G-XXXXXXXXXX
NEXT_PUBLIC_YANDEX_METRIKA_ID=XXXXXXXX

# === BRAND SETTINGS ===
NEXT_PUBLIC_COMPANY_NAME=FREESPORT Platform
NEXT_PUBLIC_SUPPORT_EMAIL=support@freesport.local
NEXT_PUBLIC_SUPPORT_PHONE=+7 (xxx) xxx-xx-xx
```

## Система Тестирования

### Существующая Pytest Конфигурация

**pytest.ini настройки:**
```ini
[pytest]
DJANGO_SETTINGS_MODULE = freesport.settings.test
testpaths = tests
addopts = 
    --cov=apps --cov-report=html:htmlcov --cov-report=term-missing
    --cov-fail-under=70  # Минимальный coverage 70%
    --create-db --nomigrations
    --maxfail=5 --durations=10

markers =
    slow: медленные тесты (например, с внешними API)
    integration: интеграционные тесты  
    unit: юнит тесты
    api: тесты API endpoints
    auth: тесты аутентификации
    models: тесты моделей Django
```

### Команды тестирования

#### Docker (рекомендуемый способ)

```bash
# Все тесты
make test

# Unit тесты только
make test-unit

# Integration тесты только  
make test-integration
```

#### Локально

```bash
cd backend

# Все тесты
pytest

# Unit тесты
pytest -m unit

# Integration тесты
pytest -m integration

# С покрытием кода
pytest --cov=apps --cov-report=html

# Конкретные тесты
pytest tests/unit/test_models/test_user_models.py::TestUserModel::test_user_creation
```

#### Frontend тесты

```bash
cd frontend

# Запуск тестов
npm test

# Тесты в watch режиме
npm run test:watch

# С покрытием
npm run test:coverage
```

### Автоматизированные скрипты

**Linux/macOS (scripts/test.sh):**
```bash
#!/bin/bash
# Полностью автоматизированный запуск тестов
./scripts/test.sh
```

**Windows (scripts/test.bat):**
```cmd
REM Автоматизированный запуск для Windows
scripts\test.bat
```

## Database Setup

### Development (PostgreSQL Docker)

**По умолчанию для разработки используется PostgreSQL:**
- ✅ Запускается через `docker-compose up -d`
- ✅ Конфигурация хранится в `backend/.env`
- ✅ Полностью совпадает с staging/production окружениями

### Testing (PostgreSQL in Docker)

**docker-compose.test.yml конфигурация:**
```yaml
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: freesport_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password123

    ports:
      - "5433:5432"  # Не конфликтует с основной БД
```

### Production Setup

**Для staging/production используется PostgreSQL:**
```bash
# Переменные в .env
DB_NAME=freesport
DB_USER=postgres
DB_PASSWORD=secure-password
DB_HOST=db-host
DB_PORT=5432

DB_SSLMODE=require
```

## IDE и Editor Setup

### VSCode (рекомендуемый)

**Рекомендуемые расширения:**

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.black-formatter", 
    "ms-python.isort",
    "ms-python.mypy-type-checker",
    "bradlc.vscode-tailwindcss",
    "esbenp.prettier-vscode",
    "ms-vscode.vscode-typescript-next"
  ]
}
```

**Settings для проекта (.vscode/settings.json):**

```json
{
  "python.defaultInterpreterPath": "./backend/venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests"],
  "python.formatting.provider": "black",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "files.associations": {
    "*.html": "html"
  },
  "tailwindCSS.includeLanguages": {
    "typescript": "javascript",
    "typescriptreact": "javascript"
  }
}
```

### PyCharm Setup

1. **Python Interpreter:** `backend/venv/bin/python`
2. **Django Support:** включить Django support
3. **Test Runner:** pytest
4. **Code Style:** Black formatter
5. **Database:** PostgreSQL для development

## Debugging

### Backend Debugging

#### Django Debug Toolbar (development)

```python
# settings/development.py уже настроен
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
```

#### Логирование

**Уже настроено в settings/development.py:**
```python
LOGGING = {
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        }
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO'},
        'freesport': {'handlers': ['console'], 'level': 'DEBUG'},
    }
}
```

#### IPython/Jupyter в Django

```bash
# Установить дополнительно для отладки
pip install ipython django-extensions jupyter

# Django shell с IPython
python manage.py shell_plus

# Notebook с Django контекстом
python manage.py shell_plus --notebook
```

### Frontend Debugging

#### Next.js Development Tools

```bash
# Турбо режим для быстрой разработки
npm run dev  # уже использует --turbopack

# Анализ bundle
npm run build
npm run analyze  # если добавить @next/bundle-analyzer
```

#### React DevTools

- ✅ Установить React DevTools в браузере
- ✅ Zustand DevTools для state management
- ✅ TanStack Query DevTools (если используется)

## Performance Monitoring

### Development Profiling

#### Backend Performance

**Уже встроенные инструменты:**
```python
# Performance тесты в tests/performance/
pytest tests/performance/ -v

# Profiling отдельного теста
pytest tests/performance/test_catalog_performance.py::test_memory_usage_catalog -v
```

#### Database Queries

```python  
# Включить логирование SQL в development
LOGGING['loggers']['django.db.backends'] = {
    'handlers': ['console'],
    'level': 'DEBUG',
}
```

### Frontend Performance

```bash
# Bundle analysis
npm run build
npm run start

# Lighthouse audit
# Использовать Chrome DevTools > Lighthouse
```

## Git Workflow

### Branch Strategy

```bash
# Основанные на существующих ветках
main       # продакшен ветка (защищена)
develop    # основная ветка разработки (защищена)
feature/*  # ветки для новых функций
hotfix/*   # критические исправления
```

### Pre-commit Setup (рекомендуется)

```bash
# Установить pre-commit
pip install pre-commit

# Создать .pre-commit-config.yaml
cat > .pre-commit-config.yaml << EOF
repos:
  - repo: https://github.com/psf/black
    rev: 23.11.0
    hooks:
      - id: black
        language_version: python3.12
  - repo: https://github.com/pycqa/isort
    rev: 5.12.0
    hooks:
      - id: isort
  - repo: https://github.com/pycqa/flake8
    rev: 6.1.0
    hooks:
      - id: flake8
EOF

# Установить хуки
pre-commit install
```

## Troubleshooting

### Часто встречающиеся проблемы

#### 1. Docker порты заняты

```bash
# Проверить занятые порты
netstat -tulpn | grep :8001
netstat -tulpn | grep :3000

# Остановить конфликтующие сервисы
make down
docker-compose ps
```

#### 2. Database migration проблемы

```bash
# PostgreSQL в Docker
docker-compose down -v  # удалить volumes
docker-compose up -d
```

#### 3. Node.js dependency conflicts

```bash
cd frontend
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

#### 4. Python virtual environment

```bash
# Пересоздать venv
rm -rf backend/venv
cd backend
python -m venv venv
source venv/bin/activate  # или venv\Scripts\activate на Windows
pip install -r requirements.txt
```

### Кодировка Windows (UTF-8)

**Уже настроено в settings/base.py:**
```python
# Настройка кодировки для Windows консоли
if sys.platform == "win32":
    try:
        locale.setlocale(locale.LC_ALL, "ru_RU.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, "Russian_Russia.1251")
        except locale.Error:
            pass
```

### Performance Issues

#### Backend медленно отвечает

1. **Проверить Database queries:**
   ```python
   from django.db import connection
   print(len(connection.queries))  # количество запросов
   ```

2. **Использовать Django Debug Toolbar**
3. **Запустить performance тесты:**
   ```bash
   pytest tests/performance/ -v
   ```

#### Frontend медленно загружается

1. **Использовать Next.js турбо режим** (уже настроен)
2. **Проверить bundle size** с bundle analyzer
3. **Проверить network requests** в DevTools

## Production Deployment

### Различия от Development

1. **Database:** PostgreSQL
2. **Cache:** Redis с персистентностью  
3. **Static files:** S3/CDN вместо локальных файлов
4. **Environment:** `DJANGO_ENVIRONMENT=production`
5. **Debug:** `DEBUG=False`
6. **HTTPS:** Обязательный SSL

**Подробности в:** `docs/architecture/15-deployment-guide.md`

## Заключение

Development environment FREESPORT полностью автоматизирован и оптимизирован:

- ✅ **Docker first** подход с полной изоляцией
- ✅ **Comprehensive testing** с 70%+ coverage требованием
- ✅ **Automated scripts** для всех платформ (Windows/Linux/macOS)  
- ✅ **Performance monitoring** встроенный в development flow
- ✅ **IDE integration** готовая конфигурация для VSCode/PyCharm
- ✅ **Troubleshooting guide** для быстрого решения проблем

**Следующие шаги для новых разработчиков:**
1. Клонировать репозиторий 
2. Выполнить `make up`
3. Открыть http://localhost:3000
4. Начать разработку!