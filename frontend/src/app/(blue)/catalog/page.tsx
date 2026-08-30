/**
 * Страница каталога товаров FREESPORT Platform
 * Загружает реальные товары из API и применяет фильтры (Story 12.7)
 */

'use client';

import React, { useCallback, useEffect, useLayoutEffect, useMemo, useState, Suspense } from 'react';
import NextImage from 'next/image';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import Button from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { SearchAutocomplete } from '@/components/business/SearchAutocomplete';
import { Skeleton } from '@/components/ui/Skeleton';
import { Grid2x2, List, ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';
import { ProductCard as BusinessProductCard } from '@/components/business/ProductCard/ProductCard';
import productsService, { type ProductFilters } from '@/services/productsService';
import categoriesService from '@/services/categoriesService';
import brandsService from '@/services/brandsService';
import type { AxiosError } from 'axios';
import type { Product, CategoryTree as CategoryTreeResponse, Brand } from '@/types/api';
import { useCartStore } from '@/stores/cartStore';
import { useAuthStore } from '@/stores/authStore';
import { useFavoritesStore } from '@/stores/favoritesStore';
import { useToast } from '@/components/ui/Toast';

type PriceRange = {
  min: number;
  max: number;
};

type PriceRangeSliderProps = {
  min: number;
  max: number;
  step: number;
  value: PriceRange;
  onChange: (value: PriceRange) => void;
};

type CategoryNode = {
  id: number;
  label: string;
  slug?: string;
  icon?: string;
  inStockCount: number;
  children?: CategoryNode[];
};

const PRICE_MIN = 1;
const PRICE_MAX = 50000;
const DEFAULT_PRICE_RANGE: PriceRange = { min: PRICE_MIN, max: PRICE_MAX };
const PRICE_STEP = 500;
// Пауза перед применением диапазона цены. Ползунок шлёт onChange на КАЖДЫЙ шаг
// перетаскивания: без паузы каждый шаг создавал бы запись в истории браузера и
// отдельный запрос товаров. UI ползунка при этом двигается сразу (см. priceDraft).
const PRICE_COMMIT_DELAY_MS = 300;
const PAGE_SIZE = 12;
const MAX_VISIBLE_PAGES = 5;
const DEFAULT_ORDERING = 'name';

// Константы анимации фильтров (F2, F5, F6)
const FILTER_ANIMATION_DURATION = 'duration-[180ms]';
const CATEGORY_MAX_HEIGHT = 'max-h-[1000px]'; // ~40 категорий × 24px + padding
const BRANDS_MAX_HEIGHT = 'max-h-[500px]'; // ~20 брендов × 24px + padding
const DESKTOP_BREAKPOINT = '(min-width: 1024px)'; // Синхронизировано с Tailwind lg:

// useLayoutEffect безопасен только на клиенте; на сервере fallback на useEffect (F1)
const useIsomorphicLayoutEffect = typeof window !== 'undefined' ? useLayoutEffect : useEffect;

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

/**
 * Разбирает query-параметр `page`. Всё, что не является строкой из одних цифр
 * (`abc`, `3abc`, `1e3`, `2.9`, `-1`, пустая строка), и всё вне безопасного
 * диапазона трактуется как первая страница — каталог не должен падать на кривой ссылке.
 */
const parsePageNumber = (value: string | null): number => {
  if (!value || !/^\d+$/.test(value)) {
    return 1;
  }
  const page = Number(value);
  return Number.isSafeInteger(page) && page >= 1 ? page : 1;
};

/** Белый список значений <select> сортировки: всё остальное — сортировка по умолчанию */
const ORDERING_OPTIONS: readonly string[] = [
  '-created_at',
  'min_retail_price',
  '-min_retail_price',
  'name',
  '-name',
];

/** Мусор в `?ordering=` не должен уезжать в запрос — страница молча берёт умолчание */
const parseOrdering = (value: string | null): string =>
  value && ORDERING_OPTIONS.includes(value) ? value : DEFAULT_ORDERING;

/**
 * Один конец диапазона цены. Всё, что не является целым числом в
 * [PRICE_MIN, PRICE_MAX], заменяется умолчанием СВОЕГО конца. Clamp запрещён:
 * бэкенд отрицательное значение и так игнорирует, а зажатие `max_price=-5`
 * к PRICE_MIN дало бы пользователю пустую выдачу вместо всего каталога.
 */
const parsePriceBound = (value: string | null, fallback: number): number => {
  if (!value || !/^\d+$/.test(value)) {
    return fallback;
  }
  const parsed = Number(value);
  return Number.isSafeInteger(parsed) && parsed >= PRICE_MIN && parsed <= PRICE_MAX
    ? parsed
    : fallback;
};

/**
 * Разбор пары концов диапазона одним правилом, а не двумя независимыми:
 * инвертированный диапазон (`?min_price=9000&max_price=1000`) сбрасывает ОБА
 * конца к умолчаниям — ни swap, ни подтягивание одного конца к другому, иначе
 * пользователь не поймёт, почему выдача не соответствует ссылке.
 * Правило идемпотентно, поэтому канонизация URL не зациклится.
 */
const parsePriceRange = (minParam: string | null, maxParam: string | null): PriceRange => {
  const min = parsePriceBound(minParam, PRICE_MIN);
  const max = parsePriceBound(maxParam, PRICE_MAX);
  return min > max ? DEFAULT_PRICE_RANGE : { min, max };
};

/** `in_stock` живёт в URL только выключенным: умолчание фильтра — «в наличии» */
const parseInStock = (value: string | null): boolean => value !== 'false';

/** `?brand=nike,adidas` → ['nike', 'adidas']; пустые значения отбрасываются */
const parseBrandSlugs = (value: string | null): string[] =>
  (value ?? '')
    .split(',')
    .map(slug => slug.trim())
    .filter(Boolean);

const getNodeKey = (path: number[]) => path.join(' > ');

const mapCategoryTreeNode = (node: CategoryTreeResponse): CategoryNode => ({
  id: node.id,
  label: node.name,
  slug: node.slug,
  icon: node.icon || undefined,
  inStockCount: node.in_stock_count ?? 0,
  children: node.children?.map(mapCategoryTreeNode),
});

const sortCategoryTree = (nodes: CategoryNode[]): CategoryNode[] =>
  [...nodes]
    .sort((a, b) => {
      if (a.slug === 'uncategorized') return 1;
      if (b.slug === 'uncategorized') return -1;
      return a.label.localeCompare(b.label, 'ru');
    })
    .map(n => ({ ...n, children: n.children ? sortCategoryTree(n.children) : undefined }));

const hasVisibleDescendant = (node: CategoryNode, visibleIds: Set<number>): boolean =>
  Boolean(node.children?.some(c => visibleIds.has(c.id) || hasVisibleDescendant(c, visibleIds)));

const findCategoryBySlug = (nodes: CategoryNode[], targetSlug: string): CategoryNode | null => {
  for (const node of nodes) {
    if (node.slug === targetSlug) {
      return node;
    }
    if (node.children) {
      const child = findCategoryBySlug(node.children, targetSlug);
      if (child) {
        return child;
      }
    }
  }
  return null;
};

const findCategoryPathById = (
  nodes: CategoryNode[],
  targetId: number,
  path: CategoryNode[] = []
): CategoryNode[] => {
  for (const node of nodes) {
    const currentPath = [...path, node];
    if (node.id === targetId) {
      return currentPath;
    }
    if (node.children?.length) {
      const childPath = findCategoryPathById(node.children, targetId, currentPath);
      if (childPath.length) {
        return childPath;
      }
    }
  }
  return [];
};

const getKeysForPath = (pathNodes: CategoryNode[]) =>
  pathNodes.map((_, index) => getNodeKey(pathNodes.slice(0, index + 1).map(node => node.id)));

const formatCurrency = (value: number) =>
  value.toLocaleString('ru-RU', { style: 'currency', currency: 'RUB', maximumFractionDigits: 0 });

const PriceRangeSlider: React.FC<PriceRangeSliderProps> = ({ min, max, step, value, onChange }) => {
  const minPercent = ((clamp(value.min, min, max) - min) / (max - min)) * 100;
  const maxPercent = ((clamp(value.max, min, max) - min) / (max - min)) * 100;

  const handleMinChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextValue = Number(event.target.value);
    const clamped = Math.min(nextValue, value.max - step);
    onChange({ min: clamp(clamped, min, max - step), max: value.max });
  };

  const handleMaxChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const nextValue = Number(event.target.value);
    const clamped = Math.max(nextValue, value.min + step);
    onChange({ min: value.min, max: clamp(clamped, min + step, max) });
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between text-sm text-gray-600">
        <span>Цена</span>
        <span>
          {formatCurrency(value.min)} — {formatCurrency(value.max)}
        </span>
      </div>

      <div className="relative h-10">
        <div className="absolute inset-y-0 left-0 right-0 flex items-center">
          <div className="h-[4px] w-full rounded-full bg-[#E1E6EF]" />
        </div>
        <div
          className="absolute inset-y-0 flex items-center"
          style={{ left: `${minPercent}%`, right: `${100 - maxPercent}%` }}
        >
          <div className="h-[4px] w-full rounded-full bg-[#FF6B00]" />
        </div>

        <input
          type="range"
          min={min}
          max={max}
          value={value.min}
          onChange={handleMinChange}
          className="price-range-thumb absolute inset-x-0 top-1/2 -translate-y-1/2 w-full appearance-none bg-transparent"
        />
        <input
          type="range"
          min={min}
          max={max}
          value={value.max}
          onChange={handleMaxChange}
          className="price-range-thumb absolute inset-x-0 top-1/2 -translate-y-1/2 w-full appearance-none bg-transparent"
        />
      </div>

      <div className="flex justify-between text-xs text-gray-500">
        <span>
          {min.toLocaleString('ru-RU')}
          <span className="ml-1 text-gray-400">₽</span>
        </span>
        <span>
          {max.toLocaleString('ru-RU')}
          <span className="ml-1 text-gray-400">₽</span>
        </span>
      </div>

      <style jsx>{`
        .price-range-thumb::-webkit-slider-thumb {
          -webkit-appearance: none;
          appearance: none;
          height: 18px;
          width: 18px;
          border-radius: 50%;
          background: #ff6b00;
          border: 4px solid #ffe0b2;
          background: #ff6600;
          border: 4px solid #ffd6b3;
          box-shadow: 0 2px 6px rgba(255, 102, 0, 0.35);
          cursor: pointer;
          margin-top: -9px;
        }

        .price-range-thumb::-moz-range-thumb {
          height: 18px;
          width: 18px;
          border-radius: 50%;
          background: #ff6600;
          border: 4px solid #ffd6b3;
          box-shadow: 0 2px 6px rgba(255, 102, 0, 0.35);
          cursor: pointer;
        }

        .price-range-thumb::-webkit-slider-runnable-track {
          height: 1px;
          background: transparent;
        }

        .price-range-thumb::-moz-range-track {
          height: 1px;
          background: transparent;
        }
      `}</style>
    </div>
  );
};

