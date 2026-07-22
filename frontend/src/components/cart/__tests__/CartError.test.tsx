/**
 * CartError Component Tests
 *
 * Покрытие:
 * - Рендеринг сообщения об ошибке
 * - Кнопка retry
 * - Accessibility
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { CartError } from '../CartError';

// Mock Breadcrumb
vi.mock('@/components/ui', () => ({
  Breadcrumb: ({ items }: { items: { label: string }[] }) => (
    <nav aria-label="Breadcrumb">
      {items.map((item, i) => (
        <span key={i}>{item.label}</span>
      ))}
    </nav>
  ),
}));

describe('CartError', () => {
  const defaultProps = {
    error: 'Тестовая ошибка',
    onRetry: vi.fn(),
  };

  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders error container', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByTestId('cart-error')).toBeInTheDocument();
    });

    it('renders error icon', () => {
      const { container } = render(<CartError {...defaultProps} />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('text-red-500');
    });

    it('renders "Ошибка загрузки" heading', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Ошибка загрузки');
    });

    it('renders error message', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByText('Тестовая ошибка')).toBeInTheDocument();
    });

    it('renders description text', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByText(/Не удалось загрузить корзину/)).toBeInTheDocument();
    });
  });

  // Retry Button
  describe('Retry Button', () => {
    it('renders retry button', () => {
      render(<CartError {...defaultProps} />);

      const button = screen.getByTestId('cart-retry-button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent('Повторить');
    });

    it('calls onRetry when clicked', () => {
      const mockRetry = vi.fn();
      render(<CartError error="Error" onRetry={mockRetry} />);

      const button = screen.getByTestId('cart-retry-button');
      fireEvent.click(button);

      expect(mockRetry).toHaveBeenCalledTimes(1);
    });

    it('button has correct styling', () => {
      render(<CartError {...defaultProps} />);

      const button = screen.getByTestId('cart-retry-button');
      expect(button).toHaveClass('h-12');
      expect(button).toHaveClass('bg-primary');
    });
  });

  // Breadcrumb
  describe('Breadcrumb', () => {
    it('renders breadcrumb navigation', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument();
    });
  });

  // Page Title
  describe('Page Title', () => {
    it('renders page title "Ваша корзина"', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ваша корзина');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has main landmark with role="main"', () => {
      render(<CartError {...defaultProps} />);

      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('error icon has aria-hidden', () => {
      const { container } = render(<CartError {...defaultProps} />);

      const icons = container.querySelectorAll('svg');
      // First icon is AlertCircle
      expect(icons[0]).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Different error messages
  describe('Error Messages', () => {
    it('displays custom error message', () => {
      render(<CartError error="Сервер недоступен" onRetry={vi.fn()} />);

      expect(screen.getByText('Сервер недоступен')).toBeInTheDocument();
    });

    it('displays long error message', () => {
      const longError = 'Очень длинное сообщение об ошибке, которое должно отображаться корректно';
      render(<CartError error={longError} onRetry={vi.fn()} />);

      expect(screen.getByText(longError)).toBeInTheDocument();
    });
  });
});
