import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import type { NextRequest } from 'next/server';

// Mock NextResponse
vi.mock('next/server', async () => {
  const actual = await vi.importActual<typeof import('next/server')>('next/server');
  return {
    ...actual,
    NextResponse: {
      next: vi.fn(),
      // Настоящий ответ: middleware ставит и удаляет на нём cookie точки возврата (41.18)
      redirect: vi.fn((...args: Parameters<typeof actual.NextResponse.redirect>) =>
        actual.NextResponse.redirect(...args)
      ),
      rewrite: vi.fn(),
    },
  };
});

/**
 * Загружает middleware с чистым модульным состоянием.
 *
 * Кэш опубликованных слагов живёт в переменных модуля, поэтому без
 * `vi.resetModules()` он протекает между тестами и результат начинает
 * зависеть от порядка их выполнения.
 */
async function loadMiddleware() {
  vi.resetModules();
  const server = await import('next/server');
  const mod = await import('../middleware');
  return { middleware: mod.middleware, NextResponse: server.NextResponse };
}

/** Ответ API со списком опубликованных CMS-слагов */
function slugsResponse(slugs: string[]) {
  return {
    ok: true,
    status: 200,
    json: async () => ({
      count: slugs.length,
      next: null,
      results: slugs.map(slug => ({ slug })),
    }),
  };
}

describe('Middleware', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  const createRequest = (pathname: string, hasToken: boolean = false, nextParam?: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    if (nextParam) {
      url.searchParams.set('next', nextParam);
    }

    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) =>
          name === 'refreshToken' && hasToken ? { value: 'token' } : undefined,
      },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;

    // Helper needed because NextRequest clone() is complex to mock fully
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;

    return req;
  };

  it('redirects unauthenticated user to login when accessing protected route', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/profile');
    const response = await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    // Один адрес входа без query, цель — в cookie точки возврата (41.18, D3)
    expect(redirectUrl.pathname).toBe('/login');
    expect(redirectUrl.search).toBe('');
    expect(response?.status).toBe(307);
    const setCookie = response?.headers.get('set-cookie') ?? '';
    expect(setCookie).toContain('loginReturnTo=%2Fprofile');
    expect(setCookie).toContain('Path=/login');
    expect(setCookie).toContain('Max-Age=600');
    expect(setCookie).toContain('SameSite=lax');
    expect(setCookie).not.toContain('Secure');
    // Редирект не должен ходить в сеть за списком слагов
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('allows authenticated user to access protected route', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/profile', true);
    await middleware(req);

    expect(NextResponse.next).toHaveBeenCalled();
  });

  it('redirects authenticated user to home from auth page when no next param', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/login', true);
    await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });

  it('redirects authenticated user to next param url from auth page', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/login', true, '/cart');
    await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const callArgs = (NextResponse.redirect as any).mock.calls[0];
    // NextResponse.redirect(new URL(...))
    const redirectUrl = callArgs[0];
    expect(redirectUrl.pathname).toBe('/cart');
  });

  it('redirects authenticated user to redirect param url from auth page', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const url = new URL('http://localhost:3000/login');
    url.searchParams.set('redirect', '/checkout');
    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) => (name === 'refreshToken' ? { value: 'token' } : undefined),
      },
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;

    await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/checkout');
  });

  it('sanitizes next param: redirects to home if next param is external domain', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/login', true, '//google.com');
    await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });

  it('sanitizes next param: redirects to home if next param does not start with /', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const req = createRequest('/login', true, 'javascript:alert(1)');
    await middleware(req);

    expect(NextResponse.redirect).toHaveBeenCalled();
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const redirectUrl = (NextResponse.redirect as any).mock.calls[0][0];
    expect(redirectUrl.pathname).toBe('/');
  });
});