const CategoryTree: React.FC<{
  nodes: CategoryNode[];
  level?: number;
  activeId?: number | null;
  expandedKeys: Set<string>;
  onToggle: (key: string) => void;
  onSelect: (node: CategoryNode) => void;
  path?: number[];
  visibleIds?: Set<number> | null;
}> = ({ nodes, level = 0, activeId, expandedKeys, onToggle, onSelect, path = [], visibleIds }) => {
  const visibleNodes = visibleIds
    ? nodes.filter(n => visibleIds.has(n.id) || hasVisibleDescendant(n, visibleIds))
    : nodes;

  if (level === 0 && visibleNodes.length === 0 && nodes.length > 0) {
    return <p className="text-sm text-gray-400 py-1">Нет категорий</p>;
  }

  return (
    <ul className={level === 0 ? 'space-y-2' : 'space-y-1 pl-3 border-l border-gray-100'}>
      {visibleNodes.map(node => {
        const currentPath = [...path, node.id];
        const nodeKey = getNodeKey(currentPath);
        const isActive = node.id === activeId;
        const hasChildren = Boolean(node.children && node.children.length > 0);
        const isExpanded = expandedKeys.has(nodeKey);

        return (
          <li key={nodeKey} className="space-y-1">
            <div className="flex items-start gap-2">
              {hasChildren ? (
                <button
                  type="button"
                  onClick={() => onToggle(nodeKey)}
                  aria-label={isExpanded ? 'Свернуть категорию' : 'Развернуть категорию'}
                  className="mt-1 text-xs text-gray-400 hover:text-gray-600"
                >
                  {isExpanded ? '▾' : '▸'}
                </button>
              ) : (
                <span className="w-3" aria-hidden="true" />
              )}

              <button
                type="button"
                onClick={() => onSelect(node)}
                className={
                  'flex-1 min-w-0 rounded-lg px-2 py-1 text-left text-sm transition-colors ' +
                  (isActive
                    ? 'bg-primary-subtle text-primary font-semibold'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900') +
                  ' flex items-start gap-2'
                }
              >
                {node.icon &&
                  (node.icon.startsWith('http') || node.icon.startsWith('/') ? (
                    <NextImage
                      src={node.icon}
                      alt=""
                      width={20}
                      height={20}
                      unoptimized
                      className="w-5 h-5 object-contain flex-shrink-0"
                    />
                  ) : (
                    <span className="text-lg flex-shrink-0 leading-none">{node.icon}</span>
                  ))}
                <span className="break-words">{node.label}</span>
              </button>
            </div>
            {hasChildren && isExpanded && (
              <CategoryTree
                nodes={node.children!}
                level={level + 1}
                activeId={activeId}
                expandedKeys={expandedKeys}
                onToggle={onToggle}
                onSelect={onSelect}
                path={currentPath}
                visibleIds={visibleIds}
              />
            )}
          </li>
        );
      })}
    </ul>
  );
};

const CatalogContent: React.FC = () => {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  // ВАЖНО: useSearchParams() отдаёт НОВЫЙ объект при каждой навигации, а номер
  // страницы теперь живёт в URL. Любой useMemo/useEffect с зависимостью
  // [searchParams] сработал бы на каждом клике по пагинации (лишний запрос
  // товаров, перезагрузка дерева категорий, откат выбранных фильтров).
  // Поэтому ниже всё завязано на примитивные значения параметров.
  const categorySlugParam = searchParams?.get('category') ?? null;
  const brandSlugParam = searchParams?.get('brand') ?? null;
  const searchParam = searchParams?.get('search') ?? null;
  const focusSearchParam = searchParams?.get('focusSearch') ?? null;
  const pageParam = searchParams?.get('page') ?? null;
  const isNewParam = searchParams?.get('is_new') ?? null;
  const isHitParam = searchParams?.get('is_hit') ?? null;
  const isSaleParam = searchParams?.get('is_sale') ?? null;
  const orderingParam = searchParams?.get('ordering') ?? null;
  const minPriceParam = searchParams?.get('min_price') ?? null;
  const maxPriceParam = searchParams?.get('max_price') ?? null;
  const inStockParam = searchParams?.get('in_stock') ?? null;
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [activeCategoryLabel, setActiveCategoryLabel] = useState('');
  // Флаг означает "попытка загрузки категорий завершена" (включая ошибку) — F3
  const [isCategoryLoadAttempted, setIsCategoryLoadAttempted] = useState(false);
  const [isCategoriesOpen, setIsCategoriesOpen] = useState(false);
  const [isBrandsOpen, setIsBrandsOpen] = useState(false);

  // Badge-фильтры из URL (is_new, is_hit, is_sale)
  const activeBadge = useMemo(
    () => ({
      is_new: isNewParam === 'true' ? true : undefined,
      is_hit: isHitParam === 'true' ? true : undefined,
      is_sale: isSaleParam === 'true' ? true : undefined,
    }),
    [isNewParam, isHitParam, isSaleParam]
  );
  const hasBadgeFilter = Boolean(activeBadge.is_new || activeBadge.is_hit || activeBadge.is_sale);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);
  // Видимость категорий в sidebar: null = показывать всё (fallback / initial)
  const [sidebarVisibleIds, setSidebarVisibleIds] = useState<Set<number> | null>(null);

  const [brands, setBrands] = useState<Brand[]>([]);
  // Видимость брендов в sidebar: null = показывать всё (fallback / initial)
  const [sidebarVisibleBrandIds, setSidebarVisibleBrandIds] = useState<Set<number> | null>(null);
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<number>>(new Set());
  const [isBrandsLoading, setIsBrandsLoading] = useState(true);
  const [brandsError, setBrandsError] = useState<string | null>(null);

  // Фильтры зеркалятся в URL той же схемой, что и page: ленивая инициализация
  // из адресной строки переживает F5, «назад» и открытие ссылки в новой вкладке.
  const [priceRange, setPriceRange] = useState<PriceRange>(() =>
    parsePriceRange(minPriceParam, maxPriceParam)
  );
  // Драфт диапазона цены — то, что видит пользователь на ползунке прямо сейчас.
  // Источником истины для запроса и URL остаётся priceRange: он принимает драфт
  // одним шагом через PRICE_COMMIT_DELAY_MS после последнего движения ползунка.
  const [priceDraft, setPriceDraft] = useState<PriceRange>(priceRange);
  // Синхронная инициализация из URL: иначе на /catalog?search=x&page=3 первый
  // запрос ушёл бы без search, поймал 404 и сбросил страницу у корректной закладки
  const [searchQuery, setSearchQuery] = useState(() => searchParam ?? '');
  const [products, setProducts] = useState<Product[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  // Номер страницы зеркалится в URL (?page=N), чтобы переживать F5, «назад» и
  // открытие ссылки в новой вкладке. Источник истины для запроса — состояние:
  // router.push обновляет searchParams асинхронно, и производное от URL значение
  // давало бы лишний запрос со старой страницей при смене фильтра.
  const [page, setPage] = useState(() => parsePageNumber(pageParam));
  const [ordering, setOrdering] = useState(() => parseOrdering(orderingParam));
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isProductsLoading, setIsProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  // По умолчанию показываем только товары в наличии; в URL это состояние не пишется
  const [inStock, setInStock] = useState(() => parseInStock(inStockParam));

  // Auth integration
  const user = useAuthStore(state => state.user);
  const userRole = user?.role || 'guest';
  const isB2B = [
    'wholesale_level1',
    'wholesale_level2',
    'wholesale_level3',
    'wholesale_level4',
    'trainer',
    'federation_rep',
    'admin',
  ].includes(userRole);

  // Cart integration
  const { addItem } = useCartStore();
  const { success, error: toastError } = useToast();

  // Favorites integration
  const favorites = useFavoritesStore(state => state.favorites);
  const { toggleFavorite, fetchFavorites } = useFavoritesStore();

  // Fetch favorites on mount or auth change
  useEffect(() => {
    if (user) {
      fetchFavorites();
    }
  }, [user, fetchFavorites]);

  // Responsive: на мобилке сворачиваем фильтры при маунте.
  // useLayoutEffect выполняется ДО paint → исключает «мигание» на мобилках (F1)
  useIsomorphicLayoutEffect(() => {
    const isDesktop = window.matchMedia(DESKTOP_BREAKPOINT).matches;
    if (!isDesktop) {
      setIsCategoriesOpen(false);
      setIsBrandsOpen(false);
    }
  }, []);

  const handleToggleFavorite = useCallback(
    async (productId: number) => {
      if (!user) {
        toastError('Пожалуйста, авторизуйтесь');
        return;
      }
      try {
        await toggleFavorite(productId);
        // Note: toasts are shown in store actions or we can show them here based on result?
        // Current store implementation handles state but not toasts internally except errors.
        // But since we can't easily know if it was added or removed in the toggle result (void),
        // we might want to check isFavorite status before toggling OR update store to return status.
        // For now, let's just rely on the UI update.
        // To verify action we can check if it is NOW in favorites.
      } catch {
        // Error is handled in store but we can show toast here if needed
      }
    },
    [user, toggleFavorite, toastError]
  );

  const activePathNodes = useMemo(() => {
    if (!activeCategoryId) {
      return [] as CategoryNode[];
    }
    return findCategoryPathById(categoryTree, activeCategoryId);
  }, [categoryTree, activeCategoryId]);

  const breadcrumbSegments = useMemo(() => {
    const base = [
      { label: 'Главная', href: '/home' },
      { label: 'Каталог', href: '/catalog' },
    ];

    if (activePathNodes.length > 0) {
      const categorySegments = activePathNodes.map(node => ({
        label: node.label,
        href: `/catalog?category=${node.slug}`,
      }));
      return [...base, ...categorySegments];
    }

    // Если активная категория выбрана, но не найдена в дереве — fallback по label (F7)
    if (activeCategoryId !== null && activeCategoryLabel) {
      return [...base, { label: activeCategoryLabel, href: null }];
    }

    return base;
  }, [activePathNodes, activeCategoryId, activeCategoryLabel]);

  // Разобранные параметры URL — единый источник для инициализации состояния,
  // синхронизации по «назад»/«вперёд» и канонизации адресной строки. Три
  // независимых разбора неизбежно разъехались бы между собой.
  const urlFilters = useMemo(
    () => ({
      ordering: parseOrdering(orderingParam),
      price: parsePriceRange(minPriceParam, maxPriceParam),
      inStock: parseInStock(inStockParam),
      brandSlugs: parseBrandSlugs(brandSlugParam),
    }),
    [orderingParam, minPriceParam, maxPriceParam, inStockParam, brandSlugParam]
  );

  // Категория в URL — slug, в состоянии — id. Пока дерево не загружено,
  // соответствие неизвестно, и «расхождения» с состоянием не существует.
  const urlActiveCategoryId = useMemo(() => {
    if (!categorySlugParam || categoryTree.length === 0) {
      return null;
    }
    return findCategoryBySlug(categoryTree, categorySlugParam)?.id ?? null;
  }, [categorySlugParam, categoryTree]);

  // Гейт запроса товаров по категории — та же логика, что и по брендам.
  // Дерево приходит одним коммитом с isCategoryLoadAttempted, но activeCategoryId
  // ставит passive-эффект синхронизации, то есть в том же проходе эффектов
  // замыкание fetchProducts построено ещё на activeCategoryId === null:
  // ссылка /catalog?category=obuv уходила бы в API дважды — сначала без
  // category_id, затем с ним (лишний запрос и мигание выдачи).
  // Условие Boolean(categorySlugParam) обязательно: собственный выбор категории
  // меняет состояние раньше URL, и без него гейт закрывал бы уже актуальный запрос.
  // Несуществующий slug гейт не держит: urlActiveCategoryId === null === состояние.
  // Условие !isCategoryLoadAttempted обязательно: до загрузки дерева
  // urlActiveCategoryId равен null, как и состояние, — расхождения «не видно»,
  // и при badge-фильтре (он снимает ожидание дерева в эффекте запроса) ссылка
  // /catalog?category=obuv&is_new=true уходила бы в API дважды: сначала без
  // category_id, затем с ним. Ошибка загрузки дерева гейт не держит:
  // isCategoryLoadAttempted ставится и в ветке ошибки.
  const isCategoryFilterPending =
    Boolean(categorySlugParam) &&
    (!isCategoryLoadAttempted || urlActiveCategoryId !== activeCategoryId);

  // Бренды в URL — slug'и, в состоянии — id. null означает «соответствие ещё
  // невозможно»: справочник брендов не загружен. Slug'и, которых в справочнике
  // нет, отбрасываются: такое расхождение сменой состояния не устраняется —
  // его снимает канонизация URL.
  const urlBrandIds = useMemo(() => {
    if (isBrandsLoading) {
      return null;
    }
    const ids = new Set<number>();
    urlFilters.brandSlugs.forEach(slug => {
      const found = brands.find(brand => brand.slug === slug);
      if (found) {
        ids.add(found.id);
      }
    });
    return ids;
  }, [urlFilters.brandSlugs, brands, isBrandsLoading]);

  const brandStateMatchesUrl = useMemo(() => {
    if (urlBrandIds === null) {
      return false;
    }
    if (urlBrandIds.size !== selectedBrandIds.size) {
      return false;
    }
    for (const id of urlBrandIds) {
      if (!selectedBrandIds.has(id)) {
        return false;
      }
    }
    return true;
  }, [urlBrandIds, selectedBrandIds]);

  // Гейт запроса товаров по брендам: пока бренд задан в URL, но набор в состоянии
  // ему не равен, запрос ушёл бы без фильтра бренда. Проверять один только
  // isBrandsLoading мало — в том же проходе эффектов, где бренды догрузились,
  // эффект запроса ещё видит пустой selectedBrandIds и успел бы сходить в API:
  // лишний запрос и мигание выдачи на закладке /catalog?brand=nike.
  // Гейт держится только при наличии параметра: собственный выбор пользователя
  // (URL ещё пуст) — это уже актуальное состояние, ждать его зеркала незачем.
  // Ошибка загрузки брендов гейт не держит: brands пуст, набор из URL тоже пуст,
  // и на ?brand=нет-такого расхождение снимается канонизацией, а не состоянием.
  const isBrandFilterPending = Boolean(brandSlugParam) && !brandStateMatchesUrl;

  // Дерево категорий грузится РОВНО ОДИН РАЗ за монтирование. Прежние
  // зависимости [categorySlugParam, hasBadgeFilter, inStock] после
  // зеркалирования фильтров в URL менялись бы от каждого действия пользователя:
  // getTree() уходил бы в API заново, а setExpandedKeys(new Set(...)) — replace,
  // не merge — схлопывал бы раскрытые ветки на каждом выборе категории.
  // hasBadgeFilter в теле эффекта не использовался вовсе — паразитная зависимость.
  useEffect(() => {
    let isMounted = true;

    const fetchCategories = async () => {
      try {
        const tree = await categoriesService.getTree();
        if (!isMounted) return;
        setCategoryTree(sortCategoryTree(tree.map(mapCategoryTreeNode)));
      } catch (error) {
        console.error('Не удалось загрузить дерево категорий', error);
        if (isMounted) {
          setCategoriesError('Не удалось загрузить категории');
        }
      } finally {
        if (isMounted) {
          setIsCategoriesLoading(false);
          setIsCategoryLoadAttempted(true);
        }
      }
    };

    fetchCategories();

    return () => {
      isMounted = false;
    };
  }, []);

  // Первичная фильтрация сайдбара по in_stock_count (до ответа visible-categories)
  // устраняет flash пустых категорий. Это производное от уже загруженного дерева,
  // перезапроса не требует. Отдельный эффект нужен и для «назад» на ?in_stock=false:
  // раньше сброс видимости делал только обработчик чекбокса, и после внешней
  // навигации сайдбар оставался сужённым.
  useEffect(() => {
    if (!inStock) {
      setSidebarVisibleIds(null);
      setSidebarVisibleBrandIds(null);
      return;
    }
    if (categoryTree.length === 0) {
      return;
    }
    const initialVisible = new Set<number>();
    const collectVisible = (nodes: CategoryNode[]) => {
      for (const n of nodes) {
        if (n.inStockCount > 0) initialVisible.add(n.id);
        if (n.children) collectVisible(n.children);
      }
    };
    collectVisible(categoryTree);
    setSidebarVisibleIds(initialVisible);
  }, [categoryTree, inStock]);

  // Категория из URL → состояние. Зависимости только «урловые»: собственный push
  // обработчика меняет состояние раньше, чем searchParams, и эффект с
  // зависимостью от activeCategoryId откатил бы выбор до commit навигации.
  // Раскрытие пути и подпись категории делает эффект [activeCategoryId, categoryTree] ниже.
  useEffect(() => {
    setActiveCategoryId(prev => (prev === urlActiveCategoryId ? prev : urlActiveCategoryId));
    if (urlActiveCategoryId === null) {
      setActiveCategoryLabel('');
    }
  }, [urlActiveCategoryId]);

  // Внешняя смена search в URL (кнопка «назад», переход из шапки)
  useEffect(() => {
    if (searchParam) {
      setSearchQuery(searchParam);
    }
  }, [searchParam]);

  useEffect(() => {
    let isMounted = true;

    const fetchBrands = async () => {
      try {
        const data = await brandsService.getAll({ has_stock: true });
        if (isMounted) {
          setBrands(data);
        }
      } catch (error) {
        console.error('Не удалось загрузить бренды', error);
        if (isMounted) {
          setBrandsError('Не удалось загрузить бренды');
        }
      } finally {
        if (isMounted) {
          setIsBrandsLoading(false);
        }
      }
    };

    fetchBrands();

    return () => {
      isMounted = false;
    };
  }, []);

  // Синхронизация фильтра бренда с URL — двусторонняя: набор в состоянии всегда
  // равен набору, распарсенному из URL по загруженному справочнику. Прежний гард
  // `if (brandSlugParam && brands.length > 0)` не снимал выбор при исчезновении
  // параметра: «назад» с ?brand=nike на /catalog оставлял Nike в запросе при
  // пустом URL. Гард на совпадение сохранён, чтобы собственный push мультивыбора
  // не пересоздавал Set вхолостую. Зависимость только «урловая» (urlBrandIds):
  // зависимость от selectedBrandIds откатывала бы выбор до commit навигации.
  useEffect(() => {
    if (urlBrandIds === null) {
      return;
    }
    setSelectedBrandIds(prev => {
      if (prev.size === urlBrandIds.size && Array.from(urlBrandIds).every(id => prev.has(id))) {
        return prev;
      }
      return new Set(urlBrandIds);
    });
  }, [urlBrandIds]);

  useEffect(() => {
    if (!activeCategoryId || !categoryTree.length) return;
    const pathNodes = findCategoryPathById(categoryTree, activeCategoryId);
    if (!pathNodes.length) return;
    setExpandedKeys(prev => {
      const next = new Set(prev);
      getKeysForPath(pathNodes).forEach(key => next.add(key));
      return next;
    });
    setActiveCategoryLabel(pathNodes[pathNodes.length - 1]?.label ?? '');
  }, [activeCategoryId, categoryTree]);

  // Очередь наших собственных, ещё не закоммиченных записей в адресную строку.
  // router.push в App Router — transition: до его commit useSearchParams отдаёт
  // прежний снимок. Два быстрых действия подряд (бренд, следом сортировка)
  // строились бы от одного и того же URL, и вторая навигация теряла бы первую.
  const priceCommitTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  // Объект, который положил в priceRange наш собственный отложенный commit.
  // Сравнение по идентичности — единственный надёжный признак источника
  // изменения: по значениям «свой commit» и «внешняя навигация на тот же
  // диапазон» неразличимы, а реакция на них разная.
  const committedPriceRef = React.useRef<PriceRange | null>(null);
  const cancelPriceCommit = useCallback(() => {
    if (priceCommitTimerRef.current !== null) {
      clearTimeout(priceCommitTimerRef.current);
      priceCommitTimerRef.current = null;
    }
  }, []);

  const pendingQueriesRef = React.useRef<string[]>([]);

  // Снимок URL, на котором эффект отработал в прошлый раз. Без него внешнюю
  // навигацию при пустой очереди не отличить от обычного ререндера.
  const lastCommittedQueryRef = React.useRef(searchParams?.toString() ?? '');

  useEffect(() => {
    const committed = searchParams?.toString() ?? '';
    if (committed === lastCommittedQueryRef.current) {
      return;
    }
    lastCommittedQueryRef.current = committed;

    const queue = pendingQueriesRef.current;
    const index = queue.indexOf(committed);
    if (index !== -1) {
      // Запись приземлилась: она и всё, что было до неё, больше не «в полёте».
      queue.splice(0, index + 1);
      return;
    }

    // Снимок не совпал ни с одной нашей записью — URL увели «назад»/«вперёд»
    // или внешним переходом, и наша база больше не действительна.
    queue.length = 0;

    // Отложенный commit цены отменяется здесь, а не эффектом синхронизации
    // драфта: тот висит на priceRange, а внешняя навигация может применённый
    // диапазон не менять вовсе (`?ordering=-created_at` → `/catalog`). Тогда
    // setPriceRange — no-op, эффект не перезапускается, и переживший навигацию
    // таймер записал бы в URL драфт, от которого пользователь уже ушёл, уведя
    // его обратно из только что открытой записи истории. Собственные навигации
    // сюда не попадают: намерение пользователя по цене они не отменяют.
    cancelPriceCommit();
    setPriceDraft(prev =>
      prev.min === urlFilters.price.min && prev.max === urlFilters.price.max
        ? prev
        : urlFilters.price
    );
  }, [searchParams, cancelPriceCommit, urlFilters]);

  // Обновление URL-параметров без перезагрузки страницы.
  // Принимает сразу несколько ключей: два последовательных вызова в одном
  // обработчике затирали бы друг друга, так как оба строятся от одного searchParams.
  const updateSearchParams = useCallback(
    (updates: Record<string, string | null>, options?: { replace?: boolean }) => {
      const committed = searchParams?.toString() ?? '';
      // База — последняя наша ещё не закоммиченная запись, иначе снимок роутера
      const current = pendingQueriesRef.current.at(-1) ?? committed;
      const params = new URLSearchParams(current);

      Object.entries(updates).forEach(([key, value]) => {
        if (value === null || value === '') {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      });

      // Ничего не изменилось — не засоряем историю браузера
      if (params.toString() === current) {
        return;
      }

      const next = params.toString();
      pendingQueriesRef.current.push(next);

      // Запятая — sub-delim, URLSearchParams кодирует её в %2C. Для CSV-параметров
      // (brand) это ломает читаемость ссылки, которой делятся; на разбор не влияет:
      // и браузер, и searchParams.get() трактуют обе формы одинаково.
      const query = next.replace(/%2C/g, ',');
      const newUrl = query ? `${pathname || '/'}?${query}` : pathname || '/';

      if (options?.replace) {
        router.replace(newUrl, { scroll: false });
      } else {
        router.push(newUrl, { scroll: false });
      }
    },
    [pathname, router, searchParams]
  );

  // updateSearchParams меняет идентичность при каждой смене URL. Внутри
  // fetchProducts он доступен только через ref — прямая зависимость вернула бы
  // ту самую нестабильность, ради устранения которой заведены примитивы выше.
  const updateSearchParamsRef = React.useRef(updateSearchParams);
  useEffect(() => {
    updateSearchParamsRef.current = updateSearchParams;
  }, [updateSearchParams]);

  // Порядковый номер запроса: медленный ответ по прошлым фильтрам не должен
  // перерисовать данные поверх актуальных и не должен утащить пользователя на 1-ю страницу
  const requestSeq = React.useRef(0);

  // Смена номера страницы обесценивает уже летящий запрос сразу, в момент
  // намерения пользователя. Ждать старта следующего запроса нельзя: React
  // обрабатывает setPage не синхронно с обработчиком события, и 404 по прежней
  // странице, пришедший в этом промежутке, откатил бы пользователя на первую
  // страницу уже после навигации. Условие обязательно: без реальной смены
  // страницы следующего запроса может не быть, и обесцененный ответ оставил бы
  // висеть скелетон загрузки.
  const invalidateOnPageChange = useCallback(
    (nextPage: number) => {
      if (nextPage !== page) {
        requestSeq.current += 1;
      }
    },
    [page]
  );

  // Кнопки «назад»/«вперёд» меняют URL без нашего обработчика: в первом render
  // после навигации состояние page ещё прежнее, productFilters не менялись, и
  // инвалидация по ним не сработает до passive-эффекта синхронизации ниже.
  // Прилетевший в это окно 404 по прежней странице считался бы актуальным и
  // откатом на первую страницу отменил бы переход пользователя. Расхождение
  // номера страницы в URL с состоянием и означает такую внешнюю навигацию;
  // сразу за ним sync-эффект меняет page, то есть следующий запрос гарантирован
  // и обесцененный ответ не оставит висеть скелетон.
  //
  // Ключ расхождения считается теми же парсерами, что и sync-эффект ниже, иначе
  // инвалидация разъедется с фактической синхронизацией. Бампится только то
  // расхождение, которое sync-эффект гарантированно устранит в том же цикле:
  // бамп без последующего запроса оставил бы висеть скелетон, потому что
  // finally в fetchProducts снимает isProductsLoading лишь при seq === requestSeq.
  // Отсюда исключения по brand: пока справочник грузится (urlBrandIds === null)
  // и для slug'ов, которых в справочнике нет, — они в urlBrandIds не попадают.
  useIsomorphicLayoutEffect(() => {
    const diverges =
      parsePageNumber(pageParam) !== page ||
      urlFilters.ordering !== ordering ||
      urlFilters.price.min !== priceRange.min ||
      urlFilters.price.max !== priceRange.max ||
      urlFilters.inStock !== inStock ||
      urlActiveCategoryId !== activeCategoryId ||
      (urlBrandIds !== null && !brandStateMatchesUrl);

    if (diverges) {
      requestSeq.current += 1;
    }
  }, [
    pageParam,
    page,
    urlFilters,
    ordering,
    priceRange.min,
    priceRange.max,
    inStock,
    urlActiveCategoryId,
    activeCategoryId,
    urlBrandIds,
    brandStateMatchesUrl,
  ]);

  // Сброс на первую страницу при смене любого фильтра: состояние и URL разом.
  // setPage в одном обработчике с фильтром батчится в один рендер → один запрос.
  // Дополнительные ключи пишутся тем же пушем: два последовательных вызова
  // updateSearchParams в одном обработчике затирали бы друг друга.
  const resetPage = useCallback(
    (updates: Record<string, string | null> = {}) => {
      invalidateOnPageChange(1);
      setPage(1);
      updateSearchParams({ ...updates, page: null });
    },
    [invalidateOnPageChange, updateSearchParams]
  );

  // resetPage меняет идентичность вместе с searchParams. Отложенный commit цены
  // срабатывает уже после нескольких рендеров, поэтому берёт его через ref —
  // тот же приём, что и updateSearchParamsRef выше.
  const resetPageRef = React.useRef(resetPage);
  useEffect(() => {
    resetPageRef.current = resetPage;
  }, [resetPage]);

  // Драфт следует за применённым диапазоном, когда тот меняется не ползунком:
  // «назад»/«вперёд», F5, кнопка «Сбросить». Отложенный commit при этом отменяется —
  // иначе он вернул бы на экран диапазон, от которого пользователь уже ушёл.
  // Ранний выход по собственному commit обязателен: между срабатыванием таймера
  // и этим эффектом пользователь успевает двинуть ползунок снова, и безусловный
  // cancel убил бы уже поставленный таймер следующего шага — диапазон завис бы
  // в драфте и не доехал ни до URL, ни до запроса.
  useEffect(() => {
    if (priceRange === committedPriceRef.current) {
      return;
    }
    cancelPriceCommit();
    setPriceDraft(prev =>
      prev.min === priceRange.min && prev.max === priceRange.max ? prev : priceRange
    );
  }, [priceRange, cancelPriceCommit]);

  useEffect(() => cancelPriceCommit, [cancelPriceCommit]);

  // Синхронизация состояния из URL для кнопок «назад»/«вперёд».
  // Функциональные сеттеры не требуют состояния в зависимостях; при совпадении — no-op.
  // Зависимости только «урловые»: собственный push обработчика меняет состояние
  // раньше searchParams, и зависимость от состояния откатывала бы фильтр.
  useEffect(() => {
    const urlPage = parsePageNumber(pageParam);
    setPage(prev => (prev === urlPage ? prev : urlPage));
    setOrdering(prev => (prev === urlFilters.ordering ? prev : urlFilters.ordering));
    setPriceRange(prev =>
      prev.min === urlFilters.price.min && prev.max === urlFilters.price.max
        ? prev
        : urlFilters.price
    );
    setInStock(prev => (prev === urlFilters.inStock ? prev : urlFilters.inStock));

    // Канонизация ждёт, пока станут разрешимы ВСЕ пришедшие в ссылке slug'и:
    // иначе смешанная мусорная ссылка чистится двумя replace — сначала по
    // параметрам, разбираемым без справочников, потом по бренду и категории.
    // Контракт требует одну атомарную замену. Ждём только загрузку, но не
    // успех: отвалившийся справочник разрешимым уже не станет, и остальные
    // параметры не должны застрять в URL из-за него.
    const awaitsBrands = Boolean(brandSlugParam) && isBrandsLoading;
    const awaitsCategory = Boolean(categorySlugParam) && !isCategoryLoadAttempted;
    if (awaitsBrands || awaitsCategory) {
      return;
    }

    // Канонизация адресной строки одним replace: значения по умолчанию, мусор и
    // несуществующие slug'и брендов в ней не остаются. `?page=1`, `?page=01` и
    // мусор (`?page=abc`, `?page=0`) означают первую страницу, канонический URL
    // которой не содержит параметра (SEO). replace, а не push: чистка пришедшей
    // извне ссылки не должна плодить записи в истории. Парсеры возвращают
    // канонические значения сами, поэтому повторный проход ничего не меняет и
    // replace не зацикливается.
    const canonical: Record<string, string | null> = {};

    if (pageParam !== null && urlPage === 1) {
      canonical.page = null;
    }

    const canonicalOrdering = urlFilters.ordering === DEFAULT_ORDERING ? null : urlFilters.ordering;
    if (orderingParam !== canonicalOrdering) {
      canonical.ordering = canonicalOrdering;
    }

    const canonicalMinPrice =
      urlFilters.price.min === PRICE_MIN ? null : String(urlFilters.price.min);
    if (minPriceParam !== canonicalMinPrice) {
      canonical.min_price = canonicalMinPrice;
    }

    const canonicalMaxPrice =
      urlFilters.price.max === PRICE_MAX ? null : String(urlFilters.price.max);
    if (maxPriceParam !== canonicalMaxPrice) {
      canonical.max_price = canonicalMaxPrice;
    }

    const canonicalInStock = urlFilters.inStock ? null : 'false';
    if (inStockParam !== canonicalInStock) {
      canonical.in_stock = canonicalInStock;
    }

    // Бренды канонизируются по УСПЕШНО загруженному справочнику. Проверять
    // brands.length нельзя: успешно загруженный пустой справочник — такое же
    // основание считать slug мусорным, как и непустой, а при таком гарде
    // неизвестный бренд оставался бы в URL навсегда. Ошибка загрузки — другое
    // дело: знать, мусорный slug или нет, страница не может, параметр остаётся.
    if (!isBrandsLoading && brandsError === null) {
      const knownSlugs = Array.from(
        new Set(urlFilters.brandSlugs.filter(slug => brands.some(brand => brand.slug === slug)))
      );
      const canonicalBrand = knownSlugs.length > 0 ? knownSlugs.join(',') : null;
      if (brandSlugParam !== canonicalBrand) {
        canonical.brand = canonicalBrand;
      }
    }

    // Категория, которой нет в загруженном дереве, — такой же мусор, как
    // неизвестный бренд: сайдбар показывает «Все категории», запрос уходит без
    // category_id, и ложный активный фильтр в адресной строке ссылку только
    // портит. Признак — успешная загрузка дерева, а не categoryTree.length:
    // успешно пришедшее пустое дерево сопоставить slug не с чем ровно так же,
    // как непустое, и по длине его не отличить от неудачной загрузки, при
    // которой параметр трогать нельзя (симметрично бренду выше).
    if (
      categorySlugParam &&
      isCategoryLoadAttempted &&
      categoriesError === null &&
      urlActiveCategoryId === null
    ) {
      canonical.category = null;
    }

    if (Object.keys(canonical).length > 0) {
      updateSearchParamsRef.current(canonical, { replace: true });
    }
  }, [
    pageParam,
    orderingParam,
    minPriceParam,
    maxPriceParam,
    inStockParam,
    brandSlugParam,
    categorySlugParam,
    urlFilters,
    brands,
    isBrandsLoading,
    brandsError,
    isCategoryLoadAttempted,
    categoriesError,
    urlActiveCategoryId,
  ]);

  // Обработчик изменения поискового запроса
  const handleSearchChange = useCallback(
    (query: string) => {
      invalidateOnPageChange(1);
      setSearchQuery(query);
      setPage(1);
      updateSearchParams({ search: query || null, page: null });
    },
    [invalidateOnPageChange, updateSearchParams]
  );

  // Производные значения фильтров — примитивы, чтобы productFilters ниже менял
  // идентичность только вместе с содержимым запроса, а не на каждый ререндер
  const brandFilter = selectedBrandIds.size > 0 ? Array.from(selectedBrandIds).join(',') : '';
  const searchFilter = searchQuery.trim().length >= 2 ? searchQuery.trim() : '';

  // Параметры запроса товаров собраны в одном месте: они же служат ключом
  // инвалидации ниже, поэтому ключ не может разъехаться с фактическим запросом
  const productFilters = useMemo<ProductFilters>(() => {
    const filters: ProductFilters = {
      page,
      page_size: PAGE_SIZE,
      ordering,
      min_price: priceRange.min,
      max_price: priceRange.max,
      ...activeBadge,
    };

    if (activeCategoryId) {
      filters.category_id = activeCategoryId;
    }

    if (brandFilter) {
      filters.brand = brandFilter;
    }

    // Фильтр по наличию
    if (inStock) {
      filters.in_stock = true;
    }

    // Добавляем поисковый запрос
    if (searchFilter) {
      filters.search = searchFilter;
    }

    return filters;
  }, [
    page,
    ordering,
    priceRange.min,
    priceRange.max,
    activeBadge,
    activeCategoryId,
    brandFilter,
    inStock,
    searchFilter,
  ]);

  // Инвалидация версии — синхронно на commit новых параметров, а не в момент
  // старта следующего запроса. Между commit и passive-эффектом с fetchProducts
  // есть окно: ответ по прежним параметрам ещё считался бы актуальным, и его
  // 404 выдёргивал бы пользователя на первую страницу уже после навигации.
  // Обычно React успевает сбросить passive-эффекты микрозадачей раньше, но это
  // деталь его планировщика, а не контракт, — корректность на неё не опирается.
  useIsomorphicLayoutEffect(() => {
    requestSeq.current += 1;
  }, [productFilters]);

  const fetchProducts = useCallback(async () => {
    const seq = ++requestSeq.current;
    const filters = productFilters;
    try {
      setIsProductsLoading(true);
      setProductsError(null);

      // Ответы сайдбара проверяют версию запроса каждый сам: они приходят
      // независимо от выдачи товаров, и медленный ответ по прежним фильтрам
      // иначе сузил бы дерево и список брендов уже после смены фильтра.
      const isCurrent = () => seq === requestSeq.current;

      const [response] = await Promise.all([
        productsService.getAll(filters),
        // Параллельно обновляем видимость категорий по текущим фильтрам
        categoriesService
          .getVisibleCategories(filters)
          .then(ids => {
            if (isCurrent()) setSidebarVisibleIds(new Set(ids));
          })
          .catch(() => {
            if (isCurrent()) setSidebarVisibleIds(null); // fallback: показать всё дерево
          }),
        // Бренды сужаем только в режиме "В наличии"; при снятии чекбокса показываем весь первичный список
        filters.in_stock
          ? brandsService
              .getVisibleBrands(filters)
              .then(ids => {
                if (isCurrent()) setSidebarVisibleBrandIds(new Set(ids));
              })
              .catch(error => {
                console.warn('Не удалось загрузить видимые бренды', error);
                if (isCurrent()) setSidebarVisibleBrandIds(null);
              })
          : Promise.resolve().then(() => {
              if (isCurrent()) setSidebarVisibleBrandIds(null);
            }),
      ]);

      if (seq !== requestSeq.current) return;

      setProducts(response.results);
      setTotalProducts(response.count);
    } catch (error) {
      if (seq !== requestSeq.current) return;

      // Страница за пределом выдачи (устаревшая закладка, сузившийся каталог):
      // DRF отдаёт 404 с телом {"detail": "Invalid page."} — молча возвращаемся
      // на первую. replace, а не push: иначе «назад» возвращает на битую
      // страницу, которая снова отталкивает вперёд.
      const status = (error as AxiosError)?.response?.status;
      if (status === 404 && (filters.page ?? 1) > 1) {
        setPage(1);
        updateSearchParamsRef.current({ page: null }, { replace: true });
        return;
      }

      console.error('Не удалось загрузить товары', error);
      setProductsError('Не удалось загрузить товары');
    } finally {
      if (seq === requestSeq.current) {
        setIsProductsLoading(false);
      }
    }
  }, [productFilters]);

  useEffect(() => {
    // Ждём пока попытка загрузки категорий завершится (даже с ошибкой — F3),
    // чтобы URL-параметр category успел установить activeCategoryId.
    // При badge-фильтре грузим сразу.
    // Бренды: пока набор в состоянии не совпал с набором из URL, запрос ушёл бы
    // с неверным фильтром (см. isBrandFilterPending).
    if (isBrandFilterPending || isCategoryFilterPending) {
      return;
    }
    if (isCategoryLoadAttempted || hasBadgeFilter) {
      fetchProducts();
    }
  }, [
    fetchProducts,
    isCategoryLoadAttempted,
    hasBadgeFilter,
    isBrandFilterPending,
    isCategoryFilterPending,
  ]);

  // Ref для поля поиска
  const searchInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Если перешли с параметром focusSearch=true, фокусируемся на поле поиска
    if (focusSearchParam === 'true') {
      // Небольшая задержка чтобы убедиться что компонент смонтирован и анимации прошли
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 100);
    }
  }, [focusSearchParam]);

  const handleToggle = (key: string) => {
    setExpandedKeys(prev => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  const handleSelectCategory = (node: CategoryNode) => {
    setActiveCategoryId(node.id);
    setActiveCategoryLabel(node.label);
    resetPage({ category: node.slug ?? null });
  };

  const handleSelectAllCategories = () => {
    if (activeCategoryId === null) {
      // Галочка «Все» уже стоит — при клике разворачиваем фильтр если свёрнут
      setIsCategoriesOpen(true);
    } else {
      // Галочка «Все» не стоит — ставим галочку, снимаем категорию
      setActiveCategoryId(null);
      setActiveCategoryLabel('');
      setExpandedKeys(new Set()); // Очищаем развёрнутые подкатегории
      resetPage({ category: null });
      // Фильтр НЕ сворачиваем
    }
  };

  // Ползунок двигается сразу, а URL и запрос получают только итог перетаскивания:
  // каждый промежуточный шаг иначе стал бы отдельной записью в истории браузера
  // и отдельным запросом товаров.
  const handlePriceRangeChange = (value: PriceRange) => {
    setPriceDraft(value);
    cancelPriceCommit();
    priceCommitTimerRef.current = setTimeout(() => {
      priceCommitTimerRef.current = null;
      committedPriceRef.current = value;
      setPriceRange(value);
      resetPageRef.current({
        min_price: value.min === PRICE_MIN ? null : String(value.min),
        max_price: value.max === PRICE_MAX ? null : String(value.max),
      });
    }, PRICE_COMMIT_DELAY_MS);
  };

  const handleBrandToggle = (brandId: number) => {
    const next = new Set(selectedBrandIds);
    if (next.has(brandId)) {
      next.delete(brandId);
    } else {
      next.add(brandId);
    }
    setSelectedBrandIds(next);

    // CSV slug'ов строится от СЛЕДУЮЩЕГО набора, а не от текущего состояния:
    // setSelectedBrandIds ещё не применён в момент записи URL.
    const slugs = Array.from(next)
      .map(id => brands.find(brand => brand.id === id)?.slug)
      .filter((slug): slug is string => Boolean(slug));
    resetPage({ brand: slugs.length > 0 ? slugs.join(',') : null });
  };

  const handleOrderingChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const value = parseOrdering(event.target.value);
    setOrdering(value);
    resetPage({ ordering: value === DEFAULT_ORDERING ? null : value });
  };

  const handleResetFilters = () => {
    setSelectedBrandIds(new Set());
    // Отложенный commit цены отменяется здесь, а не эффектом синхронизации
    // драфта: если priceRange уже равен DEFAULT_PRICE_RANGE по идентичности
    // (сброс после сброса), сеттер ничего не меняет, эффект не перезапускается,
    // и переживший сброс таймер применил бы драфт, от которого пользователь ушёл.
    cancelPriceCommit();
    setPriceDraft(DEFAULT_PRICE_RANGE);
    setPriceRange(DEFAULT_PRICE_RANGE);
    setOrdering(DEFAULT_ORDERING);
    setInStock(true); // Сбрасываем фильтр "В наличии" в true
    setSearchQuery(''); // Сбрасываем поисковый запрос

    // Сбрасываем категорию в «Все»
    setActiveCategoryId(null);
    setActiveCategoryLabel('');
    setExpandedKeys(new Set()); // Очищаем развёрнутые подкатегории

    // Один push со всеми ключами фильтров сайдбара. Бейджи is_new/is_hit/is_sale
    // намеренно переживают сброс: они приходят внешним контекстом (переход с
    // главной) и в сайдбаре как фильтр не показаны.
    resetPage({
      category: null,
      brand: null,
      ordering: null,
      min_price: null,
      max_price: null,
      in_stock: null,
      search: null,
    });
  };

  const totalPages = Math.max(1, Math.ceil(totalProducts / PAGE_SIZE));

  const handlePageChange = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages || nextPage === page) return;
    invalidateOnPageChange(nextPage);
    setPage(nextPage);
    // Первая страница остаётся каноническим /catalog без параметра (SEO)
    updateSearchParams({ page: nextPage === 1 ? null : String(nextPage) });
  };

  const visiblePages = useMemo(() => {
    if (totalPages <= MAX_VISIBLE_PAGES) {
      return Array.from({ length: totalPages }, (_, index) => index + 1);
    }

    const half = Math.floor(MAX_VISIBLE_PAGES / 2);
    const maxStart = totalPages - MAX_VISIBLE_PAGES + 1;
    const startPage = Math.max(1, Math.min(page - half, maxStart));

    return Array.from({ length: MAX_VISIBLE_PAGES }, (_, index) => startPage + index);
  }, [page, totalPages]);

  /**
   * Обработчик добавления товара в корзину
   *
   * ВАЖНО: Список товаров не содержит variants (оптимизация API).
   * Поэтому сначала запрашиваем детали товара для получения вариантов.
   * Автоматически выбираем первый доступный вариант.
   *
   * TODO: В будущем добавить модальное окно для выбора конкретного варианта
   */
  const handleAddToCart = useCallback(
    async (productId: number) => {
      const product = products.find(p => p.id === productId);
      if (!product) {
        toastError('Товар не найден');
        return;
      }

      try {
        // Запрашиваем детали товара для получения вариантов
        const productDetail = await productsService.getProductBySlug(product.slug);

        if (!productDetail.variants || productDetail.variants.length === 0) {
          toastError('У товара отсутствуют варианты для заказа');
          return;
        }

        // Выбираем первый доступный вариант
        const availableVariant = productDetail.variants.find(v => v.is_in_stock);

        if (!availableVariant) {
          toastError('К сожалению, выбранный товар недоступен');
          return;
        }

        // Добавляем в корзину
        const result = await addItem(availableVariant.id, 1);

        if (result.success) {
          success(`${product.name} добавлен в корзину`);
        } else {
          toastError(result.error || 'Ошибка при добавлении в корзину');
        }
      } catch (error) {
        console.error('Error adding to cart:', error);
        toastError('Не удалось добавить товар в корзину');
      }
    },
    [products, addItem, success, toastError]
  );

  const renderProducts = () => {
    if (isProductsLoading) {
      return (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {Array.from({ length: PAGE_SIZE }).map((_, index) => (
            <div key={index} className="h-64 rounded-3xl bg-gray-100 animate-pulse" />
          ))}
        </div>
      );
    }

    if (productsError) {
      return <div className="text-center text-sm text-red-600">{productsError}</div>;
    }

    if (products.length === 0) {
      return <div className="text-center text-sm text-gray-500">Товары не найдены</div>;
    }

    if (viewMode === 'list') {
      return (
        <div className="space-y-4">
          {products.map(product => (
            <BusinessProductCard
              key={product.id}
              product={product}
              layout="list"
              userRole={userRole}
              mode={isB2B ? 'b2b' : 'b2c'}
              onAddToCart={handleAddToCart}
              isFavorite={favorites.some(f => f.product === product.id)}
              onToggleFavorite={handleToggleFavorite}
            />
          ))}
        </div>
      );
    }

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
        {products.map(product => (
          <BusinessProductCard
            key={product.id}
            product={product}
            layout="grid"
            userRole={userRole}
            mode={isB2B ? 'b2b' : 'b2c'}
            onAddToCart={handleAddToCart}
            isFavorite={favorites.some(f => f.product === product.id)}
            onToggleFavorite={handleToggleFavorite}
          />
        ))}
      </div>
    );
  };

  return (
    <div className="bg-[#F5F7FB] min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <nav
          className="text-sm text-gray-500 flex gap-2 flex-wrap items-center"
          aria-label="Хлебные крошки каталога"
        >
          {breadcrumbSegments.map((segment, index) => {
            const isLast = index === breadcrumbSegments.length - 1;

            return (
              <React.Fragment key={`${segment.label}-${index}`}>
                {index !== 0 && <span className="text-gray-400">/</span>}
                {segment.href && !isLast ? (
                  <Link href={segment.href} className="hover:text-primary transition-colors">
                    {segment.label}
                  </Link>
                ) : (
                  <span className={isLast ? 'text-gray-900 font-medium' : 'text-gray-500'}>
                    {segment.label}
                  </span>
                )}
              </React.Fragment>
            );
          })}
        </nav>

        {/* Единый грид для Поиска и Заголовка */}
        <div className="mt-6 grid grid-cols-1 lg:grid-cols-[280px_1fr] lg:grid-rows-[auto_auto] gap-x-8 gap-y-4 lg:gap-y-6 items-start">
          {/* 1. H1 - первый в DOM, визуально на второй строке.
                 min-h адаптивен (2rem mobile, 2.5rem desktop), совпадая с размером шрифта. */}
          <h1 className="lg:row-start-2 lg:col-span-2 self-start text-2xl md:text-4xl font-semibold text-neutral-900 break-words md:break-normal min-h-[2rem] md:min-h-[2.5rem]">
            {isCategoriesLoading ? (
              <Skeleton className="h-[2rem] md:h-[2.5rem] w-[60%] max-w-sm" />
            ) : activeCategoryId !== null ? (
              activeCategoryLabel
            ) : (
              'Каталог'
            )}
          </h1>

          {/* 2. Поиск - второй в DOM, визуально на первой строке в правой колонке. */}
          <search
            role="search"
            className="lg:row-start-1 lg:col-start-2 flex flex-col sm:flex-row items-start sm:items-center gap-4 relative z-20 w-full"
          >
            {/* SearchAutocomplete должен растягиваться на w-full если нужно */}
            <SearchAutocomplete
              ref={searchInputRef}
              placeholder="Поиск в каталоге..."
              onSearch={handleSearchChange}
              minLength={2}
              debounceMs={300}
              className="w-full max-w-full relative z-30"
              aria-label="Поиск товаров в каталоге"
            />

            {/* Индикатор результатов поиска */}
            {searchQuery.trim().length >= 2 && (
              <span
                className="text-sm text-gray-600 whitespace-nowrap"
                aria-live="polite"
                role="status"
              >
                Найдено {totalProducts}{' '}
                {totalProducts === 1 ? 'товар' : totalProducts < 5 ? 'товара' : 'товаров'} по
                запросу «{searchQuery}»
              </span>
            )}
          </search>
        </div>

        {/* TODO (F9): Вынести CategoryFilterSection и BrandFilterSection в отдельные компоненты
             для снижения размера CatalogContent (>1000 строк) */}
        <div className="mt-8 grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-8">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              {/* Заголовок «Категории» + чекбокс «Все» */}
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setIsCategoriesOpen(prev => !prev)}
                  className={cn(
                    'flex items-center gap-2 cursor-pointer text-base font-semibold text-gray-900',
                    'min-h-[44px]' // Минимальный touch target для a11y (F8)
                  )}
                  aria-expanded={isCategoriesOpen}
                  aria-controls="filter-categories"
                >
                  <ChevronDown
                    className={cn(
                      `w-4 h-4 text-gray-500 transition-transform ${FILTER_ANIMATION_DURATION}`,
                      isCategoriesOpen && 'rotate-180'
                    )}
                  />
                  <span>Категории</span>
                </button>
                <Checkbox
                  label="Все"
                  checked={activeCategoryId === null}
                  onChange={() => handleSelectAllCategories()}
                />
              </div>

              {/* Содержимое — CategoryTree с анимацией */}
              <div
                id="filter-categories"
                className={cn(
                  `overflow-hidden transition-all ${FILTER_ANIMATION_DURATION}`,
                  isCategoriesOpen
                    ? `${CATEGORY_MAX_HEIGHT} opacity-100 mt-4`
                    : 'max-h-0 opacity-0 mt-0'
                )}
              >
                {isCategoriesLoading ? (
                  <div className="space-y-2">
                    {Array.from({ length: 6 }).map((_, index) => (
                      <div key={index} className="h-4 bg-gray-100 rounded animate-pulse" />
                    ))}
                  </div>
                ) : categoriesError ? (
                  <p className="text-sm text-red-600">{categoriesError}</p>
                ) : (
                  <CategoryTree
                    nodes={categoryTree}
                    activeId={activeCategoryId}
                    expandedKeys={expandedKeys}
                    onToggle={handleToggle}
                    onSelect={handleSelectCategory}
                    visibleIds={sidebarVisibleIds}
                  />
                )}
              </div>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-6">
              <h2 className="text-base font-semibold text-gray-900">Фильтры</h2>

              <PriceRangeSlider
                min={PRICE_MIN}
                max={PRICE_MAX}
                step={PRICE_STEP}
                value={priceDraft}
                onChange={handlePriceRangeChange}
              />

              <div className="space-y-2 text-sm text-gray-600">
                <button
                  type="button"
                  onClick={() => setIsBrandsOpen(prev => !prev)}
                  className={cn(
                    'cursor-pointer font-medium text-gray-900 flex items-center gap-2 w-full',
                    'min-h-[44px]' // Минимальный touch target для a11y (F8)
                  )}
                  aria-expanded={isBrandsOpen}
                  aria-controls="filter-brands"
                >
                  <ChevronDown
                    className={cn(
                      `w-4 h-4 text-gray-500 transition-transform ${FILTER_ANIMATION_DURATION}`,
                      isBrandsOpen && 'rotate-180'
                    )}
                  />
                  <span>Бренд</span>
                </button>
                <div
                  id="filter-brands"
                  className={cn(
                    `overflow-hidden transition-all ${FILTER_ANIMATION_DURATION}`,
                    isBrandsOpen ? `${BRANDS_MAX_HEIGHT} opacity-100` : 'max-h-0 opacity-0'
                  )}
                >
                  <div className="mt-2 flex flex-col gap-1">
                    {isBrandsLoading && <p className="text-xs text-gray-400">Загрузка...</p>}
                    {brandsError && <p className="text-xs text-red-500">{brandsError}</p>}
                    {!isBrandsLoading &&
                      !brandsError &&
                      (() => {
                        const visibleBrands = brands.filter(
                          brand =>
                            sidebarVisibleBrandIds === null ||
                            sidebarVisibleBrandIds.has(brand.id) ||
                            selectedBrandIds.has(brand.id)
                        );

                        if (visibleBrands.length === 0) {
                          return <p className="text-xs text-gray-400">Бренды не найдены</p>;
                        }

                        return visibleBrands.map(brand => (
                          <div key={brand.id}>
                            <Checkbox
                              label={brand.name}
                              checked={selectedBrandIds.has(brand.id)}
                              onChange={() => handleBrandToggle(brand.id)}
                            />
                          </div>
                        ));
                      })()}
                  </div>
                </div>
              </div>

              {/* Чекбокс "В наличии" */}
              <div className="pt-2 border-t border-gray-100">
                <Checkbox
                  label="В наличии"
                  checked={inStock}
                  onChange={e => {
                    const checked = e.target.checked;
                    setInStock(checked);
                    // Видимость сайдбара пересчитывает эффект [categoryTree, inStock] —
                    // он же отрабатывает и «назад» на ?in_stock=false
                    resetPage({ in_stock: checked ? null : 'false' });
                  }}
                />
              </div>

              <div className="flex flex-col gap-3">
                {/* Кнопки «Применить» больше нет: каждый фильтр применяется в своём
                    обработчике и зеркалится в URL, а кнопка была вторым, невидимым
                    в адресной строке способом запустить тот же запрос. */}
                <Button variant="secondary" size="small" onClick={handleResetFilters}>
                  Сбросить
                </Button>
              </div>
            </div>
          </aside>

          <section className="space-y-6">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <span className="text-sm text-gray-600">
                Показано {products.length} из {totalProducts} товаров
              </span>

              <div className="flex items-center gap-3">
                <div className="inline-flex items-center rounded-full bg-gray-100 p-1">
                  <button
                    className={`flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium ${
                      viewMode === 'grid' ? 'bg-white text-gray-900 shadow' : 'text-gray-500'
                    }`}
                    onClick={() => setViewMode('grid')}
                  >
                    <Grid2x2 className="h-4 w-4" />
                    <span className="hidden sm:inline">Сетка</span>
                  </button>
                  <button
                    className={`flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium ${
                      viewMode === 'list' ? 'bg-white text-gray-900 shadow' : 'text-gray-500'
                    }`}
                    onClick={() => setViewMode('list')}
                  >
                    <List className="h-4 w-4" />
                    <span className="hidden sm:inline">Список</span>
                  </button>
                </div>

                <div className="relative">
                  <select
                    value={ordering}
                    onChange={handleOrderingChange}
                    className="appearance-none border border-gray-200 rounded-full py-2 pl-4 pr-10 text-sm text-gray-700"
                  >
                    <option value="-created_at">По новизне</option>
                    <option value="min_retail_price">По цене (возр.)</option>
                    <option value="-min_retail_price">По цене (убыв.)</option>
                    <option value="name">По названию (А→Я)</option>
                    <option value="-name">По названию (Я→А)</option>
                  </select>
                  <span className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-gray-500">
                    ▼
                  </span>
                </div>
              </div>
            </div>

            {renderProducts()}

            <div className="flex justify-center">
              <nav className="flex items-center gap-2 text-sm">
                <button
                  className="h-10 w-10 rounded-[6px] border border-neutral-300 text-neutral-500 hover:border-primary hover:text-primary disabled:opacity-40 transition-colors"
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page <= 1}
                  aria-label="Предыдущая страница"
                >
                  ←
                </button>

                {visiblePages.map(pageNumber => (
                  <button
                    key={pageNumber}
                    onClick={() => handlePageChange(pageNumber)}
                    aria-current={pageNumber === page ? 'page' : undefined}
                    className={
                      pageNumber === page
                        ? 'h-10 w-10 rounded-[6px] bg-primary text-white hover:bg-primary-hover'
                        : 'h-10 w-10 rounded-[6px] border border-neutral-300 text-neutral-600 hover:border-primary hover:text-primary'
                    }
                  >
                    {pageNumber}
                  </button>
                ))}

                <button
                  className="h-10 w-10 rounded-[6px] border border-neutral-300 text-neutral-500 hover:border-primary hover:text-primary disabled:opacity-40 transition-colors"
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page >= totalPages}
                  aria-label="Следующая страница"
                >
                  →
                </button>
              </nav>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

const CatalogPage: React.FC = () => {
  return (
    <Suspense fallback={<div className="min-h-screen bg-[#F5F7FB]" />}>
      <CatalogContent />
    </Suspense>
  );
};

export default CatalogPage;
