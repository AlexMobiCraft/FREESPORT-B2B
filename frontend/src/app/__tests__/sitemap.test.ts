import { beforeEach, describe, expect, it, vi } from 'vitest';

import sitemap from '../sitemap';
import { absoluteUrl } from '@/utils/seo';

const response = (body: unknown, ok = true) =>
  ({ ok, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

const pathOf = (url: string) => new URL(url).pathname + new URL(url).search;

const COLLECTION_KEYS = ['is_new', 'is_hit', 'is_sale'] as const;

type CollectionKey = (typeof COLLECTION_KEYS)[number];

// Ответ API на проверку наполненности подборки; тест переопределяет его для отдельного ключа
let collectionResponses: Record<CollectionKey, () => Promise<Response>>;

const collectionKeyOf = (url: string) =>
  COLLECTION_KEYS.find(key => new URL(url).searchParams.get(key) === 'true');

describe('sitemap: публичные категории каталога', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
    collectionResponses = {
      is_new: () => Promise.resolve(response({ count: 5, results: [{ slug: 'ball' }] })),
      is_hit: () => Promise.resolve(response({ count: 4, results: [{ slug: 'ball' }] })),
      is_sale: () => Promise.resolve(response({ count: 5, results: [{ slug: 'ball' }] })),
    };
    vi.stubGlobal(
      'fetch',
      vi.fn((input: string | URL | Request) => {
        const url = String(input);
        if (url.includes('/categories-tree/')) {
          return Promise.resolve(
            response([
              {
                slug: 'games',
                children: [
                  {
                    slug: 'table tennis',
                    children: [{ slug: 'deep&special', children: [] }],
                  },
                  { slug: 'games', children: [] },
                  { slug: '   ', children: [] },
                  { slug: 42, children: [] },
                ],
              },
            ])
          );
        }
        const collection = url.includes('/products/') ? collectionKeyOf(url) : undefined;
        if (collection) return collectionResponses[collection]();
        if (url.includes('/products/')) {
          return Promise.resolve(
            response({ results: [{ slug: 'ball', updated_at: '2026-09-14T00:00:00Z' }], next: null })
          );
        }
        if (url.includes('/blog/')) {
          return Promise.resolve(response({ results: [{ slug: 'post' }], next: null }));
        }
        if (url.includes('/news/')) {
          return Promise.resolve(response({ results: [{ slug: 'item' }], next: null }));
        }
        if (url.includes('/pages/')) {
          return Promise.resolve(response({ results: [{ slug: 'contacts' }], next: null }));
        }
        return Promise.resolve(response({ results: [], next: null }));
      })
    );
  });

  it('добавляет корни и потомков всех уровней как query URL с дедупликацией', async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, 'timeout');
    const entries = await sitemap();
    const paths = entries.map(entry => pathOf(entry.url));

    expect(paths).toContain('/catalog?category=games');
    expect(paths).toContain('/catalog?category=table+tennis');
    expect(paths).toContain('/catalog?category=deep%26special');
    expect(paths.filter(path => path === '/catalog?category=games')).toHaveLength(1);
    expect(paths).not.toContain('/catalog?category=+++');
    expect(paths).not.toContain('/catalog?category=42');
    expect(paths).not.toContain('/catalog/games');
    expect(paths).toContain('/product/ball');
    expect(timeoutSpy).toHaveBeenCalledWith(3000);
    expect(fetch).toHaveBeenCalledWith('http://backend:8000/api/v1/categories-tree/', {
      next: { revalidate: 3600 },
      signal: expect.any(AbortSignal),
    });
  });

  it('содержит каждую непустую подборку ровно один раз и не содержит адресов фокуса поиска', async () => {
    const entries = await sitemap();
    const paths = entries.map(entry => pathOf(entry.url));

    expect(paths.filter(path => path.includes('focusSearch='))).toEqual([]);
    for (const key of COLLECTION_KEYS) {
      expect(paths.filter(path => path.includes(`${key}=`))).toEqual([`/catalog?${key}=true`]);
    }
    expect(entries.find(entry => pathOf(entry.url) === '/catalog?is_new=true')).toMatchObject({
      url: absoluteUrl('/catalog?is_new=true'),
      changeFrequency: 'daily',
      priority: 0.7,
    });
  });

  it('проверяет наполненность подборки по товарам в наличии', async () => {
    const timeoutSpy = vi.spyOn(AbortSignal, 'timeout');
    await sitemap();

    for (const key of COLLECTION_KEYS) {
      expect(fetch).toHaveBeenCalledWith(
        `http://backend:8000/api/v1/products/?${key}=true&in_stock=true&page_size=1`,
        { next: { revalidate: 3600 }, signal: expect.any(AbortSignal) }
      );
    }
    // Каждый вызов — ровно 3000 мс: суммарного счётчика мало, он пропустил бы
    // один collection-запрос с другим таймаутом
    expect(timeoutSpy.mock.calls).toEqual([[3000], [3000], [3000], [3000]]);
  });

  it('запускает проверки всех подборок параллельно', async () => {
    const started: CollectionKey[] = [];
    let releaseAll!: () => void;
    const allStarted = new Promise<void>(resolve => {
      releaseAll = resolve;
    });
    // Ответ приходит только после старта всех трёх запросов: при последовательном
    // обходе первый запрос никогда не разрешится и гонку выиграет таймер
    for (const key of COLLECTION_KEYS) {
      collectionResponses[key] = () => {
        started.push(key);
        if (started.length === COLLECTION_KEYS.length) releaseAll();
        return allStarted.then(() => response({ count: 5, results: [] }));
      };
    }

    const entries = sitemap();
    const outcome = await Promise.race([
      allStarted.then(() => 'параллельно' as const),
      new Promise<'последовательно'>(resolve => setTimeout(() => resolve('последовательно'), 50)),
    ]);

    expect(outcome).toBe('параллельно');
    expect(started).toEqual([...COLLECTION_KEYS]);

    const paths = (await entries).map(entry => pathOf(entry.url));
    for (const key of COLLECTION_KEYS) {
      expect(paths).toContain(`/catalog?${key}=true`);
    }
  });

  it('размещает подборки сразу после категорий и до товаров', async () => {
    const paths = (await sitemap()).map(entry => pathOf(entry.url));
    const categoryIndexes = paths
      .map((path, index) => (path.startsWith('/catalog?category=') ? index : -1))
      .filter(index => index >= 0);
    const collectionIndexes = COLLECTION_KEYS.map(key => paths.indexOf(`/catalog?${key}=true`));

    expect(categoryIndexes.length).toBeGreaterThan(0);
    expect(collectionIndexes).not.toContain(-1);
    // Подборки идут подряд, сразу за последней категорией, в порядке COLLECTION_KEYS
    expect(collectionIndexes).toEqual(
      COLLECTION_KEYS.map((_, offset) => Math.max(...categoryIndexes) + 1 + offset)
    );
    expect(Math.max(...collectionIndexes)).toBeLessThan(paths.indexOf('/product/ball'));
  });

  it.each([
    ['count: 0', () => Promise.resolve(response({ count: 0, results: [] }))],
    ['не-2xx', () => Promise.resolve(response({ count: 5 }, false))],
    ['сетевая ошибка', () => Promise.reject(new Error('network'))],
    ['таймаут', () => Promise.reject(new DOMException('timeout', 'TimeoutError'))],
    ['тело без count', () => Promise.resolve(response({ results: [{ slug: 'ball' }] }))],
    ["count: '5'", () => Promise.resolve(response({ count: '5' }))],
    ['невалидный JSON', () => Promise.resolve({ ok: true, json: () => Promise.reject(new SyntaxError('json')) } as unknown as Response)],
  ])('%s у одной подборки убирает только её', async (_label, reply) => {
    collectionResponses.is_hit = reply;

    const paths = (await sitemap()).map(entry => pathOf(entry.url));

    expect(paths.some(path => path.includes('is_hit='))).toBe(false);
    expect(paths).toContain('/catalog?is_new=true');
    expect(paths).toContain('/catalog?is_sale=true');
    expect(paths).toContain('/catalog');
    expect(paths).toContain('/home');
    expect(paths).toContain('/catalog?category=games');
    expect(paths).toContain('/product/ball');
    expect(paths).toContain('/blog/post');
    expect(paths).toContain('/news/item');
    expect(paths).toContain('/contacts');
  });

  it('не сочетает подборки с другими параметрами', async () => {
    const paths = (await sitemap()).map(entry => pathOf(entry.url));
    const collectionPaths = paths.filter(path => /is_(new|hit|sale)=/.test(path));

    expect(collectionPaths).toHaveLength(3);
    for (const path of collectionPaths) {
      expect(new URL(path, 'https://optisport.ru').searchParams.size).toBe(1);
    }
  });

  it('ошибка дерева не удаляет статические и остальные динамические адреса', async () => {
    vi.mocked(fetch).mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes('/categories-tree/')) return Promise.reject(new Error('network'));
      if (url.includes('/products/')) {
        return Promise.resolve(response({ results: [{ slug: 'ball' }], next: null }));
      }
      return Promise.resolve(response({ results: [], next: null }));
    });

    const paths = (await sitemap()).map(entry => pathOf(entry.url));

    expect(paths).toContain('/catalog');
    expect(paths).toContain('/home');
    expect(paths).toContain('/product/ball');
    expect(paths.some(path => path.startsWith('/catalog?category='))).toBe(false);
  });

  it('невалидное тело дерева не роняет sitemap', async () => {
    vi.mocked(fetch).mockImplementation((input: string | URL | Request) => {
      const url = String(input);
      if (url.includes('/categories-tree/')) return Promise.resolve(response({ results: [] }));
      return Promise.resolve(response({ results: [], next: null }));
    });

    await expect(sitemap()).resolves.toEqual(expect.arrayContaining([expect.objectContaining({})]));
  });
});