describe('Middleware: точка возврата после входа (Story 41.18 — AC1/AC2)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  const request = (
    pathAndQuery: string,
    options: { token?: boolean; returnCookie?: string; headers?: Record<string, string> } = {}
  ) => {
    const url = new URL(`http://localhost:3000${pathAndQuery}`);
    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) => {
          if (name === 'refreshToken' && options.token) return { value: 'token' };
          if (name === 'loginReturnTo' && options.returnCookie !== undefined) {
            return { value: options.returnCookie };
          }
          return undefined;
        },
      },
      headers: new Headers(options.headers),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const redirectTarget = (NextResponse: any) => NextResponse.redirect.mock.calls[0][0] as URL;

  it.each(['/profile', '/profile/favorites', '/profile/orders/5'])(
    'гость на %s → 307 /login без query, cookie равна пути',
    async pathname => {
      const { middleware, NextResponse } = await loadMiddleware();
      const response = await middleware(request(pathname));

      const target = redirectTarget(NextResponse);
      expect(target.pathname).toBe('/login');
      expect(target.search).toBe('');
      expect(response?.status).toBe(307);
      expect(response?.cookies.get('loginReturnTo')?.value).toBe(pathname);
    }
  );

  it('query исходного запроса снимается: /profile?tab=1 → /login, cookie /profile', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const response = await middleware(request('/profile?tab=1'));

    const target = redirectTarget(NextResponse);
    expect(target.pathname).toBe('/login');
    expect(target.search).toBe('');
    expect(response?.headers.get('location')).not.toContain('tab=1');
    expect(response?.cookies.get('loginReturnTo')?.value).toBe('/profile');
  });

  it('в production cookie получает Secure', async () => {
    vi.stubEnv('NODE_ENV', 'production');
    const { middleware } = await loadMiddleware();
    const response = await middleware(request('/profile/favorites'));

    const setCookie = response?.headers.get('set-cookie') ?? '';
    expect(setCookie).toContain('loginReturnTo=%2Fprofile%2Ffavorites');
    expect(setCookie).toContain('Secure');
  });

  it.each([
    { 'next-router-prefetch': '1' },
    { purpose: 'prefetch' },
    { 'sec-purpose': 'prefetch;prerender' },
  ] as Record<string, string>[])('prefetch-запрос %o → 307 без Set-Cookie', async headers => {
    const { middleware, NextResponse } = await loadMiddleware();
    const response = await middleware(request('/profile', { headers }));

    expect(redirectTarget(NextResponse).pathname).toBe('/login');
    expect(response?.status).toBe(307);
    expect(response?.headers.get('set-cookie')).toBeNull();
  });

  /** Set-Cookie удаления: пустое значение, тот же Path=/login, срок в прошлом. */
  function expectCookieDeleted(response: Response | undefined) {
    const setCookie = response?.headers.get('set-cookie') ?? '';
    expect(setCookie).toMatch(/loginReturnTo=;/);
    expect(setCookie).toContain('Path=/login');
    expect(setCookie).toMatch(/Expires=Thu, 01 Jan 1970|Max-Age=0/);
  }

  it('авторизованный на /login с cookie и без query → цель из cookie, cookie удалена', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const response = await middleware(
      request('/login', { token: true, returnCookie: '/profile/favorites' })
    );

    expect(redirectTarget(NextResponse).pathname).toBe('/profile/favorites');
    expectCookieDeleted(response);
  });

  it('?next=/cart и cookie → /cart, cookie всё равно удалена', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const response = await middleware(
      request('/login?next=%2Fcart', { token: true, returnCookie: '/profile' })
    );

    expect(redirectTarget(NextResponse).pathname).toBe('/cart');
    expectCookieDeleted(response);
  });

  it('опасный next и cookie → цель из cookie', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    const response = await middleware(
      request('/login?next=https%3A%2F%2Fevil.com', { token: true, returnCookie: '/checkout' })
    );

    expect(redirectTarget(NextResponse).pathname).toBe('/checkout');
    expectCookieDeleted(response);
  });

  it.each(['//evil.com', '/login', 'https://evil.com'])(
    'подменённая cookie %s → "/", cookie удалена',
    async returnCookie => {
      const { middleware, NextResponse } = await loadMiddleware();
      const response = await middleware(request('/login', { token: true, returnCookie }));

      const target = redirectTarget(NextResponse);
      expect(target.origin).toBe('http://localhost:3000');
      expect(target.pathname).toBe('/');
      expectCookieDeleted(response);
    }
  );

  it('редирект на главную не переносит исходную query', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(request('/login?next=%2F%2Fevil.com', { token: true }));

    const target = redirectTarget(NextResponse);
    expect(target.pathname).toBe('/');
    expect(target.search).toBe('');
  });

  it('без cookie в запросе ответ авторизованному не несёт Set-Cookie', async () => {
    const { middleware } = await loadMiddleware();
    const response = await middleware(request('/login?next=%2Fcart', { token: true }));

    expect(response?.headers.get('set-cookie')).toBeNull();
  });
});

