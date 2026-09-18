# FREESPORT Frontend

[![Frontend CI/CD](https://github.com/AlexMobiCraft/FREESPORT/actions/workflows/frontend-ci.yml/badge.svg)](https://github.com/AlexMobiCraft/FREESPORT/actions/workflows/frontend-ci.yml)

Next.js 15.4.6 фронтенд для платформы FREESPORT, построенный с использованием React 19, TypeScript и Tailwind CSS.

## Технологический стек

- **Next.js 15.4.6** - React фреймворк с App Router
- **React 19.1.0** - UI библиотека
- **TypeScript 5.0+** - строгая типизация
- **Tailwind CSS 4.0** - utility-first CSS
- **Zustand 4.5.7** - управление состоянием
- **Axios 1.11.0** - HTTP клиент
- **React Hook Form 7.62.0** - управление формами

## Требования

- Node.js >= 18 LTS
- Docker и Docker Compose (для запуска через контейнеры)
- npm >= 9

## Быстрый старт

### Запуск через Docker (рекомендуется)

```bash
# Из корня проекта
cd ..
docker compose --env-file .env -f docker/docker-compose.yml up frontend
```

Фронтенд будет доступен на `http://localhost:3000`.

### Локальная разработка

```bash
# Установка зависимостей
npm install

# Создание .env.local (если не существует)
cp .env.example .env.local

# Запуск dev сервера
npm run dev
```

Откройте [http://localhost:3000](http://localhost:3000) в браузере.

## Первоначальная настройка

После первого клонирования репозитория выполните установку зависимостей, чтобы Husky автоматически создал git hook'и через скрипт `prepare`.

```bash
cd frontend
npm install
```

При необходимости повторите шаг после обновления зависимостей. Проверить наличие hook'ов можно командой `npx husky list`.

## Доступные команды

### Разработка

```bash
npm run dev          # Запуск dev сервера с Turbopack
npm run build        # Сборка для продакшена
npm run start        # Запуск продакшен сборки
```

### Качество кода

```bash
npm run lint         # Проверка ESLint
npm run lint:fix     # Исправление ошибок ESLint
npm run format       # Форматирование кода Prettier
npm run format:check # Проверка форматирования
```

### Тестирование

```bash
npm test              # Запуск всех тестов (Vitest)
npm run test:watch    # Тесты в watch режиме
npm run test:coverage # Тесты с покрытием кода
npm run test:ui       # Vitest UI для визуальной отладки
```

**Технологии тестирования:**

- Vitest 2.1.5 - современный тестовый раннер с ESM support
- MSW v2 - мокирование API запросов
- React Testing Library - тестирование компонентов
- Happy-DOM - быстрая DOM environment

**Подробнее:** См. [docs/testing-standards.md](docs/testing-standards.md) и [docs/vitest-troubleshooting.md](docs/vitest-troubleshooting.md)

### E2E Тестирование (Playwright)

```bash
npm run test:e2e              # Запуск всех E2E тестов
npm run test:e2e:headed       # С визуальным браузером
npm run test:e2e:debug        # Режим отладки (шаг за шагом)
npm run test:e2e:report       # Открыть HTML отчёт
```

**Технологии E2E:**

- Playwright - современный фреймворк для E2E тестирования
- Chromium - основной браузер для тестов
- Page Object Model - паттерн для организации тестов

**Структура E2E тестов:**

```plaintext
tests/
└── e2e/
    ├── checkout.spec.ts      # E2E тесты checkout флоу
    └── pages/
        └── CheckoutPage.ts   # Page Object для checkout
```

**Запуск конкретного теста:**

```bash
npm run test:e2e -- --grep "complete checkout flow"
npm run test:e2e -- tests/e2e/checkout.spec.ts
```

**Отладка тестов:**

```bash
# Режим отладки с Playwright Inspector
npm run test:e2e:debug

# Запуск с трассировкой
npm run test:e2e -- --trace on
```

**CI/CD:** E2E тесты автоматически запускаются через GitHub Actions при push/PR в develop и main. См. `.github/workflows/e2e-tests.yml`.

## Переменные окружения

Создайте файл `.env.local` на основе `.env.example`:

```bash
# API Configuration
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
NEXT_PUBLIC_API_TIMEOUT=30000

# Environment
NODE_ENV=development

# Next.js Configuration
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Структура проекта

```plaintext
frontend/
├── src/
│   ├── app/              # Страницы (Next.js App Router)
│   ├── components/       # React компоненты
│   │   └── ui/          # UI Kit компоненты
│   ├── hooks/           # Кастомные React хуки
│   ├── services/        # API сервисы
│   ├── stores/          # Zustand stores
│   └── types/           # TypeScript типы
├── public/              # Статические файлы
├── __tests__/           # Тесты
├── .prettierrc          # Prettier конфигурация
├── eslint.config.mjs    # ESLint конфигурация
├── jest.config.js       # Jest конфигурация
└── next.config.ts       # Next.js конфигурация
```

## Стандарты кодирования

### ESLint

- Используется `eslint-config-next` с правилами для TypeScript
- Плагины: `react-hooks`, `jsx-a11y` (WCAG 2.1 AA)
- Максимум 0 предупреждений при сборке

### Prettier

- Single quotes
- 2 spaces отступ
- Semicolons обязательны
- Trailing commas (ES5)
- 100 символов максимальная длина строки

### Pre-commit hooks

Используется `husky` + `lint-staged` для автоматической проверки перед коммитом:

- ESLint с автоисправлением
- Prettier форматирование

## Docker

### Development

```bash
# Запуск frontend сервиса
docker compose --env-file .env -f docker/docker-compose.yml up frontend

# Просмотр логов
docker compose --env-file .env -f docker/docker-compose.yml logs -f frontend

# Остановка
docker compose --env-file .env -f docker/docker-compose.yml down
```

### Production

```bash
# Сборка образа
docker build -t freesport-frontend .

# Запуск контейнера
docker run -p 3000:3000 freesport-frontend
```

## Hot Reload

При запуске через Docker hot-reload работает благодаря volume mounting:

```yaml
volumes:
  - ../frontend:/app
  - /app/node_modules
  - /app/.next
```

Изменения в `src/` автоматически перезагружают страницу.

## Troubleshooting

### Порт 3000 занят

```bash
# Windows
netstat -ano | findstr :3000
taskkill /PID <PID> /F

# Linux/macOS
lsof -ti:3000 | xargs kill -9
```

### Node modules конфликты

```bash
rm -rf node_modules package-lock.json
npm install
```

### Docker build ошибки

```bash
# Очистка Docker кеша
docker system prune -a

# Пересборка без кеша
docker compose --env-file .env -f docker/docker-compose.yml build --no-cache frontend
```

## CI/CD

GitHub Actions автоматически:

- Запускает ESLint и Prettier проверки
- Выполняет тесты с покрытием
- Проверяет TypeScript типы
- Собирает production build
- Публикует Docker образ в GHCR

См. `.github/workflows/frontend-ci.yml` для деталей.

## Документация

- [Next.js Documentation](https://nextjs.org/docs)
- [React Documentation](https://react.dev)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [Tailwind CSS](https://tailwindcss.com/docs)
- [Zustand](https://docs.pmnd.rs/zustand/getting-started/introduction)
