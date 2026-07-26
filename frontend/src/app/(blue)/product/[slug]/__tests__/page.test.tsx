/**
 * Unit тесты для Product Detail Page (SSR)
 * Тестирует серверный вызов getUserRole и ролевое ценообразование
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { cookies } from 'next/headers';

// Mock Next.js modules
vi.mock('next/headers', () => ({
  cookies: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  notFound: vi.fn(),
}));

vi.mock('@/services/productsService', () => ({
  default: {
    getProductBySlug: vi.fn(),
  },
}));

// Mock components to avoid issues during import
vi.mock('@/components/product/ProductBreadcrumbs', () => ({ default: () => null }));
vi.mock('@/components/product/ProductInfo', () => ({ default: () => null }));
vi.mock('@/components/product/ProductSpecs', () => ({ default: () => null }));
vi.mock('@/components/product/ProductImageGallery', () => ({ default: () => null }));

import { getUserRole } from '@/utils/server-auth';

// Mock getUserRole

describe('Product Detail Page - SSR getUserRole', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Сброс переменных окружения
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8001';
  });

  it('должен вернуть guest когда нет sessionid cookie', async () => {
    // Arrange
    const mockCookieStore = {
      get: vi.fn().mockReturnValue(undefined),
    };
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );

    // Act
    await getUserRole();

    // Assert - проверяем что cookies.get был вызван
    expect(mockCookieStore.get).toHaveBeenCalledWith('sessionid');
    expect(mockCookieStore.get).toHaveBeenCalledWith('fs_session');
  });

  it('должен вернуть guest когда API вернул 401', async () => {
    // Arrange
    const mockCookieStore = {
      get: vi.fn().mockReturnValue({ value: 'test-session-id' }),
    };
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );

    // Mock fetch для возврата 401
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
    });

    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('guest');
  });

  it('должен вернуть роль retail для розничного покупателя', async () => {
    // Arrange
    const mockCookieStore = {
      get: vi.fn().mockReturnValue({ value: 'test-session-id' }),
    };
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );

    // Mock fetch для возврата профиля retail пользователя
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        id: 1,
        email: 'customer@example.com',
        role: 'retail',
        first_name: 'Иван',
        last_name: 'Петров',
      }),
    });

    // Act
    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('retail');
  });

  it('должен вернуть роль wholesale_level1 для оптового покупателя', async () => {
    // Arrange
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 2,
        email: 'wholesale@example.com',
        role: 'wholesale_level1',
        company_name: 'ООО Спорт',
        tax_id: '1234567890',
      }),
    });

    // Act
    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('wholesale_level1');
  });

  it('должен вернуть роль trainer для тренера', async () => {
    // Arrange
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 3,
        email: 'trainer@example.com',
        role: 'trainer',
      }),
    });

    // Act
    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('trainer');
  });

  it('должен вернуть роль federation_rep для представителя федерации', async () => {
    // Arrange
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 4,
        email: 'fed@example.com',
        role: 'federation_rep',
      }),
    });

    // Act
    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('federation_rep');
  });

  it('должен обработать ошибку сети и вернуть guest', async () => {
    // Arrange
    const mockCookieStore = {
      get: vi.fn().mockReturnValue({ value: 'test-session-id' }),
    };
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );

    // Mock fetch для выброса ошибки сети
    global.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('guest');
  });

  it('должен использовать fallback retail для неизвестной роли', async () => {
    // Arrange
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: 5,
        email: 'unknown@example.com',
        role: 'unknown_role', // Невалидная роль
      }),
    });

    // Act
    // Act
    const role = await getUserRole();

    // Assert
    expect(role).toBe('retail');
  });

  it('должен корректно передать Cookie header в запросе', async () => {
    // Arrange
    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ role: 'retail' }),
    });
    global.fetch = fetchSpy;

    const sessionId = 'abc123-session-id';
    const mockCookieStore = {
      get: vi.fn().mockReturnValue({ value: sessionId }),
    };
    vi.mocked(cookies).mockResolvedValue(
      mockCookieStore as unknown as Awaited<ReturnType<typeof cookies>>
    );

    // Act
    // Act
    await getUserRole();

    // Assert
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8001/api/v1/users/profile/',
      expect.objectContaining({
        headers: expect.objectContaining({
          Cookie: 'sessionid=abc123-session-id',
        }),
      })
    );
  });

  it('должен использовать переменную окружения NEXT_PUBLIC_API_URL', async () => {
    // Arrange
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8001';

    const fetchSpy = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ role: 'retail' }),
    });
    global.fetch = fetchSpy;

    // Act
    await getUserRole();

    // Assert
    expect(fetchSpy).toHaveBeenCalledWith(
      'http://localhost:8001/api/v1/users/profile/',
      expect.anything()
    );
  });
});
