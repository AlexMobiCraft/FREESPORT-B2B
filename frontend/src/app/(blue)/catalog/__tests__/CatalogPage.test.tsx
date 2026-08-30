/**
 * Unit-тесты для интеграции поиска в CatalogPage (Story 18.4)
 */

import { describe, it, expect, vi, beforeEach, afterAll, type Mock } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import CatalogPage from '../page';

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
    getVisibleCategories: vi.fn(() => Promise.resolve([1])),
  },
}));

// Mock для brandsService
vi.mock('@/services/brandsService', () => ({
  default: {
    getAll: vi.fn(() => Promise.resolve(mockBrands)),
    getVisibleBrands: vi.fn(() => Promise.resolve([1, 2])),
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

// Mock для next/navigation.
let mockSearchParams = new URLSearchParams();

/** Хронологический журнал навигаций: push и replace в одном порядке вызова */
type Navigation = { type: 'push' | 'replace'; url: string };
const navigationLog: Navigation[] = [];

const queryOf = (url: string) => {
  const queryIndex = url.indexOf('?');
  return queryIndex === -1 ? '' : url.slice(queryIndex + 1);
};

// Реальный App Router обновляет useSearchParams асинхронно: router.push — это
// transition, и до его commit хук отдаёт прежний снимок. Синхронный мок это
// окно прячет, поэтому блоки, которым оно нужно, включают отложенный режим.
let deferNavigation = false;
const deferredNavigations: string[] = [];

const setDeferNavigation = (value: boolean) => {
  deferNavigation = value;
  deferredNavigations.length = 0;
};

/** Досылает отложенные навигации в useSearchParams — как commit transition */
const flushDeferredNavigation = () => {
  const url = deferredNavigations.at(-1);
  deferredNavigations.length = 0;
  if (url !== undefined) {
    mockSearchParams = new URLSearchParams(queryOf(url));
  }
};

const applyNavigation = (type: Navigation['type']) => (url: string) => {
  if (deferNavigation) {
    deferredNavigations.push(url);
  } else {
    mockSearchParams = new URLSearchParams(queryOf(url));
  }
  navigationLog.push({ type, url });
};

const resetSearchParams = (query = '') => {
  mockSearchParams = new URLSearchParams(query);
  navigationLog.length = 0;
  setDeferNavigation(false);
};

// По умолчанию роутер-мок — пустышка: навигация без последствий, как было
// до появления пагинации в URL. Блоки, которым нужна честная навигация,
// включают её через enableRouterNavigation() и возвращают исходные
// реализации через restoreRouterMocks() в afterAll.
const mockPush = vi.fn();
const mockReplace = vi.fn();

const enableRouterNavigation = () => {
  mockPush.mockImplementation(applyNavigation('push'));
  mockReplace.mockImplementation(applyNavigation('replace'));
};

const restoreRouterMocks = () => {
  mockPush.mockReset();
  mockReplace.mockReset();
};

vi.mock('next/navigation', () => ({
  useRouter: vi.fn(() => ({
    push: mockPush,
    replace: mockReplace,
  })),
  useSearchParams: vi.fn(() => mockSearchParams),
  usePathname: vi.fn(() => '/catalog'),
}));

describe('CatalogPage - Search Integration (Story 18.4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.useRealTimers();
    resetSearchParams();
    mockPush.mockClear();

    // Mock matchMedia for responsive filter state
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: query === '(min-width: 1024px)', // Simulate desktop
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });
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
          })
        );
      },
      { timeout: 500 }
    );
  });

  it('AC 3: должен удалять параметр search из URL при пустом запросе', async () => {
    const user = userEvent.setup();

    // Запрос уже в URL: SearchAutocomplete держит текст поля во внутреннем
    // состоянии, поэтому вводим его и в поле — только так очистка меняет URL
    resetSearchParams('search=test');

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

    // Запрос уже в URL — иначе сбрасывать в адресной строке нечего
    resetSearchParams('search=nike');

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
    resetSearchParams('search=adidas');

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

  it('AC 4: должен отображать состояния загрузки (Skeleton) при ожидании категорий', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });

    const categoriesService = await import('@/services/categoriesService');
    // Мокаем API с задержкой
    (categoriesService.default.getTree as Mock).mockImplementationOnce(
      () => new Promise(resolve => setTimeout(() => resolve(mockCategories), 100))
    );

    render(<CatalogPage />);

    // Проверяем наличие Skeleton
    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading.querySelector('.animate-pulse')).toBeInTheDocument();

    // Разрешаем таймер
    act(() => {
      vi.runAllTimers();
    });

    // Ждем разрешения категории
    await waitFor(() => {
      expect(screen.getByRole('heading', { level: 1, name: 'Каталог' })).toBeInTheDocument();
    });

    vi.useRealTimers();
  });

  it('AC 3: должен содержать корректную семантику: <search role="search"> и правильный порядок DOM для H1', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByRole('search')).toBeInTheDocument();
    });

    const searchRegion = screen.getByRole('search');
    expect(searchRegion.tagName.toLowerCase()).toBe('search');

    const heading = screen.getByRole('heading', { level: 1 });
    expect(heading).toHaveClass('text-neutral-900');

    const parent = heading.parentElement;
    if (parent) {
      const children = Array.from(parent.children);
      const headingIndex = children.indexOf(heading);
      const searchIndex = children.indexOf(searchRegion);
      expect(headingIndex).toBeLessThan(searchIndex);
    }
  });

  it('F4: фильтры должны быть свёрнуты на мобильных устройствах', async () => {
    // Переопределяем matchMedia для мобильного устройства
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: vi.fn().mockImplementation(query => ({
        matches: false, // Мобильное устройство — ни один media query не совпадает
        media: query,
        onchange: null,
        addListener: vi.fn(),
        removeListener: vi.fn(),
        addEventListener: vi.fn(),
        removeEventListener: vi.fn(),
        dispatchEvent: vi.fn(),
      })),
    });

    render(<CatalogPage />);

    await waitFor(() => {
      // Проверяем, что кнопки фильтров имеют aria-expanded="false"
      const categoryButton = screen.getByRole('button', { name: /Категории/i });
      expect(categoryButton).toHaveAttribute('aria-expanded', 'false');

      const brandButton = screen.getByRole('button', { name: /Бренд/i });
      expect(brandButton).toHaveAttribute('aria-expanded', 'false');
    });
  });
});

// ---------------------------------------------------------------------------
// Тесты сортировки и скрытия пустых категорий (bugfix: Без категории)
// ---------------------------------------------------------------------------
import categoriesService from '@/services/categoriesService';
import brandsService from '@/services/brandsService';

