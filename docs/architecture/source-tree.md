# Структура исходного кода

Этот документ описывает структуру каталогов и файлов проекта, их назначение и ключевые компоненты.

## Общая структура

```text
freesport/
│
├── .github/                    # Настройки GitHub Actions
│   └── workflows/              # CI/CD пайплайны
│       ├── backend-ci.yml      # CI для бэкенда
│       ├── frontend-ci.yml     # CI для фронтенда
│       └── main.yml            # Основной пайплайн (деплой)
│
├── backend/                    # Django бэкенд
│   ├── apps/                   # Django приложения
│   │   ├── banners/            # Баннеры Hero-секции
│   │   ├── cart/               # Корзина покупок
│   │   ├── common/             # Общие компоненты
│   │   ├── integrations/       # Интеграции с внешними системами
│   │   ├── orders/             # Заказы
│   │   ├── pages/              # Статические страницы
│   │   ├── products/           # Товары и каталог
│   │   └── users/              # Пользователи и аутентификация
│   ├── freesport/              # Основные настройки проекта
│   │   ├── settings/           # Настройки для разных окружений
│   │   ├── celery.py           # Конфигурация Celery
│   │   ├── urls.py             # Главный роутинг
│   │   ├── asgi.py             # ASGI конфигурация
│   │   └── wsgi.py             # WSGI конфигурация
│   ├── tests/                  # Каталог с тестами
│   │   ├── integration/        # Интеграционные тесты
│   │   │   └── test_management_commands/  # Тесты для management команд
│   │   └── fixtures/           # Фикстуры для тестов
│   ├── manage.py               # Утилита для управления Django
│   └── requirements.txt        # Зависимости Python
│
├── frontend/                   # Next.js фронтенд
│   ├── public/                 # Статические файлы
│   ├── src/                    # Исходный код фронтенда
│   │   ├── app/                # Страницы (Next.js App Router)
│   │   │   ├── news/           # Список новостей
│   │   │   │   └── [slug]/     # Детальная страница новости
│   │   │   ├── blog/           # Список статей блога
│   │   │   │   └── [slug]/     # Детальная страница статьи
│   │   ├── components/         # React компоненты
│   │   ├── hooks/              # Кастомные React хуки
│   │   ├── services/           # Сервисы для работы с API
│   │   ├── stores/             # State management
│   │   ├── types/              # TypeScript типы
│   │   ├── utils/              # Утилиты
│   │   ├── __mocks__/          # Моки для тестирования
│   │   └── __tests__/          # Тесты для компонентов и утилит
│   ├── package.json            # Зависимости Node.js
│   ├── tsconfig.json           # Конфигурация TypeScript
│   ├── next.config.ts          # Конфигурация Next.js
│   ├── vitest.config.mts       # Конфигурация Vitest
│   └── vitest.setup.ts         # Настройка окружения тестирования
│
├── docs/                       # Общая документация проекта
│   ├── architecture/           # Архитектурные решения
│   │   ├── ai-implementation/  # Детали реализации AI
│   │   ├── 01-introduction.md
│   │   ├── 02-data-models.md
│   │   ├── 03-api-specification.md
│   │   ├── 04-component-structure.md
│   │   ├── 05-tech-stack.md
│   │   ├── 06-system-architecture.md
│   │   ├── 07-integrations.md
│   │   ├── 08-workflows.md
│   │   ├── 09-database-schema.md
│   │   ├── 10-testing-strategy.md
│   │   ├── 11-security-performance.md
│   │   ├── 12-error-handling.md
│   │   ├── 13-monitoring.md
│   │   ├── 14-cicd-deployment.md
│   │   ├── 15-deployment-guide.md
│   │   ├── 16-ai-implementation-guide.md
│   │   ├── 17-performance-sla.md
│   │   ├── 18-b2b-verification-workflow.md
│   │   ├── 19-development-environment.md
│   │   ├── 20-1c-integration.md
│   │   ├── coding-standards.md
│   │   ├── documentation-update-plan.md
│   │   ├── index.md
│   │   ├── request-to-1c-developer.md
│   │   ├── source-tree.md
│   │   └── tech-stack.md
│   ├── database/               # Схемы и миграции БД
│   ├── decisions/              # ADR (Architecture Decision Records)
│   ├── epics/                  # Описание эпиков
│   ├── implementation/         # Детали реализации
│   ├── prd/                    # PRD и спецификации
│   ├── qa/                     # Документация по тестированию
│   ├── releases/               # Информация о релизах
│   ├── stories/                # User Stories
│   ├── arhiv/                  # Архивные документы
│   ├── fixes/                   # Исправления ошибок и багов
│   ├── guides/                  # Руководства и инструкции
│   ├── ci-cd/                  # CI/CD документация
│   ├── deploy/                  # Документация по развертыванию
│   └── frontend/               # Документация по фронтенду
│
├── scripts/                    # Скрипты автоматизации
│   ├── docs/                   # Скрипты для работы с документацией
│   ├── inport_from_1C/         # Скрипты импорта из 1С
│   ├── server/                  # Скрипты для работы с сервером
│   └── tests/                   # Скрипты для тестирования
│
├── docker/                     # Docker конфигурации
│   ├── docker-compose.dev.yml    # Конфигурация Docker Compose (разработка)
│   ├── docker-compose.prod.yml   # Конфигурация Docker Compose (production)
│   ├── docker-compose.test.yml   # Конфигурация Docker Compose (тестирование)
│   ├── docker-compose.yml        # Основная конфигурация Docker Compose
│   ├── Dockerfile.dev           # Dockerfile для разработки
│   ├── Dockerfile.prod          # Dockerfile для production
│   ├── Dockerfile.test          # Dockerfile для тестирования
│   ├── nginx/                  # Конфигурация Nginx
│   └── pg_hba.conf             # Конфигурация PostgreSQL
│
├── .bmad-core/                 # BMad методология
│   ├── agents/                 # Определения агентов
│   ├── agent-teams/            # Команды агентов
│   ├── checklists/             # Чек-листы
│   └── data/                   # Данные методологии
│
├── .windsurf/                  # Windsurf workflows
│   └── workflows/              # Рабочие процессы
│
├── web-bundles/                 # Web-бандлы
│   └── agents/                 # Определения агентов
│
├── .kilocode/                  # Kilo Code конфигурация
│   └── rules/                  # Правила и Memory Bank
│
├── .husky/                     # Git hooks
│
├── .claude/                     # Claude AI конфигурация
│
├── .gemini/                     # Gemini AI конфигурация
│
├── data/                       # Данные для импорта
│
├── docker-compose.yml          # Конфигурация Docker Compose
├── docker-compose.test.yml     # Конфигурация Docker Compose (тесты)
├── Makefile                    # Команды для управления проектом
├── README.md                   # Основная информация о проекте
├── pyrightconfig.json          # Конфигурация Pyright
├── pytest.ini                  # Конфигурация pytest
├── .coverage                    # Отчеты о покрытии кода тестами
├── coverage.xml                 # XML отчеты о покрытии кода
├── import_full.log              # Лог импорта
├── import_verbose.log           # Детальный лог импорта
├── .env                        # Переменные окружения
├── .env.example                 # Пример переменных окружения
├── .env.prod                    # Переменные окружения для production
├── .env.prod.example             # Пример переменных окружения для production
├── codebase.xml                 # XML представление кодовой базы
├── CLAUDE.md                   # Инструкции для Claude AI
├── GEMINI.md                   # Инструкции для Gemini AI
└── .gitignore                  # Файлы, исключенные из Git
```

