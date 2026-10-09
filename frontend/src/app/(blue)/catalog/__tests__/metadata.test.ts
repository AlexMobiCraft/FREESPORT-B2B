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
  ])('подборка %s=true получает собственные metadata с собственным canonical', async (key, texts) => {
    const metadata = await metadataFor({ [key]: 'true' });

    expect(metadata).toMatchObject({
      title: texts.title,
      description: texts.description,
      keywords: null,
      alternates: { canonical: `/catalog?${key}=true` },
      openGraph: {
        title: texts.title,
        description: texts.description,
        url: `/catalog?${key}=true`,
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

  describe('страницы брендов', () => {
    const FEATURED_BRANDS_URL = 'http://backend:8000/api/v1/brands/featured/';
    const BRAND_TEXTS_FORBIDDEN = /рознич|розниц|B2B|Ведущ|Крупнейш/i;

    // Форма ответа BrandFeaturedSerializer: image — относительный URL, is_featured в ответе нет
    const featuredBrand = (id: number, name: string, slug: string) => ({
      id,
      name,
      slug,
      image: `/media/brands/${slug}.png`,
      website: `https://${slug}.example`,
    });
    const FEATURED_BRANDS = [
      featuredBrand(1, 'BoyBo', 'boybo'),
      featuredBrand(2, 'Cosmoride', 'cosmoride'),
      featuredBrand(3, 'Eclectica', 'eclectica'),
    ];

    const brandTexts = (name: string) => ({
      title: `Спортивные товары ${name} оптом | OPTISPORT`,
      description: `Товары бренда ${name} в каталоге OPTISPORT: цены и условия заказа для оптовых покупателей, доставка по России.`,
    });

    const mockFeaturedBrands = (body: unknown = FEATURED_BRANDS) =>
      vi.mocked(fetch).mockResolvedValue(response(body));

    it('избранный бренд получает собственные metadata и self-canonical', async () => {
      const timeoutSpy = vi.spyOn(AbortSignal, 'timeout');
      mockFeaturedBrands();

      const metadata = await metadataFor({ brand: 'boybo' });
      const texts = brandTexts('BoyBo');

      expect(metadata).toMatchObject({
        title: texts.title,
        description: texts.description,
        keywords: null,
        alternates: { canonical: '/catalog?brand=boybo' },
        openGraph: {
          title: texts.title,
          description: texts.description,
          url: '/catalog?brand=boybo',
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
      expect(texts.title).toHaveLength(41);
      expect(texts.description).toHaveLength(108);
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith(FEATURED_BRANDS_URL, {
        next: { revalidate: 3600 },
        signal: expect.any(AbortSignal),
      });
      expect(timeoutSpy).toHaveBeenCalledWith(3000);
    });

    it('шесть избранных брендов получают уникальные title, description и canonical', async () => {
      const brands = [
        featuredBrand(1, 'BoyBo', 'boybo'),
        featuredBrand(2, 'Cosmoride', 'cosmoride'),
        featuredBrand(3, 'Eclectica', 'eclectica'),
        featuredBrand(4, 'Elous', 'elous'),
        featuredBrand(5, 'ESPADO', 'espado'),
        featuredBrand(6, 'InGame', 'ingame'),
      ];
      mockFeaturedBrands(brands);

      const results = [];
      for (const { slug } of brands) results.push(await metadataFor({ brand: slug }));

      for (const field of ['title', 'description'] as const) {
        expect(new Set(results.map(metadata => metadata[field])).size).toBe(brands.length);
      }
      expect(results.map(metadata => metadata.alternates?.canonical)).toEqual(
        brands.map(({ slug }) => `/catalog?brand=${slug}`)
      );
      expect(results.every(metadata => metadata.keywords === null)).toBe(true);
    });

    it('обрезает пробелы в slug адреса и в name записи', async () => {
      mockFeaturedBrands([featuredBrand(1, '  BoyBo  ', 'boybo')]);

      const metadata = await metadataFor({ brand: ' boybo ' });

      expect(metadata).toMatchObject({
        ...brandTexts('BoyBo'),
        alternates: { canonical: '/catalog?brand=boybo' },
      });
    });

    it('игнорирует ключи со значением undefined при распознавании страницы бренда', async () => {
      mockFeaturedBrands();

      const metadata = await metadataFor({ brand: 'boybo', page: undefined });

      expect(metadata.title).toBe(brandTexts('BoyBo').title);
    });

    it('кодирует canonical бренда единым URLSearchParams', async () => {
      mockFeaturedBrands([featuredBrand(1, 'Brand & Co', 'brand & co')]);

      const metadata = await metadataFor({ brand: 'brand & co' });

      expect(metadata.title).toBe(brandTexts('Brand & Co').title);
      expect(metadata.alternates).toEqual({ canonical: '/catalog?brand=brand+%26+co' });
    });

    it('в тексте бренда нет розницы, «B2B» и превосходных степеней', async () => {
      mockFeaturedBrands();

      const metadata = await metadataFor({ brand: 'boybo' });

      expect(metadata.title).not.toMatch(BRAND_TEXTS_FORBIDDEN);
      expect(metadata.description).not.toMatch(BRAND_TEXTS_FORBIDDEN);
    });

    it.each([
      ['имя до 40 символов', 40, 143],
      ['граничное имя из 57 символов', 57, 160],
    ])('description бренда: %s укладывается в 160 символов', async (_name, nameLength, length) => {
      const name = 'Я'.repeat(nameLength);
      mockFeaturedBrands([featuredBrand(1, name, 'long')]);

      const metadata = await metadataFor({ brand: 'long' });

      expect(metadata.description).toBe(brandTexts(name).description);
      expect(metadata.description).toHaveLength(length);
      expect((metadata.description as string).length).toBeLessThanOrEqual(160);
      expect(fetch).toHaveBeenCalledTimes(1);
    });

    it.each([
      ['бренд вне списка избранных', { brand: 'intex' }],
      ['другой регистр slug', { brand: 'BoyBo' }],
      ['slug с пробелом внутри', { brand: 'boy bo' }],
    ])('%s даёт базовые metadata', async (_name, params) => {
      mockFeaturedBrands();

      expectBaseMetadata(await metadataFor(params));
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith(FEATURED_BRANDS_URL, expect.anything());
    });

    it.each([
      ['404 сборки бэкенда без /featured/', () => Promise.resolve(response({}, false))],
      ['другой не-2xx', () => Promise.resolve(response(FEATURED_BRANDS, false))],
      ['сетевая ошибка', () => Promise.reject(new Error('network'))],
      ['таймаут', () => Promise.reject(new DOMException('timed out', 'TimeoutError'))],
      [
        'невалидный JSON',
        () =>
          Promise.resolve({
            ok: true,
            json: vi.fn().mockRejectedValue(new SyntaxError('Unexpected token')),
          } as unknown as Response),
      ],
    ])('сбой API (%s) даёт базовые metadata без исключения', async (_name, implementation) => {
      vi.mocked(fetch).mockImplementation(implementation as typeof fetch);

      expectBaseMetadata(await metadataFor({ brand: 'boybo' }));
    });

    it.each([
      ['null', null],
      ['объект', { results: FEATURED_BRANDS }],
      ['строка', 'boybo'],
      ['пустой массив', []],
    ])('тело ответа «%s» даёт базовые metadata', async (_name, body) => {
      mockFeaturedBrands(body);

      expectBaseMetadata(await metadataFor({ brand: 'boybo' }));
    });

    it.each([
      ['пустое name', { ...featuredBrand(1, '', 'boybo') }],
      ['name из пробелов', { ...featuredBrand(1, '   ', 'boybo') }],
      ['нестроковое name', { ...featuredBrand(1, 'BoyBo', 'boybo'), name: 123 }],
      ['name null', { ...featuredBrand(1, 'BoyBo', 'boybo'), name: null }],
      ['запись без name', { id: 1, slug: 'boybo' }],
      ['пустой slug', { ...featuredBrand(1, 'BoyBo', '') }],
      ['нестроковый slug', { ...featuredBrand(1, 'BoyBo', 'boybo'), slug: 5 }],
    ])('запись с невалидным полем (%s) не создаёт metadata бренда', async (_name, record) => {
      mockFeaturedBrands([record]);

      expectBaseMetadata(await metadataFor({ brand: 'boybo' }));
    });

    it('пропускает мусорные записи массива и берёт валидные', async () => {
      mockFeaturedBrands([
        null,
        'boybo',
        42,
        [],
        { slug: 'boybo' },
        { name: 'Без slug' },
        featuredBrand(2, 'Cosmoride', 'cosmoride'),
      ]);

      expectBaseMetadata(await metadataFor({ brand: 'boybo' }));
      expect(await metadataFor({ brand: 'cosmoride' })).toMatchObject(brandTexts('Cosmoride'));
    });

    it('при повторе slug в списке берёт первую запись', async () => {
      mockFeaturedBrands([featuredBrand(1, 'BoyBo', 'boybo'), featuredBrand(2, 'Другое', 'boybo')]);

      expect(await metadataFor({ brand: 'boybo' })).toMatchObject(brandTexts('BoyBo'));
    });

    it.each([
      ['мультибренд', { brand: 'boybo,espado' }],
      ['мультибренд с пробелами', { brand: 'boybo, espado' }],
      ['пустой brand', { brand: '' }],
      ['brand из пробелов', { brand: '   ' }],
      ['повтор brand', { brand: ['boybo', 'espado'] }],
      ['повтор одинакового brand', { brand: ['boybo', 'boybo'] }],
      ['brand и page', { brand: 'boybo', page: '2' }],
      ['brand и ordering', { brand: 'boybo', ordering: '-name' }],
      ['brand и is_new', { brand: 'boybo', is_new: 'true' }],
      ['brand и трекинговый параметр', { brand: 'boybo', utm_source: 'mail' }],
    ])('%s не считается страницей бренда и не вызывает API', async (_name, params) => {
      mockFeaturedBrands();

      expectBaseMetadata(await metadataFor(params));
      expect(fetch).not.toHaveBeenCalled();
    });

    it('бренд вместе с валидной category даёт metadata категории без запроса брендов', async () => {
      vi.mocked(fetch).mockResolvedValue(
        response([{ name: 'Игры', slug: 'games', children: [] }])
      );

      const metadata = await metadataFor({ brand: 'boybo', category: 'games' });

      expect(metadata).toMatchObject({
        title: 'Игры — спортивные товары',
        alternates: { canonical: '/catalog?category=games' },
      });
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith('http://backend:8000/api/v1/categories-tree/', {
        next: { revalidate: 3600 },
        signal: expect.any(AbortSignal),
      });
    });

    it('бренд вместе с невалидной category даёт базовые metadata без запроса брендов', async () => {
      vi.mocked(fetch).mockResolvedValue(
        response([{ name: 'Игры', slug: 'games', children: [] }])
      );

      expectBaseMetadata(await metadataFor({ brand: 'boybo', category: 'unknown' }));
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(fetch).toHaveBeenCalledWith(
        'http://backend:8000/api/v1/categories-tree/',
        expect.anything()
      );
    });

    it.each([
      ['слеш', 'a/b'],
      ['вопросительный знак', 'a?b'],
      ['две точки', '..'],
      ['точка', '.'],
      ['нулевой символ', 'boybo\u0000'],
      ['решётка', 'a#b'],
      ['процент', '100%'],
    ])('спецсимвол (%s) не попадает в адрес запроса и даёт базовые metadata', async (_name, brand) => {
      mockFeaturedBrands();

      expectBaseMetadata(await metadataFor({ brand }));
      expect(fetch).toHaveBeenCalledTimes(1);
      expect(vi.mocked(fetch).mock.calls[0][0]).toBe(FEATURED_BRANDS_URL);
    });

    it('/catalog и подборки не запрашивают список брендов', async () => {
      await metadataFor({});
      await metadataFor({ is_new: 'true' });

      expect(fetch).not.toHaveBeenCalled();
    });
  });
});