const mockMatchMedia = () => {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(min-width: 1024px)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
};

describe('CatalogPage — сортировка и скрытие пустых категорий', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia();
    resetSearchParams();
    // Сбрасываем getVisibleCategories к дефолтному значению
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([1]);
  });

  it('не показывает категорию Без категории если она скрыта (in_stock_count=0)', async () => {
    (categoriesService.getTree as Mock).mockResolvedValue([
      { id: 1, name: 'Обувь', slug: 'shoes', in_stock_count: 5, products_count: 5, children: [] },
      {
        id: 2,
        name: 'Без категории',
        slug: 'uncategorized',
        in_stock_count: 0,
        products_count: 3,
        children: [],
      },
    ]);
    // visible-categories не возвращает uncategorized (нет in_stock товаров)
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([1]);

    render(<CatalogPage />);

    // Открываем панель категорий
    const categoryBtn = await screen.findByRole('button', { name: /Категории/i });
    await act(async () => {
      categoryBtn.click();
    });

    await waitFor(() => {
      expect(screen.queryByText('Без категории')).not.toBeInTheDocument();
      expect(screen.getByText('Обувь')).toBeInTheDocument();
    });
  });

  it('показывает "Нет категорий" если все категории скрыты', async () => {
    (categoriesService.getTree as Mock).mockResolvedValue([
      { id: 1, name: 'Обувь', slug: 'shoes', in_stock_count: 3, products_count: 3, children: [] },
    ]);
    // visible-categories вернул пустой список
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([]);

    render(<CatalogPage />);

    const categoryBtn = await screen.findByRole('button', { name: /Категории/i });
    await act(async () => {
      categoryBtn.click();
    });

    await waitFor(() => {
      expect(screen.getByText('Нет категорий')).toBeInTheDocument();
    });
  });

  it('показывает весь список если getVisibleCategories вернул ошибку (graceful degradation)', async () => {
    (categoriesService.getTree as Mock).mockResolvedValue([
      { id: 1, name: 'Обувь', slug: 'shoes', in_stock_count: 3, products_count: 3, children: [] },
      {
        id: 2,
        name: 'Без категории',
        slug: 'uncategorized',
        in_stock_count: 0,
        products_count: 1,
        children: [],
      },
    ]);
    (categoriesService.getVisibleCategories as Mock).mockRejectedValue(new Error('500'));

    render(<CatalogPage />);

    const categoryBtn = await screen.findByRole('button', { name: /Категории/i });
    await act(async () => {
      categoryBtn.click();
    });

    await waitFor(() => {
      // При ошибке fallback = показывать всё дерево
      expect(screen.getByText('Обувь')).toBeInTheDocument();
      expect(screen.getByText('Без категории')).toBeInTheDocument();
    });
  });

  it('сохраняет родительскую категорию видимой если дочерняя видима', async () => {
    (categoriesService.getTree as Mock).mockResolvedValue([
      {
        id: 10,
        name: 'Спорт',
        slug: 'sport',
        in_stock_count: 0,
        products_count: 0,
        children: [
          {
            id: 11,
            name: 'Лыжи',
            slug: 'skiing',
            in_stock_count: 2,
            products_count: 2,
            children: [],
          },
        ],
      },
    ]);
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([11]); // только дочерняя

    render(<CatalogPage />);

    const categoryBtn = await screen.findByRole('button', { name: /Категории/i });
    await act(async () => {
      categoryBtn.click();
    });

    await waitFor(() => {
      // Родитель виден потому что дочерняя видима
      expect(screen.getByText('Спорт')).toBeInTheDocument();
    });
  });
});

// ---------------------------------------------------------------------------
// Тесты скрытия брендов без товаров и динамического visible-brands
// ---------------------------------------------------------------------------

describe('CatalogPage — видимость брендов по наличию и фильтрам', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia();
    resetSearchParams();
    (categoriesService.getTree as Mock).mockResolvedValue([
      { id: 1, name: 'Футбол', slug: 'football', in_stock_count: 5, products_count: 5, children: [] },
    ]);
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([1]);
    (brandsService.getAll as Mock).mockResolvedValue(mockBrands);
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([1, 2]);
  });

  it('вызывает первичную загрузку брендов с has_stock=true', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(brandsService.getAll).toHaveBeenCalledWith({ has_stock: true });
    });
  });

  it('не показывает out-of-stock бренд, если его нет в первичном ответе getAll', async () => {
    (brandsService.getAll as Mock).mockResolvedValue([{ id: 2, name: 'Adidas', slug: 'adidas' }]);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
      expect(screen.queryByLabelText('Nike')).not.toBeInTheDocument();
    });
  });

  it('скрывает бренды, которых нет в visible-brands', async () => {
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([1]);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByLabelText('Nike')).toBeInTheDocument();
      expect(screen.queryByLabelText('Adidas')).not.toBeInTheDocument();
    });
  });

  it('сохраняет выбранный бренд видимым, даже если он не входит в visible-brands', async () => {
    const user = userEvent.setup();
    (brandsService.getVisibleBrands as Mock)
      .mockResolvedValueOnce([1, 2])
      .mockResolvedValueOnce([]);

    render(<CatalogPage />);

    const nike = await screen.findByLabelText('Nike');
    await user.click(nike);

    await waitFor(() => {
      expect(screen.getByLabelText('Nike')).toBeInTheDocument();
      expect(screen.queryByLabelText('Adidas')).not.toBeInTheDocument();
    });
  });

  it('показывает полный список брендов при сетевой ошибке visible-brands', async () => {
    (brandsService.getVisibleBrands as Mock).mockRejectedValue(new Error('500'));

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByLabelText('Nike')).toBeInTheDocument();
      expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
    });
  });

  it('показывает "Бренды не найдены", когда visible-brands пустой и нет выбора', async () => {
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([]);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Бренды не найдены')).toBeInTheDocument();
      expect(screen.queryByLabelText('Nike')).not.toBeInTheDocument();
      expect(screen.queryByLabelText('Adidas')).not.toBeInTheDocument();
    });
  });

  it('сбрасывает sidebarVisibleBrandIds при снятии чекбокса "В наличии"', async () => {
    const user = userEvent.setup();
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([]);

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Бренды не найдены')).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText('В наличии'));

    await waitFor(() => {
      expect(screen.getByLabelText('Nike')).toBeInTheDocument();
      expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
    });
  });
});


// ---------------------------------------------------------------------------
// Тесты сохранения номера страницы в URL
// (bugfix: пагинация сбрасывалась на первую страницу при обновлении браузера)
// ---------------------------------------------------------------------------
import productsService from '@/services/productsService';