describe('Middleware: настоящий 404 для несуществующих адресов', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  it('отдаёт 404 на несуществующий адрес верхнего уровня', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [destination, init] = (NextResponse.rewrite as any).mock.calls[0];
    expect(destination.pathname).toBe('/_not-found');
    expect(init).toEqual({ status: 404 });
    expect(NextResponse.next).not.toHaveBeenCalled();
  });

  it.each(['/terms', '/korzina', '/basket', '/order', '/product'])(
    'отдаёт 404 на фантомный адрес %s из отчёта аудита',
    async pathname => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(anonymousRequest(pathname));

      expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
    }
  );

  it.each(['/examples', '/test', '/design-comparison', '/electric-orange-test', '/electric-orange'])(
    'отдаёт 404 на удалённый демо-маршрут %s',
    async pathname => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(anonymousRequest(pathname));

      expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const [destination, init] = (NextResponse.rewrite as any).mock.calls[0];
      expect(destination.pathname).toBe('/_not-found');
      expect(init).toEqual({ status: 404 });
      expect(NextResponse.next).not.toHaveBeenCalled();
    }
  );

  it('пропускает опубликованную CMS-страницу', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/oferta'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
  });

  it.each(['/about', '/catalog', '/coming-soon', '/electric', '/unsubscribe'])(
    'пропускает известный маршрут %s без обращения к API',
    async pathname => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(anonymousRequest(pathname));

      expect(NextResponse.next).toHaveBeenCalled();
      expect(NextResponse.rewrite).not.toHaveBeenCalled();
      expect(fetchMock).not.toHaveBeenCalled();
    }
  );

  it('защищает страницу отписки от кэша и передачи referrer', async () => {
    const { middleware, NextResponse } = await loadMiddleware();

    await middleware(anonymousRequest('/unsubscribe'));

    expect(NextResponse.next).toHaveBeenCalledWith({
      headers: {
        'Cache-Control': 'no-store',
        'Referrer-Policy': 'no-referrer',
      },
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each(['/', '/foo/bar', '/profile/orders/1'])(
    'не вмешивается в путь %s (не зона catch-all)',
    async pathname => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(anonymousRequest(pathname));

      expect(NextResponse.rewrite).not.toHaveBeenCalled();
      expect(fetchMock).not.toHaveBeenCalled();
    }
  );

  it('fail-open: пропускает запрос, когда backend недоступен', async () => {
    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: пропускает запрос, когда API отвечает ошибкой', async () => {
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) });
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: пропускает запрос, когда ответ API не разобрался', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({ count: 1, next: null, results: 42 }),
    });
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('кэширует список слагов: два запроса подряд дают один вызов API', async () => {
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('запрашивает список слагов заново после истечения TTL', async () => {
    vi.useFakeTimers();
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // TTL — 5 минут; сдвигаем время за его пределы
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('запрашивает список слагов с page_size, покрывающим всю выдачу', async () => {
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).toContain('/pages/');
    expect(requestedUrl).toContain('page_size=1000');
  });

  it('ограничивает запрос списка слагов таймаутом', async () => {
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    const init = fetchMock.mock.calls[0][1] as RequestInit | undefined;
    expect(init?.signal).toBeDefined();
  });

  it('схлопывает параллельные промахи холодного кэша в один запрос к API', async () => {
    // Запрос к API «зависает», пока мы не отпустим его вручную: только так
    // второй запрос попадёт в кэш ровно в момент, когда первый ещё в полёте.
    let releaseFetch: () => void = () => {};
    fetchMock.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          releaseFetch = () => resolve(slugsResponse(['oferta']));
        })
    );

    const { middleware, NextResponse } = await loadMiddleware();

    const first = middleware(anonymousRequest('/offer'));
    const second = middleware(anonymousRequest('/terms'));

    // Второй промах обязан переиспользовать незавершённый запрос первого
    expect(fetchMock).toHaveBeenCalledTimes(1);

    releaseFetch();
    await Promise.all([first, second]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(NextResponse.rewrite).toHaveBeenCalledTimes(2);
  });
});

