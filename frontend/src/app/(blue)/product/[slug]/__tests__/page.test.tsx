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
vi.mock('@/components/product/ProductPageClient', () => ({ default: () => null }));

import { getUserRole } from '@/utils/server-auth';
import productsService from '@/services/productsService';
import { generateMetadata } from '../page';

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

describe('Product Detail Page - generateMetadata', () => {
  const baseProduct = {
    id: 1,
    slug: 'mjach-futbolnyj-gibridnyj-no4',
    name: 'Мяч футбольный гибридный №4',
    sku: 'BALL-4',
    brand: 'Без ТМ',
    brand_slug: 'bez-tm',
    description: 'Гибридный мяч для тренировок',
    price: { retail: 1000, currency: 'RUB' },
    stock_quantity: 1,
    images: [],
    category: { id: 1, name: 'Мячи', slug: 'balls', breadcrumbs: [] },
    is_in_stock: true,
    can_be_ordered: true,
  };

  async function metadataFor(overrides: Record<string, unknown>) {
    vi.mocked(productsService.getProductBySlug).mockResolvedValue({
      ...baseProduct,
      ...overrides,
    } as Awaited<ReturnType<typeof productsService.getProductBySlug>>);
    return generateMetadata({ params: Promise.resolve({ slug: baseProduct.slug }) });
  }

  it.each([
    ['Без ТМ', 'bez-tm'],
    ['No Brand', 'no-brand'],
    ['Без бренда', 'bez-brenda'],
    ['', ''],
    ['  ', ''],
    ['-', ''],
  ])('не добавляет в title заглушку бренда «%s»', async (brand, brand_slug) => {
    const metadata = await metadataFor({ brand, brand_slug });
    expect(metadata.title).toBe('Мяч футбольный гибридный №4 | OPTISPORT');
  });

  it('узнаёт заглушку по имени, если slug отличается', async () => {
    const metadata = await metadataFor({ brand: 'Без ТМ', brand_slug: 'bez-tm-2' });
    expect(metadata.title).toBe('Мяч футбольный гибридный №4 | OPTISPORT');
  });

  it('сохраняет настоящий бренд в title', async () => {
    const metadata = await metadataFor({ brand: ' BoyBo ', brand_slug: 'boybo' });
    expect(metadata.title).toBe('Мяч футбольный гибридный №4 - BoyBo | OPTISPORT');
  });

  it('отдаёт description без тегов, не длиннее 160 и без разрыва слова', async () => {
    const description = `Коврик<br>для йоги<br />${'материал NBR '.repeat(20)}`;
    const metadata = await metadataFor({ description });

    // 160-й символ приходится на «м» двенадцатого «материал» — слово отбрасывается целиком
    const expected = `Коврик для йоги ${Array(11).fill('материал NBR').join(' ')}`;
    expect(metadata.description).toBe(expected);
    expect(expected.length).toBeLessThanOrEqual(160);
    expect(metadata.openGraph?.description).toBe(expected);
    expect(metadata.twitter?.description).toBe(expected);
  });
});
