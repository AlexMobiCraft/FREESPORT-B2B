/**
 * EmptyCart Component Tests
 *
 * Покрытие:
 * - Рендеринг иконки, текста, кнопки
 * - Навигация в каталог
 * - Accessibility
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { EmptyCart } from '../EmptyCart';

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

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

describe('EmptyCart', () => {
  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders empty cart component', () => {
      render(<EmptyCart />);

      expect(screen.getByTestId('empty-cart')).toBeInTheDocument();
    });

    it('renders shopping cart icon', () => {
      const { container } = render(<EmptyCart />);

      const icon = container.querySelector('svg');
      expect(icon).toBeInTheDocument();
      expect(icon).toHaveClass('w-16', 'h-16');
    });

    it('renders "Ваша корзина пуста" heading', () => {
      render(<EmptyCart />);

      expect(screen.getByRole('heading', { level: 2 })).toHaveTextContent('Ваша корзина пуста');
    });

    it('renders subtitle text', () => {
      render(<EmptyCart />);

      expect(screen.getByText('Добавьте товары из каталога')).toBeInTheDocument();
    });
  });

  // CTA Button
  describe('CTA Button', () => {
    it('renders "В каталог" button', () => {
      render(<EmptyCart />);

      const button = screen.getByTestId('go-to-catalog-button');
      expect(button).toBeInTheDocument();
      expect(button).toHaveTextContent('В каталог');
    });

    it('button links to /catalog', () => {
      render(<EmptyCart />);

      const button = screen.getByTestId('go-to-catalog-button');
      expect(button).toHaveAttribute('href', '/catalog');
    });

    it('button has correct styling classes', () => {
      render(<EmptyCart />);

      const button = screen.getByTestId('go-to-catalog-button');
      expect(button).toHaveClass('h-12');
      expect(button).toHaveClass('bg-primary');
    });
  });

  // Breadcrumb
  describe('Breadcrumb', () => {
    it('renders breadcrumb navigation', () => {
      render(<EmptyCart />);

      expect(screen.getByRole('navigation', { name: /breadcrumb/i })).toBeInTheDocument();
    });

    it('shows correct breadcrumb items', () => {
      render(<EmptyCart />);

      expect(screen.getByText('Главная')).toBeInTheDocument();
      expect(screen.getByText('Корзина')).toBeInTheDocument();
    });
  });

  // Page Title
  describe('Page Title', () => {
    it('renders page title "Ваша корзина"', () => {
      render(<EmptyCart />);

      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ваша корзина');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has main landmark with role="main"', () => {
      render(<EmptyCart />);

      expect(screen.getByRole('main')).toBeInTheDocument();
    });

    it('icon has aria-hidden', () => {
      const { container } = render(<EmptyCart />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Styling
  describe('Styling', () => {
    it('has centered content layout', () => {
      const { container } = render(<EmptyCart />);

      const contentBox = container.querySelector('.flex-col.items-center');
      expect(contentBox).toBeInTheDocument();
    });

    it('has proper container max-width', () => {
      render(<EmptyCart />);

      const main = screen.getByRole('main');
      expect(main).toHaveClass('max-w-[1280px]');
    });
  });
});
