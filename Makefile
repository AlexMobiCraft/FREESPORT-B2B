# Makefile для FREESPORT Platform

ROOT_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
DOCS_SCRIPTS_DIR := $(ROOT_DIR)scripts/docs

.PHONY: help build build-frontend up down test test-unit test-integration test-performance test-slow clean logs shell \
         format lint migrate createsuperuser collectstatic \
         docs-validate docs-search-obsolete docs-check-links docs-check-api docs-update-index \
         check-env-consistency fix-black-quick fix-existing-venv remove-venv

# По умолчанию показываем help
help:
	@echo "FREESPORT Platform - Доступные команды:"
	@echo ""
	@echo "Разработка:"
	@echo "  build          - Собрать все Docker образы"
	@echo "  build-frontend - Production-сборка Next.js внутри контейнера"
	@echo "  up             - Запустить среду разработки"
	@echo "  down           - Остановить среду разработки"
	@echo "  logs           - Показать логи всех сервисов"
	@echo "  clean          - Очистить Docker volumes и образы"
	@echo ""
	@echo "Форматирование и линтинг:"
	@echo "  format         - Форматирование через Docker (полный контекст)"
	@echo "  format-fast    - Быстрое форматирование через lightweight Docker"
	@echo "  format-local   - Локальное форматирование (требует venv)"
	@echo "  lint           - Линтинг через Docker (полный контекст)"
	@echo "  lint-fast      - Быстрый линтинг через lightweight Docker"
	@echo "  lint-local     - Локальный линтинг (требует venv)"
	@echo ""
	@echo "Тестирование (PostgreSQL + Redis через Docker):"
	@echo "  test           - Запустить все тесты в Docker с PostgreSQL"
	@echo "  test-unit      - Запустить только unit-тесты"
	@echo "  test-integration - Запустить интеграционные тесты"
	@echo "  test-performance - Перф-тесты (вне обычного гейта)"
	@echo "  test-slow      - Медленные тесты (маркер slow, вне обычного гейта)"
	@echo "  test-fast      - Быстрые тесты (без пересборки образов)"
	@echo "  test-fast-tools - Быстрые тесты через lightweight Docker"
	@echo "  test-local     - Локальное тестирование (требует venv)"
	@echo ""
	@echo "Документация:"
	@echo "  docs-validate      - Полная валидация документации"
	@echo "  docs-search-obsolete - Поиск устаревших терминов"
	@echo "  docs-check-links   - Проверка кросс-ссылок"
	@echo "  docs-check-api     - Проверка покрытия API"
	@echo "  docs-update-index  - Обновление индекса документации"
	@echo "  docs-sync-api      - Сверка API (код ↔ docs)"
	@echo "  docs-sync-decisions - Сверка решений (docs ↔ код)"
	@echo "  docs-sync-all      - Выполнить все синхронизации"
	@echo "  docs-update-index-apply - Обновить индексы с записью"
	@echo ""
	@echo "Мониторинг:"
	@echo "  check-env-consistency - Проверка согласованности окружений"
	@echo "  fix-black-quick   - Быстрое исправление проблемы с black"
	@echo "  fix-existing-venv - Исправление существующего venv"
	@echo "  remove-venv      - Удаление виртуального окружения"
	@echo ""
	@echo "Отладка:"
	@echo "  shell          - Открыть shell в backend контейнере"
	@echo "  db-shell       - Подключиться к базе данных"

# Сборка образов
build:
	cd docker && docker compose build

# Production-сборка frontend внутри контейнера (NODE_ENV=production обязателен)
build-frontend:
	docker compose --env-file .env -f docker/docker-compose.yml exec -T frontend sh -c "NODE_ENV=production npm run build"

# Запуск среды разработки
up:
	cd docker && docker compose up -d

# Остановка среды разработки
down:
	cd docker && docker compose down

# ВАЖНО: `--env-file` для docker-compose.test.yml не указывается намеренно. Файла docker/.env
# в репозитории нет (`.env` лежит в корне), и с ним все таргеты ниже падали на
# `couldn't find env file`. Он и не нужен: в docker-compose.test.yml нет ни одной подстановки
# переменных — имя проекта, пароли и порты 5433/6380 зашиты литералами. Побочная выгода:
# таргеты работают в worktree, где `.env` отсутствует.

# Все тесты
test:
	@echo "Запуск всех тестов..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down --remove-orphans --volumes
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from backend
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down

# Unit-тесты. `and not slow` — не случайность: цель зеркалит фильтр PR-гейтов
# (`backend-ci.yml`, `main.yml`, `deploy.yml` все исключают slow). Таймингозависимые
# тесты падают от загрузки машины, а не от дефекта, и гоняются целью test-slow.
test-unit:
	@echo "Запуск unit-тестов..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down --remove-orphans
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend pytest -v -m "unit and not slow" --cov=apps --cov-report=term-missing
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down

# Интеграционные тесты. `and not slow` — по той же причине, что и в test-unit.
# Сейчас под `integration and slow` не подпадает ни один тест; фильтр стоит ради
# симметрии, чтобы первый же помеченный slow интеграционный тест не влез в цель.
test-integration:
	@echo "Запуск интеграционных тестов..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down --remove-orphans
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend pytest -v -m "integration and not slow" --cov=apps --cov-report=term-missing
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down

# Перф-тесты (вне обычного гейта — медленные и шумные)
test-performance:
	@echo "Запуск перф-тестов..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down --remove-orphans
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend pytest -v -m performance
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down

# Медленные тесты (маркер slow, ставится вручную; в CI гоняются только nightly)
test-slow:
	@echo "Запуск медленных тестов..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down --remove-orphans
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend pytest -v -m slow
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml down