describe('Middleware: протухший кэш не даёт оснований для 404', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  /** Прогревает кэш слагов и сдвигает время за пределы TTL */
  async function warmCacheAndExpire(middleware: (req: NextRequest) => Promise<unknown>) {
    await middleware(anonymousRequest('/oferta'));
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
  }

  it('вновь опубликованная страница открывается, а не получает 404 из устаревшего списка', async () => {
    vi.useFakeTimers();
    const { middleware, NextResponse } = await loadMiddleware();
    await warmCacheAndExpire(middleware);

    // Страница опубликована уже после того, как кэш был наполнен
    fetchMock.mockImplementationOnce(async () => slugsResponse(['oferta', 'arenda']));
    await middleware(anonymousRequest('/arenda'));

    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(NextResponse.next).toHaveBeenCalledTimes(2);
  });

  it('fail-open: протухший кэш и недоступный backend не дают ложного 404', async () => {
    vi.useFakeTimers();
    const { middleware, NextResponse } = await loadMiddleware();
    await warmCacheAndExpire(middleware);

    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    await middleware(anonymousRequest('/arenda'));

    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(NextResponse.next).toHaveBeenCalledTimes(2);
    expect(warnSpy).toHaveBeenCalled();
  });

  it('положительное решение по протухшему кэшу принимается сразу, обновление идёт фоном', async () => {
    vi.useFakeTimers();
    const { middleware, NextResponse } = await loadMiddleware();
    await warmCacheAndExpire(middleware);

    // Фоновое обновление «зависает» — ответ пользователю ждать его не должен
    fetchMock.mockImplementationOnce(() => new Promise(() => {}));
    await middleware(anonymousRequest('/oferta'));

    expect(NextResponse.next).toHaveBeenCalledTimes(2);
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('Middleware: неполный или невалидный ответ API не становится allowlist-ом', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  /** Ответ API, который не должен приниматься за полный список слагов */
  const apiResponse = (payload: unknown) => ({
    ok: true,
    status: 200,
    json: async () => payload,
  });

  it('fail-open: элемент выдачи без строкового slug', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ count: 2, next: null, results: [{ slug: 'oferta' }, { title: 'без слага' }] })
    );
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: выдача обрезана пагинацией (есть next)', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({
        count: 25,
        next: 'http://backend:8000/api/v1/pages/?page=2',
        results: [{ slug: 'oferta' }],
      })
    );
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: count не совпадает с числом полученных записей', async () => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ count: 25, next: null, results: [{ slug: 'oferta' }] })
    );
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: в ответе нет числового count', async () => {
    // Без count непонятно, полон ли список: принимать его за allowlist нельзя.
    fetchMock.mockResolvedValueOnce(apiResponse({ next: null, results: [{ slug: 'oferta' }] }));
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('fail-open: в ответе нет признака завершённой пагинации', async () => {
    // DRF всегда отдаёт next; его отсутствие означает неизвестную форму ответа.
    fetchMock.mockResolvedValueOnce(apiResponse({ count: 1, results: [{ slug: 'oferta' }] }));
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('пустой список страниц — валидный ответ, а не признак поломки', async () => {
    fetchMock.mockResolvedValueOnce(apiResponse({ count: 0, next: null, results: [] }));
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });
});