/** 40 товаров при PAGE_SIZE=12 → 4 страницы пагинации */
const buildProductsResponse = (count: number) => ({
  count,
  next: null,
  previous: null,
  results: mockProducts,
});

/** Последняя навигация по хронологии — не по склейке двух массивов вызовов */
const lastNavigation = (): Navigation | null => navigationLog.at(-1) ?? null;

/** Последний URL, переданный в push/replace */
const lastNavigationUrl = () => lastNavigation()?.url ?? null;

/**
 * Барьер «страница смонтирована и монтажный запрос товаров уже ушёл».
 * Отрисовки брендов для этого мало: справочник брендов и дерево категорий
 * грузятся независимо, а первый getAll уходит только после попытки загрузки
 * дерева (isCategoryLoadAttempted). Под нагрузкой бренды успевают отрисоваться
 * раньше — и mockClear() после такого барьера стирал бы счётчик ДО монтажного
 * запроса, засчитывая его следующему действию пользователя.
 */
const settleCatalog = async () => {
  await screen.findByLabelText('Nike');
  await waitFor(() => {
    expect(productsService.getAll).toHaveBeenCalled();
  });
};

describe('CatalogPage — сохранение страницы пагинации в URL', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia();
    // Честный роутер-мок: push/replace меняют то, что вернёт следующий
    // useSearchParams(). Пустышка делала бы навигацию беспоследственной,
    // и регрессии «клик по странице перезапускает эффекты на [searchParams]»
    // были бы не видны в тестах.
    enableRouterNavigation();
    resetSearchParams();
    (productsService.getAll as Mock).mockResolvedValue(buildProductsResponse(40));
    (categoriesService.getTree as Mock).mockResolvedValue(mockCategories);
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([1]);
    (brandsService.getAll as Mock).mockResolvedValue(mockBrands);
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([1, 2]);
  });

  afterAll(() => {
    // Возвращаем исходные (пустышечные) реализации, чтобы честная навигация
    // не протекала в блоки, написанные под беспоследственный push
    restoreRouterMocks();
    resetSearchParams();
  });

  it('читает номер страницы из URL при монтировании (сценарий F5)', async () => {
    resetSearchParams('page=3');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });
  });

  it('пишет page в URL при клике по номеру страницы', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await user.click(await screen.findByRole('button', { name: '3' }));

    expect(lastNavigationUrl()).toBe('/catalog?page=3');
    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });
  });

  it('делает ровно один запрос товаров на клик по странице', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await screen.findByRole('button', { name: '3' });
    (productsService.getAll as Mock).mockClear();
    (categoriesService.getTree as Mock).mockClear();

    await user.click(screen.getByRole('button', { name: '3' }));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });
    // Смена URL не должна перезапускать эффекты, завязанные на searchParams
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(categoriesService.getTree).not.toHaveBeenCalled();
  });

  it('убирает page из URL при возврате на первую страницу', async () => {
    const user = userEvent.setup();
    resetSearchParams('page=3');

    render(<CatalogPage />);

    await user.click(await screen.findByRole('button', { name: '1' }));

    expect(lastNavigationUrl()).toBe('/catalog');
  });

  it('помечает активную страницу через aria-current', async () => {
    resetSearchParams('page=2');

    render(<CatalogPage />);

    const active = await screen.findByRole('button', { name: '2' });
    expect(active).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('button', { name: '3' })).not.toHaveAttribute('aria-current');
  });

  it('сохраняет остальные параметры URL при смене страницы', async () => {
    const user = userEvent.setup();
    resetSearchParams('search=nike&page=2');

    render(<CatalogPage />);

    await user.click(await screen.findByRole('button', { name: '3' }));

    const url = lastNavigationUrl() ?? '';
    expect(url).toContain('search=nike');
    expect(url).toContain('page=3');
  });

  it('сбрасывает страницу одним запросом при смене фильтра', async () => {
    const user = userEvent.setup();
    resetSearchParams('page=3');

    render(<CatalogPage />);

    await settleCatalog();
    (productsService.getAll as Mock).mockClear();
    mockPush.mockClear();

    await user.click(screen.getByLabelText('Nike'));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    });
    // Ровно один запрос: старая страница вместе с новым фильтром не запрашивается
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    // Бренд теперь зеркалится в URL тем же пушем, что убирает page
    expect(lastNavigationUrl()).toBe('/catalog?brand=nike');
  });

  it('не откатывает выбранную в сайдбаре категорию при клике по странице', async () => {
    const user = userEvent.setup();
    resetSearchParams('category=sport');
    (categoriesService.getTree as Mock).mockResolvedValue([
      { id: 1, name: 'Спорт', slug: 'sport', in_stock_count: 5, products_count: 5, children: [] },
      { id: 2, name: 'Обувь', slug: 'shoes', in_stock_count: 5, products_count: 5, children: [] },
    ]);
    (categoriesService.getVisibleCategories as Mock).mockResolvedValue([1, 2]);

    render(<CatalogPage />);

    await user.click(await screen.findByText('Обувь'));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ category_id: 2 })
      );
    });

    (productsService.getAll as Mock).mockClear();
    await user.click(await screen.findByRole('button', { name: '2' }));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
    });
    // Категория из URL (sport) не должна вытеснить выбранную в сайдбаре (shoes)
    expect(productsService.getAll).toHaveBeenLastCalledWith(
      expect.objectContaining({ category_id: 2, page: 2 })
    );
  });

  it('не схлопывает мультивыбор брендов при клике по странице', async () => {
    const user = userEvent.setup();
    resetSearchParams('brand=nike');

    render(<CatalogPage />);

    await user.click(await screen.findByLabelText('Adidas'));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ brand: '1,2' })
      );
    });

    (productsService.getAll as Mock).mockClear();
    await user.click(await screen.findByRole('button', { name: '2' }));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenLastCalledWith(
        expect.objectContaining({ brand: '1,2', page: 2 })
      );
    });
  });

  it.each(['page=abc', 'page=0', 'page=-1', 'page=1.5', 'page=3abc', 'page=1e3', 'page='])(
    'трактует мусорное значение "%s" как первую страницу',
    async query => {
      resetSearchParams(query);

      render(<CatalogPage />);

      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
      });
    }
  );

  it.each(['page=1', 'page=01', 'page=abc', 'page=0', 'page='])(
    'убирает неканоничный "%s" из URL через replace',
    async query => {
      resetSearchParams(query);

      render(<CatalogPage />);

      await waitFor(() => {
        expect(lastNavigationUrl()).toBe('/catalog');
      });
      // replace, а не push: канонизация внешней ссылки не плодит историю
      expect(lastNavigation()?.type).toBe('replace');
      expect(mockPush).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
      });
      expect(productsService.getAll).toHaveBeenCalledTimes(1);
    }
  );

  it('при канонизации первой страницы удаляет только page', async () => {
    resetSearchParams('category=sport&page=1');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog?category=sport');
    });
    expect(lastNavigation()?.type).toBe('replace');
  });

  it('не трогает URL, когда page уже канонична', async () => {
    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    });
    expect(lastNavigation()).toBeNull();
  });

  it('откатывается на первую страницу через replace, когда API отдаёт 404', async () => {
    resetSearchParams('page=999');
    (productsService.getAll as Mock)
      .mockRejectedValueOnce({ response: { status: 404 } })
      .mockResolvedValue(buildProductsResponse(24));

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    });
    expect(screen.queryByText('Не удалось загрузить товары')).not.toBeInTheDocument();
    // replace, а не push: иначе «назад» возвращает на битую страницу
    expect(mockReplace).toHaveBeenCalledWith('/catalog', expect.anything());
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('показывает ошибку, если 404 пришёл уже на первой странице', async () => {
    (productsService.getAll as Mock).mockRejectedValue({ response: { status: 404 } });

    render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Не удалось загрузить товары')).toBeInTheDocument();
    });
  });

  it('подхватывает страницу из URL при навигации «назад»', async () => {
    resetSearchParams('page=3');

    const { rerender } = render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });

    // Кнопка «назад»: URL сменился, компонент остался смонтированным
    resetSearchParams('page=2');
    rerender(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
    });
  });

  it('не выдёргивает пользователя с новой страницы устаревшим 404', async () => {
    let rejectStale: (reason: unknown) => void = () => {};
    const stalePageThree = new Promise<never>((_, reject) => {
      rejectStale = reject;
    });
    // Ответ по 3-й странице «зависает» и провалится 404 уже после того,
    // как пользователь ушёл на 2-ю
    (productsService.getAll as Mock).mockImplementation((filters: { page?: number }) =>
      filters.page === 3 ? stalePageThree : Promise.resolve(buildProductsResponse(40))
    );

    render(<CatalogPage />);

    const pageThree = await screen.findByRole('button', { name: '3' });
    await act(async () => {
      pageThree.click();
    });
    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });
    // История вызовов до критической секции неинтересна: запрос 1-й страницы
    // при монтировании легитимен, проверяем только последствия устаревшего 404
    (productsService.getAll as Mock).mockClear();
    mockReplace.mockClear();

    // Гонка из находки ревью: 404 по прежней странице приходит уже после того,
    // как пользователь ушёл на другую. В React 19 и сам дискретный клик
    // обрабатывается микрозадачей, поэтому продолжение упавшего запроса
    // успевает отработать даже ДО commit нового page — инвалидации по commit
    // (layout-эффект) для этого мало, версия обязана расти уже в момент
    // намерения пользователя, в обработчике события.
    //
    // act-окружение отключаем намеренно: под act клик, рендер и эффекты
    // сливаются в одну очередь и гонки нет. Порядок задан явно (отказ → один
    // microtask hop → клик), чтобы продолжение catch гарантированно опередило
    // микрозадачу React, а не зависело от деталей его планировщика.
    const actGlobal = globalThis as typeof globalThis & {
      IS_REACT_ACT_ENVIRONMENT?: boolean;
    };
    const prevActEnv = actGlobal.IS_REACT_ACT_ENVIRONMENT;
    actGlobal.IS_REACT_ACT_ENVIRONMENT = false;
    try {
      rejectStale({ response: { status: 404 } });
      // Один hop: реакция Promise.all уже отработала, продолжение catch стоит
      // следующим в очереди — клик вклинивается ровно перед ним
      await Promise.resolve();
      screen.getByRole('button', { name: '2' }).click();

      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
      });
    } finally {
      actGlobal.IS_REACT_ACT_ENVIRONMENT = prevActEnv;
    }

    // Устаревший 404 не откатывает ни состояние, ни URL
    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-current', 'page');
    expect(productsService.getAll).not.toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    expect(mockReplace).not.toHaveBeenCalled();
    expect(lastNavigationUrl()).toBe('/catalog?page=2');
  });
  it('не отменяет навигацию «назад»/«вперёд» устаревшим 404', async () => {
    let rejectStale: (reason: unknown) => void = () => {};
    const stalePageThree = new Promise<never>((_, reject) => {
      rejectStale = reject;
    });
    (productsService.getAll as Mock).mockImplementation((filters: { page?: number }) =>
      filters.page === 3 ? stalePageThree : Promise.resolve(buildProductsResponse(40))
    );

    resetSearchParams('page=3');
    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 3 }));
    });
    (productsService.getAll as Mock).mockClear();
    mockReplace.mockClear();
    navigationLog.length = 0;

    // Кнопка «назад» отличается от клика по пагинации: обработчика события у нас
    // нет, состояние page в первом render после смены URL ещё равно 3, а
    // productFilters не меняется — инвалидация по productFilters не успевает
    // сработать до passive-эффекта синхронизации. Если в это окно прилетит 404
    // по прежней странице, его seq всё ещё актуален и откат на первую страницу
    // отменит навигацию пользователя.
    //
    // act-окружение отключаем намеренно: под act commit и passive-эффекты
    // сливаются в одну очередь, и окна между ними не существует.
    const actGlobal = globalThis as typeof globalThis & {
      IS_REACT_ACT_ENVIRONMENT?: boolean;
    };
    const prevActEnv = actGlobal.IS_REACT_ACT_ENVIRONMENT;
    actGlobal.IS_REACT_ACT_ENVIRONMENT = false;
    try {
      // Браузер сменил URL на предыдущую запись истории
      resetSearchParams('page=2');
      // Ререндер с новым URL. В приложении его вызывает router-transition,
      // в тесте — любое безобидное локальное состояние: важен сам факт commit
      // нового pageParam, а не то, что его инициировало.
      screen.getByRole('button', { name: 'Список' }).click();
      // Дискретный клик React 19 обрабатывает микрозадачей: после этих hop'ов
      // render, commit и layout-эффекты отработали, а passive-эффекты
      // (в том числе синхронизация page из URL) ещё ждут макрозадачи
      await Promise.resolve();
      await Promise.resolve();

      rejectStale({ response: { status: 404 } });
      // Макрозадача: продолжение catch отработало, отложенные passive-эффекты
      // (синхронизация page из URL и следующий запрос) успели сработать
      await new Promise(resolve => setTimeout(resolve, 0));

      // Устаревший 404 не отменил переход браузера: ни отката состояния, ни чистки URL
      expect(mockReplace).not.toHaveBeenCalled();
      expect(navigationLog).toEqual([]);

      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }));
      });
    } finally {
      actGlobal.IS_REACT_ACT_ENVIRONMENT = prevActEnv;
    }

    expect(productsService.getAll).not.toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    expect(screen.getByRole('button', { name: '2' })).toHaveAttribute('aria-current', 'page');
  });
});