## Ключевые каталоги

### `backend/`

Бэкенд, построенный на Django. Содержит всю серверную логику, API и управление базой данных.

- **`apps/`**: Модульная структура, где каждое приложение отвечает за свою бизнес-логику:
  - `banners/` — управление баннерами Hero-секции
  - `users/` — пользователи и аутентификация
  - `products/` — товары и каталог
    - `services/` — сервисы для импорта и обработки данных (parser.py, processor.py)
    - `management/commands/` — Django management команды для импорта данных
  - `orders/` — заказы
  - `cart/` — корзина покупок
  - `common/` — общие компоненты
  - `pages/` — статические страницы
- **`backend/`**: Устаревшая папка с настройками (используется `freesport/`).
- **`freesport/`**: Ядро Django-проекта с основными настройками (`settings/`, `urls.py`, `asgi.py`, `wsgi.py`).
- **`tests/`**: Набор тестов для проверки корректности работы API и бизнес-логики:
  - `unit/` — юнит-тесты
  - `integration/` — интеграционные тесты
    - `test_management_commands/` — тесты для management команд
  - `functional/` — функциональные тесты
  - `performance/` — тесты производительности
  - `legacy/` — устаревшие тесты
  - `fixtures/` — фикстуры для тестов

### `frontend/`

Фронтенд, построенный на Next.js. Отвечает за пользовательский интерфейс и взаимодействие с API.

