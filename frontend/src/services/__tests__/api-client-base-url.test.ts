/**
 * Выбор baseURL серверного apiClient.
 * @vitest-environment node
 *
 * На этапе `next build` INTERNAL_API_URL нет — он задаётся только в рантайме компоуза.
 * Раньше клиент в этом случае уходил на заглушку localhost:8001, запрос падал, и
 * /home вмораживал в пререндер пустой список брендов до первой ISR-ревалидации.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';

const loadBaseUrl = async () => {
  vi.resetModules();
  const { default: apiClient } = await import('../api-client');
  return apiClient.defaults.baseURL;
};

describe('apiClient: baseURL на сервере', () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it('берёт INTERNAL_API_URL, когда он задан (рантайм прод-контейнера)', async () => {
    vi.stubEnv('INTERNAL_API_URL', 'http://backend:8000');
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://optisport.ru/api/v1');

    expect(await loadBaseUrl()).toBe('http://backend:8000/api/v1');
  });

  it('без внутренних адресов уходит на публичный NEXT_PUBLIC_API_URL (этап сборки)', async () => {
    vi.stubEnv('INTERNAL_API_URL', '');
    vi.stubEnv('NEXT_PUBLIC_API_URL_INTERNAL', '');
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'https://optisport.ru/api/v1');

    expect(await loadBaseUrl()).toBe('https://optisport.ru/api/v1');
  });

  it('NEXT_PUBLIC_API_URL_INTERNAL приоритетнее публичного адреса (dev-контейнер)', async () => {
    vi.stubEnv('INTERNAL_API_URL', '');
    vi.stubEnv('NEXT_PUBLIC_API_URL_INTERNAL', 'http://backend:8000/api/v1');
    vi.stubEnv('NEXT_PUBLIC_API_URL', 'http://localhost/api/v1');

    expect(await loadBaseUrl()).toBe('http://backend:8000/api/v1');
  });
});
