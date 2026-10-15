/**
 * Тесты метаданных catch-all страницы CMS `(blue)/[slug]`.
 *
 * Доказательство второй половины AC2 стори 41.0: middleware пропускает
 * опубликованный slug дальше (это проверяет `middleware.test.ts`), а здесь
 * проверяется, что пропущенный запрос действительно получает нормальные
 * метаданные через `buildMetadata` и БЕЗ `noindex`. Обратная ветка — страховка
 * на случай fail-open и гонки «slug ещё в списке, но страница уже снята»: она
 * обязана оставаться закрытой от индексации.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { buildMetadata } from '@/utils/seo';

const publishedPage = {
  id: 1,
  title: 'Публичная оферта',
  slug: 'oferta',
  content: '<p>Текст оферты</p>',
  seo_title: 'Публичная оферта | OPTISPORT',
  seo_description: 'Условия публичной оферты',
  is_published: true,
};

/** Загружает страницу с чистым состоянием: `fetchPage` мемоизирован через React cache */
async function loadPage() {
  vi.resetModules();
  return import('../page');
}

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  const fetchMock = vi.fn(async () => response as Response);
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

describe('CMS-страница: метаданные опубликованной страницы (AC2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('опубликованная страница получает метаданные buildMetadata без noindex', async () => {
    mockFetch({ ok: true, status: 200, json: async () => publishedPage });
    const { generateMetadata } = await loadPage();

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'oferta' }) });

    const expected = buildMetadata({
      title: publishedPage.seo_title,
      description: publishedPage.seo_description,
      path: '/oferta',
    });

    expect(metadata).toEqual(expected);
    expect(metadata.title).toBe('Публичная оферта | OPTISPORT');
    expect(metadata.alternates?.canonical).toBe('/oferta');
    // Главное утверждение AC2: закрывающего индексацию признака здесь быть не должно
    expect(metadata.robots).toBeUndefined();
  });

  it('без seo_title заголовок собирается из названия страницы, noindex не появляется', async () => {
    mockFetch({
      ok: true,
      status: 200,
      json: async () => ({ ...publishedPage, seo_title: undefined, seo_description: undefined }),
    });
    const { generateMetadata } = await loadPage();

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'oferta' }) });

    expect(metadata.title).toBe('Публичная оферта | OPTISPORT');
    expect(metadata.robots).toBeUndefined();
  });

  it('несуществующая страница остаётся закрытой от индексации (страховка fail-open)', async () => {
    mockFetch({ ok: false, status: 404, json: async () => ({ detail: 'Not found' }) });
    const { generateMetadata } = await loadPage();

    const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'offer' }) });

    expect(metadata.title).toBe('Страница не найдена | OPTISPORT');
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });
});
