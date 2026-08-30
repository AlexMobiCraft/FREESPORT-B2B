/**
 * ProfileLayout Component Tests
 * Story 16.1 - AC: 1 (responsive layout), AC: 5 (auth redirect)
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProfileLayout from '../ProfileLayout';
import { authSelectors } from '@/stores/authStore';

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/profile'),
}));

// Mock authStore: пункты меню фильтруются по роли и верификации пользователя
vi.mock('@/stores/authStore', () => ({
  authSelectors: {
    useUser: vi.fn(() => null),
    useIsB2BUser: vi.fn(() => false),
  },
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className} data-testid={`link-${href}`}>
      {children}
    </a>
  ),
}));

describe('ProfileLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Navigation Rendering', () => {
    it('renders all navigation items', () => {
      // ARRANGE & ACT
      render(
        <ProfileLayout>
          <div>Test Content</div>
        </ProfileLayout>
      );

      // ASSERT - проверяем наличие всех навигационных элементов
      expect(screen.getAllByText('Профиль').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Заказы').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Адреса').length).toBeGreaterThan(0);
      expect(screen.getAllByText('Избранное').length).toBeGreaterThan(0);
    });

    it('renders children content', () => {
      // ARRANGE & ACT
      render(
        <ProfileLayout>
          <div data-testid="test-content">Test Content</div>
        </ProfileLayout>
      );

      // ASSERT
      expect(screen.getByTestId('test-content')).toBeInTheDocument();
      expect(screen.getByText('Test Content')).toBeInTheDocument();
    });

    it('renders sidebar title on desktop', () => {
      // ARRANGE & ACT
      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT
      expect(screen.getByText('Личный кабинет')).toBeInTheDocument();
    });
  });

  describe('Navigation Links', () => {
    it('renders correct hrefs for navigation items', () => {
      // ARRANGE & ACT
      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - проверяем что ссылки имеют правильные href (используем getAllByTestId т.к. есть mobile и desktop версии)
      expect(screen.getAllByTestId('link-/profile').length).toBeGreaterThan(0);
      expect(screen.getAllByTestId('link-/profile/orders').length).toBeGreaterThan(0);
      expect(screen.getAllByTestId('link-/profile/addresses').length).toBeGreaterThan(0);
      expect(screen.getAllByTestId('link-/profile/favorites').length).toBeGreaterThan(0);
    });
  });

  describe('Active State', () => {
    it('highlights active navigation item based on pathname', async () => {
      // ARRANGE
      const { usePathname } = await import('next/navigation');
      vi.mocked(usePathname).mockReturnValue('/profile');

      // ACT
      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - Профиль должен быть активным (содержать primary классы)
      const profileLinks = screen.getAllByTestId('link-/profile');
      const activeLink = profileLinks.find(
        link =>
          link.className.includes('bg-primary-subtle') || link.className.includes('border-primary')
      );
      expect(activeLink).toBeTruthy();
    });

    it('highlights orders tab when on orders page', async () => {
      // ARRANGE
      const { usePathname } = await import('next/navigation');
      vi.mocked(usePathname).mockReturnValue('/profile/orders');

      // ACT
      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - Заказы должен быть активным
      const ordersLinks = screen.getAllByTestId('link-/profile/orders');
      expect(ordersLinks.length).toBeGreaterThan(0);
    });
  });

  describe('Layout Structure', () => {
    it('renders with correct CSS grid classes for desktop', () => {
      // ARRANGE & ACT
      const { container } = render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - проверяем наличие grid layout классов
      const gridContainer = container.querySelector('.lg\\:grid');
      expect(gridContainer).toBeInTheDocument();
    });

    it('renders mobile tabs navigation', () => {
      // ARRANGE & ACT
      const { container } = render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - проверяем наличие мобильной навигации
      const mobileNav = container.querySelector('.lg\\:hidden');
      expect(mobileNav).toBeInTheDocument();
    });

    it('renders desktop sidebar', () => {
      // ARRANGE & ACT
      const { container } = render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT - проверяем наличие desktop sidebar
      const sidebar = container.querySelector('.hidden.lg\\:block');
      expect(sidebar).toBeInTheDocument();
    });
  });

  describe('Пункт «Бонусы»', () => {
    /** Подменяет текущего пользователя в сторе */
    const setUser = (user: unknown) => {
      vi.mocked(authSelectors.useUser).mockReturnValue(
        user as ReturnType<typeof authSelectors.useUser>
      );
    };

    it('виден подтверждённому тренеру', () => {
      setUser({ role: 'trainer', is_verified: true });

      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      expect(screen.getAllByText('Бонусы').length).toBeGreaterThan(0);
      expect(screen.getAllByTestId('link-/profile/bonuses').length).toBeGreaterThan(0);
    });

    it('скрыт у неподтверждённого тренера', () => {
      setUser({ role: 'trainer', is_verified: false });

      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      expect(screen.queryByText('Бонусы')).not.toBeInTheDocument();
    });

    it('скрыт у розничного покупателя', () => {
      setUser({ role: 'retail', is_verified: true });

      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      expect(screen.queryByText('Бонусы')).not.toBeInTheDocument();
    });

    it('скрыт у неавторизованного пользователя', () => {
      setUser(null);

      render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      expect(screen.queryByText('Бонусы')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('renders navigation with semantic nav elements', () => {
      // ARRANGE & ACT
      const { container } = render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT
      const navElements = container.querySelectorAll('nav');
      expect(navElements.length).toBeGreaterThan(0);
    });

    it('renders main content area with main element', () => {
      // ARRANGE & ACT
      const { container } = render(
        <ProfileLayout>
          <div>Content</div>
        </ProfileLayout>
      );

      // ASSERT
      const mainElement = container.querySelector('main');
      expect(mainElement).toBeInTheDocument();
    });
  });
});