# Быстрые тесты (без сборки образов)
test-fast:
	@echo "Быстрый запуск тестов (без пересборки)..."
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend pytest -v --tb=short

# Логи всех сервисов
logs:
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml logs -f

# Shell в backend контейнере.
# `run --rm`, а не `exec`: у сервиса backend в docker-compose.test.yml команда по умолчанию —
# pytest, контейнер отрабатывает и выходит, а все test-таргеты завершаются `down`, поэтому
# подключаться `exec` обычно не к чему.
shell:
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm backend bash

# Подключение к тестовой БД. Учётные данные — из docker-compose.test.yml (postgres/freesport_test),
# а не из dev-окружения: прежние `-U freesport_user -d freesport` в тестовом контейнере не существуют.
db-shell:
	cd docker && docker compose -p freesport-test -f docker-compose.test.yml run --rm db psql -h db -U postgres -d freesport_test

# Очистка Docker volumes и неиспользуемых образов
clean:
	@echo "Очистка Docker volumes и образов..."
	cd docker && docker compose --env-file .env -f docker-compose.yml down --volumes --remove-orphans
	docker system prune -f
	docker volume prune -f

# Форматирование кода
format:
	docker compose --env-file .env -f docker-compose.yml exec backend black .
	docker compose --env-file .env -f docker-compose.yml exec backend isort .

# Быстрое форматирование через lightweight Docker
format-fast:
	docker build -f docker/Dockerfile.dev-tools -t freesport-dev-tools ../backend
	docker run --rm -v $(PWD)/backend:/app freesport-dev-tools black .
	docker run --rm -v $(PWD)/backend:/app freesport-dev-tools isort .

# Локальное форматирование (если venv доступно)
format-local:
	cd backend && venv/Scripts/black.exe .
	cd backend && venv/Scripts/isort.exe .

# Линтинг кода
lint:
	docker-compose exec backend flake8 .
	docker-compose exec backend mypy .

# Быстрый линтинг через lightweight Docker
lint-fast:
	docker build -f docker/Dockerfile.dev-tools -t freesport-dev-tools ../backend
	docker run --rm -v $(PWD)/backend:/app freesport-dev-tools flake8 .
	docker run --rm -v $(PWD)/backend:/app freesport-dev-tools mypy .

# Локальный линтинг (если venv доступно)
lint-local:
	cd backend && venv/Scripts/flake8.exe .
	cd backend && venv/Scripts/mypy.exe .

# Быстрое тестирование через lightweight Docker
test-fast-tools:
	docker build -f docker/Dockerfile.dev-tools -t freesport-dev-tools ../backend
	docker run --rm -v $(PWD)/backend:/app freesport-dev-tools pytest -v --tb=short

# Локальное тестирование (если venv доступно)
test-local:
	cd backend && venv/Scripts/pytest.exe -v --tb=short

# Миграции БД
migrate:
# Создание суперпользователя
createsuperuser:
	docker compose --env-file .env -f docker-compose.yml exec backend python manage.py createsuperuser

# Сбор статических файлов
collectstatic:
	docker compose --env-file .env -f docker-compose.yml exec backend python manage.py collectstatic --noinput

# Валидация документации
docs-validate:
	@echo "Валидация документации..."
	python "$(DOCS_SCRIPTS_DIR)/docs_validator.py" validate

# Поиск устаревших терминов
docs-search-obsolete:
	@echo "Поиск устаревших терминов..."
	python "$(DOCS_SCRIPTS_DIR)/docs_validator.py" obsolete

# Проверка кросс-ссылок
docs-check-links:
	@echo "Проверка кросс-ссылок..."
	python "$(DOCS_SCRIPTS_DIR)/docs_validator.py" cross-links

# Проверка покрытия API
docs-check-api:
	@echo "Проверка покрытия API..."
	python "$(DOCS_SCRIPTS_DIR)/docs_validator.py" api-coverage

# Обновление индекса документации
docs-update-index:
	@echo "Обновление индекса документации..."
	python "$(DOCS_SCRIPTS_DIR)/docs_index_generator.py"

# Синхронизация документации: API ↔ Views
docs-sync-api:
	@echo "Синхронизация API (код ↔ документация)..."
	python "$(DOCS_SCRIPTS_DIR)/docs_sync.py" api-sync

# Синхронизация документации: Decisions ↔ Код
docs-sync-decisions:
	@echo "Синхронизация решений (docs ↔ код)..."
	python "$(DOCS_SCRIPTS_DIR)/docs_sync.py" decisions-sync

# Синхронизация: все шаги
docs-sync-all:
	@echo "Полная синхронизация документации..."
	python "$(DOCS_SCRIPTS_DIR)/docs_sync.py" all

# Обновление индексов с применением изменений
docs-update-index-apply:
	@echo "Обновление индексов документации (apply)..."
	python "$(DOCS_SCRIPTS_DIR)/docs_sync.py" update-index --apply
# Проверка согласованности виртуальных окружений
check-env-consistency:
	@echo "Проверка согласованности виртуальных окружений..."
	powershell -ExecutionPolicy Bypass -File scripts/migration/check-env-consistency.ps1
# Быстрое исправление проблемы с black
fix-black-quick:
	@echo "Быстрое исправление проблемы с black..."
	powershell -ExecutionPolicy Bypass -File scripts/migration/fix-black-quick.ps1
# Исправление существующего виртуального окружения
fix-existing-venv:
	@echo "Исправление существующего виртуального окружения..."
	powershell -ExecutionPolicy Bypass -File scripts/migration/fix-existing-venv.ps1
# Удаление виртуального окружения
remove-venv:
	@echo "Удаление виртуального окружения с резервным копированием..."
	powershell -ExecutionPolicy Bypass -File scripts/migration/remove-venv.ps1