- **`src/app/`**: Страницы приложения (Next.js App Router).
- **`src/components/`**: Переиспользуемые UI-компоненты (кнопки, формы, карточки товаров).
- **`src/services/`**: Сервисы для работы с API.
  - `newsService.ts` — сервис для получения новостей.
  - `blogService.ts` — сервис для работы с блогом.
- **`src/stores/`**: Хранилища состояния (state management).
- **`src/types/`**: TypeScript типы и интерфейсы.
- **`src/hooks/`**: Кастомные React хуки.
- **`src/utils/`**: Утилиты для общих функций.
- **`src/__mocks__/`**: Моки для тестирования.
- **`src/__tests__/`**: Тесты для компонентов и утилит.

### `docs/`

Централизованное хранилище всей документации проекта.

- **`architecture/`**: Описание архитектуры, включая:
  - Нумерованные документы (01-20): введение, модели данных, API, компоненты, tech stack, архитектура системы, интеграции, workflows, БД, тестирование, безопасность, обработка ошибок, мониторинг, CI/CD, деплой, AI, производительность, B2B, окружение разработки, интеграция с 1C
  - `ai-implementation/` — детали реализации AI-функционала
  - Дополнительные документы: coding standards, tech stack, source tree, index и др.
- **`database/`**: ER-диаграммы, описание моделей данных.
- **`decisions/`**: Записи о принятых архитектурных решениях (ADR).
- **`epics/`**: Описание эпиков.
- **`stories/`**: User Stories.
- **`implementation/`**: Детали реализации.
- **`releases/`**: Информация о релизах.
- **`prd/`**: Product Requirements Documents.
- **`qa/`**: Документация по тестированию.
- **`arhiv/`**: Архивные документы.
- **`fixes/`**: Исправления ошибок и багов.
- **`guides/`**: Руководства и инструкции.
- **`ci-cd/`**: CI/CD документация.
- **`deploy/`**: Документация по развертыванию.
- **`frontend/`**: Документация по фронтенду.
- Корневые файлы: `Brief.md`, `PRD.md`, `api-spec.yaml`, `api-views-documentation.md`, `brownfield-architecture.md`, `architecture.md`, `docker-configuration.md`, `front-end-spec.md`, `index.md`, `test-catalog-api.md`, `testing-docker.md` и др.

### `scripts/`

Скрипты для автоматизации рутинных задач. Все скрипты написаны на PowerShell (`.ps1`):

- **`docs/`**: Скрипты для работы с документацией.
  - `docs_index_generator.py` — генератор индекса документации.
  - `docs_link_checker.py` — проверка ссылок в документации.
  - `docs_sync.py` — синхронизация документации.
  - `docs_validator.py` — валидация документации.
  - `README.md` — описание скриптов для документации.
- **`inport_from_1C/`**: Скрипты импорта из 1С.
  - `run_catalog_import_with_backup.ps1` — запуск импорта каталога с созданием резервной копии.
  - `run_catalog_import.ps1` — запуск импорта каталога.
  - `README_SERVER_SYNC.md` — описание синхронизации с сервером.
  - `README.md` — описание скриптов импорта из 1С.
