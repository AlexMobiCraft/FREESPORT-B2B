/**
 * Skeleton Component Tests
 *
 * Покрытие:
 * - Рендеринг с разными размерами
 * - Варианты скругления
 * - Анимация pulse
 * - Accessibility
 */

import React from 'react';
import { render } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { Skeleton } from '../Skeleton';

describe('Skeleton', () => {
  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders skeleton element', () => {
      const { container } = render(<Skeleton />);

      const skeleton = container.firstChild;
      expect(skeleton).toBeInTheDocument();
    });

    it('has animate-pulse class', () => {
      const { container } = render(<Skeleton />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('animate-pulse');
    });

    it('has neutral background', () => {
      const { container } = render(<Skeleton />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('bg-neutral-200');
    });
  });

  // Custom className
  describe('Custom className', () => {
    it('applies custom className', () => {
      const { container } = render(<Skeleton className="w-32 h-8" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('w-32');
      expect(skeleton).toHaveClass('h-8');
    });

    it('merges custom className with base styles', () => {
      const { container } = render(<Skeleton className="custom-class" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('custom-class');
      expect(skeleton).toHaveClass('animate-pulse');
      expect(skeleton).toHaveClass('bg-neutral-200');
    });
  });

  // Width and Height props
  describe('Width and Height Props', () => {
    it('applies width as number (pixels)', () => {
      const { container } = render(<Skeleton width={100} />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.width).toBe('100px');
    });

    it('applies height as number (pixels)', () => {
      const { container } = render(<Skeleton height={50} />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.height).toBe('50px');
    });

    it('applies width as string', () => {
      const { container } = render(<Skeleton width="50%" />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.width).toBe('50%');
    });

    it('applies height as string', () => {
      const { container } = render(<Skeleton height="100%" />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.height).toBe('100%');
    });

    it('applies both width and height', () => {
      const { container } = render(<Skeleton width={200} height={100} />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.width).toBe('200px');
      expect(skeleton.style.height).toBe('100px');
    });
  });

  // Rounded variants
  describe('Rounded Variants', () => {
    it('applies default rounded-md', () => {
      const { container } = render(<Skeleton />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('rounded-[var(--radius-md)]');
    });

    it('applies rounded-none', () => {
      const { container } = render(<Skeleton rounded="none" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('rounded-none');
    });

    it('applies rounded-sm', () => {
      const { container } = render(<Skeleton rounded="sm" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('rounded-[var(--radius-sm)]');
    });

    it('applies rounded-lg', () => {
      const { container } = render(<Skeleton rounded="lg" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('rounded-[var(--radius-lg)]');
    });

    it('applies rounded-full', () => {
      const { container } = render(<Skeleton rounded="full" />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveClass('rounded-full');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has aria-hidden attribute', () => {
      const { container } = render(<Skeleton />);

      const skeleton = container.firstChild;
      expect(skeleton).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Edge cases
  describe('Edge Cases', () => {
    it('handles undefined width and height gracefully', () => {
      const { container } = render(<Skeleton width={undefined} height={undefined} />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.width).toBe('');
      expect(skeleton.style.height).toBe('');
    });

    it('handles zero values', () => {
      const { container } = render(<Skeleton width={0} height={0} />);

      const skeleton = container.firstChild as HTMLElement;
      expect(skeleton.style.width).toBe('0px');
      expect(skeleton.style.height).toBe('0px');
    });
  });
});
