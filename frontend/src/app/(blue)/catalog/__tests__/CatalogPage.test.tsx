/**
 * Unit-тесты для интеграции поиска в CatalogPage (Story 18.4)
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CatalogPage from '../page';
import { useSearchParams } from 'next/navigation';

// Mock данные для тестов
const mockProducts = [
  {
    id: 1,
    name: 'Nike Air Max 90',
    slug: 'nike-air-max-90',
    retail_price: 12990,
    main_image: '/images/nike-air-max.jpg',
    is_in_stock: true,
    stock_quantity: 10,
    can_be_ordered: true,
    brand: { id: 1, name: 'Nike', slug: 'nike', is_featured: false },
    category: { id: 1, name: 'Обувь', slug: 'shoes' },
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
  {
    id: 2,
    name: 'Nike Dunk Low',
    slug: 'nike-dunk-low',
    retail_price: 9990,
    main_image: '/images/nike-dunk.jpg',
    is_in_stock: true,
    stock_quantity: 5,
    can_be_ordered: true,
    brand: { id: 1, name: 'Nike', slug: 'nike', is_featured: false },
    category: { id: 1, name: 'Обувь', slug: 'shoes' },
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  },
];

const mockApiResponse = {
  count: 2,
  next: null,
  previous: null,
  results: mockProducts,
};

const mockCategories = [
  {
    id: 1,
    name: 'Спорт',
    slug: 'sport',
    children: [],
  },
];

const mockBrands = [
  { id: 1, name: 'Nike', slug: 'nike' },
  { id: 2, name: 'Adidas', slug: 'adidas' },
];

// Mock для productsService
vi.mock('@/services/productsService', () => ({
  default: {
    getAll: vi.fn(() => Promise.resolve(mockApiResponse)),
    search: vi.fn(() => Promise.resolve({ results: mockProducts })),
    getProductBySlug: vi.fn(() =>
      Promise.resolve({
        ...mockProducts[0],
        variants: [
          {
            id: 1,
            sku: 'NIKE-001',
            is_in_stock: true,
            stock_quantity: 10,
            current_price: '12990',
          },
        ],
      })
    ),
  },
}));

// Mock для categoriesService
vi.mock('@/services/categoriesService', () => ({
  default: {
    getTree: vi.fn(() => Promise.resolve(mockCategories)),
  },
}));

// Mock для brandsService
vi.mock('@/services/brandsService', () => ({
  default: {
    getAll: vi.fn(() => Promise.resolve(mockBrands)),
  },
}));

// Mock для cartStore
vi.mock('@/stores/cartStore', () => ({
  useCartStore: vi.fn(() => ({
    addItem: vi.fn(() => Promise.resolve({ success: true })),
  })),
}));

// Mock для Toast
vi.mock('@/components/ui/Toast', () => ({
  useToast: vi.fn(() => ({
    success: vi.fn(),
    error: vi.fn(),
  })),
}));

// Mock для next/navigation
const mockPush = vi.fn();
const mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: mockPush,
    replace: vi.fn(),
  })),
  useSearchParams: vi.fn(() => mockSearchParams),
  usePathname: vi.fn(() => '/catalog'),
}));

describe('CatalogPage - Search Integration (Story 18.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams.delete('search');
    mockPush.mockClear();
  });

  it('AC 1: должен отображать SearchField на странице каталога', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      const searchField = screen.getByPlaceholderText('Поиск в каталоге...');
      expect(searchField).toBeInTheDocument();
    });
  });

  it('AC 3: должен обновлять URL с параметром search при вводе запроса', async () => {
    const user = userEvent.setup();
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Вводим поисковый запрос
    await user.type(searchInput, 'nike');

    // Ждем debounce (300ms)
    await waitFor(
      () => {
        expect(mockPush).toHaveBeenCalledWith(
          expect.stringContaining('search=nike'),
          expect.anything()
        );
      },
      { timeout: 500 }
    );
  });

  it('AC 2, AC 4: должен передавать параметр search в API вместе с существующими фильтрами', async () => {
    const user = userEvent.setup();
    const productsService = await import('@/services/productsService');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Вводим поисковый запрос
    await user.type(searchInput, 'nike');

    // Ждем debounce и вызов API
    await waitFor(
      () => {
        expect(productsService.default.getAll).toHaveBeenCalledWith(
          expect.objectContaining({
            search: 'nike',
            category_id: expect.any(Number),
          })
        );
      },
      { timeout: 500 }
    );
  });

  it('AC 3: должен удалять параметр search из URL при пустом запросе', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Вводим поисковый запрос
    await user.type(searchInput, 'test');

    // Ждем появления кнопки очистки
    await waitFor(() => {
      expect(screen.getByLabelText('Очистить поиск')).toBeInTheDocument();
    });

    // Очищаем поле через кнопку очистки
    const clearButton = screen.getByLabelText('Очистить поиск');
    await user.click(clearButton);

    // Проверяем, что URL обновлен без параметра search
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/catalog', expect.anything());
    });
  });

  it('AC 5: должен сбрасывать поисковый запрос при нажатии кнопки "Сбросить"', async () => {
    const user = userEvent.setup();
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Вводим поисковый запрос
    await user.type(searchInput, 'nike');

    await waitFor(() => {
      expect(searchInput).toHaveValue('nike');
    });

    // Нажимаем кнопку "Сбросить"
    const resetButton = screen.getByText('Сбросить');
    await user.click(resetButton);

    // Проверяем, что поисковый запрос сброшен
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith('/catalog', expect.anything());
    });
  });

  it('AC 2: должен показывать индикатор результатов при активном поиске', async () => {
    const user = userEvent.setup();
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Вводим поисковый запрос
    await user.type(searchInput, 'nike');

    // Проверяем, что индикатор результатов отображается
    await waitFor(
      () => {
        const indicator = screen.getByText(/Найдено.*товар.*по запросу «nike»/i);
        expect(indicator).toBeInTheDocument();
        expect(indicator).toHaveAttribute('aria-live', 'polite');
        expect(indicator).toHaveAttribute('role', 'status');
      },
      { timeout: 500 }
    );
  });

  it('должен читать параметр search из URL при загрузке страницы', async () => {
    // Устанавливаем параметр search в URL
    mockSearchParams.set('search', 'adidas');
    (useSearchParams as Mock).mockReturnValue(mockSearchParams);

    const productsService = await import('@/services/productsService');

    render(<CatalogPage />);

    // Проверяем, что API вызван с параметром search из URL
    await waitFor(() => {
      expect(productsService.default.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          search: 'adidas',
        })
      );
    });
  });

  it('не должен отправлять параметр search если длина меньше minLength (2 символа)', async () => {
    const user = userEvent.setup();
    const productsService = await import('@/services/productsService');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByPlaceholderText('Поиск в каталоге...')).toBeInTheDocument();
    });

    const searchInput = screen.getByPlaceholderText('Поиск в каталоге...');

    // Очищаем предыдущие вызовы
    vi.clearAllMocks();

    // Вводим 1 символ
    await user.type(searchInput, 'n');

    // Ждем debounce, обернув в act чтобы поймать обновление состояния
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 400));
    });

    // Проверяем, что API не был вызван с параметром search
    const calls = (productsService.default.getAll as Mock).mock.calls;
    const callsWithSearch = calls.filter((call: Array<Record<string, unknown>>) => call[0]?.search);
    expect(callsWithSearch).toHaveLength(0);
  });
});
