import { beforeEach, describe, expect, it, vi } from 'vitest';

import sitemap from '../sitemap';

const response = (body: unknown, ok = true) =>
  ({ ok, json: vi.fn().mockResolvedValue(body) }) as unknown as Response;

const pathOf = (url: string) => new URL(url).pathname + new URL(url).search;

describe('sitemap: публичные категории каталога', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
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
        if (url.includes('/products/')) {
          return Promise.resolve(
            response({ results: [{ slug: 'ball', updated_at: '2026-09-14T00:00:00Z' }], next: null })
          );
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
