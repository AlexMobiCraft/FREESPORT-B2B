/**
 * Unit Tests для authService - Story 31.2
 * Тестирование метода logoutFromServer()
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import authService from '@/services/authService';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

describe('AuthService - logoutFromServer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    server.resetHandlers();
  });

  /**
   * AC 1: authService.logout() отправляет POST запрос на /auth/logout/
   * AC 2: Request body содержит { refresh: token_value }
   */
  it('sends POST request to /auth/logout/ with refresh token', async () => {
    const refreshToken = 'test-refresh-token';
    let capturedMethod = '';
    let capturedUrl = '';
    let capturedBody: unknown = null;

    // Override handler для захвата request
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, async ({ request }) => {
        capturedMethod = request.method;
        capturedUrl = request.url;
        capturedBody = await request.json();
        return new HttpResponse(null, { status: 204 });
      })
    );

    await authService.logoutFromServer(refreshToken);

    expect(capturedMethod).toBe('POST');
    expect(capturedUrl).toContain('/auth/logout/');
    expect(capturedBody).toEqual({ refresh: refreshToken });
  });

  /**
   * AC 3: При успехе (204) возвращается resolved Promise
   */
  it('resolves on 204 response', async () => {
    const refreshToken = 'valid-refresh-token';

    await expect(authService.logoutFromServer(refreshToken)).resolves.toBeUndefined();
  });

  /**
   * AC 4: При ошибке (400) не выбрасывает исключение (fail-safe)
   */
  it('does not throw on 400 response - missing token', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return HttpResponse.json({ error: 'Refresh token is required' }, { status: 400 });
      })
    );

    await expect(authService.logoutFromServer('')).resolves.toBeUndefined();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  /**
   * AC 4: При ошибке (400) - invalid token не выбрасывает исключение
   */
  it('does not throw on 400 response - invalid token', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const invalidToken = 'invalid-refresh-token';

    await expect(authService.logoutFromServer(invalidToken)).resolves.toBeUndefined();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  /**
   * AC 4: При ошибке (401) не выбрасывает исключение
   */
  it('does not throw on 401 response', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return HttpResponse.json({ detail: 'Unauthorized' }, { status: 401 });
      })
    );

    await expect(authService.logoutFromServer('some-token')).resolves.toBeUndefined();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });

  /**
   * AC 4: При network error не выбрасывает исключение
   */
  it('does not throw on network error', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    server.use(
      http.post(`${API_BASE_URL}/auth/logout/`, () => {
        return HttpResponse.error();
      })
    );

    await expect(authService.logoutFromServer('some-token')).resolves.toBeUndefined();
    expect(consoleSpy).toHaveBeenCalled();
    consoleSpy.mockRestore();
  });
});
