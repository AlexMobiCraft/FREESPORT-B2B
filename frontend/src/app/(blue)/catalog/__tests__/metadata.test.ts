import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../CatalogPageClient', () => ({ default: () => null }));

import { generateMetadata } from '../page';
import { DEFAULT_OG_IMAGE, DEFAULT_OG_IMAGE_META } from '@/utils/seo';

const BASE_TITLE = 'Каталог спортивных товаров | OPTISPORT';
const BASE_DESCRIPTION =
  'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и розничные цены, доставка по России.';
const BASE_KEYWORDS =
  'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка';

const response = (body: unknown, ok = true) =>
  ({ ok, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

const metadataFor = (params: Record<string, string | string[] | undefined>) =>
  generateMetadata({ searchParams: Promise.resolve(params) });

function expectBaseMetadata(metadata: Awaited<ReturnType<typeof generateMetadata>>) {
  expect(metadata).toMatchObject({
    title: BASE_TITLE,
    description: BASE_DESCRIPTION,
    keywords: BASE_KEYWORDS,
    alternates: { canonical: '/catalog' },
    openGraph: {
      title: BASE_TITLE,
      description: BASE_DESCRIPTION,
      url: '/catalog',
      type: 'website',
    },
    twitter: { title: BASE_TITLE, description: BASE_DESCRIPTION },
  });
  expect(metadata.openGraph).toHaveProperty('images');
}

describe('generateMetadata каталога', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubGlobal('fetch', vi.fn());
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
  });

  it('сохраняет точные базовые metadata без category и не загружает дерево', async () => {
    const metadata = await metadataFor({});

    expectBaseMetadata(metadata);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('строит metadata валидной вложенной категории только из публичного дерева', async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, 'timeout');
    vi.mocked(fetch).mockResolvedValue(
      response([
        {
          name: 'Игры',
          slug: 'games',
          children: [{ name: 'Настольный теннис', slug: 'table-tennis', children: [] }],
        },
      ])
    );

    const metadata = await metadataFor({
      category: 'table-tennis',
      page: '2',
      brand: 'nike',
    });
    const title = 'Настольный теннис — спортивные товары';
    const description =
      'Спортивные товары категории «Настольный теннис» в каталоге OPTISPORT: информация о товарах, ценах и условиях заказа для розничных и оптовых покупателей.';

    expect(metadata).toMatchObject({
      title,
      description,
      keywords: null,
      alternates: { canonical: '/catalog?category=table-tennis' },
      openGraph: {
        title,
        description,
        url: '/catalog?category=table-tennis',
        type: 'website',
        images: [DEFAULT_OG_IMAGE_META],
      },
      twitter: {
        card: 'summary_large_image',
        title,
        description,
        images: [DEFAULT_OG_IMAGE],
      },
    });
    expect(metadata.openGraph).toMatchObject({
      images: [DEFAULT_OG_IMAGE_META],
      type: 'website',
    });
    expect(metadata.twitter).toMatchObject({
      images: [DEFAULT_OG_IMAGE],
      card: 'summary_large_image',
    });
    expect(fetch).toHaveBeenCalledWith('http://backend:8000/api/v1/categories-tree/', {
      next: { revalidate: 3600 },
      signal: expect.any(AbortSignal),
    });
    expect(timeoutSpy).toHaveBeenCalledWith(3000);
  });

  it('кодирует canonical единым URLSearchParams и не выводит имя из slug', async () => {
    vi.mocked(fetch).mockResolvedValue(
      response([{ name: 'Имя только из API', slug: 'лыжи & бег', children: [] }])
    );

    const metadata = await metadataFor({ category: 'лыжи & бег' });

    expect(metadata.title).toBe('Имя только из API — спортивные товары');
    expect(metadata.alternates).toEqual({
      canonical: '/catalog?category=%D0%BB%D1%8B%D0%B6%D0%B8+%26+%D0%B1%D0%B5%D0%B3',
    });
  });

  it.each([
    ['пустой category', { category: '   ' }],
    ['повтор разных category', { category: ['games', 'running'] }],
    ['повтор одинаковых category', { category: ['games', 'games'] }],
  ])('%s возвращает базовые metadata без API-запроса', async (_name, params) => {
    const metadata = await metadataFor(params);

    expectBaseMetadata(metadata);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('не индексирует slug вне публичного дерева, включая скрытый активный узел', async () => {
    vi.mocked(fetch).mockResolvedValue(
      response([{ name: 'Публичная категория', slug: 'public', children: [] }])
    );

    expectBaseMetadata(await metadataFor({ category: 'active-but-hidden' }));
  });

  it.each([
    ['невалидное тело', () => Promise.resolve(response({ results: [] }))],
    ['ответ 5xx', () => Promise.resolve(response([], false))],
    ['сетевая ошибка', () => Promise.reject(new Error('network'))],
    ['таймаут', () => Promise.reject(new DOMException('timed out', 'TimeoutError'))],
  ])('%s даёт полный fail-soft fallback', async (_name, implementation) => {
    vi.mocked(fetch).mockImplementation(implementation as typeof fetch);

    expectBaseMetadata(await metadataFor({ category: 'games' }));
  });
});
