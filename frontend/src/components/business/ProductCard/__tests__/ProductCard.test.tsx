/**
 * ProductCard Component Tests
 *
 * Comprehensive test suite covering:
 * - Grid/List/Compact layouts
 * - Role-based pricing
 * - Badge logic
 * - Interactivity (add to cart, favorite)
 * - Accessibility attributes
 *
 * Target coverage: >= 80%
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from 'react';
import { ProductCard } from '../ProductCard';
import type { Product } from '@/types/api';
import type { ProductBadgeProps } from '@/components/common/ProductBadge';

type MockImageProps = ComponentProps<'img'> & { src: string; alt: string; fill?: boolean };
type MockHeartProps = ComponentProps<'svg'> & { fill?: string };
type MockButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode };
type MockCnArgs = Array<string | false | null | undefined>;

// Mock Next.js Image component
// Mock Next.js Image component
vi.mock('next/image', () => ({
  default: ({ src, alt, fill, ...rest }: MockImageProps) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} {...rest} data-fill={fill} />
  ),
}));

// Mock lucide-react icons
vi.mock('lucide-react', () => ({
  Heart: ({ className, fill }: MockHeartProps) => (
    <svg data-testid="heart-icon" className={className} data-fill={fill ?? undefined} />
  ),
}));

// Mock ProductBadge component
vi.mock('@/components/common/ProductBadge', () => ({
  ProductBadge: ({ product }: ProductBadgeProps) => {
    if (product.is_sale && product.discount_percent) {
      return <span data-testid="badge-sale">{product.discount_percent}% скидка</span>;
    }
    if (product.is_new) {
      return <span data-testid="badge-new">Новинка</span>;
    }
    if (product.is_hit) {
      return <span data-testid="badge-hit">Хит</span>;
    }
    return null;
  },
}));

// Mock Button component
vi.mock('@/components/ui', () => ({
  Button: ({ children, onClick, type = 'button', ...props }: MockButtonProps) => (
    <button type={type} onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

// Mock cn utility
vi.mock('@/utils/cn', () => ({
  cn: (...classes: MockCnArgs) => classes.filter(Boolean).join(' '),
}));

describe('ProductCard', () => {
  const mockProduct: Product = {
    id: 1,
    name: 'Test Product',
    slug: 'test-product',
    description: 'Test description',
    retail_price: 1200,
    opt1_price: 1000,
    opt2_price: 900,
    opt3_price: 800,
    is_in_stock: true,
    stock_quantity: 50,
    category: {
      id: 1,
      name: 'Test Category',
      slug: 'test-category',
    },
    brand: {
      id: 1,
      name: 'Nike',
      slug: 'nike',
      is_featured: false,
    },
    images: [
      {
        id: 1,
        image: '/test-image.jpg',
        is_primary: true,
      },
    ],
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  };

  const mockOnAddToCart = vi.fn();
  const mockOnToggleFavorite = vi.fn();

  beforeEach(() => {
    mockOnAddToCart.mockClear();
    mockOnToggleFavorite.mockClear();
  });

  describe('Grid Layout', () => {
    it('renders grid layout correctly', () => {
      render(<ProductCard product={mockProduct} layout="grid" onAddToCart={mockOnAddToCart} />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
      expect(screen.getByText('В корзину')).toBeInTheDocument();
    });

    it('displays product image with correct alt text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const image = screen.getByRole('img', { name: 'Test Product' });
      expect(image).toBeInTheDocument();
      // resolveImageUrl добавляет MEDIA_BASE_URL к относительным путям
      expect(image).toHaveAttribute('src', 'http://localhost:8001/test-image.jpg');
    });

    it('shows placeholder when no image available', () => {
      const productWithoutImage = { ...mockProduct, images: [] };
      render(<ProductCard product={productWithoutImage} layout="grid" />);

      // Placeholder SVG should be rendered
      const svg = screen.getByRole('article').querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('calls onAddToCart when button is clicked', () => {
      render(<ProductCard product={mockProduct} layout="grid" onAddToCart={mockOnAddToCart} />);

      const addButton = screen.getByText('В корзину');
      fireEvent.click(addButton);

      expect(mockOnAddToCart).toHaveBeenCalledWith(1);
      expect(mockOnAddToCart).toHaveBeenCalledTimes(1);
    });

    it('does not show add to cart button when out of stock', () => {
      const outOfStockProduct = { ...mockProduct, is_in_stock: false };
      render(
        <ProductCard product={outOfStockProduct} layout="grid" onAddToCart={mockOnAddToCart} />
      );

      expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
      expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
    });
  });

  describe('List Layout', () => {
    it('renders list layout correctly', () => {
      render(<ProductCard product={mockProduct} layout="list" onAddToCart={mockOnAddToCart} />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('Test description')).toBeInTheDocument();
      expect(screen.getByText('В корзину')).toBeInTheDocument();
    });

    it('displays description in list layout', () => {
      render(<ProductCard product={mockProduct} layout="list" />);

      expect(screen.getByText('Test description')).toBeInTheDocument();
    });
  });

  describe('Compact Layout', () => {
    it('renders compact layout correctly', () => {
      const mockOnClick = vi.fn();
      render(<ProductCard product={mockProduct} layout="compact" onClick={mockOnClick} />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
      expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
    });

    it('calls onClick when card is clicked in compact layout', () => {
      const mockOnClick = vi.fn();
      render(<ProductCard product={mockProduct} layout="compact" onClick={mockOnClick} />);

      const card = screen.getByRole('article');
      fireEvent.click(card);

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('shows out of stock message in compact layout', () => {
      const outOfStockProduct = { ...mockProduct, is_in_stock: false };
      render(<ProductCard product={outOfStockProduct} layout="compact" />);

      expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
    });
  });

  describe('Role-based Pricing', () => {
    it('displays retail pricing for B2C users', () => {
      render(<ProductCard product={mockProduct} userRole="retail" mode="b2c" layout="grid" />);

      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 1 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level1" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('1 000 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 2 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level2" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('900 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 3 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level3" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('800 ₽')).toBeInTheDocument();
    });

    it('falls back to retail price when wholesale price not available', () => {
      const productWithoutWholesale = { ...mockProduct, opt1_price: undefined };
      render(
        <ProductCard product={productWithoutWholesale} userRole="wholesale_level1" layout="grid" />
      );

      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    });

    it('displays RRP for B2B users when showRRP is true', () => {
      const productWithRRP = {
        ...mockProduct,
        rrp: 1300,
      };
      render(
        <ProductCard
          product={productWithRRP}
          userRole="wholesale_level1"
          mode="b2b"
          showRRP={true}
          layout="grid"
        />
      );

      expect(screen.getByText(/РРЦ.*1 300/)).toBeInTheDocument();
    });
  });

  describe('Badge Logic', () => {
    it('displays SALE badge when product has discount', () => {
      const saleProduct = { ...mockProduct, is_sale: true, discount_percent: 20 };
      render(<ProductCard product={saleProduct} layout="grid" />);

      expect(screen.getByTestId('badge-sale')).toBeInTheDocument();
      expect(screen.getByText('20% скидка')).toBeInTheDocument();
    });

    it('displays NEW badge when product is new', () => {
      const newProduct = { ...mockProduct, is_new: true };
      render(<ProductCard product={newProduct} layout="grid" />);

      expect(screen.getByTestId('badge-new')).toBeInTheDocument();
    });

    it('displays HIT badge when product is hit', () => {
      const hitProduct = { ...mockProduct, is_hit: true };
      render(<ProductCard product={hitProduct} layout="grid" />);

      expect(screen.getByTestId('badge-hit')).toBeInTheDocument();
    });

    it('does not display badge when no flags are set', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.queryByTestId('badge-sale')).not.toBeInTheDocument();
      expect(screen.queryByTestId('badge-new')).not.toBeInTheDocument();
      expect(screen.queryByTestId('badge-hit')).not.toBeInTheDocument();
    });

    it('displays old price with line-through when discount exists', () => {
      const discountProduct = { ...mockProduct, discount_percent: 20 };
      const { container } = render(<ProductCard product={discountProduct} layout="grid" />);

      const oldPriceElement = container.querySelector('.line-through');
      expect(oldPriceElement).toBeInTheDocument();
      expect(oldPriceElement).toHaveTextContent('1 200 ₽');
    });
  });

  describe('Favorite Button', () => {
    it('calls onToggleFavorite when favorite button is clicked', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      expect(mockOnToggleFavorite).toHaveBeenCalledWith(1);
      expect(mockOnToggleFavorite).toHaveBeenCalledTimes(1);
    });

    it('shows correct aria-label when product is favorite', () => {
      render(
        <ProductCard
          product={mockProduct}
          layout="grid"
          onToggleFavorite={mockOnToggleFavorite}
          isFavorite={true}
        />
      );

      expect(screen.getByLabelText('Удалить из избранного')).toBeInTheDocument();
    });

    it('shows correct aria-label when product is not favorite', () => {
      render(
        <ProductCard
          product={mockProduct}
          layout="grid"
          onToggleFavorite={mockOnToggleFavorite}
          isFavorite={false}
        />
      );

      expect(screen.getByLabelText('Добавить в избранное')).toBeInTheDocument();
    });

    it('renders filled heart icon when isFavorite is true', () => {
      render(<ProductCard product={mockProduct} layout="grid" isFavorite={true} />);

      const heartIcon = screen.getByTestId('heart-icon');
      expect(heartIcon).toHaveAttribute('data-fill', 'currentColor');
    });

    it('renders outline heart icon when isFavorite is false', () => {
      render(<ProductCard product={mockProduct} layout="grid" isFavorite={false} />);

      const heartIcon = screen.getByTestId('heart-icon');
      expect(heartIcon).toHaveAttribute('data-fill', 'none');
    });

    it('prevents event bubbling when favorite button is clicked', () => {
      const mockOnClick = vi.fn();
      render(
        <ProductCard
          product={mockProduct}
          layout="compact"
          onClick={mockOnClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      expect(mockOnToggleFavorite).toHaveBeenCalledTimes(1);
      expect(mockOnClick).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has correct role attribute', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const card = screen.getByRole('article');
      expect(card).toBeInTheDocument();
    });

    it('has correct aria-label on card', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.getByLabelText('Товар: Test Product')).toBeInTheDocument();
    });

    it('has correct aria-label on favorite button', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      expect(screen.getByLabelText('Добавить в избранное')).toBeInTheDocument();
    });

    it('favorite button has role="button"', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      const favoriteButton = screen.getByRole('button', { name: 'Добавить в избранное' });
      expect(favoriteButton).toBeInTheDocument();
    });

    it('product image has alt text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const image = screen.getByRole('img', { name: 'Test Product' });
      expect(image).toBeInTheDocument();
    });

    it('has title attribute on product name for truncated text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const productName = screen.getByText('Test Product');
      expect(productName).toHaveAttribute('title', 'Test Product');
    });
  });

  describe('Edge Cases', () => {
    it('handles product without brand', () => {
      const productWithoutBrand = { ...mockProduct, brand: undefined };
      render(<ProductCard product={productWithoutBrand} layout="grid" />);

      expect(screen.queryByText('Nike')).not.toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
    });

    it('handles product without description in list layout', () => {
      const productWithoutDescription = { ...mockProduct, description: '' };
      render(<ProductCard product={productWithoutDescription} layout="list" />);

      expect(screen.queryByText('Test description')).not.toBeInTheDocument();
    });

    it('handles missing onAddToCart callback', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
    });

    it('handles missing onToggleFavorite callback', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      // Should not throw error
      expect(favoriteButton).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<ProductCard product={mockProduct} layout="grid" className="custom-class" />);

      const card = screen.getByRole('article');
      expect(card).toHaveClass('custom-class');
    });
  });
});
