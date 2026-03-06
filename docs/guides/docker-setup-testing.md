# Настройка Docker для запуска Backend тестов

## Требования

### Обязательно
- **Docker Desktop** версии 20.10 или выше
- **Docker Compose** v2 (встроенный в Docker Desktop)
- Минимум 4 GB RAM для Docker
- Минимум 10 GB свободного места на диске

### Операционные системы
- Windows 11 (рекомендуется)
- Windows 10 Pro/Enterprise (с WSL2)
- macOS 10.15+
- Linux (Ubuntu 20.04+, Debian 11+, etc.)

## Установка Docker

### Windows 11

1. **Скачать Docker Desktop**
   ```
   https://www.docker.com/products/docker-desktop/
   ```

2. **Установить Docker Desktop**
   - Запустить установщик
   - Включить WSL2 backend (рекомендуется)
   - Перезагрузить компьютер

3. **Проверить установку**
   ```powershell
   docker --version
   docker compose version
   ```

4. **Настроить ресурсы**
   - Открыть Docker Desktop → Settings → Resources
   - Выделить минимум 4 GB RAM
   - Выделить минимум 2 CPU cores

### macOS

1. **Скачать Docker Desktop для Mac**
   ```
   https://www.docker.com/products/docker-desktop/
   ```

2. **Установить**
   - Перетащить Docker.app в Applications
   - Запустить Docker Desktop
   - Дождаться инициализации

3. **Проверить установку**
   ```bash
   docker --version
   docker compose version
   ```

### Linux (Ubuntu/Debian)

1. **Установить Docker Engine**
   ```bash
   # Удалить старые версии
   sudo apt-get remove docker docker-engine docker.io containerd runc

   # Установить зависимости
   sudo apt-get update
   sudo apt-get install -y ca-certificates curl gnupg lsb-release

   # Добавить официальный GPG ключ Docker
   sudo mkdir -p /etc/apt/keyrings
   curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

   # Настроить репозиторий
   echo \
     "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
     $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

   # Установить Docker
   sudo apt-get update
   sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
   ```

2. **Настроить права доступа**
   ```bash
   # Добавить текущего пользователя в группу docker
   sudo usermod -aG docker $USER

   # Применить изменения (требуется logout/login)
   newgrp docker
   ```

3. **Проверить установку**
   ```bash
   docker --version
   docker compose version
   ```

## Структура тестового окружения

```
FREESPORT/
├── docker/
│   ├── docker-compose.test.yml    # Конфигурация для тестов
│   └── ...
├── backend/
│   ├── Dockerfile.test            # Образ для тестирования
│   ├── pytest.ini                 # Настройки pytest
│   └── apps/
│       └── __tests__/             # Тесты приложений
└── Makefile                       # Команды для запуска тестов
```

## Конфигурация тестового окружения

### docker-compose.test.yml

**Сервисы:**
- `db` - PostgreSQL 15 на порту 5433
- `redis` - Redis 7 на порту 6380
- `backend` - Django с pytest

**Особенности:**
- Использует отдельные порты (5433, 6380) для избежания конфликтов
- tmpfs для ускорения тестов
- Healthchecks для гарантии готовности сервисов
- Volume для сохранения coverage отчетов

## Команды для запуска тестов

### Базовые команды

```bash
# Показать все доступные команды
make help

# Запустить все тесты (с пересборкой образов)
make test

# Запустить только unit-тесты
make test-unit

# Запустить только интеграционные тесты
make test-integration

# Быстрые тесты (без пересборки образов)
make test-fast
```

### Детальные команды

**Полный цикл тестирования:**
```bash
# 1. Остановить старые контейнеры и очистить volumes
cd docker && docker compose -f docker-compose.test.yml down --remove-orphans --volumes

# 2. Собрать образы и запустить тесты
cd docker && docker compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend

# 3. Очистить после тестов
cd docker && docker compose -f docker-compose.test.yml down
```

**Запуск конкретных тестов:**
```bash
# Запустить тесты конкретного модуля
cd docker && docker compose -f docker-compose.test.yml run --rm backend pytest apps/products/tests/

# Запустить конкретный тестовый файл
cd docker && docker compose -f docker-compose.test.yml run --rm backend pytest apps/products/tests/test_models.py

# Запустить конкретный тест
cd docker && docker compose -f docker-compose.test.yml run --rm backend pytest apps/products/tests/test_models.py::test_product_creation

# С увеличенной детализацией
cd docker && docker compose -f docker-compose.test.yml run --rm backend pytest -vv --tb=long
```

