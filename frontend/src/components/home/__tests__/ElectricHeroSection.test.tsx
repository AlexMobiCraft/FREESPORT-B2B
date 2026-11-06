/**
 * Fallback-картинка hero темы Electric (стори 41.6, AC5).
 *
 * Компонент подставляет `/hero-fallback.jpg`, когда баннер из API не пришёл:
 * `currentBanner?.image_url || '/hero-fallback.jpg'`. До стори 41.6 файл носил
 * имя соцпревью, хотя на деле работал заглушкой hero. Простое удаление файла
 * (как предполагал текст эпика) дало бы битую картинку ровно в момент
 * недоступности API баннеров.
 *
 * Проверяется именно эта ветка: SSR отдаёт скелетон, а сам fallback виден
 * только после того, как клиентский запрос баннеров завершился ошибкой.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { ElectricHeroSection } from '../ElectricHeroSection';
import { useAuthStore } from '@/stores/authStore';
import bannersService from '@/services/bannersService';
import type { User } from '@/types/api';

vi.mock('@/stores/authStore');
vi.mock('@/services/bannersService');

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

/** Гость без баннеров из API — состояние, в котором работает fallback */
function mockGuestWithoutBanners(failure: 'error' | 'empty') {
  if (failure === 'error') {
    vi.mocked(bannersService.getActive).mockRejectedValue(new Error('API Error'));
  } else {
    vi.mocked(bannersService.getActive).mockResolvedValue([]);
  }

  vi.mocked(useAuthStore).mockReturnValue({
    user: null,
    isAuthenticated: false,
    accessToken: null,
    setTokens: vi.fn(),
    setUser: vi.fn(),
    logout: vi.fn(),
    getRefreshToken: vi.fn(),
  });
}

describe('ElectricHeroSection: fallback-картинка', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('показывает /hero-fallback.jpg при ошибке API баннеров', async () => {
    mockGuestWithoutBanners('error');

    render(<ElectricHeroSection />);

    const image = await screen.findByAltText('OPTISPORT');
    expect(image).toHaveAttribute('src', '/hero-fallback.jpg');
  });

  it('показывает /hero-fallback.jpg при пустом ответе API баннеров', async () => {
    mockGuestWithoutBanners('empty');

    render(<ElectricHeroSection />);

    const image = await screen.findByAltText('OPTISPORT');
    expect(image).toHaveAttribute('src', '/hero-fallback.jpg');
  });
});

/** Авторизованный клиент с ролью `role` без баннеров из API */
function mockUserWithoutBanners(role: User['role'], failure: 'error' | 'empty') {
  if (failure === 'error') {
    vi.mocked(bannersService.getActive).mockRejectedValue(new Error('API Error'));
  } else {
    vi.mocked(bannersService.getActive).mockResolvedValue([]);
  }

  vi.mocked(useAuthStore).mockReturnValue({
    user: {
      id: 7,
      email: `${role}@test.com`,
      first_name: 'Test',
      last_name: 'B2B',
      phone: '+79001234567',
      role,
    },
    isAuthenticated: true,
    accessToken: 'mock-token',
    setTokens: vi.fn(),
    setUser: vi.fn(),
    logout: vi.fn(),
    getRefreshToken: vi.fn(),
  });
}

// Роли vip и special_price назначает менеджер или 1С, но резервный баннер у них оптовый, как у
// остальных B2B. Без условия для них баннер откатился бы на универсальный, гостевой.
describe.each(['vip', 'special_price'] as const)(
  'ElectricHeroSection: резервный оптовый баннер для роли %s',
  role => {
    beforeEach(() => {
      vi.clearAllMocks();
    });

    it.each(['error', 'empty'] as const)('показывает оптовый баннер: %s', async failure => {
      mockUserWithoutBanners(role, failure);

      render(<ElectricHeroSection />);

      expect(await screen.findByText('ОПТОВЫЕ ПОСТАВКИ СПОРТИВНЫХ ТОВАРОВ')).toBeInTheDocument();
      expect(screen.queryByText('OPTISPORT — ВАШ СПОРТИВНЫЙ ПАРТНЁР')).not.toBeInTheDocument();
    });
  }
);