// ---------------------------------------------------------------------------
// Тесты зеркалирования фильтров сайдбара в URL
// (bugfix: цена, сортировка, «в наличии», бренды и категория сбрасывались на F5)
// ---------------------------------------------------------------------------

/** Дерево с товарами в наличии во всех узлах + узел без наличия (id 4) */
const filterTree = [
  {
    id: 1,
    name: 'Спорт',
    slug: 'sport',
    in_stock_count: 5,
    products_count: 5,
    children: [
      { id: 3, name: 'Лыжи', slug: 'skiing', in_stock_count: 2, products_count: 2, children: [] },
    ],
  },
  { id: 2, name: 'Обувь', slug: 'obuv', in_stock_count: 5, products_count: 5, children: [] },
  { id: 4, name: 'Архив', slug: 'archive', in_stock_count: 0, products_count: 7, children: [] },
];

/** Скелетон выдачи товаров: 12 плиток h-64 с animate-pulse */
const productSkeletonCount = () => document.querySelectorAll('.h-64.animate-pulse').length;

const rangeInputs = () =>
  Array.from(document.querySelectorAll<HTMLInputElement>('input[type="range"]'));

/** На странице два элемента с ролью combobox: автокомплит поиска и <select> сортировки */
const orderingSelect = () => document.querySelector('select') as HTMLSelectElement;

