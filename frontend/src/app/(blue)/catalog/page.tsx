/**
 * Страница каталога товаров FREESPORT Platform
 * Загружает реальные товары из API и применяет фильтры (Story 12.7)
 */

'use client';

import React, { useCallback, useEffect, useMemo, useState, Suspense } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import Link from 'next/link';
import Button from '@/components/ui/Button';
import { Checkbox } from '@/components/ui/Checkbox';
import { SearchAutocomplete } from '@/components/business/SearchAutocomplete';
import { Grid2x2, List } from 'lucide-react';
import { ProductCard as BusinessProductCard } from '@/components/business/ProductCard/ProductCard';
import productsService, { type ProductFilters } from '@/services/productsService';
import categoriesService from '@/services/categoriesService';
import brandsService from '@/services/brandsService';
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
  children?: CategoryNode[];
};

const PRICE_MIN = 1;
const PRICE_MAX = 50000;
const DEFAULT_PRICE_RANGE: PriceRange = { min: PRICE_MIN, max: PRICE_MAX };
const PRICE_STEP = 500;
const PAGE_SIZE = 12;
const MAX_VISIBLE_PAGES = 5;
const DEFAULT_ORDERING = 'name';
const DEFAULT_CATEGORY_LABEL = 'Спорт';

const CATEGORY_ICON_MAP: Record<string, string> = {
  sport: '🏃',
  спорт: '🏃',
  tourism: '🥾',
  туризм: '🥾',
  fitness: '💪',
  фитнес: '💪',
  'фитнес и атлетика': '💪',
  swimming: '🏊',
  плавание: '🏊',
  games: '⚽',
  'спортивные игры': '⚽',
  martial: '🥊',
  единоборства: '🥊',
  gymnastics: '🤸',
  гимнастика: '🤸',
  apparel: '👕',
  'одежда спортивная': '👕',
  transport: '🚲',
  'детский транспорт': '🚲',
};

const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const getNodeKey = (path: number[]) => path.join(' > ');

const getIconForCategory = (name: string, slug?: string) => {
  const normalizedSlug = slug
    ?.toLowerCase()
    .replace(/[^a-z0-9\-а-яё]/gi, '')
    .trim();
  const normalizedName = name.toLowerCase();
  if (normalizedSlug && CATEGORY_ICON_MAP[normalizedSlug]) {
    return CATEGORY_ICON_MAP[normalizedSlug];
  }
  if (CATEGORY_ICON_MAP[normalizedName]) {
    return CATEGORY_ICON_MAP[normalizedName];
  }
  return undefined;
};

const mapCategoryTreeNode = (node: CategoryTreeResponse): CategoryNode => ({
  id: node.id,
  label: node.name,
  slug: node.slug,
  icon: getIconForCategory(node.name, node.slug),
  children: node.children?.map(mapCategoryTreeNode),
});