describe('Middleware: пауза после неудачного запроса к API', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  it('после сетевого отказа не долбит API до конца паузы, продолжая fail-open', async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const { middleware, NextResponse } = await loadMiddleware();

    await middleware(anonymousRequest('/offer'));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // Пауза ещё держится: нового запроса нет, но и ложного 404 тоже
    vi.advanceTimersByTime(29 * 1000);
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(NextResponse.next).toHaveBeenCalledTimes(2);
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
  });

  it('после окончания паузы снова обращается к API и возвращается к 404', async () => {
    vi.useFakeTimers();
    fetchMock.mockRejectedValueOnce(new Error('ECONNREFUSED'));
    const { middleware, NextResponse } = await loadMiddleware();

    await middleware(anonymousRequest('/offer'));
    vi.advanceTimersByTime(31 * 1000);
    await middleware(anonymousRequest('/offer'));

    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });

  it('пауза включается и на быстрый отказ вида HTTP 500', async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) });
    const { middleware } = await loadMiddleware();

    await middleware(anonymousRequest('/offer'));
    vi.advanceTimersByTime(10 * 1000);
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('успешный ответ паузу не включает: обновление после TTL уходит сразу', async () => {
    vi.useFakeTimers();
    const { middleware } = await loadMiddleware();

    await middleware(anonymousRequest('/offer'));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // TTL истёк — обновление должно уйти немедленно, а не ждать паузы
    vi.advanceTimersByTime(5 * 60 * 1000 + 1);
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('Middleware: запрос к API из edge-рантайма', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  it('помечает внутренний запрос как пришедший по HTTPS', async () => {
    // В проде у backend включён SECURE_SSL_REDIRECT: без этого заголовка Django
    // редиректит http://backend:8000 на https://backend:8000, где TLS нет.
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers['X-Forwarded-Proto']).toBe('https');
  });

  it('fail-open: backend ответил редиректом вместо списка', async () => {
    // Ровно то, что делает SECURE_SSL_REDIRECT при запросе по http://backend:8000.
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 301,
      redirected: true,
      json: async () => ({}),
    });
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('редирект'));
  });

  it('не следует за редиректом молча', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.redirect).toBe('manual');
    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });
});

describe('Middleware: percent-encoded адреса', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['аренда-инвентаря']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  it('опубликованный slug в percent-encoding не получает ложный 404', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest(`/${encodeURIComponent('аренда-инвентаря')}`));

    expect(NextResponse.next).toHaveBeenCalled();
    expect(NextResponse.rewrite).not.toHaveBeenCalled();
  });

  it('несуществующий адрес в percent-encoding по-прежнему отдаёт 404', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest(`/${encodeURIComponent('такой-страницы-нет')}`));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });

  it('битая percent-последовательность не роняет middleware', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/%E0%A4%A'));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });
});

describe('Middleware: matcher', () => {
  it('не применяется к путям API, включая точный /api', async () => {
    // Приблизительная проверка намерения: Next компилирует matcher сам, но
    // отрицательный lookahead в нём — обычная регулярка. Точный `/api` до
    // правки проходил в middleware и перехватывался логикой 404 раньше, чем
    // срабатывал rewrite `/api/:path*` из next.config.ts.
    vi.resetModules();
    const { config } = await import('../middleware');
    const pattern = new RegExp(`^${config.matcher[0]}$`);

    expect(pattern.test('/api')).toBe(false);
    expect(pattern.test('/api/v1/pages/')).toBe(false);
    expect(pattern.test('/robots.txt')).toBe(false);
    expect(pattern.test('/_next/static/chunk.js')).toBe(false);
    expect(pattern.test('/offer')).toBe(true);
    expect(pattern.test('/apiary')).toBe(true);
  });
});

