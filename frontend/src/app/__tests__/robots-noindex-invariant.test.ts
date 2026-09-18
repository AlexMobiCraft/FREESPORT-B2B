/**
 * Инвариант D4 (стори 41.18, AC5): у адреса один механизм исключения из индекса.
 *
 * - Адрес под `Disallow` в robots.txt не несёт meta `noindex`: робот, соблюдающий
 *   robots.txt, страницу не запрашивает и тег не прочитает, а сканер аудита видит
 *   противоречивые сигналы.
 * - Ни один адрес из sitemap не закрыт `Disallow`.
 * - `noindex` вне `Disallow` сохраняется: 404, `/unsubscribe`, условный `noindex`
 *   неопубликованных карточек и CMS-страниц.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import robots from '../robots';
import sitemap from '../sitemap';

vi.mock('@/components/cart', () => ({ CartPage: () => null }));
vi.mock('../(blue)/checkout/CheckoutPageClient', () => ({ CheckoutPageClient: () => null }));
vi.mock('@/components/business/SearchPageClient', () => ({ SearchPageClient: () => null }));
vi.mock('../(blue)/unsubscribe/UnsubscribeClient', () => ({ default: () => null }));

const APP_DIR = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

/** Файлы, которые App Router считает страницей или layout сегмента */
const ROUTE_FILES = new Set(
  ['page', 'layout'].flatMap(base => ['tsx', 'ts', 'jsx', 'js', 'mdx'].map(ext => `${base}.${ext}`))
);

type Rule = { userAgent?: string | string[]; disallow?: string | string[] };

function getDisallow(): string[] {
  const { rules } = robots();
  const list = (Array.isArray(rules) ? rules : [rules]) as Rule[];
  return list.flatMap(({ disallow }) =>
    Array.isArray(disallow) ? disallow : disallow ? [disallow] : []
  );
}

/** Семантика `Disallow` без `*` и `$` — чистый префикс пути. */
function isDisallowed(pathname: string, rules: string[]): boolean {
  return rules.some(rule => pathname.startsWith(rule));
}

type RouteFile = { file: string; prefix: string };

/**
 * Обходит `src/app` и возвращает route-файлы со статическим URL-префиксом.
 * Группы `(x)` прозрачны; на первом динамическом сегменте `[x]` префикс
 * фиксируется, но обход продолжается — файлы глубже наследуют тот же префикс.
 */
function collectRouteFiles(dir: string, segments: string[], frozen: boolean): RouteFile[] {
  const result: RouteFile[] = [];

  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);

    if (entry.isFile()) {
      if (ROUTE_FILES.has(entry.name)) {
        result.push({
          file: path.relative(APP_DIR, full).split(path.sep).join('/'),
          prefix: `/${segments.join('/')}`,
        });
      }
      continue;
    }

    const name = entry.name;
    if (name === '__tests__' || name.startsWith('_') || name.startsWith('@')) continue;

    if (name.startsWith('(') && name.endsWith(')')) {
      result.push(...collectRouteFiles(full, segments, frozen));
    } else if (frozen || name.startsWith('[')) {
      result.push(...collectRouteFiles(full, segments, true));
    } else {
      result.push(...collectRouteFiles(full, [...segments, name], false));
    }
  }

  return result;
}

/** Исходник без комментариев: в них встречается «noIndex не ставится». */
function stripComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/.*$/gm, '$1');
}

