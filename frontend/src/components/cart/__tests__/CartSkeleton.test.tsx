/**
 * CartSkeleton Component Tests
 *
 * Покрытие:
 * - Рендеринг skeleton элементов
 * - Accessibility атрибуты
 * - Layout структура
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CartSkeleton } from '../CartSkeleton';

// Mock Skeleton
vi.mock('@/components/ui/Skeleton', () => ({
  Skeleton: ({ className }: { className?: string }) => (
    <div className={className} data-testid="skeleton" />
  ),
}));

describe('CartSkeleton', () => {
  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders skeleton container', () => {
      render(<CartSkeleton />);

      expect(screen.getByTestId('cart-skeleton')).toBeInTheDocument();
    });

    it('renders multiple skeleton elements', () => {
      render(<CartSkeleton />);

      const skeletons = screen.getAllByTestId('skeleton');
      expect(skeletons.length).toBeGreaterThan(0);
    });
  });

  // Layout
  describe('Layout', () => {
    it('has grid layout for content', () => {
      const { container } = render(<CartSkeleton />);

      const grid = container.querySelector('.grid');
      expect(grid).toBeInTheDocument();
      expect(grid).toHaveClass('grid-cols-1');
      expect(grid).toHaveClass('lg:grid-cols-3');
    });

    it('renders 3 cart item skeletons', () => {
      const { container } = render(<CartSkeleton />);

      // Each cart item has an image skeleton (w-20 h-20)
      const itemImageSkeletons = container.querySelectorAll('.w-20.h-20');
      expect(itemImageSkeletons.length).toBe(3);
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('не рендерит собственный main: единственный main — в LayoutWrapper', () => {
      render(<CartSkeleton />);

      expect(screen.queryByRole('main')).not.toBeInTheDocument();
    });

    it('has named region for loading state', () => {
      render(<CartSkeleton />);

      expect(screen.getByRole('region', { name: 'Загрузка корзины' })).toBe(
        screen.getByTestId('cart-skeleton')
      );
    });

    it('has aria-busy for loading indication', () => {
      render(<CartSkeleton />);

      expect(screen.getByTestId('cart-skeleton')).toHaveAttribute('aria-busy', 'true');
    });
  });

  // Условия возврата и поддержка (Story 41.10, FR-41-15)
  describe('ReturnsAndSupportNotice', () => {
    it('renders exactly one returns-support-notice block', () => {
      render(<CartSkeleton />);

      expect(screen.getAllByTestId('returns-support-notice')).toHaveLength(1);
    });
  });

  // Styling
  describe('Styling', () => {
    it('has proper container max-width', () => {
      render(<CartSkeleton />);

      expect(screen.getByTestId('cart-skeleton')).toHaveClass('max-w-[1280px]');
    });

    it('has proper padding', () => {
      render(<CartSkeleton />);

      const container = screen.getByTestId('cart-skeleton');
      expect(container).toHaveClass('px-4');
      expect(container).toHaveClass('lg:px-6');
    });
  });
});