describe('Middleware: строгость признаков ответа и базового URL', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  const apiResponse = (payload: unknown) => ({
    ok: true,
    status: 200,
    json: async () => payload,
  });

  // DRF отдаёт в `next` либо строку-URL, либо null. Любое другое значение —
  // ответ неизвестной формы: считать его признаком завершённой пагинации нельзя,
  // иначе частичный список станет авторитетным allowlist-ом и даст ложные 404.
  it.each([
    ['false', false],
    ['ноль', 0],
    ['пустая строка', ''],
  ])('fail-open: признак next неизвестной формы (%s)', async (_label, nextValue) => {
    fetchMock.mockResolvedValueOnce(
      apiResponse({ count: 1, next: nextValue, results: [{ slug: 'oferta' }] })
    );
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(NextResponse.next).toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalled();
  });

  it('next === null по-прежнему принимается за полный список', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
  });

  it('базовый URL с завершающим слэшем не даёт двойного слэша в пути', async () => {
    // `.../api/v1/` + `/pages/` = `.../api/v1//pages/` — такой адрес backend не
    // обслуживает, и middleware уходил бы в постоянный fail-open.
    vi.stubEnv('NEXT_PUBLIC_API_URL_INTERNAL', 'http://backend:8000/api/v1/');
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    const requestedUrl = String(fetchMock.mock.calls[0][0]);
    expect(requestedUrl).not.toContain('//pages/');
    expect(requestedUrl).toContain('http://backend:8000/api/v1/pages/');
  });

  it('кэш считается протухшим ровно на границе TTL', async () => {
    // AC6 обещает видимость «не позднее TTL»: на точной границе отрицательное
    // решение уже не должно приниматься по старому списку без обновления.
    vi.useFakeTimers();
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));
    expect(fetchMock).toHaveBeenCalledTimes(1);

    vi.advanceTimersByTime(5 * 60 * 1000);
    await middleware(anonymousRequest('/terms'));

    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

describe('Middleware: поддерживаемый лимит числа CMS-страниц', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  const manySlugs = (count: number) => Array.from({ length: count }, (_, i) => `page-${i}`);

  it('предупреждает, когда число страниц подбирается к лимиту выдачи', async () => {
    // Решение владельца: поддерживаемый предел — 1000 CMS-страниц. За ним список
    // обрезается пагинацией, middleware уходит в вечный fail-open и 404 исчезают
    // молча. Предупреждение обязано появиться ДО того, как это случится.
    fetchMock.mockResolvedValueOnce(slugsResponse(manySlugs(900)));
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    // Решение принимается как обычно — предупреждение ничего не ломает
    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('1000'));
  });

  it('при обычном количестве страниц не предупреждает', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
    expect(warnSpy).not.toHaveBeenCalled();
  });

  it('за пределами лимита список считается неполным и middleware уходит в fail-open', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: async () => ({
        count: 1001,
        next: 'http://backend:8000/api/v1/pages/?page=2&page_size=1000',
        results: manySlugs(1000).map(slug => ({ slug })),
      }),
    });
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(NextResponse.next).toHaveBeenCalled();
    expect(warnSpy).toHaveBeenCalledWith(expect.stringContaining('1000'));
  });
});

