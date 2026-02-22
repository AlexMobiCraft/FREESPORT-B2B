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
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
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
  const mockOnAddToCart = vi.fn();
  const mockOnRemoveFavorite = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders product information correctly', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onAddToCart={mockOnAddToCart}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    expect(screen.getByText('Мяч футбольный Nike')).toBeInTheDocument();
    expect(screen.getByText('Артикул: BALL-001')).toBeInTheDocument();
    expect(screen.getByText(/2\s?500/)).toBeInTheDocument(); // Price with locale formatting
  });

  it('shows "В корзину" button when product is available (AC: 5)', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onAddToCart={mockOnAddToCart}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    expect(screen.getByRole('button', { name: /в корзину/i })).toBeInTheDocument();
  });

  it('calls onAddToCart when "В корзину" button is clicked (AC: 5)', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onAddToCart={mockOnAddToCart}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ACT
    const addButton = screen.getByRole('button', { name: /в корзину/i });
    fireEvent.click(addButton);

    // ASSERT
    expect(mockOnAddToCart).toHaveBeenCalledTimes(1);
  });

  it('shows out of stock badge when product is not available (AC: 7)', () => {
    // ARRANGE
    const unavailableFavorite = { ...mockFavorite, isAvailable: false };
    render(
      <FavoriteProductCard
        favorite={unavailableFavorite}
        onAddToCart={mockOnAddToCart}
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
        onAddToCart={mockOnAddToCart}
        onRemoveFavorite={mockOnRemoveFavorite}
      />
    );

    // ASSERT
    const notifyButton = screen.getByRole('button', { name: /сообщить о поступлении/i });
    expect(notifyButton).toBeInTheDocument();
    expect(notifyButton).toBeDisabled();
  });

  it('calls onRemoveFavorite when heart button is clicked (AC: 6)', () => {
    // ARRANGE
    render(
      <FavoriteProductCard
        favorite={mockFavorite}
        onAddToCart={mockOnAddToCart}
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
        onAddToCart={mockOnAddToCart}
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
        onAddToCart={mockOnAddToCart}
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
