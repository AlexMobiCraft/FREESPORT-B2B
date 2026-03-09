/**
 * SearchPageClient Component Tests
 * @see Story 18.2 - Страница результатов поиска
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchPageClient } from '../SearchPageClient';
import type { Product, PaginatedResponse } from '@/types/api';

// Mock next/navigation
const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  useSearchParams: () => mockSearchParams,
}));

// Mock child components
vi.mock('@/components/business/SearchResults', () => ({
  SearchResults: ({ products, isLoading }: { products: Product[]; isLoading: boolean }) => (
    <div data-testid="search-results" data-loading={isLoading}>
      {products.map(p => (
        <div key={p.id} data-testid={`result-${p.id}`}>
          {p.name}
        </div>
      ))}
    </div>
  ),
}));

vi.mock('@/components/business/EmptySearchResults', () => ({
  EmptySearchResults: ({ query }: { query: string }) => (
    <div data-testid="empty-results">Ничего не найдено по запросу: {query}</div>
  ),
}));

vi.mock('@/components/ui/Pagination', () => ({
  Pagination: ({
    currentPage,
    totalPages,
    onPageChange,
  }: {
    currentPage: number;
    totalPages: number;
    onPageChange: (page: number) => void;
  }) => (
    <div data-testid="pagination">
      <button onClick={() => onPageChange(currentPage - 1)} disabled={currentPage === 1}>
        Prev
      </button>
      <span data-testid="current-page">{currentPage}</span>
      <span data-testid="total-pages">{totalPages}</span>
      <button onClick={() => onPageChange(currentPage + 1)} disabled={currentPage === totalPages}>
        Next
      </button>
    </div>
  ),
}));

// Mock productsService
vi.mock('@/services/productsService', () => ({
  default: {
    getAll: vi.fn(),
    getHits: vi.fn(),
  },
}));

import productsService from '@/services/productsService';

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
    name: 'Nike Dri-FIT Training Top',
    slug: 'nike-dri-fit-training-top',
    retail_price: 3990,
    is_in_stock: true,
    stock_quantity: 25,
    main_image: '/images/products/nike-top.jpg',
    category: { id: 2, name: 'Одежда', slug: 'odezhda' },
    brand: { id: 1, name: 'Nike', slug: 'nike', is_featured: false },
    is_hit: false,
    is_new: true,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

const mockPaginatedResponse: PaginatedResponse<Product> = {
  count: 48,
  next: '/api/v1/products/?search=nike&page=2',
  previous: null,
  results: mockProducts,
};

const mockEmptyResponse: PaginatedResponse<Product> = {
  count: 0,
  next: null,
  previous: null,
  results: [],
};

const mockHitProducts: Product[] = [
  {
    id: 101,
    name: 'Мяч футбольный',
    slug: 'myach-futbolnyy',
    retail_price: 2500,
    is_in_stock: true,
    stock_quantity: 20,
    main_image: '/images/products/ball.jpg',
    category: { id: 3, name: 'Мячи', slug: 'myachi' },
    brand: { id: 2, name: 'Adidas', slug: 'adidas', is_featured: false },
    is_hit: true,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

describe('SearchPageClient', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.set('q', 'nike');
    mockSearchParams.set('page', '1');
    (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(mockPaginatedResponse);
    (productsService.getHits as ReturnType<typeof vi.fn>).mockResolvedValue(mockHitProducts);
  });

  afterEach(() => {
    vi.clearAllMocks();
    mockSearchParams.delete('q');
    mockSearchParams.delete('page');
  });

  describe('Rendering', () => {
    it('renders search results page with query', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByText('Результаты поиска: «nike»')).toBeInTheDocument();
      });
    });

    it('renders results count', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByText(/Найдено 48 товаров/)).toBeInTheDocument();
      });
    });

    it('renders correct pluralization for count', async () => {
      const singleProduct: PaginatedResponse<Product> = {
        count: 1,
        next: null,
        previous: null,
        results: [mockProducts[0]],
      };
      (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(singleProduct);

      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByText(/Найдено 1 товар/)).toBeInTheDocument();
      });
    });

    it('renders empty state when no query provided', () => {
      mockSearchParams.delete('q');
      render(<SearchPageClient initialQuery="" initialPage={1} />);

      expect(screen.getByText('Введите запрос для поиска товаров')).toBeInTheDocument();
    });
  });

  describe('Search Functionality', () => {
    it('calls productsService.getAll() with correct parameters', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith({
          search: 'nike',
          page: 1,
          page_size: 24,
        });
      });
    });

    it('displays search results', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('search-results')).toBeInTheDocument();
        expect(screen.getByTestId('result-1')).toBeInTheDocument();
        expect(screen.getByTestId('result-2')).toBeInTheDocument();
      });
    });

    it('shows loading state initially', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      const searchResults = screen.getByTestId('search-results');
      expect(searchResults).toHaveAttribute('data-loading', 'true');

      // Wait for data to load to avoid act warning
      await waitFor(() => {
        expect(searchResults).toHaveAttribute('data-loading', 'false');
      });
    });

    it('hides loading state after data is fetched', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        const searchResults = screen.getByTestId('search-results');
        expect(searchResults).toHaveAttribute('data-loading', 'false');
      });
    });
  });

  describe('Empty State', () => {
    it('renders EmptySearchResults when no results found', async () => {
      (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptyResponse);

      render(<SearchPageClient initialQuery="zzz" initialPage={1} />);

      // Проверяем что EmptySearchResults рендерится
      const emptyResults = await screen.findByTestId('empty-results', {}, { timeout: 2000 });
      expect(emptyResults).toBeInTheDocument();
    });

    it('fetches recommended products when no results', async () => {
      (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptyResponse);

      render(<SearchPageClient initialQuery="zzz" initialPage={1} />);

      await waitFor(() => {
        expect(productsService.getHits).toHaveBeenCalledWith({ page_size: 4 });
      });
    });

    it('displays "Ничего не найдено" in count', async () => {
      (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(mockEmptyResponse);

      render(<SearchPageClient initialQuery="zzz" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByText('Ничего не найдено')).toBeInTheDocument();
      });
    });
  });

  describe('Pagination', () => {
    it('renders pagination when totalPages > 1', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('pagination')).toBeInTheDocument();
      });
    });

    it('does not render pagination when totalPages = 1', async () => {
      const singlePageResponse: PaginatedResponse<Product> = {
        count: 10,
        next: null,
        previous: null,
        results: mockProducts,
      };
      (productsService.getAll as ReturnType<typeof vi.fn>).mockResolvedValue(singlePageResponse);

      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.queryByTestId('pagination')).not.toBeInTheDocument();
      });
    });

    it('calculates total pages correctly (48 items / 24 per page = 2 pages)', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('total-pages')).toHaveTextContent('2');
      });
    });

    it('updates URL when page changes', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('pagination')).toBeInTheDocument();
      });

      const nextButton = screen.getByText('Next');
      await user.click(nextButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith(
          expect.stringContaining('page=2'),
          expect.any(Object)
        );
      });
    });

    it('displays current page', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('current-page')).toHaveTextContent('1');
      });
    });
  });

  describe('Accessibility', () => {
    it('has main heading with search query', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        const heading = screen.getByRole('heading', { level: 1 });
        expect(heading).toHaveTextContent('Результаты поиска: «nike»');
      });
    });

    it('has aria-live on results count', async () => {
      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        const countElement = screen.getByText(/Найдено 48 товаров/);
        expect(countElement).toHaveAttribute('aria-live', 'polite');
      });
    });
  });

  describe('Error Handling', () => {
    it('handles API errors gracefully', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      (productsService.getAll as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('API Error')
      );

      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(consoleError).toHaveBeenCalledWith(
          'Error fetching search results:',
          expect.any(Error)
        );
      });

      consoleError.mockRestore();
    });

    it('displays empty results on API error', async () => {
      const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
      (productsService.getAll as ReturnType<typeof vi.fn>).mockRejectedValue(
        new Error('API Error')
      );

      render(<SearchPageClient initialQuery="nike" initialPage={1} />);

      await waitFor(() => {
        expect(screen.getByTestId('empty-results')).toBeInTheDocument();
      });

      consoleError.mockRestore();
    });
  });
});