describe('Middleware: закодированный слэш в адресе', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  // `%2F` разделителем сегментов для Next не является: путь остаётся
  // односегментным и попадает в catch-all `(blue)/[slug]`, то есть в зону 404.
  // Пропускать такой адрес «как многосегментный» — значит вернуть soft-404 с 200.
  it.each([
    ['/foo%2Fbar', 'обычный'],
    ['/%2F', 'только слэш'],
    ['/foo%2f', 'строчная форма и хвостовой слэш'],
  ])('несуществующий адрес с %s закодированным слэшем отдаёт 404 (%s)', async pathname => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest(pathname));

    expect(NextResponse.rewrite).toHaveBeenCalledTimes(1);
    expect(NextResponse.next).not.toHaveBeenCalled();
  });

  it('настоящий многосегментный путь по-прежнему не трогаем', async () => {
    const { middleware, NextResponse } = await loadMiddleware();
    await middleware(anonymousRequest('/foo/bar'));

    expect(NextResponse.rewrite).not.toHaveBeenCalled();
    expect(NextResponse.next).toHaveBeenCalled();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe('Middleware: источник адреса API', () => {
  let fetchMock: ReturnType<typeof vi.fn>;
  let warnSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
    warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
    warnSpy.mockRestore();
    vi.useRealTimers();
  });

  const anonymousRequest = (pathname: string) => {
    const url = new URL(`http://localhost:3000${pathname}`);
    const req = {
      nextUrl: url,
      cookies: { get: () => undefined },
      headers: new Headers(),
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  it('приоритет у выделенной переменной middleware', async () => {
    // Переменная нужна отдельная: общий `NEXT_PUBLIC_API_URL_INTERNAL`,
    // подставленный на этапе сборки, переключил бы на внутренний HTTP-адрес и
    // серверные компоненты CMS-страниц, у которых нет `X-Forwarded-Proto`.
    vi.stubEnv('NEXT_PUBLIC_MIDDLEWARE_API_URL', 'http://backend:8000/api/v1');
    vi.stubEnv('NEXT_PUBLIC_API_URL_INTERNAL', 'http://wrong-host:9999/api/v1');
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(String(fetchMock.mock.calls[0][0])).toContain('http://backend:8000/api/v1/pages/');
  });

  it('без неё используется NEXT_PUBLIC_API_URL_INTERNAL — так работает dev-контейнер', async () => {
    vi.stubEnv('NEXT_PUBLIC_API_URL_INTERNAL', 'http://backend:8000/api/v1');
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(String(fetchMock.mock.calls[0][0])).toContain('http://backend:8000/api/v1/pages/');
  });

  it('завершающий слэш срезается и у выделенной переменной', async () => {
    vi.stubEnv('NEXT_PUBLIC_MIDDLEWARE_API_URL', 'http://backend:8000/api/v1/');
    const { middleware } = await loadMiddleware();
    await middleware(anonymousRequest('/offer'));

    expect(String(fetchMock.mock.calls[0][0])).not.toContain('//pages/');
  });
});

describe('Middleware: усиленный isSafeRedirectUrl (Story 41.12 — AC5/AC6)', () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    vi.clearAllMocks();
    fetchMock = vi.fn(async () => slugsResponse(['oferta']));
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  /** Запрос на /login уже авторизованным пользователем с произвольной query. */
  const authRequest = (query: string) => {
    const url = new URL('http://localhost:3000/login');
    for (const [key, value] of new URLSearchParams(query)) {
      url.searchParams.append(key, value);
    }
    const req = {
      nextUrl: url,
      cookies: {
        get: (name: string) => (name === 'refreshToken' ? { value: 'token' } : undefined),
      },
      url: url.toString(),
    } as unknown as NextRequest;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    req.nextUrl.clone = () => new URL(url.toString()) as any;
    return req;
  };

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const redirectTarget = (NextResponse: any) => NextResponse.redirect.mock.calls[0][0] as URL;

  describe.each(['next', 'redirect'] as const)('один параметр (%s)', param => {
    const safeRows = [
      { encoded: `${param}=%2F`, pathname: '/', search: '', hash: '' },
      { encoded: `${param}=%2Fcheckout`, pathname: '/checkout', search: '', hash: '' },
      { encoded: `${param}=%2Fprofile`, pathname: '/profile', search: '', hash: '' },
      {
        encoded: `${param}=%2Fcatalog%3Fcategory%3Dx%23top`,
        pathname: '/catalog',
        search: '?category=x',
        hash: '#top',
      },
      {
        encoded: `${param}=%2Fdelivery%23pickup`,
        pathname: '/delivery',
        search: '',
        hash: '#pickup',
      },
    ];

    it.each(safeRows)(
      'безопасная цель "$encoded" открывается',
      async ({ encoded, pathname, search, hash }) => {
        const { middleware, NextResponse } = await loadMiddleware();
        await middleware(authRequest(encoded));

        const target = redirectTarget(NextResponse);
        expect(target.pathname).toBe(pathname);
        expect(target.search).toBe(search);
        expect(target.hash).toBe(hash);
      }
    );

    const unsafeRows = [
      '',
      `${param}=`,
      `${param}=https%3A%2F%2Fevil.com`,
      `${param}=%2F%2Fevil.com`,
      `${param}=javascript%3Aalert%281%29`,
      `${param}=%5Cevil.com`,
      `${param}=%2F%5Cevil.com`,
      `${param}=%2Fcatalog%5Citem`,
    ];

    it.each(unsafeRows)('опасная цель "$encoded" → "/"', async encoded => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(authRequest(encoded));

      expect(redirectTarget(NextResponse).pathname).toBe('/');
    });

    it('runtime-значения с обратным слэшем декодируются в один "\\"', () => {
      const cases: Array<[string, string]> = [
        [`${param}=%5Cevil.com`, '\\evil.com'],
        [`${param}=%2F%5Cevil.com`, '/\\evil.com'],
        [`${param}=%2Fcatalog%5Citem`, '/catalog\\item'],
      ];

      for (const [encoded, runtime] of cases) {
        expect(new URLSearchParams(encoded).get(param)).toBe(runtime);
      }
    });

    const authRoutes = [
      '/login',
      '/login/',
      '/login/anything',
      '/login?next=%2Fprofile',
      '/register',
      '/register/',
      '/register/anything',
      '/b2b-register',
      '/b2b-register/',
      '/b2b-register/anything',
      '/password-reset',
      '/password-reset/',
      '/password-reset/confirm/u/t',
      '/foo/../login',
    ];

    it.each(authRoutes)('auth-route %s → "/" (не на запрещённую цель)', async route => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(authRequest(`${param}=${encodeURIComponent(route)}`));

      expect(redirectTarget(NextResponse).pathname).toBe('/');
    });
  });

  describe('оба параметра и приоритет', () => {
    const rows = [
      { encoded: 'next=%2Fcheckout&redirect=%2Fprofile', pathname: '/checkout' },
      { encoded: 'next=%2Fprofile&redirect=https%3A%2F%2Fevil.com', pathname: '/profile' },
      { encoded: 'next=https%3A%2F%2Fevil.com&redirect=%2Fprofile', pathname: '/' },
      { encoded: 'next=%2Flogin%2F&redirect=%2Fprofile', pathname: '/' },
      { encoded: 'next=%2F%5Cevil.com&redirect=%2Fprofile', pathname: '/' },
      { encoded: 'next=&redirect=%2Fprofile', pathname: '/profile' },
      { encoded: 'redirect=%2Fprofile', pathname: '/profile' },
      { encoded: 'next=&redirect=', pathname: '/' },
    ];

    it.each(rows)('$encoded → $pathname', async ({ encoded, pathname }) => {
      const { middleware, NextResponse } = await loadMiddleware();
      await middleware(authRequest(encoded));

      expect(redirectTarget(NextResponse).pathname).toBe(pathname);
    });
  });
});
