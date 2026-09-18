/**
 * Story 41.21 (code review) — чистые функции гейта production-сборки
 * `scripts/check-production-build.mjs`. Сам гейт исполняется в CI после
 * `npm run build`; здесь закреплено, из чего он собирает состав чанков и как
 * читает теги robots, — ошибка в этих функциях дала бы ложный зелёный.
 */
import { describe, expect, it } from 'vitest';
import {
  chunkRefsFromHtml,
  chunksForPage,
  matchContext,
  middlewareApiBase,
  robotsMetaContents,
  selectPublicPages,
  FORBIDDEN_IN_PUBLIC_CHUNKS,
} from '../../scripts/check-production-build.mjs';

const APP_PAGES: Record<string, string[]> = {
  '/layout': ['static/chunks/root-layout.js', 'static/css/app.css'],
  '/not-found': ['static/chunks/root-not-found.js'],
  '/(blue)/layout': ['static/chunks/blue-layout.js'],
  '/(blue)/home/page': ['static/chunks/home-page.js'],
  '/(blue)/product/[slug]/loading': ['static/chunks/product-loading.js'],
  '/(blue)/product/[slug]/page': ['static/chunks/product-page.js'],
  '/(blue)/profile/layout': ['static/chunks/profile-layout.js'],
  '/(blue)/profile/orders/[id]/page': ['static/chunks/jspdf.js'],
  '/(electric)/layout': ['static/chunks/electric-layout.js'],
};

describe('selectPublicPages', () => {
  it('берёт страницы и исключает только /profile (решение Q1)', () => {
    expect(selectPublicPages(Object.keys(APP_PAGES))).toEqual([
      '/(blue)/home/page',
      '/(blue)/product/[slug]/page',
    ]);
  });
});

describe('chunksForPage', () => {
  it('добавляет чанки layout-ов всех предков и полифилы, без CSS', () => {
    expect(chunksForPage('/(blue)/home/page', APP_PAGES, ['static/chunks/polyfills.js'])).toEqual([
      'static/chunks/blue-layout.js',
      'static/chunks/home-page.js',
      'static/chunks/polyfills.js',
      'static/chunks/root-layout.js',
      'static/chunks/root-not-found.js',
    ]);
  });

  it('берёт записи своего сегмента (loading), но не соседних разделов', () => {
    const chunks = chunksForPage('/(blue)/product/[slug]/page', APP_PAGES, []);

    expect(chunks).toContain('static/chunks/product-loading.js');
    expect(chunks).not.toContain('static/chunks/profile-layout.js');
    expect(chunks).not.toContain('static/chunks/electric-layout.js');
    expect(chunks).not.toContain('static/chunks/home-page.js');
  });
});

describe('chunkRefsFromHtml', () => {
  it('берёт чанки из <script src> и экранированных RSC-данных, декодирует [slug]', () => {
    const html =
      '<script src="/_next/static/chunks/6110-abc.js" async=""></script>' +
      '<script>self.__next_f.push([1,"3:I[\\"static/chunks/app/(blue)/%5Bslug%5D/page-1.js\\"]"])</script>' +
      '<script src="/_next/static/chunks/6110-abc.js"></script>' +
      '<link rel="preload" href="/_next/static/chunks/data.json"/>';

    expect(chunkRefsFromHtml(html)).toEqual([
      'static/chunks/6110-abc.js',
      'static/chunks/app/(blue)/[slug]/page-1.js',
    ]);
  });
});

describe('matchContext', () => {
  it('находит example без учёта регистра и возвращает окрестность', () => {
    const text = 'aaa [zustand devtools middleware] Example: { "type": "__setState" } bbb';

    expect(matchContext(text, FORBIDDEN_IN_PUBLIC_CHUNKS)).toContain('Example: {');
    expect(matchContext('чисто', FORBIDDEN_IN_PUBLIC_CHUNKS)).toBeNull();
  });
});

describe('robotsMetaContents', () => {
  it('возвращает все теги robots — два тега видны как два', () => {
    const html =
      '<meta name="robots" content="noindex"/><meta name="description" content="x"/>' +
      '<meta name="robots" content="noindex, nofollow"/>';

    expect(robotsMetaContents(html)).toEqual(['noindex', 'noindex, nofollow']);
  });

  it('не зависит от порядка атрибутов и не путает googlebot с robots', () => {
    const html = '<meta content="noindex, follow" name="robots"><meta name="googlebot" content="x">';

    expect(robotsMetaContents(html)).toEqual(['noindex, follow']);
  });
});

describe('middlewareApiBase', () => {
  it('повторяет приоритет getApiBaseUrl из middleware и срезает слэш', () => {
    expect(
      middlewareApiBase({
        NEXT_PUBLIC_MIDDLEWARE_API_URL: 'http://localhost:1/api/v1/',
        NEXT_PUBLIC_API_URL: 'http://localhost:2/api/v1',
      })
    ).toBe('http://localhost:1/api/v1');
    expect(middlewareApiBase({ NEXT_PUBLIC_API_URL: 'http://localhost:2/api/v1' })).toBe(
      'http://localhost:2/api/v1'
    );
    expect(middlewareApiBase({})).toBe('');
  });
});
