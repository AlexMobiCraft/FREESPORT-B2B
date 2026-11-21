/**
 * FavoriteProductCard Component Tests
 * Story 16.3: Управление избранными товарами (AC: 4, 5, 6, 7)
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { FavoriteProductCard } from './FavoriteProductCard';
import type { FavoriteWithAvailability } from '@/types/favorite';

// Mock next/image
vi.mock('next/image', () => ({
  default: () => <div data-testid="next-image-mock" />,
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: { children: React.ReactNode; href: string } & React.AnchorHTMLAttributes<HTMLAnchorElement>) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const mockFavorite: FavoriteWithAvailability = {
  id: 1,
  product: 10,
  product_name: 'Мяч футбольный Nike',
  product_price: '2500.00',
  product_image: '/images/ball.jpg',
  product_slug: 'myach-futbolny-nike',
  product_sku: 'BALL-001',
  created_at: '2025-01-01T00:00:00Z',
  isAvailable: true,
  variantId: 101,
  stockQuantity: 10,
};

describe('FavoriteProductCard', () => {
  const mockOnRemoveFavorite = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders product information correctly', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    expect(screen.getByText('Мяч футбольный Nike')).toBeInTheDocument();
    expect(screen.getByText('Артикул: BALL-001')).toBeInTheDocument();
    expect(screen.getByText(/2\s?500/)).toBeInTheDocument(); // Price with locale formatting
  });

  it('«Выбрать» ведёт на страницу товара вместо добавления в корзину', () => {
    // ARRANGE
    render(<FavoriteProductCard favorite={mockFavorite} onRemoveFavorite={mockOnRemoveFavorite} />);

    // ASSERT
    expect(screen.getByRole('link', { name: 'Выбрать Мяч футбольный Nike' })).toHaveAttribute(
      'href',
      '/product/myach-futbolny-nike'
    );
    expect(screen.queryByRole('button', { name: /в корзину/i })).not.toBeInTheDocument();
  });

  it('shows out of stock badge when product is not available (AC: 7)', () => {
    // ARRANGE
    const unavailableFavorite = { ...mockFavorite, isAvailable: false };
    render(
      <FavoriteProductCard
        favorite={unavailableFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    expect(screen.getByTestId('out-of-stock-badge')).toBeInTheDocument();
    expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
  });

  it('shows disabled button with alternative text when product is not available (AC: 7)', () => {
    // ARRANGE
    const unavailableFavorite = { ...mockFavorite, isAvailable: false };
    render(
      <FavoriteProductCard
        favorite={unavailableFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    const notifyButton = screen.getByRole('button', { name: /сообщить о поступлении/i });
    expect(notifyButton).toBeInTheDocument();
    expect(notifyButton).toBeDisabled();
    expect(screen.queryByRole('link', { name: /^выбрать/i })).not.toBeInTheDocument();
  });

  it('calls onRemoveFavorite when heart button is clicked (AC: 6)', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ACT
    const removeButton = screen.getByRole('button', { name: /удалить из избранного/i });
    fireEvent.click(removeButton);

    // ASSERT
    expect(mockOnRemoveFavorite).toHaveBeenCalledTimes(1);
  });

  it('applies opacity when isRemoving is true', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
        isRemoving={true}
      />
    );

    // ASSERT
    const card = screen.getByTestId('favorite-card');
    expect(card).toHaveClass('opacity-50');
  });

  it('has link to product page', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    const links = screen.getAllByRole('link');
    const productLink = links.find(
      link => link.getAttribute('href') === '/product/myach-futbolny-nike'
    );
    expect(productLink).toBeInTheDocument();
  });
});