describe('CatalogPage — фильтры сайдбара в URL', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockMatchMedia();
    enableRouterNavigation();
    resetSearchParams();
    (productsService.getAll as Mock).mockResolvedValue(buildProductsResponse(40));
    (categoriesService.getTree as Mock).mockResolvedValue(filterTree);
    // Сервер сужает список категорий ровно так же, как фильтр выдачи: с in_stock
    // узел без наличия не возвращается, без него — возвращается
    (categoriesService.getVisibleCategories as Mock).mockImplementation(
      (filters: { in_stock?: boolean }) =>
        Promise.resolve(filters?.in_stock ? [1, 2, 3] : [1, 2, 3, 4])
    );
    (brandsService.getAll as Mock).mockResolvedValue(mockBrands);
    (brandsService.getVisibleBrands as Mock).mockResolvedValue([1, 2]);
  });

  afterAll(() => {
    restoreRouterMocks();
    resetSearchParams();
  });

  // --- Восстановление состояния из URL -------------------------------------

  it('восстанавливает все пять фильтров из URL при монтировании (сценарий F5)', async () => {
    resetSearchParams(
      'category=obuv&brand=nike,adidas&ordering=-created_at&min_price=1000&max_price=5000&in_stock=false'
    );

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          category_id: 2,
          brand: '1,2',
          ordering: '-created_at',
          min_price: 1000,
          max_price: 5000,
          page: 1,
        })
      );
    });
    // in_stock снят — в запрос параметр не уходит
    expect((productsService.getAll as Mock).mock.calls[0][0]).not.toHaveProperty('in_stock');
    // Ровно один запрос: промежуточного рендера с дефолтами не было
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    // URL уже канонический — навигаций быть не должно
    expect(lastNavigation()).toBeNull();
    expect(screen.getByLabelText('Nike')).toBeChecked();
    expect(screen.getByLabelText('Adidas')).toBeChecked();
    expect(screen.getByLabelText('В наличии')).not.toBeChecked();
    expect(orderingSelect()).toHaveValue('-created_at');
  });

  it('применяет все параметры ссылки, открытой в новой вкладке, одним запросом', async () => {
    resetSearchParams('category=obuv&brand=nike,adidas&ordering=-created_at&page=2');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({
          category_id: 2,
          brand: '1,2',
          ordering: '-created_at',
          page: 2,
        })
      );
    });
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
  });

  it('делает один запрос на ссылке только с категорией', async () => {
    resetSearchParams('category=obuv');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ category_id: 2 })
      );
    });
    // Промежуточного запроса без category_id быть не должно: slug → id
    // резолвится из дерева, и до синхронизации запрос ждёт
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(lastNavigation()).toBeNull();
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
  });

  it('не оставляет висеть скелетон на ссылке с несуществующей категорией', async () => {
    resetSearchParams('category=нет-такой');

    render(<CatalogPage />);

    // Гейт по категории не должен закрыться навсегда: slug в дереве не найден,
    // расхождения с состоянием (null === null) нет, запрос уходит без category_id
    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalled();
    });
    expect((productsService.getAll as Mock).mock.calls[0][0]).not.toHaveProperty('category_id');
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
  });

  // --- Запись фильтров в URL ------------------------------------------------

  it('пишет категорию в URL, не перезапрашивая дерево и не схлопывая ветки', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    // Раскрываем «Спорт», чтобы проверить, что выбор категории ветку не схлопнет
    await user.click(await screen.findByRole('button', { name: 'Развернуть категорию' }));
    expect(screen.getByText('Лыжи')).toBeInTheDocument();

    (productsService.getAll as Mock).mockClear();
    (categoriesService.getTree as Mock).mockClear();

    await user.click(screen.getByText('Обувь'));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ category_id: 2 })
      );
    });
    expect(lastNavigationUrl()).toBe('/catalog?category=obuv');
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(categoriesService.getTree).not.toHaveBeenCalled();
    expect(screen.getByText('Лыжи')).toBeInTheDocument();
  });

  it('пишет мультивыбор брендов в URL как CSV из slug-ов', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await user.click(await screen.findByLabelText('Nike'));
    expect(lastNavigationUrl()).toBe('/catalog?brand=nike');

    await user.click(screen.getByLabelText('Adidas'));
    expect(lastNavigationUrl()).toBe('/catalog?brand=nike,adidas');

    await user.click(screen.getByLabelText('Nike'));
    expect(lastNavigationUrl()).toBe('/catalog?brand=adidas');

    // Снятие последнего бренда убирает параметр целиком
    await user.click(screen.getByLabelText('Adidas'));
    expect(lastNavigationUrl()).toBe('/catalog');
    await waitFor(() => {
      expect((productsService.getAll as Mock).mock.calls.at(-1)?.[0]).not.toHaveProperty('brand');
    });
  });

  it('сохраняет поведение старой одиночной ссылки на бренд', async () => {
    resetSearchParams('brand=nike');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ brand: '1' }));
    });
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText('Nike')).toBeChecked();
    expect(screen.getByLabelText('Adidas')).not.toBeChecked();
    expect(lastNavigation()).toBeNull();
  });

  it('пишет сортировку в URL и делает ровно один запрос', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await settleCatalog();
    (productsService.getAll as Mock).mockClear();
    (categoriesService.getTree as Mock).mockClear();

    await user.selectOptions(orderingSelect(), '-created_at');

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: '-created_at' })
      );
    });
    expect(lastNavigationUrl()).toBe('/catalog?ordering=-created_at');
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(categoriesService.getTree).not.toHaveBeenCalled();
  });

  it('пишет диапазон цены в URL, не записывая значения по умолчанию', async () => {
    render(<CatalogPage />);

    await settleCatalog();
    const [minInput, maxInput] = rangeInputs();

    await act(async () => {
      fireEvent.change(minInput, { target: { value: '1000' } });
    });
    // Верхняя граница по умолчанию в URL не пишется.
    // Явный бюджет ожидания: каждый ассерт пережидает PRICE_COMMIT_DELAY_MS
    // (300 мс) продуктового debounce, и умолчания waitFor в 1000 мс под
    // нагрузкой не хватало — тест падал через раз не по существу.
    await waitFor(
      () => {
        expect(lastNavigationUrl()).toBe('/catalog?min_price=1000');
      },
      { timeout: 3000 }
    );

    await act(async () => {
      fireEvent.change(maxInput, { target: { value: '5000' } });
    });
    await waitFor(
      () => {
        expect(lastNavigationUrl()).toBe('/catalog?min_price=1000&max_price=5000');
      },
      { timeout: 3000 }
    );

    await waitFor(
      () => {
        expect(productsService.getAll).toHaveBeenCalledWith(
          expect.objectContaining({ min_price: 1000, max_price: 5000 })
        );
      },
      { timeout: 3000 }
    );
  });

  it('применяет диапазон цены один раз после паузы, не записывая промежуточные шаги', async () => {
    render(<CatalogPage />);

    await settleCatalog();
    (productsService.getAll as Mock).mockClear();
    navigationLog.length = 0;

    const [minInput] = rangeInputs();

    // Перетаскивание ползунка: onChange на каждый шаг
    await act(async () => {
      fireEvent.change(minInput, { target: { value: '1000' } });
      fireEvent.change(minInput, { target: { value: '1500' } });
      fireEvent.change(minInput, { target: { value: '2000' } });
    });

    // UI ползунка реагирует на каждый шаг сразу
    expect((minInput as HTMLInputElement).value).toBe('2000');
    // Промежуточные шаги не уходят ни в историю, ни в API
    expect(navigationLog).toEqual([]);
    expect(productsService.getAll).not.toHaveBeenCalled();

    await waitFor(
      () => {
        expect(lastNavigationUrl()).toBe('/catalog?min_price=2000');
      },
      { timeout: 3000 }
    );
    // Одна запись в истории на всё перетаскивание
    expect(navigationLog).toHaveLength(1);
    expect(navigationLog[0].type).toBe('push');

    await waitFor(
      () => {
        expect(productsService.getAll).toHaveBeenCalledWith(
          expect.objectContaining({ min_price: 2000 })
        );
      },
      { timeout: 3000 }
    );
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
  });

  it('пишет только снятое «в наличии» и не перезапрашивает дерево категорий', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await screen.findByLabelText('В наличии');
    (categoriesService.getTree as Mock).mockClear();

    await user.click(screen.getByLabelText('В наличии'));
    expect(lastNavigationUrl()).toBe('/catalog?in_stock=false');
    // Сайдбар распахивается до полного дерева: узел без наличия становится виден
    await waitFor(() => {
      expect(screen.getByText('Архив')).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText('В наличии'));
    expect(lastNavigationUrl()).toBe('/catalog');
    await waitFor(() => {
      expect(screen.queryByText('Архив')).not.toBeInTheDocument();
    });

    // getTree за всё время жизни страницы вызывается ровно один раз
    expect(categoriesService.getTree).not.toHaveBeenCalled();
  });

  // --- Внешняя навигация «назад»/«вперёд» -----------------------------------

  it('снимает выбор брендов при «назад» на URL без brand', async () => {
    resetSearchParams('brand=nike');

    const { rerender } = render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ brand: '1' }));
    });
    (productsService.getAll as Mock).mockClear();

    resetSearchParams('');
    rerender(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByLabelText('Nike')).not.toBeChecked();
    });
    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalled();
    });
    expect((productsService.getAll as Mock).mock.calls.at(-1)?.[0]).not.toHaveProperty('brand');
  });

  it('возвращает сортировку к умолчанию при «назад» и перезапрашивает выдачу', async () => {
    resetSearchParams('ordering=-created_at');

    const { rerender } = render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: '-created_at' })
      );
    });

    resetSearchParams('');
    rerender(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: 'name' })
      );
    });
    expect(orderingSelect()).toHaveValue('name');
  });

  it('распахивает сайдбар при «назад» на ?in_stock=false', async () => {
    const { rerender } = render(<CatalogPage />);

    await waitFor(() => {
      expect(screen.queryByText('Архив')).not.toBeInTheDocument();
    });

    resetSearchParams('in_stock=false');
    rerender(<CatalogPage />);

    await waitFor(() => {
      expect(screen.getByText('Архив')).toBeInTheDocument();
    });
    expect((productsService.getAll as Mock).mock.calls.at(-1)?.[0]).not.toHaveProperty('in_stock');
  });

  // --- Канонизация URL ------------------------------------------------------

  it('вычищает значения по умолчанию из внешней ссылки одним replace', async () => {
    resetSearchParams('ordering=name&in_stock=true&min_price=1');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    // replace, а не push: чистка внешней ссылки не должна плодить историю
    expect(navigationLog).toHaveLength(1);
    expect(navigationLog[0].type).toBe('replace');
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('трактует мусор в параметрах как умолчания и вычищает его из URL', async () => {
    resetSearchParams('ordering=drop_table&min_price=abc&max_price=-5&brand=нет-такого');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    expect(mockPush).not.toHaveBeenCalled();

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: 'name', min_price: 1, max_price: 50000 })
      );
    });
    // max_price=-5 → умолчание СВОЕГО конца (50000), а не clamp к PRICE_MIN
    expect((productsService.getAll as Mock).mock.calls.at(-1)?.[0]).not.toHaveProperty('brand');
    expect(screen.queryByText('Не удалось загрузить товары')).not.toBeInTheDocument();
  });

  it('сбрасывает инвертированный диапазон цены к обоим умолчаниям', async () => {
    resetSearchParams('min_price=9000&max_price=1000');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ min_price: 1, max_price: 50000 })
      );
    });
    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
  });

  it('не оставляет висеть скелетон на ссылке с несуществующим брендом', async () => {
    resetSearchParams('brand=нет-такого');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalled();
    });
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect(lastNavigationUrl()).toBe('/catalog');
    expect(lastNavigation()?.type).toBe('replace');
  });

  // --- Сброс фильтров -------------------------------------------------------

  it('сбрасывает фильтры сайдбара одной навигацией и одним запросом', async () => {
    const user = userEvent.setup();
    resetSearchParams(
      'category=obuv&brand=nike&ordering=-name&min_price=1000&max_price=5000&in_stock=false'
    );

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ category_id: 2, brand: '1' })
      );
    });
    (productsService.getAll as Mock).mockClear();
    navigationLog.length = 0;

    await user.click(screen.getByRole('button', { name: 'Сбросить' }));

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: 'name', min_price: 1, max_price: 50000, in_stock: true })
      );
    });
    expect(navigationLog).toHaveLength(1);
    expect(navigationLog[0]).toEqual({ type: 'push', url: '/catalog' });
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
  });

  it('сохраняет активный бейдж при сбросе фильтров', async () => {
    const user = userEvent.setup();
    resetSearchParams('is_new=true&brand=nike&ordering=-name');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(expect.objectContaining({ brand: '1' }));
    });
    navigationLog.length = 0;

    await user.click(screen.getByRole('button', { name: 'Сбросить' }));

    expect(lastNavigationUrl()).toBe('/catalog?is_new=true');
    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ is_new: true, ordering: 'name' })
      );
    });
    expect((productsService.getAll as Mock).mock.calls.at(-1)?.[0]).not.toHaveProperty('brand');
  });

  it('не показывает кнопку «Применить»', async () => {
    render(<CatalogPage />);

    await screen.findByRole('button', { name: 'Сбросить' });
    expect(screen.queryByRole('button', { name: 'Применить' })).not.toBeInTheDocument();
  });

  // --- Устаревший ответ при внешней навигации -------------------------------

  it('не отменяет «назад» по ordering устаревшим 404', async () => {
    let rejectStale: (reason: unknown) => void = () => {};
    const staleOrdering = new Promise<never>((_, reject) => {
      rejectStale = reject;
    });
    (productsService.getAll as Mock).mockImplementation((filters: { ordering?: string }) =>
      filters.ordering === '-created_at' ? staleOrdering : Promise.resolve(buildProductsResponse(40))
    );

    resetSearchParams('ordering=-created_at&page=2');
    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ ordering: '-created_at', page: 2 })
      );
    });
    (productsService.getAll as Mock).mockClear();
    mockReplace.mockClear();
    navigationLog.length = 0;

    // act-окружение отключаем намеренно: под act commit и passive-эффекты
    // сливаются в одну очередь, и окна между ними не существует. Здесь важно
    // именно окно: в первом render после «назад» состояние ordering ещё прежнее,
    // productFilters не менялись, и без обобщённой инвалидации requestSeq
    // прилетевший 404 считался бы актуальным и откатил бы страницу на первую.
    const actGlobal = globalThis as typeof globalThis & {
      IS_REACT_ACT_ENVIRONMENT?: boolean;
    };
    const prevActEnv = actGlobal.IS_REACT_ACT_ENVIRONMENT;
    actGlobal.IS_REACT_ACT_ENVIRONMENT = false;
    try {
      // Браузер сменил URL на предыдущую запись истории
      resetSearchParams('page=2');
      // Ререндер с новым URL — как в тесте пагинации, через безобидное локальное состояние
      screen.getByRole('button', { name: 'Список' }).click();
      await Promise.resolve();
      await Promise.resolve();

      rejectStale({ response: { status: 404 } });
      await new Promise(resolve => setTimeout(resolve, 0));

      expect(mockReplace).not.toHaveBeenCalled();
      expect(navigationLog).toEqual([]);

      await waitFor(() => {
        expect(productsService.getAll).toHaveBeenCalledWith(
          expect.objectContaining({ ordering: 'name', page: 2 })
        );
      });
    } finally {
      actGlobal.IS_REACT_ACT_ENVIRONMENT = prevActEnv;
    }

    // Устаревший 404 не выдернул пользователя на первую страницу
    expect(productsService.getAll).not.toHaveBeenCalledWith(expect.objectContaining({ page: 1 }));
    // Скелетон не остался висеть: за бампом requestSeq последовал запрос
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
  });

  // --- Findings ревью: гонки снимка URL, устаревшие ответы, канонизация ------

  it('не теряет первый фильтр, когда второй меняют до обновления снимка searchParams', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);

    await settleCatalog();
    navigationLog.length = 0;
    // До commit транзишена useSearchParams отдаёт прежний снимок: вторая
    // навигация обязана достроиться к первой, а не строиться от URL до неё.
    setDeferNavigation(true);

    await user.click(screen.getByLabelText('Nike'));
    await user.selectOptions(orderingSelect(), '-created_at');

    expect(lastNavigationUrl()).toBe('/catalog?brand=nike&ordering=-created_at');

    // Снимок догнал наши записи — дальше база снова берётся из него
    await act(async () => {
      flushDeferredNavigation();
    });
    setDeferNavigation(false);
  });

  it('отменяет ожидающий debounce цены при сбросе фильтров', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);
    await settleCatalog();

    // Первый сброс приводит priceRange к константе умолчаний: со второго раза
    // setPriceRange(DEFAULT_PRICE_RANGE) не меняет идентичность объекта, эффект
    // синхронизации драфта не перезапускается — и таймер debounce остаётся жить.
    await user.click(screen.getByRole('button', { name: 'Сбросить' }));

    const [minInput] = rangeInputs();
    await act(async () => {
      fireEvent.change(minInput, { target: { value: '3000' } });
    });

    navigationLog.length = 0;
    (productsService.getAll as Mock).mockClear();

    await user.click(screen.getByRole('button', { name: 'Сбросить' }));

    // Пауза заведомо длиннее PRICE_COMMIT_DELAY_MS (300 мс)
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 400));
    });

    expect(navigationLog.some(navigation => navigation.url.includes('min_price'))).toBe(false);
    expect((minInput as HTMLInputElement).value).toBe('1');
    // Драфт, от которого пользователь ушёл, не доезжает ни до URL, ни до API
    expect(productsService.getAll).not.toHaveBeenCalledWith(
      expect.objectContaining({ min_price: 3000 })
    );
  });

  it('делает один запрос на ссылке с категорией и бейджем', async () => {
    resetSearchParams('category=obuv&is_new=true');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ category_id: 2, is_new: true })
      );
    });
    // Бейдж не должен обходить гейт по категории: промежуточного запроса
    // без category_id (дерево ещё не загружено) быть не должно
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect((productsService.getAll as Mock).mock.calls[0][0]).toHaveProperty('category_id', 2);
  });

  it('игнорирует устаревший ответ visible-categories', async () => {
    const user = userEvent.setup();
    let resolveStale: (ids: number[]) => void = () => {};
    let call = 0;
    (categoriesService.getVisibleCategories as Mock).mockImplementation(() => {
      call += 1;
      if (call === 1) {
        return new Promise<number[]>(resolve => {
          resolveStale = resolve;
        });
      }
      return Promise.resolve([1, 2, 3]);
    });

    render(<CatalogPage />);

    await settleCatalog();
    await user.selectOptions(orderingSelect(), '-created_at');

    await waitFor(() => {
      expect(categoriesService.getVisibleCategories).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.getByText('Обувь')).toBeInTheDocument();
    });

    // Ответ по прежним фильтрам приходит последним — сайдбар он менять не вправе
    await act(async () => {
      resolveStale([1]);
    });

    expect(screen.getByText('Обувь')).toBeInTheDocument();
  });

  it('игнорирует устаревший ответ visible-brands', async () => {
    const user = userEvent.setup();
    let resolveStale: (ids: number[]) => void = () => {};
    let call = 0;
    (brandsService.getVisibleBrands as Mock).mockImplementation(() => {
      call += 1;
      if (call === 1) {
        return new Promise<number[]>(resolve => {
          resolveStale = resolve;
        });
      }
      return Promise.resolve([1, 2]);
    });

    render(<CatalogPage />);

    await settleCatalog();
    await user.selectOptions(orderingSelect(), '-created_at');

    await waitFor(() => {
      expect(brandsService.getVisibleBrands).toHaveBeenCalledTimes(2);
    });
    await waitFor(() => {
      expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
    });

    await act(async () => {
      resolveStale([1]);
    });

    expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
  });

  it('вычищает неизвестный бренд из URL, когда справочник брендов пуст', async () => {
    (brandsService.getAll as Mock).mockResolvedValue([]);
    resetSearchParams('brand=nike');

    render(<CatalogPage />);

    // Справочник загрузился успешно и пуст — сопоставить slug не с чем,
    // значит параметр в URL заведомо мусорный и остаться в нём не должен
    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    expect(lastNavigation()?.type).toBe('replace');
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('оставляет бренд в URL, если справочник брендов не загрузился', async () => {
    (brandsService.getAll as Mock).mockRejectedValue(new Error('network'));
    resetSearchParams('brand=nike');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalled();
    });
    // Ошибка загрузки — не повод стирать валидный параметр: знать, что он
    // мусорный, страница не может
    expect(navigationLog).toEqual([]);
  });

  it('канонизирует мусорную ссылку с неизвестным брендом одной заменой', async () => {
    resetSearchParams('ordering=drop_table&min_price=abc&brand=нет-такого');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    // Контракт: мусор вычищается ОДНИМ replace, а не по мере догрузки справочников
    expect(navigationLog).toHaveLength(1);
    expect(navigationLog[0].type).toBe('replace');
  });

  it('вычищает несуществующую категорию из URL', async () => {
    resetSearchParams('category=нет-такой');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    expect(lastNavigation()?.type).toBe('replace');
    expect(navigationLog).toHaveLength(1);
    expect(productsService.getAll).toHaveBeenCalledTimes(1);
    expect((productsService.getAll as Mock).mock.calls[0][0]).not.toHaveProperty('category_id');
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
  });
  it('отменяет отложенный commit цены при «назад», не менявшем диапазон', async () => {
    resetSearchParams('ordering=-created_at');

    const { rerender } = render(<CatalogPage />);
    await settleCatalog();

    const [minInput] = rangeInputs();
    await act(async () => {
      fireEvent.change(minInput, { target: { value: '3000' } });
    });

    // «Назад» на URL без ordering. Применённый priceRange при этом не меняется
    // (в обеих ссылках цена — умолчания), поэтому setPriceRange остаётся no-op,
    // эффект синхронизации драфта не перезапускается и таймер debounce переживает
    // внешнюю навигацию, если её не обнаружить отдельно.
    resetSearchParams('');
    (productsService.getAll as Mock).mockClear();
    rerender(<CatalogPage />);

    // Пауза заведомо длиннее PRICE_COMMIT_DELAY_MS (300 мс)
    await act(async () => {
      await new Promise(resolve => setTimeout(resolve, 400));
    });

    expect(navigationLog.some(navigation => navigation.url.includes('min_price'))).toBe(false);
    expect(productsService.getAll).not.toHaveBeenCalledWith(
      expect.objectContaining({ min_price: 3000 })
    );
    // Драфт возвращается к применённому диапазону, а не остаётся на 3000
    expect((minInput as HTMLInputElement).value).toBe('1');
  });

  it('не отменяет debounce цены собственной навигацией другого фильтра', async () => {
    const user = userEvent.setup();

    render(<CatalogPage />);
    await settleCatalog();

    const [minInput] = rangeInputs();
    await act(async () => {
      fireEvent.change(minInput, { target: { value: '3000' } });
    });

    // Собственный push другого фильтра тоже меняет снимок searchParams, но
    // намерение пользователя по цене остаётся в силе — отменять его нельзя
    await user.click(screen.getByLabelText('Nike'));

    await waitFor(
      () => {
        expect(lastNavigationUrl()).toBe('/catalog?brand=nike&min_price=3000');
      },
      { timeout: 3000 }
    );
  });

  it('вычищает категорию из URL, когда дерево категорий успешно пустое', async () => {
    (categoriesService.getTree as Mock).mockResolvedValue([]);
    resetSearchParams('category=obuv');

    render(<CatalogPage />);

    // Успешно загруженное пустое дерево — такое же основание считать slug
    // мусорным, как и непустое: сопоставить его не с чем
    await waitFor(() => {
      expect(lastNavigationUrl()).toBe('/catalog');
    });
    expect(lastNavigation()?.type).toBe('replace');
    expect(navigationLog).toHaveLength(1);
    await waitFor(() => {
      expect(productSkeletonCount()).toBe(0);
    });
  });

  it('оставляет категорию в URL, если дерево категорий не загрузилось', async () => {
    (categoriesService.getTree as Mock).mockRejectedValue(new Error('network'));
    resetSearchParams('category=obuv');

    render(<CatalogPage />);

    await waitFor(() => {
      expect(productsService.getAll).toHaveBeenCalled();
    });
    // Ошибка загрузки — не повод стирать валидный параметр: знать, что он
    // мусорный, страница не может
    expect(navigationLog).toEqual([]);
  });
});
