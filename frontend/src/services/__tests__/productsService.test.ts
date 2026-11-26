/**
 * Products Service Tests
 * @vitest-environment node
 */
import productsService from '../productsService';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

describe('productsService', () => {
  describe('getAll', () => {
    test('fetches products list successfully', async () => {
      const result = await productsService.getAll();

      expect(result.count).toBe(100);
      expect(result.results).toHaveLength(1);
      expect(result.results[0].name).toBe('Test Product');
    });

    test('fetches products with filters', async () => {
      const result = await productsService.getAll({
        page: 1,
        limit: 20,
        category: 'category',
      });

      expect(result.results).toBeDefined();
    });

    test('handles network error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/', () => {
          return HttpResponse.error();
        })
      );

      await expect(productsService.getAll()).rejects.toThrow();
    });
  });

  describe('getById', () => {
    test('fetches single product successfully', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:id/', ({ params }) => {
          return HttpResponse.json({
            id: Number(params.id),
            name: 'Test Product',
            slug: 'test-product',
            description: 'Test',
            retail_price: 2500,
            is_in_stock: true,
            category: { id: 1, name: 'Category', slug: 'category' },
            images: [],
          });
        })
      );

      const result = await productsService.getById(1);

      expect(result.id).toBe(1);
      expect(result.name).toBe('Test Product');
    });

    test('handles 404 error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:id/', () => {
          return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
        })
      );

      await expect(productsService.getById(999)).rejects.toThrow();
    });
  });

  describe('search', () => {
    test('searches products successfully', async () => {
      let capturedSearchParam: string | null = null;

      server.use(
        http.get('http://localhost:8001/api/v1/products/', ({ request }) => {
          capturedSearchParam = new URL(request.url).searchParams.get('search');

          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                name: 'Search Result',
                slug: 'search-result',
                description: 'Test',
                retail_price: 2500,
                is_in_stock: true,
                category: { id: 1, name: 'Category', slug: 'category' },
                images: [],
              },
            ],
          });
        })
      );

      const result = await productsService.search('test query');

      expect(capturedSearchParam).toBe('test query');
      expect(result.results).toHaveLength(1);
      expect(result.results[0].name).toBe('Search Result');
    });
  });

  describe('filter', () => {
    test('filters products successfully', async () => {
      const result = await productsService.filter({
        category: 'category',
        min_price: 1000,
        max_price: 5000,
      });

      expect(result.results).toBeDefined();
    });
  });

  describe('getProductBySlug', () => {
    test('протаскивает артикул номенклатуры из ответа API', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:slug/', () => {
          return HttpResponse.json({
            id: 1,
            name: 'Test Product',
            slug: 'test-product',
            article: 'ES2123PK',
            retail_price: 2500,
            stock_quantity: 10,
            is_in_stock: true,
            can_be_ordered: true,
            category: { id: 1, name: 'Category', slug: 'category', breadcrumbs: [] },
            images: [],
            variants: [],
          });
        })
      );

      const result = await productsService.getProductBySlug('test-product');

      expect(result.article).toBe('ES2123PK');
    });

    test('протаскивает slug бренда и даёт пустые brand/brand_slug при brand: null', async () => {
      const apiProduct = {
        id: 1,
        name: 'Test Product',
        slug: 'test-product',
        retail_price: 2500,
        stock_quantity: 10,
        is_in_stock: true,
        can_be_ordered: true,
        category: { id: 1, name: 'Category', slug: 'category', breadcrumbs: [] },
        images: [],
        variants: [],
      };
      server.use(
        http.get('http://localhost:8001/api/v1/products/with-brand/', () =>
          HttpResponse.json({ ...apiProduct, brand: { id: 5, name: 'Без ТМ', slug: 'bez-tm' } })
        ),
        http.get('http://localhost:8001/api/v1/products/no-brand/', () =>
          HttpResponse.json({ ...apiProduct, brand: null })
        )
      );

      const withBrand = await productsService.getProductBySlug('with-brand');
      expect(withBrand.brand).toBe('Без ТМ');
      expect(withBrand.brand_slug).toBe('bez-tm');

      const noBrand = await productsService.getProductBySlug('no-brand');
      expect(noBrand.brand).toBe('');
      expect(noBrand.brand_slug).toBe('');
    });

    test('подставляет пустой артикул, когда в 1С он не заполнен', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:slug/', () => {
          return HttpResponse.json({
            id: 1,
            name: 'Test Product',
            slug: 'test-product',
            retail_price: 2500,
            stock_quantity: 10,
            is_in_stock: true,
            can_be_ordered: true,
            category: { id: 1, name: 'Category', slug: 'category', breadcrumbs: [] },
            images: [],
            variants: [],
          });
        })
      );

      const result = await productsService.getProductBySlug('test-product');

      expect(result.article).toBe('');
    });

    test('fetches product detail by slug with custom headers', async () => {
      let capturedHeaders: Headers | undefined;

      server.use(
        http.get('http://localhost:8001/api/v1/products/:slug/', ({ request }) => {
          capturedHeaders = request.headers;
          return HttpResponse.json({
            id: 1,
            name: 'Test Product',
            slug: 'test-product',
            retail_price: 2500,
            stock_quantity: 10,
            is_in_stock: true,
            can_be_ordered: true,
            category: { id: 1, name: 'Category', slug: 'category', breadcrumbs: [] },
            images: [],
            variants: [
              {
                id: 1,
                sku: 'SKU1',
                current_price: '2500.00',
                stock_quantity: 10,
                is_in_stock: true,
                available_quantity: 10,
                rrp: '3000.00',
                msrp: '3500.00',
              },
            ],
          });
        })
      );

      const headers = { Cookie: 'sessionid=123' };
      const result = await productsService.getProductBySlug('test-product', headers);

      expect(result.slug).toBe('test-product');
      // Check if headers were passed
      expect(capturedHeaders?.get('cookie')).toBe('sessionid=123');
      // Check if RRP/MSRP mapped correctly
      expect(result.variants?.[0].rrp).toBe('3000.00');
      expect(result.variants?.[0].msrp).toBe('3500.00');
    });
  });

  describe('getAllHits / getAllNew / getAllPromo — все страницы выдачи', () => {
    const PRODUCTS_URL = 'http://localhost:8001/api/v1/products/';

    const makeProducts = (fromId: number, toId: number) =>
      Array.from({ length: toId - fromId + 1 }, (_, i) => ({
        id: fromId + i,
        name: `Товар ${fromId + i}`,
        slug: `product-${fromId + i}`,
        retail_price: 1000,
        is_in_stock: true,
      }));

    /** next — абсолютный URL с чужим хостом, как на проде: переходить по нему нельзя */
    const nextUrl = (page: number) => `https://optisport.example/api/v1/products/?page=${page}`;

    /** Отдаёт заранее заданные страницы по параметру page и записывает запросы. */
    const servePages = (
      pages: Record<number, { results: unknown[]; next: string | null } | number>,
      requests: URL[]
    ) => {
      server.use(
        http.get(PRODUCTS_URL, ({ request }) => {
          const url = new URL(request.url);
          requests.push(url);
          const page = pages[Number(url.searchParams.get('page'))];
          if (page === undefined) {
            return HttpResponse.json({ detail: 'Invalid page.' }, { status: 404 });
          }
          if (typeof page === 'number') {
            return HttpResponse.json({ detail: 'error' }, { status: page });
          }
          return HttpResponse.json({ count: 0, previous: null, ...page });
        })
      );
    };

    test('несколько страниц: page_size=100, page=1 и 2, все 130 товаров по порядку', async () => {
      const requests: URL[] = [];
      servePages(
        {
          1: { results: makeProducts(1, 100), next: nextUrl(2) },
          2: { results: makeProducts(101, 130), next: null },
        },
        requests
      );

      const result = await productsService.getAllHits();

      expect(requests).toHaveLength(2);
      requests.forEach((url, index) => {
        expect(url.host).toBe('localhost:8001');
        expect(url.searchParams.get('page_size')).toBe('100');
        expect(url.searchParams.get('page')).toBe(String(index + 1));
        expect(url.searchParams.get('is_hit')).toBe('true');
        expect(url.searchParams.get('ordering')).toBe('category_tree');
        expect(url.searchParams.get('in_stock')).toBe('true');
      });
      expect(result).toHaveLength(130);
      expect(result.map(p => p.id)).toEqual(makeProducts(1, 130).map(p => p.id));
    });

    test('одна страница: next=null — один запрос, 32 товара', async () => {
      const requests: URL[] = [];
      servePages({ 1: { results: makeProducts(1, 32), next: null } }, requests);

      const result = await productsService.getAllHits();

      expect(requests).toHaveLength(1);
      expect(result).toHaveLength(32);
    });

    test('пусто: count=0 — пустой массив', async () => {
      const requests: URL[] = [];
      servePages({ 1: { results: [], next: null } }, requests);

      await expect(productsService.getAllHits()).resolves.toEqual([]);
      expect(requests).toHaveLength(1);
    });

    test('повтор на стыке страниц: товар попадает в результат один раз', async () => {
      const requests: URL[] = [];
      servePages(
        {
          1: { results: makeProducts(1, 100), next: nextUrl(2) },
          2: { results: makeProducts(100, 105), next: null },
        },
        requests
      );

      const result = await productsService.getAllHits();

      expect(result.map(p => p.id)).toEqual(makeProducts(1, 105).map(p => p.id));
    });

    test('сбой первой страницы (500) — вызов отклоняется', { timeout: 20000 }, async () => {
      const requests: URL[] = [];
      servePages({ 1: 500 }, requests);

      await expect(productsService.getAllHits()).rejects.toThrow();
    });

    test('сбой второй страницы (404) — отдаются товары первой страницы', async () => {
      const requests: URL[] = [];
      servePages({ 1: { results: makeProducts(1, 100), next: nextUrl(2) } }, requests);

      const result = await productsService.getAllHits();

      expect(requests).toHaveLength(2);
      expect(result).toHaveLength(100);
    });

    test(
      'сбой второй страницы (500, после повторов api-client) — отдаются товары первой страницы',
      { timeout: 20000 },
      async () => {
        const requests: URL[] = [];
        servePages({ 1: { results: makeProducts(1, 100), next: nextUrl(2) }, 2: 500 }, requests);

        const result = await productsService.getAllHits();

        expect(requests[0].searchParams.get('page')).toBe('1');
        expect(requests.some(url => url.searchParams.get('page') === '2')).toBe(true);
        expect(result).toHaveLength(100);
      }
    );

    test('бесконечная пагинация: не больше 10 запросов, отдаётся собранное', async () => {
      const requests: URL[] = [];
      server.use(
        http.get(PRODUCTS_URL, ({ request }) => {
          const url = new URL(request.url);
          requests.push(url);
          const page = Number(url.searchParams.get('page'));
          return HttpResponse.json({
            count: 99999,
            next: nextUrl(page + 1),
            previous: null,
            results: makeProducts(page, page),
          });
        })
      );

      const result = await productsService.getAllHits();

      expect(requests).toHaveLength(10);
      expect(result.map(p => p.id)).toEqual(makeProducts(1, 10).map(p => p.id));
    });

    test.each([
      ['getAllNew', 'is_new'],
      ['getAllPromo', 'is_promo'],
    ] as const)('%s: фильтр %s, наличие и сортировка', async (method, flag) => {
      const requests: URL[] = [];
      servePages({ 1: { results: makeProducts(1, 12), next: null } }, requests);

      const result = await productsService[method]();

      expect(result).toHaveLength(12);
      expect(requests).toHaveLength(1);
      const params = requests[0].searchParams;
      expect(params.get(flag)).toBe('true');
      expect(params.get('in_stock')).toBe('true');
      expect(params.get('ordering')).toBe('category_tree');
      expect(params.get('page_size')).toBe('100');
      expect(params.get('page')).toBe('1');
    });

    test('getHits по-прежнему запрашивает 8 товаров одной страницей', async () => {
      const requests: URL[] = [];
      server.use(
        http.get(PRODUCTS_URL, ({ request }) => {
          requests.push(new URL(request.url));
          return HttpResponse.json({
            count: 8,
            next: null,
            previous: null,
            results: makeProducts(1, 8),
          });
        })
      );

      await productsService.getHits();

      expect(requests).toHaveLength(1);
      expect(requests[0].searchParams.get('page_size')).toBe('8');
      expect(requests[0].searchParams.has('page')).toBe(false);
    });
  });
});
