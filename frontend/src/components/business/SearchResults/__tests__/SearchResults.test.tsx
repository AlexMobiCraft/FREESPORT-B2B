/**
 * SearchResults Component Tests
 * @see Story 18.2 - Страница результатов поиска
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SearchResults } from '../SearchResults';
import type { Product } from '@/types/api';

// Mock ProductCard and ProductGrid
vi.mock('@/components/business/ProductCard', () => ({
  ProductCard: ({ product }: { product: Product }) => (
    <div data-testid={`product-card-${product.id}`}>{product.name}</div>
  ),
}));

vi.mock('@/components/business/ProductGrid', () => ({
  ProductGrid: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="product-grid" role="list">
      {children}
    </div>
  ),
}));

const mockProducts: Product[] = [
  {
    id: 1,
    name: 'Nike Air Zoom Pegasus 40',
    slug: 'nike-air-zoom-pegasus-40',
    retail_price: 12990,
    is_in_stock: true,
    stock_quantity: 15,
    main_image: '/images/products/nike-pegasus.jpg',
    category: { id: 1, name: 'Обувь', slug: 'obuv' },
    brand: { id: 1, name: 'Nike', slug: 'nike', is_featured: false },
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 2,
    name: 'Adidas Ultraboost 22',
    slug: 'adidas-ultraboost-22',
    retail_price: 14990,
    is_in_stock: true,
    stock_quantity: 8,
    main_image: '/images/products/adidas-ultraboost.jpg',
    category: { id: 1, name: 'Обувь', slug: 'obuv' },
    brand: { id: 2, name: 'Adidas', slug: 'adidas', is_featured: false },
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

describe('SearchResults', () => {
  describe('Rendering', () => {
    it('renders ProductGrid with products', () => {
      render(<SearchResults products={mockProducts} isLoading={false} />);

      expect(screen.getByTestId('product-grid')).toBeInTheDocument();
      expect(screen.getByTestId('product-card-1')).toBeInTheDocument();
      expect(screen.getByTestId('product-card-2')).toBeInTheDocument();
      expect(screen.getByText('Nike Air Zoom Pegasus 40')).toBeInTheDocument();
      expect(screen.getByText('Adidas Ultraboost 22')).toBeInTheDocument();
    });

    it('renders correct number of products', () => {
      render(<SearchResults products={mockProducts} isLoading={false} />);

      const productCards = screen.getAllByTestId(/^product-card-/);
      expect(productCards).toHaveLength(2);
    });

    it('renders empty grid when no products', () => {
      render(<SearchResults products={[]} isLoading={false} />);

      expect(screen.getByTestId('product-grid')).toBeInTheDocument();
      expect(screen.queryByTestId(/^product-card-/)).not.toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    it('renders loading skeleton when isLoading=true', () => {
      render(<SearchResults products={[]} isLoading={true} />);

      expect(screen.getByRole('status')).toBeInTheDocument();
      expect(screen.getByLabelText('Загрузка результатов поиска')).toBeInTheDocument();
      expect(screen.getByText('Загрузка результатов...')).toBeInTheDocument();
    });

    it('renders 8 skeleton items during loading', () => {
      const { container } = render(<SearchResults products={[]} isLoading={true} />);

      const skeletons = container.querySelectorAll('[aria-hidden="true"]');
      expect(skeletons).toHaveLength(8);
    });

    it('does not render ProductGrid when loading', () => {
      render(<SearchResults products={mockProducts} isLoading={true} />);

      expect(screen.queryByTestId('product-grid')).not.toBeInTheDocument();
      expect(screen.queryByTestId('product-card-1')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('has role="list" on ProductGrid', () => {
      render(<SearchResults products={mockProducts} isLoading={false} />);

      expect(screen.getByRole('list')).toBeInTheDocument();
    });

    it('loading state has role="status" and aria-live', () => {
      render(<SearchResults products={[]} isLoading={true} />);

      const loadingContainer = screen.getByRole('status');
      expect(loadingContainer).toHaveAttribute('aria-label', 'Загрузка результатов поиска');
    });

    it('has sr-only text for screen readers during loading', () => {
      render(<SearchResults products={[]} isLoading={true} />);

      const srText = screen.getByText('Загрузка результатов...');
      expect(srText).toHaveClass('sr-only');
    });
  });
});