- **`server/`**: Скрипты для работы с сервером.
  - `create-ssl-certs.ps1` — создание SSL сертификатов.
  - `create-ssl-certs.sh` — создание SSL сертификатов.
  - `diagnose-server.sh` — диагностика сервера.
  - `import_catalog_on_server.ps1` — импорт каталога на сервере.
  - `README.md` — описание серверных скриптов.
  - `setup_ssh.ps1` — настройка SSH.
  - `ssh_server.ps1` — подключение к серверу по SSH.
  - `sync_import_data.ps1` — синхронизация данных импорта.
  - `update_server_code.ps1` — обновление кода на сервере.
- **`tests/`**: Скрипты для тестирования.
  - `run-integration-tests.ps1` — запуск интеграционных тестов.
  - `run-story-3-1-2-tests.ps1` — запуск тестов для story 3.1.2.
  - `run-tests-docker-local.ps1` — запуск тестов в Docker локально.
  - `run-tests-interactive.ps1` — запуск тестов в интерактивном режиме.
  - `README.md` — описание скриптов тестирования.

### `.github/workflows/`

Определение пайплайнов CI/CD для автоматической сборки, тестирования и развертывания приложения:

- **`backend-ci.yml`**: CI пайплайн для бэкенда — линтинг (flake8), type checking (mypy), security checks (bandit), запуск тестов с PostgreSQL и Redis.
- **`frontend-ci.yml`**: CI пайплайн для фронтенда — линтинг (ESLint), type checking (TypeScript), сборка проекта, запуск тестов.
- **`main.yml`**: Основной пайплайн — комплексная проверка всего проекта, включая бэкенд и фронтенд.

### `docker/`

Дополнительные конфигурации для Docker:

- **`nginx/`**: Конфигурационные файлы Nginx для production окружения.
- **`docker-compose.dev.yml`**: Конфигурация Docker Compose для разработки.
- **`docker-compose.prod.yml`**: Конфигурация Docker Compose для production.
- **`docker-compose.test.yml`**: Конфигурация Docker Compose для тестирования.
- **`docker-compose.yml`**: Основная конфигурация Docker Compose.
- **`Dockerfile.dev`**: Dockerfile для разработки.
- **`Dockerfile.prod`**: Dockerfile для production.
- **`Dockerfile.test`**: Dockerfile для тестирования.
- **`nginx/`**: Конфигурационные файлы Nginx для production окружения.
- **`pg_hba.conf`**: Конфигурация PostgreSQL для аутентификации.

### `.bmad-core/`

Файлы методологии BMad (Business Model Analysis and Design) для управления проектом:

- **`agents/`**: Определения агентов (analyst, architect, dev, pm, po, qa, sm, ux-expert и др.) — 10 файлов.
- **`agent-teams/`**: Конфигурации команд агентов для различных задач — 4 файла.
- **`checklists/`**: Чек-листы для различных процессов (architect, change, pm и др.) — 6 файлов.
- **`data/`**: Базы знаний и методологические материалы — 6 файлов.

### `.windsurf/`

Workflows для Windsurf IDE:

- **`workflows/`**: Рабочие процессы (analyst, architect, bmad-master, dev, docs-workflow, pm, po, qa, sm, ux-expert и др.) — 11 файлов.

## Дополнительные файлы

### Корневые конфигурационные файлы

- **`Makefile`**: Команды для управления проектом (запуск, тестирование, деплой).
- **`docker-compose.yml`**: Конфигурация для production окружения.
- **`docker-compose.test.yml`**: Конфигурация для тестового окружения.
- **`pyrightconfig.json`**: Настройки type checker для Python.
- **`pytest.ini`**: Конфигурация pytest для запуска тестов.
- **`CLAUDE.md`**, **`GEMINI.md`**: Инструкции для AI-ассистентов.
- **`COMMIT_INSTRUCTIONS.md`**: Правила оформления коммитов.
