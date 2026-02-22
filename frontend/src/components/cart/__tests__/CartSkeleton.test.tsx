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
    it('has main landmark with role="main"', () => {
      render(<CartSkeleton />);

      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('has aria-label for loading state', () => {
      render(<CartSkeleton />);

      const main = screen.getByRole('main');
      expect(main).toHaveAttribute('aria-label', 'Загрузка корзины');
    });

    it('has aria-busy for loading indication', () => {
      render(<CartSkeleton />);

      const main = screen.getByRole('main');
      expect(main).toHaveAttribute('aria-busy', 'true');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has proper container max-width', () => {
      render(<CartSkeleton />);

      const main = screen.getByRole('main');
      expect(main).toHaveClass('max-w-[1280px]');
    });

    it('has proper padding', () => {
      render(<CartSkeleton />);

      const main = screen.getByRole('main');
      expect(main).toHaveClass('px-4');
      expect(main).toHaveClass('lg:px-6');
    });
  });
});