**Работа с coverage:**
```bash
# Тесты с coverage отчетом
cd docker && docker compose -f docker-compose.test.yml run --rm backend pytest --cov=apps --cov-report=html --cov-report=term-missing

# Посмотреть coverage отчет
# HTML отчет будет в backend/htmlcov/index.html
```

## Отладка тестов

### Интерактивный режим

```bash
# Запустить bash в контейнере backend
cd docker && docker compose -f docker-compose.test.yml run --rm backend bash

# Внутри контейнера можно запускать pytest напрямую
pytest -v --tb=short
pytest --pdb  # С отладчиком
```

### Просмотр логов

```bash
# Логи всех сервисов
cd docker && docker compose -f docker-compose.test.yml logs

# Логи конкретного сервиса
cd docker && docker compose -f docker-compose.test.yml logs backend
cd docker && docker compose -f docker-compose.test.yml logs db

# Следить за логами в реальном времени
cd docker && docker compose -f docker-compose.test.yml logs -f backend
```

### Проверка состояния сервисов

```bash
# Статус контейнеров
cd docker && docker compose -f docker-compose.test.yml ps

# Проверка healthcheck
cd docker && docker compose -f docker-compose.test.yml ps --format json | jq -r '.[].Health'
```

## Решение проблем

### Проблема: "Cannot connect to the Docker daemon"

**Решение:**
```bash
# Убедиться что Docker Desktop запущен
# Windows: Проверить в System Tray
# Linux:
sudo systemctl status docker
sudo systemctl start docker
```

### Проблема: "port 5433 is already allocated"

**Решение:**
```bash
# Найти процесс использующий порт
# Windows:
netstat -ano | findstr :5433

# Linux/macOS:
lsof -i :5433

# Остановить конфликтующие контейнеры
docker ps -a
docker stop <container_id>
```

### Проблема: "no space left on device"

**Решение:**
```bash
# Очистить неиспользуемые образы и контейнеры
docker system prune -a --volumes

# Увеличить место для Docker в настройках Docker Desktop
```

### Проблема: Тесты падают с ошибками БД

**Решение:**
```bash
# Полная очистка и пересоздание
cd docker && docker compose -f docker-compose.test.yml down --volumes
cd docker && docker compose -f docker-compose.test.yml up --build
```

## Best Practices

1. **Всегда используйте `make test` для CI/CD**
   - Гарантирует чистое окружение
   - Пересобирает образы с изменениями

2. **Используйте `make test-fast` для локальной разработки**
   - Быстрее, т.к. не пересобирает образы
   - Подходит для итеративной разработки

3. **Регулярно очищайте Docker**
   ```bash
   # Раз в неделю
   docker system prune -a --volumes
   ```

4. **Мониторьте использование ресурсов**
   ```bash
   docker stats
   ```

5. **Изолируйте тестовые данные**
   - Никогда не используйте production БД для тестов
   - Используйте fixtures и фабрики для генерации данных

## Переменные окружения для тестов

Редактируйте `docker/docker-compose.test.yml` для изменения:

```yaml
environment:
  - DJANGO_SETTINGS_MODULE=freesport.settings.test
  - SECRET_KEY=test-secret-key-for-testing-only
  - DB_NAME=freesport_test
  - DB_USER=postgres
  - DB_PASSWORD=password123
  - DB_HOST=db
  - DB_PORT=5432
  - REDIS_URL=redis://:redis123@redis:6379/1
  - DEBUG=0
```

## CI/CD Integration

### GitHub Actions

Пример workflow для запуска тестов:

```yaml
name: Backend Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Run tests
        run: make test

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./backend/htmlcov/index.html
```

## Дополнительная информация

- **Документация pytest**: https://docs.pytest.org/
- **Docker Compose документация**: https://docs.docker.com/compose/
- **PostgreSQL в Docker**: https://hub.docker.com/_/postgres
- **Redis в Docker**: https://hub.docker.com/_/redis

## КРИТИЧНО: Security

⚠️ **НИКОГДА не коммитьте:**
- Реальные пароли БД в docker-compose файлы
- GitHub Personal Access Tokens
- API ключи
- Production credentials

Используйте:
- `.env` файлы (добавлены в `.gitignore`)
- GitHub Secrets для CI/CD
- Отдельные credentials для dev/test/prod окружений
