import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../CatalogPageClient', () => ({ default: () => null }));

import { generateMetadata } from '../page';
import { DEFAULT_OG_IMAGE, DEFAULT_OG_IMAGE_META } from '@/utils/seo';

const BASE_TITLE = 'Каталог спортивных товаров | OPTISPORT';
const BASE_DESCRIPTION =
  'Каталог спортивных товаров: фитнес и атлетика, единоборства, спортивные игры, плавание, туризм. Оптовые и рекомендованные розничные цены, доставка по России.';
const BASE_KEYWORDS =
  'каталог спортивных товаров, спортинвентарь оптом, спортивная экипировка';

const COLLECTIONS = {
  is_new: {
    title: 'Новинки — каталог спортивных товаров | OPTISPORT',
    description:
      'Новинки в каталоге OPTISPORT: подборка спортивных товаров с ценами и условиями заказа для оптовых покупателей.',
  },
  is_hit: {
    title: 'Лидеры продаж — каталог спортивных товаров | OPTISPORT',
    description:
      'Лидеры продаж в каталоге OPTISPORT: подборка спортивных товаров с ценами и условиями заказа для оптовых покупателей.',
  },
  is_sale: {
    title: 'Скидки — каталог спортивных товаров | OPTISPORT',
    description:
      'Скидки в каталоге OPTISPORT: подборка спортивных товаров со сниженными ценами и условиями заказа для оптовых покупателей.',
  },
};

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

  it('базовый description укладывается в 157 символов и называет розничные цены рекомендованными', async () => {
    const metadata = await metadataFor({});

    expect(metadata.description).toBe(BASE_DESCRIPTION);
    expect(BASE_DESCRIPTION).toHaveLength(157);
  });

  it.each([
    ['is_new', COLLECTIONS.is_new],
    ['is_hit', COLLECTIONS.is_hit],
    ['is_sale', COLLECTIONS.is_sale],
  ])('подборка %s=true получает собственные metadata с canonical /catalog', async (key, texts) => {
    const metadata = await metadataFor({ [key]: 'true' });

    expect(metadata).toMatchObject({
      title: texts.title,
      description: texts.description,
      keywords: null,
      alternates: { canonical: '/catalog' },
      openGraph: {
        title: texts.title,
        description: texts.description,
        url: '/catalog',
        type: 'website',
        images: [DEFAULT_OG_IMAGE_META],
      },
      twitter: {
        card: 'summary_large_image',
        title: texts.title,
        description: texts.description,
        images: [DEFAULT_OG_IMAGE],
      },
    });
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each([
    ['два флага', { is_new: 'true', is_hit: 'true' }],
    ['значение false', { is_new: 'false' }],
    ['пустое значение', { is_new: '' }],
    ['значение TRUE', { is_hit: 'TRUE' }],
    ['значение 1', { is_sale: '1' }],
    ['повтор флага', { is_new: ['true', 'true'] }],
    ['флаг и page', { is_new: 'true', page: '2' }],
    ['флаг и ordering', { is_hit: 'true', ordering: '-name' }],
    ['флаг и focusSearch', { is_sale: 'true', focusSearch: 'true' }],
    ['только focusSearch', { focusSearch: 'true' }],
  ])('%s не считается подборкой и даёт базовые metadata без API-запроса', async (_name, params) => {
    const metadata = await metadataFor(params);

    expectBaseMetadata(metadata);
    expect(fetch).not.toHaveBeenCalled();
  });

  it('игнорирует ключи со значением undefined при распознавании подборки', async () => {
    const metadata = await metadataFor({ is_new: 'true', page: undefined });

    expect(metadata.title).toBe(COLLECTIONS.is_new.title);
  });

  it('флаг подборки вместе с валидной category даёт metadata категории', async () => {
    vi.mocked(fetch).mockResolvedValue(
      response([{ name: 'Игры', slug: 'games', children: [] }])
    );

    const metadata = await metadataFor({ is_new: 'true', category: 'games' });

    expect(metadata).toMatchObject({
      title: 'Игры — спортивные товары',
      description:
        'Товары категории «Игры» в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей.',
      keywords: null,
      alternates: { canonical: '/catalog?category=games' },
    });
  });

  it.each([
    ['самое длинное реальное имя', 'Форма для кикбоксинга и тайского бокса', 126],
    ['граничное имя из 72 символов', 'Я'.repeat(72), 160],
  ])('description категории: %s укладывается в 160 символов', async (_name, name, length) => {
    vi.mocked(fetch).mockResolvedValue(response([{ name, slug: 'long', children: [] }]));

    const metadata = await metadataFor({ category: 'long' });

    expect(metadata.description).toBe(
      `Товары категории «${name}» в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей.`
    );
    expect(metadata.description).toHaveLength(length);
    expect((metadata.description as string).length).toBeLessThanOrEqual(160);
    expect(metadata.description).not.toMatch(/розничн/i);
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
      'Товары категории «Настольный теннис» в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей.';

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
