import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('../CatalogPageClient', () => ({ default: () => null }));

const cookieValues = new Map<string, string>();
const headerValues = new Map<string, string>();
vi.mock('next/headers', () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      cookieValues.has(name) ? { name, value: cookieValues.get(name) } : undefined,
  })),
  headers: vi.fn(async () => ({
    has: (name: string) => headerValues.has(name),
    get: (name: string) => headerValues.get(name) ?? null,
  })),
}));

import CatalogPage from '../page';
import { buildInitialProductFilters, productFiltersKey } from '../catalogQuery';
import type { CatalogInitialProducts } from '../catalogQuery';

const response = (body: unknown, ok = true) =>
  ({ ok, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

const PRODUCTS = { count: 30, results: [{ id: 1, name: 'Мяч', slug: 'myach' }] };
const TREE = [{ id: 7, name: 'Обувь', slug: 'obuv', children: [{ id: 8, name: 'Кеды', slug: 'kedy' }] }];

async function initialProductsFor(
  params: Record<string, string | string[] | undefined>
): Promise<CatalogInitialProducts | null> {
  const element = (await CatalogPage({ searchParams: Promise.resolve(params) })) as ReactElement<{
    initialProducts: CatalogInitialProducts | null;
  }>;
  return element.props.initialProducts;
}

const keyFor = (query: string, categoryId: number | null = null) => {
  const params = new URLSearchParams(query);
  return productFiltersKey(buildInitialProductFilters(name => params.get(name), categoryId));
};

const requestedUrl = (call = 0) => new URL(String(vi.mocked(fetch).mock.calls[call][0]));

describe('серверная первая страница выдачи каталога', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    cookieValues.clear();
    headerValues.clear();
    vi.stubGlobal('fetch', vi.fn());
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it('загружает выдачу анонимно без кэша и передаёт её клиенту с ключом фильтров', async () => {
    vi.mocked(fetch).mockResolvedValue(response(PRODUCTS));

    const initial = await initialProductsFor({ page: '2', is_new: 'true' });

    expect(initial).toEqual({
      ...PRODUCTS,
      key: keyFor('page=2&is_new=true'),
      token: expect.any(String),
    });
    const url = requestedUrl();
    expect(url.pathname).toBe('/api/v1/products/');
    expect(Object.fromEntries(url.searchParams)).toEqual({
      page: '2',
      page_size: '12',
      ordering: 'name',
      min_price: '1',
      max_price: '50000',
      is_new: 'true',
      in_stock: 'true',
    });
    expect(vi.mocked(fetch).mock.calls[0][1]).toEqual({
      cache: 'no-store',
      signal: expect.any(AbortSignal),
    });
  });

  it('берёт category_id из дерева категорий по slug', async () => {
    vi.mocked(fetch).mockImplementation(async input =>
      String(input).includes('categories-tree') ? response(TREE) : response(PRODUCTS)
    );

    const initial = await initialProductsFor({ category: 'kedy' });

    expect(initial?.key).toBe(keyFor('category=kedy', 8));
    expect(requestedUrl(1).searchParams.get('category_id')).toBe('8');
  });

  it('несуществующий slug категории даёт выдачу без category_id — как у клиента', async () => {
    vi.mocked(fetch).mockImplementation(async input =>
      String(input).includes('categories-tree') ? response(TREE) : response(PRODUCTS)
    );

    const initial = await initialProductsFor({ category: 'net-takoy' });

    expect(initial?.key).toBe(keyFor(''));
    expect(requestedUrl(1).searchParams.has('category_id')).toBe(false);
  });

  it('выдаёт каждому запросу свой токен', async () => {
    vi.mocked(fetch).mockResolvedValue(response(PRODUCTS));

    const first = await initialProductsFor({});
    const second = await initialProductsFor({});

    expect(first?.token).toBeTruthy();
    expect(first?.token).not.toBe(second?.token);
  });

  it('не грузит выдачу на клиентской навигации: её выполняет fetch роутера', async () => {
    headerValues.set('sec-fetch-dest', 'empty');

    expect(await initialProductsFor({ page: '2' })).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('грузит выдачу для документа, открытого браузером', async () => {
    headerValues.set('sec-fetch-dest', 'document');
    vi.mocked(fetch).mockResolvedValue(response(PRODUCTS));

    expect(await initialProductsFor({})).not.toBeNull();
  });

  it('не грузит выдачу при cookie refreshToken: цены роли загрузит клиент', async () => {
    cookieValues.set('refreshToken', 'token');

    expect(await initialProductsFor({})).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('не грузит выдачу по ссылке с брендом', async () => {
    expect(await initialProductsFor({ brand: 'nike' })).toBeNull();
    expect(fetch).not.toHaveBeenCalled();
  });

  it('пустой параметр brand выдачу не отключает', async () => {
    vi.mocked(fetch).mockResolvedValue(response(PRODUCTS));

    expect(await initialProductsFor({ brand: ' , ' })).not.toBeNull();
  });

  it.each([
    ['ответ не 2xx', () => vi.mocked(fetch).mockResolvedValue(response({ detail: 'x' }, false))],
    ['сетевую ошибку или таймаут', () => vi.mocked(fetch).mockRejectedValue(new Error('timeout'))],
    ['ответ без count и results', () => vi.mocked(fetch).mockResolvedValue(response({}))],
  ])('возвращает null на %s', async (_, arrange) => {
    arrange();

    expect(await initialProductsFor({ page: '99' })).toBeNull();
  });

  it('возвращает null, если дерево категорий не загрузилось', async () => {
    vi.mocked(fetch).mockResolvedValue(response({ detail: 'x' }, false));

    expect(await initialProductsFor({ category: 'obuv' })).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});
