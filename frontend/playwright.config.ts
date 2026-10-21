/**
 * Playwright E2E Test Configuration
 * Story 15.5: E2E тестирование упрощённого флоу checkout
 *
 * Конфигурация для E2E тестов на основе Playwright.
 * Поддерживает Chromium для основного тестирования.
 */

import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  // Папка с E2E тестами
  testDir: './tests/e2e',

  // Полностью параллельное выполнение тестов
  fullyParallel: true,

  // Запретить .only в CI
  forbidOnly: !!process.env.CI,

  // Повторы при сбоях в CI
  retries: process.env.CI ? 2 : 0,

  // Количество воркеров
  workers: process.env.CI ? 1 : undefined,

  // HTML отчёт
  reporter: [['html', { open: 'never' }], ['list']],

  // Глобальные настройки для всех тестов
  use: {
    // Базовый URL приложения
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',

    // Трассировка при первой попытке retry
    trace: 'on-first-retry',

    // Скриншоты при сбоях
    screenshot: 'only-on-failure',

    // Видео при сбоях (в CI)
    video: process.env.CI ? 'on-first-retry' : 'off',

    // Таймауты
    actionTimeout: 15000,
    // Увеличен timeout навигации из-за медленной компиляции Next.js в Docker
    navigationTimeout: 120000,
  },

  // Общий таймаут теста
  timeout: 150000,

  // Ожидание результата expect
  expect: {
    timeout: 10000,
  },

  // Проекты (браузеры)
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    // Firefox и WebKit опционально для CI
    // {
    //   name: 'firefox',
    //   use: { ...devices['Desktop Firefox'] },
    // },
    // {
    //   name: 'webkit',
    //   use: { ...devices['Desktop Safari'] },
    // },
  ],

  // Web server для локального тестирования
  // ВАЖНО: Frontend запущен в Docker контейнере
  // Используем reuseExistingServer: true для подключения к Docker контейнеру
  webServer: process.env.CI
    ? {
        command: 'npm run dev',
        url: 'http://localhost:3000',
        reuseExistingServer: false,
        timeout: 120000,
      }
    : undefined,
});
