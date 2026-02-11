/**
 * SearchAutocomplete Component Tests
 * @see Story 18.1 - Интеграция поиска в Header
 * @see Story 18.3 - История и автодополнение поиска
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchAutocomplete } from '../SearchAutocomplete';

// Mock next/navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// Mock productsService
vi.mock('@/services/productsService', () => ({
  default: {
    search: vi.fn(),
  },
}));

// Mock useSearchHistory hook
const mockAddSearch = vi.fn();
const mockRemoveSearch = vi.fn();
const mockClearHistory = vi.fn();
const mockHistory = ['кроссовки Nike', 'футболка Adidas'];

vi.mock('@/hooks/useSearchHistory', () => ({
  useSearchHistory: () => ({
    history: mockHistory,
    addSearch: mockAddSearch,
    removeSearch: mockRemoveSearch,
    clearHistory: mockClearHistory,
  }),
}));

import productsService from '@/services/productsService';

const mockProducts = [
  {
    id: 1,
    name: 'Мяч футбольный Nike',
    slug: 'myach-futbolny-nike',
    retail_price: 2500,
    category: { id: 1, name: 'Мячи', slug: 'balls' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 2,
    name: 'Кроссовки Adidas',
    slug: 'krossovki-adidas',
    retail_price: 8900,
    category: { id: 2, name: 'Обувь', slug: 'shoes' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 3,
    name: 'Ракетка теннисная Wilson',
    slug: 'raketka-tennisnaya-wilson',
    retail_price: 15000,
    category: { id: 3, name: 'Теннис', slug: 'tennis' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 4,
    name: 'Шлем хоккейный Bauer',
    slug: 'shlem-hokkeynyy-bauer',
    retail_price: 12000,
    category: { id: 4, name: 'Хоккей', slug: 'hockey' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 5,
    name: 'Коньки фигурные Jackson',
    slug: 'konki-figurnye-jackson',
    retail_price: 25000,
    category: { id: 4, name: 'Хоккей', slug: 'hockey' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 6,
    name: 'Перчатки боксерские Everlast',
    slug: 'perchatki-bokserskie-everlast',
    retail_price: 5500,
    category: { id: 5, name: 'Единоборства', slug: 'fight' },
    is_in_stock: true,
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

describe('SearchAutocomplete', () => {
  const user = userEvent.setup();

  beforeEach(() => {
    vi.clearAllMocks();
    (productsService.search as ReturnType<typeof vi.fn>).mockResolvedValue({
      results: mockProducts,
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('renders SearchField component', () => {
      render(<SearchAutocomplete />);

      expect(screen.getByTestId('search-autocomplete')).toBeInTheDocument();
      expect(screen.getByRole('combobox')).toBeInTheDocument();
    });

    it('renders with custom placeholder', () => {
      render(<SearchAutocomplete placeholder="Найти товар..." />);

      expect(screen.getByPlaceholderText('Найти товар...')).toBeInTheDocument();
    });

    it('renders in desktop mode with max-width constraint', () => {
      render(<SearchAutocomplete />);

      const container = screen.getByTestId('search-autocomplete');
      expect(container).toHaveClass('max-w-[300px]');
    });

    it('renders in mobile mode with full width', () => {
      render(<SearchAutocomplete isMobile />);

      const container = screen.getByTestId('search-autocomplete');
      expect(container).not.toHaveClass('max-w-[300px]');
      expect(container).toHaveClass('w-full');
    });
  });

  describe('Search Functionality', () => {
    it('calls productsService.search() when user types query', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      // Wait for debounce (300ms)
      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalledWith('мяч');
        },
        { timeout: 500 }
      );
    });

    it('does not call search for queries less than 2 characters', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'м');

      // Wait and verify no call was made, wrapped in act
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 400));
      });

      expect(productsService.search).not.toHaveBeenCalled();
    });

    it('limits displayed products to 5', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'товар');

      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Even though mock returns 6 products, only 5 should be shown
      // This is verified by checking that the 6th product is not in the DOM
      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons.length).toBeLessThanOrEqual(5);
        },
        { timeout: 500 }
      );
    });
  });

  describe('Navigation', () => {
    it('navigates to /search?q=... on Enter key', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'кроссовки');
      await user.keyboard('{Enter}');

      expect(mockPush).toHaveBeenCalledWith(
        '/search?q=%D0%BA%D1%80%D0%BE%D1%81%D1%81%D0%BE%D0%B2%D0%BA%D0%B8'
      );
    });

    it('does not navigate on Enter if query is too short', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'м');
      await user.keyboard('{Enter}');

      expect(mockPush).not.toHaveBeenCalled();
    });

    it('calls onNavigate callback after navigation', async () => {
      const onNavigate = vi.fn();
      render(<SearchAutocomplete onNavigate={onNavigate} />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'кроссовки');
      await user.keyboard('{Enter}');

      expect(onNavigate).toHaveBeenCalled();
    });
  });

  describe('Product Click', () => {
    it('navigates to product page on product click', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Wait for dropdown to appear and click first product
      await waitFor(
        async () => {
          const productButtons = screen.getAllByRole('option');
          if (productButtons.length > 0) {
            await user.click(productButtons[0]);
          }
        },
        { timeout: 500 }
      );

      // Verify navigation to product page
      await waitFor(
        () => {
          expect(mockPush).toHaveBeenCalledWith('/product/myach-futbolny-nike');
        },
        { timeout: 500 }
      );
    });
  });

  describe('Accessibility', () => {
    it('has proper aria-label on input', () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      expect(input).toHaveAttribute('aria-label', 'Поиск товаров');
    });

    it('announces search results count to screen readers', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Check for aria-live region
      await waitFor(
        () => {
          const liveRegion = screen.getByText(/Найдено \d+ товаров/);
          expect(liveRegion).toHaveAttribute('aria-live', 'polite');
        },
        { timeout: 500 }
      );
    });
  });

  describe('Mobile Mode', () => {
    it('closes mobile menu after navigation', async () => {
      const onNavigate = vi.fn();
      render(<SearchAutocomplete isMobile onNavigate={onNavigate} />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'тест');
      await user.keyboard('{Enter}');

      expect(onNavigate).toHaveBeenCalled();
    });
  });

  describe('Loading Skeleton', () => {
    it('shows loading skeleton while searching', async () => {
      // Make search slow to capture loading state
      (productsService.search as ReturnType<typeof vi.fn>).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ results: mockProducts }), 500))
      );

      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      // Wait for debounce, loading should appear
      await waitFor(
        () => {
          const loadingEl = document.querySelector('[role="status"]');
          expect(loadingEl).toBeInTheDocument();
        },
        { timeout: 500 }
      );
    });

    it('hides skeleton after search completes', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      // Wait for results
      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Wait for products to appear
      await waitFor(
        () => {
          const buttons = screen.queryAllByRole('option');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 500 }
      );

      // Skeleton should be gone
      const loadingEl = document.querySelector('[aria-label="Загрузка результатов"]');
      expect(loadingEl).not.toBeInTheDocument();
    });
  });

  describe('Keyboard Navigation', () => {
    it('navigates down with Arrow Down key', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 500 }
      );

      // Press arrow down
      await user.keyboard('{ArrowDown}');

      // First item should be highlighted
      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons[0]).toHaveAttribute('aria-selected', 'true');
        },
        { timeout: 300 }
      );
    });

    it('navigates up with Arrow Up key', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 500 }
      );

      // Press arrow up - should wrap to last item
      await user.keyboard('{ArrowUp}');

      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          const lastButton = buttons[buttons.length - 1];
          expect(lastButton).toHaveAttribute('aria-selected', 'true');
        },
        { timeout: 300 }
      );
    });

    it('closes dropdown with Escape key', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 500 }
      );

      // Press Escape
      await user.keyboard('{Escape}');

      // Dropdown should close
      await waitFor(
        () => {
          const buttons = screen.queryAllByRole('option');
          expect(buttons.length).toBe(0);
        },
        { timeout: 300 }
      );
    });

    it('selects product with Enter on highlighted item', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          const buttons = screen.getAllByRole('option');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 500 }
      );

      // Navigate to first item and press Enter
      await user.keyboard('{ArrowDown}');
      await user.keyboard('{Enter}');

      // Should navigate to the product page
      await waitFor(
        () => {
          expect(mockPush).toHaveBeenCalledWith('/product/myach-futbolny-nike');
        },
        { timeout: 300 }
      );
    });
  });

  describe('Search History (Story 18.3)', () => {
    it('shows history on focus when field is empty', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.click(input);

      // История должна появиться
      await waitFor(() => {
        expect(screen.getByText('История поиска')).toBeInTheDocument();
        expect(screen.getByText('кроссовки Nike')).toBeInTheDocument();
        expect(screen.getByText('футболка Adidas')).toBeInTheDocument();
      });
    });

    it('hides history when user types in search field', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.click(input);

      // Проверяем что история показывается
      await waitFor(() => {
        expect(screen.getByText('История поиска')).toBeInTheDocument();
      });

      // Вводим текст
      await user.type(input, 'мяч');

      // История должна скрыться
      await waitFor(
        () => {
          expect(screen.queryByText('История поиска')).not.toBeInTheDocument();
        },
        { timeout: 500 }
      );
    });

    it('adds search query to history on Enter', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'новый запрос');
      await user.keyboard('{Enter}');

      expect(mockAddSearch).toHaveBeenCalledWith('новый запрос');
    });

    it('adds search query to history on product click', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.type(input, 'мяч');

      await waitFor(
        () => {
          expect(productsService.search).toHaveBeenCalled();
        },
        { timeout: 500 }
      );

      // Кликаем на первый товар
      await waitFor(
        async () => {
          const productButtons = screen.getAllByRole('option');
          if (productButtons.length > 0) {
            await user.click(productButtons[0]);
          }
        },
        { timeout: 500 }
      );

      expect(mockAddSearch).toHaveBeenCalledWith('мяч');
    });

    it('executes search when clicking on history item', async () => {
      render(<SearchAutocomplete />);

      const input = screen.getByRole('combobox');
      await user.click(input);

      // Ждем появления истории
      await waitFor(() => {
        expect(screen.getByText('кроссовки Nike')).toBeInTheDocument();
      });

      // Кликаем на элемент истории
      const historyItem = screen.getByRole('option', {
        name: /Выбрать запрос: кроссовки Nike/,
      });
      await user.click(historyItem);

      // Должна быть навигация и добавление в историю
      expect(mockAddSearch).toHaveBeenCalledWith('кроссовки Nike');
      expect(mockPush).toHaveBeenCalledWith(
        '/search?q=%D0%BA%D1%80%D0%BE%D1%81%D1%81%D0%BE%D0%B2%D0%BA%D0%B8%20Nike'
      );
    });
  });
});
