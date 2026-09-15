/**
 * Тест-страж: список известных маршрутов верхнего уровня в middleware обязан
 * покрывать фактическую структуру `src/app`.
 *
 * Без этой сверки новая страница верхнего уровня, добавленная в `app/`, но не
 * внесённая в `KNOWN_TOP_LEVEL_ROUTES`, начнёт молча отдавать 404: middleware
 * посчитает её несуществующим адресом.
 *
 * Обратное включение не проверяется — в списке есть `electric-orange`, который
 * живёт не в `app/`, а в `public/` и обслуживается rewrite из `next.config.ts`.
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { KNOWN_TOP_LEVEL_ROUTES } from '../middleware';

const APP_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'app');

/** Имена файлов, которые App Router считает страницей сегмента */
const PAGE_FILES = ['page.tsx', 'page.ts', 'page.jsx', 'page.js', 'page.mdx'];

/** Группа маршрутов `(name)` — прозрачна для URL */
function isRouteGroup(name: string): boolean {
  return name.startsWith('(') && name.endsWith(')');
}

/**
 * Есть ли у сегмента собственная страница.
 *
 * Файл `page.tsx` может лежать не в самом каталоге сегмента, а в группе внутри
 * него: `app/oferta/(blue)/page.tsx` тоже даёт URL `/oferta`. Проверка только
 * `oferta/page.tsx` такой маршрут не замечала, и он молча начинал отдавать 404.
 */
function hasOwnPage(dir: string): boolean {
  if (PAGE_FILES.some(file => fs.existsSync(path.join(dir, file)))) return true;

  return fs
    .readdirSync(dir, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && isRouteGroup(entry.name))
    .some(entry => hasOwnPage(path.join(dir, entry.name)));
}

/**
 * Собирает односегментные публичные маршруты App Router.
 *
 * Каталоги-группы `(name)` прозрачны для URL, динамические `[param]` и
 * служебные (`_`, `@`) пропускаются. Сегмент считается маршрутом, если у него
 * есть собственная страница — своя или лежащая в группе внутри него.
 */
function collectTopLevelRoutes(dir: string): Set<string> {
  const routes = new Set<string>();

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;

    const name = entry.name;
    const full = path.join(dir, name);

    if (isRouteGroup(name)) {
      // Группа маршрутов: её содержимое остаётся на том же уровне URL
      for (const nested of collectTopLevelRoutes(full)) routes.add(nested);
      continue;
    }

    if (name.startsWith('[') || name.startsWith('_') || name.startsWith('@')) continue;

    if (hasOwnPage(full)) routes.add(name);
  }

  return routes;
}

describe('Список известных маршрутов верхнего уровня', () => {
  it('покрывает все односегментные страницы из src/app', () => {
    const actual = [...collectTopLevelRoutes(APP_DIR)].sort();
    const missing = actual.filter(route => !KNOWN_TOP_LEVEL_ROUTES.has(route));

    expect(missing).toEqual([]);
  });

  it('содержит electric-orange — rewrite на статику, а не страницу app/', () => {
    // Rewrites из next.config.ts выполняются ПОСЛЕ middleware, поэтому без
    // записи в списке рабочий адрес превратился бы в 404.
    expect(KNOWN_TOP_LEVEL_ROUTES.has('electric-orange')).toBe(true);
  });

  it('не содержит несуществующих маршрутов /product, /orders и /b2b-dashboard', () => {
    // У этих путей нет собственной страницы: /product существует только как
    // /product/[slug], а /orders и /b2b-dashboard перечислены в isProtectedRoute,
    // но страниц под них нет. Все три обязаны отдавать 404.
    expect(KNOWN_TOP_LEVEL_ROUTES.has('product')).toBe(false);
    expect(KNOWN_TOP_LEVEL_ROUTES.has('orders')).toBe(false);
    expect(KNOWN_TOP_LEVEL_ROUTES.has('b2b-dashboard')).toBe(false);
  });
});

describe('Сборщик маршрутов: раскрытие групп на любом уровне', () => {
  /** Создаёт временное дерево каталогов вида `src/app` */
  function makeFixture(layout: string[]): string {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), 'app-routes-'));

    for (const filePath of layout) {
      const full = path.join(root, filePath);
      fs.mkdirSync(path.dirname(full), { recursive: true });
      fs.writeFileSync(full, 'export default function Page() { return null; }');
    }

    return root;
  }

  it('видит маршрут, у которого page.tsx лежит в группе внутри сегмента', () => {
    // Реальный приём App Router: `app/oferta/(blue)/page.tsx` даёт URL /oferta.
    // Сборщик, проверяющий только `oferta/page.tsx`, такой маршрут не замечал —
    // и он молча начинал отдавать 404.
    const root = makeFixture(['oferta/(blue)/page.tsx']);

    try {
      expect(collectTopLevelRoutes(root)).toEqual(new Set(['oferta']));
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it('видит маршрут через две вложенные группы', () => {
    const root = makeFixture(['delivery/(blue)/(marketing)/page.tsx']);

    try {
      expect(collectTopLevelRoutes(root)).toEqual(new Set(['delivery']));
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });

  it('не считает маршрутом каталог, где page.tsx лежит глубже статического сегмента', () => {
    // `app/product/[slug]/page.tsx` даёт /product/xxx, но не /product.
    const root = makeFixture(['product/details/page.tsx']);

    try {
      expect(collectTopLevelRoutes(root)).toEqual(new Set());
    } finally {
      fs.rmSync(root, { recursive: true, force: true });
    }
  });
});