const findCategoryByLabel = (nodes: CategoryNode[], targetLabel: string): CategoryNode | null => {
  for (const node of nodes) {
    if (node.label === targetLabel) {
      return node;
    }
    if (node.children) {
      const child = findCategoryByLabel(node.children, targetLabel);
      if (child) {
        return child;
      }
    }
  }
  return null;
};

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
          background: #FF6B00;
          border: 4px solid #FFE0B2;
          background: #FF6600;
          border: 4px solid #FFD6B3;
          box-shadow: 0 2px 6px rgba(255, 102, 0, 0.35);
          cursor: pointer;
          margin-top: -9px;
        }

        .price-range-thumb::-moz-range-thumb {
          height: 18px;
          width: 18px;
          border-radius: 50%;
          background: #FF6600;
          border: 4px solid #FFD6B3;
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
}> = ({ nodes, level = 0, activeId, expandedKeys, onToggle, onSelect, path = [] }) => {
  return (
    <ul className={level === 0 ? 'space-y-2' : 'space-y-1 pl-3 border-l border-gray-100'}>
      {nodes.map(node => {
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
                  'flex-1 rounded-lg px-2 py-1 text-left text-sm transition-colors ' +
                  (isActive
                    ? 'bg-primary-subtle text-primary font-semibold'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900')
                }
              >
                {node.label}
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
  const [categoryTree, setCategoryTree] = useState<CategoryNode[]>([]);
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);
  const [activeCategoryLabel, setActiveCategoryLabel] = useState(DEFAULT_CATEGORY_LABEL);

  // Badge-фильтры из URL (is_new, is_hit, is_sale)
  const activeBadge = useMemo(() => {
    const isNew = searchParams.get('is_new');
    const isHit = searchParams.get('is_hit');
    const isSale = searchParams.get('is_sale');
    return {
      is_new: isNew === 'true' ? true : undefined,
      is_hit: isHit === 'true' ? true : undefined,
      is_sale: isSale === 'true' ? true : undefined,
    };
  }, [searchParams]);
  const hasBadgeFilter = Boolean(activeBadge.is_new || activeBadge.is_hit || activeBadge.is_sale);
  const [isCategoriesLoading, setIsCategoriesLoading] = useState(true);
  const [categoriesError, setCategoriesError] = useState<string | null>(null);

  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<number>>(new Set());
  const [isBrandsLoading, setIsBrandsLoading] = useState(true);
  const [brandsError, setBrandsError] = useState<string | null>(null);

  const [priceRange, setPriceRange] = useState<PriceRange>(DEFAULT_PRICE_RANGE);
  const [searchQuery, setSearchQuery] = useState('');
  const [products, setProducts] = useState<Product[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState(DEFAULT_ORDERING);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [isProductsLoading, setIsProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);
  const [inStock, setInStock] = useState(true); // По умолчанию показываем только товары в наличии

  // Auth integration
  const user = useAuthStore(state => state.user);
  const userRole = user?.role || 'guest';
  const isB2B = [
    'wholesale_level1',
    'wholesale_level2',
    'wholesale_level3',
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

    // Если активной категории нет или она не найдена в дереве, но есть activeCategoryLabel (например "Спорт")
    // хотя в текущей логике activeCategoryLabel обновляется из activePathNodes,
    // но на всякий случай оставим fallback, но без ссылки, так как slug неизвестен
    if (activeCategoryLabel && activeCategoryLabel !== DEFAULT_CATEGORY_LABEL) {
      return [...base, { label: activeCategoryLabel, href: null }];
    }

    return base;
  }, [activePathNodes, activeCategoryLabel]);

  useEffect(() => {
    let isMounted = true;

    const fetchCategories = async () => {
      try {
        const tree = await categoriesService.getTree();
        if (!isMounted) return;
        const mapped = tree.map(mapCategoryTreeNode);
        setCategoryTree(mapped);

        const categorySlug = searchParams.get('category');
        let initialCategory: CategoryNode | null = null;

        if (categorySlug) {
          initialCategory = findCategoryBySlug(mapped, categorySlug);
        }

        if (!initialCategory && !hasBadgeFilter) {
          // Если нет badge-фильтра, выбираем категорию по умолчанию
          initialCategory =
            findCategoryByLabel(mapped, DEFAULT_CATEGORY_LABEL) ?? mapped[0] ?? null;
        }

        if (initialCategory) {
          setActiveCategoryId(initialCategory.id);
          setActiveCategoryLabel(initialCategory.label);
          const pathNodes = findCategoryPathById(mapped, initialCategory.id);
          setExpandedKeys(new Set(getKeysForPath(pathNodes)));
        }
      } catch (error) {
        console.error('Не удалось загрузить дерево категорий', error);
        if (isMounted) {
          setCategoriesError('Не удалось загрузить категории');
        }
      } finally {
        if (isMounted) {
          setIsCategoriesLoading(false);
        }
      }
    };

    fetchCategories();

    return () => {
      isMounted = false;
    };
  }, [searchParams, hasBadgeFilter]);

  // Чтение параметра search из URL при инициализации
  useEffect(() => {
    const searchFromUrl = searchParams.get('search');
    if (searchFromUrl) {
      setSearchQuery(searchFromUrl);
    }
  }, [searchParams]);

  useEffect(() => {
    let isMounted = true;

    const fetchBrands = async () => {
      try {
        const data = await brandsService.getAll();
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

  // Синхронизация фильтра бренда с URL
  useEffect(() => {
    const brandSlug = searchParams.get('brand');
    // Если есть параметр в URL и бренды загружены
    if (brandSlug && brands.length > 0) {
      const foundBrand = brands.find(b => b.slug === brandSlug);
      if (foundBrand) {
        // Устанавливаем фильтр (заменяем текущий выбор или добавляем - логичнее заменить при прямом переходе)
        setSelectedBrandIds(new Set([foundBrand.id]));
      }
    }
  }, [searchParams, brands]);

  useEffect(() => {
    if (!activeCategoryId || !categoryTree.length) return;
    const pathNodes = findCategoryPathById(categoryTree, activeCategoryId);
    if (!pathNodes.length) return;
    setExpandedKeys(prev => {
      const next = new Set(prev);
      getKeysForPath(pathNodes).forEach(key => next.add(key));
      return next;
    });
    setActiveCategoryLabel(pathNodes[pathNodes.length - 1]?.label ?? DEFAULT_CATEGORY_LABEL);
  }, [activeCategoryId, categoryTree]);

  // Функция для обновления URL параметров без перезагрузки страницы
  const updateSearchParams = useCallback(
    (key: string, value: string | null) => {
      const params = new URLSearchParams(searchParams.toString());

      if (value === null || value === '') {
        params.delete(key);
      } else {
        params.set(key, value);
      }

      const newUrl = params.toString() ? `${pathname}?${params.toString()}` : pathname;
      router.push(newUrl, { scroll: false });
    },
    [pathname, router, searchParams]
  );

  // Обработчик изменения поискового запроса
  const handleSearchChange = useCallback(
    (query: string) => {
      setSearchQuery(query);
      updateSearchParams('search', query || null);
      setPage(1);
    },
    [updateSearchParams]
  );

  const fetchProducts = useCallback(async () => {
    try {
      setIsProductsLoading(true);
      setProductsError(null);

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

      if (selectedBrandIds.size > 0) {
        filters.brand = Array.from(selectedBrandIds).join(',');
      }

      // Фильтр по наличию
      if (inStock) {
        filters.in_stock = true;
      }

      // Добавляем поисковый запрос
      if (searchQuery.trim().length >= 2) {
        filters.search = searchQuery.trim();
      }

      const response = await productsService.getAll(filters);
      setProducts(response.results);
      setTotalProducts(response.count);
    } catch (error) {
      console.error('Не удалось загрузить товары', error);
      setProductsError('Не удалось загрузить товары');
    } finally {
      setIsProductsLoading(false);
    }
  }, [
    activeCategoryId,
    ordering,
    page,
    priceRange.max,
    priceRange.min,
    selectedBrandIds,
    inStock,
    searchQuery,
    activeBadge,
  ]);

  useEffect(() => {
    // Ждём пока категория будет установлена перед запросом товаров
    // При badge-фильтре запрашиваем без ожидания категории
    if (activeCategoryId !== null || hasBadgeFilter) {
      fetchProducts();
    }
  }, [fetchProducts, activeCategoryId, hasBadgeFilter]);

  // Ref для поля поиска
  const searchInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    // Если перешли с параметром focusSearch=true, фокусируемся на поле поиска
    if (searchParams.get('focusSearch') === 'true') {
      // Небольшая задержка чтобы убедиться что компонент смонтирован и анимации прошли
      setTimeout(() => {
        searchInputRef.current?.focus();
      }, 100);
    }
  }, [searchParams]);

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
    setPage(1);
  };

  const handlePriceRangeChange = (value: PriceRange) => {
    setPriceRange(value);
    setPage(1);
  };

  const handleBrandToggle = (brandId: number) => {
    setSelectedBrandIds(prev => {
      const next = new Set(prev);
      if (next.has(brandId)) {
        next.delete(brandId);
      } else {
        next.add(brandId);
      }
      return next;
    });
    setPage(1);
  };

  const handleOrderingChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setOrdering(event.target.value);
    setPage(1);
  };

  const handleResetFilters = () => {
    setSelectedBrandIds(new Set());
    setPriceRange(DEFAULT_PRICE_RANGE);
    setOrdering(DEFAULT_ORDERING);
    setInStock(true); // Сбрасываем фильтр "В наличии" в true
    setSearchQuery(''); // Сбрасываем поисковый запрос
    setPage(1);

    // Очищаем параметр search из URL
    updateSearchParams('search', null);

    if (categoryTree.length) {
      const fallbackCategory =
        findCategoryByLabel(categoryTree, DEFAULT_CATEGORY_LABEL) ?? categoryTree[0] ?? null;
      if (fallbackCategory) {
        setActiveCategoryId(fallbackCategory.id);
        setActiveCategoryLabel(fallbackCategory.label);
      }
    }
  };

  const totalPages = Math.max(1, Math.ceil(totalProducts / PAGE_SIZE));

  const handlePageChange = (nextPage: number) => {
    if (nextPage < 1 || nextPage > totalPages) return;
    setPage(nextPage);
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

        {/* Заголовок и поиск выровнены по сетке основного контента */}
        <div className="mt-6 grid gap-8 lg:grid-cols-[280px_1fr] items-center">
          <h1 className="text-4xl font-semibold text-gray-900">{activeCategoryLabel}</h1>

          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
            <SearchAutocomplete
              ref={searchInputRef}
              placeholder="Поиск в каталоге..."
              onSearch={handleSearchChange}
              minLength={2}
              debounceMs={300}
              className="w-full sm:max-w-md"
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
          </div>
        </div>

        <div className="mt-8 grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-8">
            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6">
              <details>
                <summary className="cursor-pointer text-base font-semibold text-gray-900">
                  Категории
                </summary>
                <div className="mt-4">
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
                    />
                  )}
                </div>
              </details>
            </div>

            <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 space-y-6">
              <h2 className="text-base font-semibold text-gray-900">Фильтры</h2>

              <PriceRangeSlider
                min={PRICE_MIN}
                max={PRICE_MAX}
                step={PRICE_STEP}
                value={priceRange}
                onChange={handlePriceRangeChange}
              />

              <div className="space-y-2 text-sm text-gray-600">
                <details open>
                  <summary className="cursor-pointer font-medium text-gray-900">Бренд</summary>
                  <div className="mt-2 flex flex-col gap-1">
                    {isBrandsLoading && <p className="text-xs text-gray-400">Загрузка...</p>}
                    {brandsError && <p className="text-xs text-red-500">{brandsError}</p>}
                    {!isBrandsLoading && !brandsError && brands.length === 0 && (
                      <p className="text-xs text-gray-400">Бренды не найдены</p>
                    )}
                    {!isBrandsLoading &&
                      !brandsError &&
                      brands.map(brand => (
                        <div key={brand.id}>
                          <Checkbox
                            label={brand.name}
                            checked={selectedBrandIds.has(brand.id)}
                            onChange={() => handleBrandToggle(brand.id)}
                          />
                        </div>
                      ))}
                  </div>
                </details>
              </div>

              {/* Чекбокс "В наличии" */}
              <div className="pt-2 border-t border-gray-100">
                <Checkbox
                  label="В наличии"
                  checked={inStock}
                  onChange={e => {
                    setInStock(e.target.checked);
                    setPage(1);
                  }}
                />
              </div>

              <div className="flex flex-col gap-3">
                <Button variant="primary" size="small" onClick={fetchProducts}>
                  Применить
                </Button>
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
                    className={`flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium ${viewMode === 'grid' ? 'bg-white text-gray-900 shadow' : 'text-gray-500'
                      }`}
                    onClick={() => setViewMode('grid')}
                  >
                    <Grid2x2 className="h-4 w-4" />
                    <span className="hidden sm:inline">Сетка</span>
                  </button>
                  <button
                    className={`flex items-center gap-1 rounded-full px-3 py-2 text-sm font-medium ${viewMode === 'list' ? 'bg-white text-gray-900 shadow' : 'text-gray-500'
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
                  disabled={page === 1}
                  aria-label="Предыдущая страница"
                >
                  ←
                </button>

                {visiblePages.map(pageNumber => (
                  <button
                    key={pageNumber}
                    onClick={() => handlePageChange(pageNumber)}
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
                  disabled={page === totalPages}
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