const NOINDEX_PATTERNS = [
  /noIndex\s*:\s*true/,
  /\bindex\s*:\s*false/,
  /(['"`])[^'"`\n]*noindex[^'"`\n]*\1/i,
];

function carriesNoindex(file: string): boolean {
  const source = stripComments(fs.readFileSync(path.join(APP_DIR, file), 'utf-8'));
  return NOINDEX_PATTERNS.some(pattern => pattern.test(source));
}

describe('Инвариант D4: адрес под Disallow не несёт meta noindex', () => {
  const rules = getDisallow();

  it('правила Disallow — чистые префиксы (без * и $), сравнение startsWith корректно', () => {
    expect(rules.length).toBeGreaterThan(0);
    for (const rule of rules) {
      expect(rule).not.toMatch(/[*$]/);
    }
  });

  describe('(а) скан дерева src/app', () => {
    const routeFiles = collectRouteFiles(APP_DIR, [], false);
    const disallowed = routeFiles.filter(({ prefix }) => isDisallowed(prefix, rules));
    // Layout-предок адреса под Disallow отдаёт свои метаданные и ему
    const ancestorLayouts = routeFiles.filter(
      ({ file, prefix }) =>
        /(^|\/)layout\.[jt]sx?$/.test(file) &&
        !isDisallowed(prefix, rules) &&
        rules.some(rule => rule.startsWith(prefix === '/' ? '/' : `${prefix}/`))
    );

    it('выборка не пуста: в неё попали известные страницы под Disallow', () => {
      const files = disallowed.map(({ file }) => file);
      for (const expected of [
        '(blue)/cart/page.tsx',
        '(blue)/checkout/page.tsx',
        '(blue)/(auth)/login/layout.tsx',
        '(blue)/search/page.tsx',
        '(blue)/profile/layout.tsx',
        '(electric)/electric/page.tsx',
        '(coming-soon)/coming-soon/page.tsx',
      ]) {
        expect(files).toContain(expected);
      }
    });

    it('catch-all (blue)/[slug] не считается адресом под Disallow', () => {
      expect(disallowed.map(({ file }) => file)).not.toContain('(blue)/[slug]/page.tsx');
    });

    it('ни один route-файл под Disallow не задаёт noindex', () => {
      const offenders = disallowed.filter(({ file }) => carriesNoindex(file)).map(f => f.file);
      expect(offenders).toEqual([]);
    });

    it('layout-предки адресов под Disallow не задают noindex', () => {
      expect(ancestorLayouts.map(({ file }) => file)).toContain('layout.tsx');
      const offenders = ancestorLayouts.filter(({ file }) => carriesNoindex(file)).map(f => f.file);
      expect(offenders).toEqual([]);
    });
  });

  describe('(б) метаданные четырёх страниц из AC5', () => {
    it('/cart — robots не задан', async () => {
      const { metadata } = await import('../(blue)/cart/page');
      expect(metadata.robots).toBeUndefined();
    });

    it('/checkout — robots не задан', async () => {
      const { metadata } = await import('../(blue)/checkout/page');
      expect(metadata.robots).toBeUndefined();
    });

    it('/login — robots не задан', async () => {
      const { metadata } = await import('../(blue)/(auth)/login/layout');
      expect(metadata.robots).toBeUndefined();
    });

    it('/search — robots не задан', async () => {
      const { generateMetadata } = await import('../(blue)/search/page');
      const metadata = await generateMetadata({ searchParams: Promise.resolve({ q: 'мяч' }) });
      expect(metadata.robots).toBeUndefined();
    });
  });
});

describe('Инвариант D4: ни один адрес sitemap не закрыт Disallow', () => {
  const response = (body: unknown) =>
    ({ ok: true, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

  beforeEach(() => {
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('по одному элементу каждого типа: товар, статья, новость, CMS-страница, категория', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        const one = (slug: string) => Promise.resolve(response({ results: [{ slug }], next: null }));
        if (url.includes('/categories-tree/')) {
          return Promise.resolve(response([{ slug: 'games', children: [] }]));
        }
        if (url.includes('/products/')) return one('ball');
        if (url.includes('/blog/')) return one('post');
        if (url.includes('/news/')) return one('item');
        if (url.includes('/pages/')) return one('oferta');
        return Promise.resolve(response({ results: [], next: null }));
      })
    );

    const pathnames = (await sitemap()).map(entry => new URL(entry.url).pathname);
    expect(pathnames).toEqual(
      expect.arrayContaining([
        '/home',
        '/catalog',
        '/product/ball',
        '/blog/post',
        '/news/item',
        '/oferta',
      ])
    );
    expect(pathnames.filter(pathname => isDisallowed(pathname, getDisallow()))).toEqual([]);
  });

  it('статические маршруты при недоступном API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.reject(new Error('network')))
    );

    const pathnames = (await sitemap()).map(entry => new URL(entry.url).pathname);
    expect(pathnames).toContain('/home');
    expect(pathnames.filter(pathname => isDisallowed(pathname, getDisallow()))).toEqual([]);
  });
});

describe('Инвариант D4: noindex вне Disallow сохранён', () => {
  // Стори 41.21, AC7: `noindex` на ответ 404 ставит сам Next (`app-render.js`,
  // условие `is404Page`). Собственный `robots` давал второй тег `noindex, nofollow`.
  // Итоговый HTML (настоящий 404, ровно один `noindex`; soft-404 — 200 и один
  // `noindex, follow`) проверяет на собранном приложении
  // `scripts/check-production-build.mjs robots` — шаг CI после `npm run build`.
  it('404 — robots не задан, noindex ставит Next', async () => {
    const { metadata } = await import('../not-found');
    expect(metadata.robots).toBeUndefined();
  });

  it('/unsubscribe — noindex, nofollow', async () => {
    const { metadata } = await import('../(blue)/unsubscribe/page');
    expect(metadata.robots).toEqual({ index: false, follow: false });
  });

  // Поведение закреплено тестом страницы (есть у [slug]), здесь — страж от удаления
  it.each([
    '(blue)/product/[slug]/page.tsx',
    '(blue)/blog/[slug]/page.tsx',
    '(blue)/news/[slug]/page.tsx',
    '(blue)/[slug]/page.tsx',
  ])('%s сохраняет условный noindex', file => {
    const source = stripComments(fs.readFileSync(path.join(APP_DIR, file), 'utf-8'));
    expect(source).toMatch(/robots:\s*\{\s*index:\s*false,\s*follow:\s*true\s*\}/);
  });
});
