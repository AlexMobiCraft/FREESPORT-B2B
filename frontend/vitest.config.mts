/**
 * Конфигурация Vitest для тестирования Next.js приложения
 */
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  css: {
    // Отключаем обработку CSS в тестах
    modules: {
      classNameStrategy: 'non-scoped',
    },
  },
  test: {
    // Глобальные API для describe, it, expect
    globals: true,

    // Среда выполнения тестов (happy-dom для производительности)
    environment: 'happy-dom',

    // Файлы настройки тестового окружения
    setupFiles: ['./vitest.setup.ts'],

    // Игнорировать CSS импорты в тестах
    css: false,

    // Паттерны для поиска тестовых файлов
    include: ['src/**/__tests__/**/*.{test,spec}.{ts,tsx}', 'src/**/*.{test,spec}.{ts,tsx}'],

    // Настройки покрытия кода
    coverage: {
      provider: 'v8',
      reporter: ['text', 'lcov', 'html'],
      exclude: [
        'node_modules/',
        '.next/',
        'coverage/',
        '**/*.d.ts',
        '**/*.config.*',
        '**/index.{ts,tsx}',
      ],
      thresholds: {
        functions: 65,
        lines: 65,
        branches: 65,
        statements: 65,
      },
    },
  },

  // Настройка alias для поддержки @ импортов
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
});
