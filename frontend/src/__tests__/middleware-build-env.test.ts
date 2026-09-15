/**
 * Тест-страж: адрес API для middleware доставляется в сборку ОТДЕЛЬНОЙ
 * переменной и не подменяет источник API остальному фронтенду.
 *
 * В edge-бандл middleware переменные подставляются на этапе сборки, и попадают
 * туда только `NEXT_PUBLIC_*`. Но подстановка на этапе сборки действует не
 * только на middleware: `process.env.NEXT_PUBLIC_*` инлайнится во весь код,
 * включая серверные компоненты. Поэтому build-arg `NEXT_PUBLIC_API_URL_INTERNAL`
 * переводил на внутренний `http://backend:8000` и страницы `/oferta`,
 * `/privacy-policy` — а они, в отличие от middleware, не отправляют
 * `X-Forwarded-Proto: https`, и при штатном `SECURE_SSL_REDIRECT=True` backend
 * уводил бы их запрос в `https://backend:8000`, где TLS нет.
 *
 * Отсюда контракт, который проверяется здесь: в образ фронта на этапе сборки
 * попадает только `NEXT_PUBLIC_MIDDLEWARE_API_URL`.
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const FRONTEND_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const REPO_ROOT = path.resolve(FRONTEND_DIR, '..');

const DOCKERFILE = path.join(FRONTEND_DIR, 'Dockerfile');
const PROD_COMPOSE = path.join(REPO_ROOT, 'docker', 'docker-compose.prod.yml');

/** Строки файла без комментариев — чтобы пояснения не подменяли собой факты */
function significantLines(file: string): string[] {
  return fs
    .readFileSync(file, 'utf-8')
    .split('\n')
    .filter(line => !line.trim().startsWith('#'));
}

describe('Сборка фронта: адрес API для middleware', () => {
  it('Dockerfile объявляет выделенную переменную до npm run build', () => {
    const lines = significantLines(DOCKERFILE);
    const argIndex = lines.findIndex(line => /^\s*ARG\s+NEXT_PUBLIC_MIDDLEWARE_API_URL/.test(line));
    const envIndex = lines.findIndex(line => /^\s*ENV\s+NEXT_PUBLIC_MIDDLEWARE_API_URL/.test(line));
    const buildIndex = lines.findIndex(line => /^\s*RUN\s+npm run build/.test(line));

    expect(argIndex).toBeGreaterThanOrEqual(0);
    expect(envIndex).toBeGreaterThanOrEqual(0);
    expect(buildIndex).toBeGreaterThanOrEqual(0);
    // После `npm run build` значение в бандл уже не попадёт
    expect(argIndex).toBeLessThan(buildIndex);
    expect(envIndex).toBeLessThan(buildIndex);
  });

  it('Dockerfile не подставляет общий NEXT_PUBLIC_API_URL_INTERNAL на этапе сборки', () => {
    const lines = significantLines(DOCKERFILE);

    expect(lines.some(line => /NEXT_PUBLIC_API_URL_INTERNAL/.test(line))).toBe(false);
  });

  it.skipIf(!fs.existsSync(PROD_COMPOSE))(
    'prod-compose передаёт в сборку только выделенную переменную',
    () => {
      const lines = significantLines(PROD_COMPOSE);
      const content = lines.join('\n');

      expect(content).toMatch(/NEXT_PUBLIC_MIDDLEWARE_API_URL:\s*http:\/\/backend:8000\/api\/v1/);
      expect(content).not.toMatch(/NEXT_PUBLIC_API_URL_INTERNAL/);
    }
  );
});
