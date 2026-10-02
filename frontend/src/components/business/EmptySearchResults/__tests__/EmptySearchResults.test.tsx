/**
 * EmptySearchResults Component Tests
 * @see Story 18.2 - Страница результатов поиска
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { EmptySearchResults } from '../EmptySearchResults';
import type { Product } from '@/types/api';

// Mock ProductCard
vi.mock('@/components/business/ProductCard', () => ({
  ProductCard: ({ product }: { product: Product }) => (
    <div data-testid={`recommended-product-${product.id}`}>{product.name}</div>
  ),
}));

const mockQuery = 'несуществующий товар';

const mockRecommendedProducts: Product[] = [
  {
    id: 101,
    name: 'Мяч футбольный Nike',
    slug: 'myach-futbolnyy-nike',
    retail_price: 2500,
    is_in_stock: true,
    stock_quantity: 20,
    main_image: '/images/products/ball.jpg',
    category: { id: 1, name: 'Мячи', slug: 'myachi' },
    brand: { id: 1, name: 'Nike', slug: 'nike', is_featured: false },
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 102,
    name: 'Кроссовки Adidas',
    slug: 'krossovki-adidas',
    retail_price: 8900,
    is_in_stock: true,
    stock_quantity: 10,
    main_image: '/images/products/shoes.jpg',
    category: { id: 2, name: 'Обувь', slug: 'obuv' },
    brand: { id: 2, name: 'Adidas', slug: 'adidas', is_featured: false },
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 103,
    name: 'Шлем хоккейный Bauer',
    slug: 'shlem-hokkeynyy-bauer',
    retail_price: 12000,
    is_in_stock: true,
    stock_quantity: 5,
    main_image: '/images/products/helmet.jpg',
    category: { id: 3, name: 'Экипировка', slug: 'ekipirovka' },
    brand: { id: 3, name: 'Bauer', slug: 'bauer', is_featured: false },
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 104,
    name: 'Коньки Jackson',
    slug: 'konki-jackson',
    retail_price: 25000,
    is_in_stock: true,
    stock_quantity: 3,
    main_image: '/images/products/skates.jpg',
    category: { id: 4, name: 'Коньки', slug: 'konki' },
    brand: { id: 4, name: 'Jackson', slug: 'jackson', is_featured: false },
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

describe('EmptySearchResults', () => {
  describe('Rendering', () => {
    it('renders empty state message with query', () => {
      render(<EmptySearchResults query={mockQuery} />);

      expect(screen.getByText(`По запросу «${mockQuery}» ничего не найдено`)).toBeInTheDocument();
    });

    it('renders search icon', () => {
      render(<EmptySearchResults query={mockQuery} />);

      // Search icon should be present (via lucide-react)
      const icon = screen.getByRole('status').querySelector('svg');
      expect(icon).toBeInTheDocument();
    });

    it('renders helpful suggestions', () => {
      render(<EmptySearchResults query={mockQuery} />);

      expect(screen.getByText('Попробуйте:')).toBeInTheDocument();
      expect(screen.getByText(/Изменить поисковый запрос/i)).toBeInTheDocument();
      expect(screen.getByText(/Проверить правильность написания/i)).toBeInTheDocument();
      expect(screen.getByText(/Использовать более общие термины/i)).toBeInTheDocument();
      expect(screen.getByText(/Воспользоваться фильтрами в каталоге/i)).toBeInTheDocument();
    });
  });

  describe('Recommended Products', () => {
    it('does not render recommended section when no products', () => {
      render(<EmptySearchResults query={mockQuery} />);

      expect(screen.queryByText('Популярные товары')).not.toBeInTheDocument();
    });

    it('renders recommended products section when provided', () => {
      render(
        <EmptySearchResults query={mockQuery} recommendedProducts={mockRecommendedProducts} />
      );

      expect(screen.getByText('Популярные товары')).toBeInTheDocument();
    });

    it('renders maximum of 4 recommended products', () => {
      const manyProducts = [...mockRecommendedProducts, ...mockRecommendedProducts]; // 8 products
      render(<EmptySearchResults query={mockQuery} recommendedProducts={manyProducts} />);

      const recommendedCards = screen.getAllByTestId(/^recommended-product-/);
      expect(recommendedCards).toHaveLength(4);
    });

    it('renders all recommended products if less than 4', () => {
      const twoProducts = mockRecommendedProducts.slice(0, 2);
      render(<EmptySearchResults query={mockQuery} recommendedProducts={twoProducts} />);

      const recommendedCards = screen.getAllByTestId(/^recommended-product-/);
      expect(recommendedCards).toHaveLength(2);
    });

    it('renders product names in recommended section', () => {
      render(
        <EmptySearchResults query={mockQuery} recommendedProducts={mockRecommendedProducts} />
      );

      expect(screen.getByText('Мяч футбольный Nike')).toBeInTheDocument();
      expect(screen.getByText('Кроссовки Adidas')).toBeInTheDocument();
      expect(screen.getByText('Шлем хоккейный Bauer')).toBeInTheDocument();
      expect(screen.getByText('Коньки Jackson')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role="status" for screen readers', () => {
      render(<EmptySearchResults query={mockQuery} />);

      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    it('has aria-live="polite" for dynamic updates', () => {
      render(<EmptySearchResults query={mockQuery} />);

      const statusElement = screen.getByRole('status');
      expect(statusElement).toHaveAttribute('aria-live', 'polite');
    });

    it('has proper heading structure', () => {
      render(
        <EmptySearchResults query={mockQuery} recommendedProducts={mockRecommendedProducts} />
      );

      const mainHeading = screen.getByRole('heading', { level: 2 });
      expect(mainHeading).toHaveTextContent(`По запросу «${mockQuery}» ничего не найдено`);

      const recommendedHeading = screen.getByRole('heading', { level: 3 });
      expect(recommendedHeading).toHaveTextContent('Популярные товары');
    });

    it('recommended section has aria-labelledby', () => {
      render(
        <EmptySearchResults query={mockQuery} recommendedProducts={mockRecommendedProducts} />
      );

      const section = screen.getByRole('region');
      expect(section).toHaveAttribute('aria-labelledby', 'recommended-products-heading');

      const heading = screen.getByText('Популярные товары');
      expect(heading).toHaveAttribute('id', 'recommended-products-heading');
    });

    it('search icon has aria-hidden', () => {
      render(<EmptySearchResults query={mockQuery} />);

      const icon = screen.getByRole('status').querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  describe('Visual Structure', () => {
    it('renders with correct CSS classes for layout', () => {
      const { container } = render(<EmptySearchResults query={mockQuery} />);

      const mainContainer = container.firstChild;
      expect(mainContainer).toHaveClass('w-full', 'py-12');
    });

    it('recommended products are in grid layout', () => {
      render(
        <EmptySearchResults query={mockQuery} recommendedProducts={mockRecommendedProducts} />
      );

      const gridContainer = screen.getByRole('region').querySelector('.grid');
      expect(gridContainer).toHaveClass(
        'grid',
        'gap-4',
        'grid-cols-2',
        'md:grid-cols-3',
        'lg:grid-cols-4'
      );
    });
  });
});
