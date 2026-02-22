/**
 * Страница каталога товаров FREESPORT Platform (Electric Orange Edition)
 * Parallel Route for Design System Migration
 */

'use client';

import React, { useCallback, useEffect, useState, Suspense, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';

// Electric Orange Components
import ElectricProductCard from '@/components/ui/ProductCard/ElectricProductCard';
import ElectricSidebar from '@/components/ui/Sidebar/ElectricSidebar';
import ElectricPagination from '@/components/ui/Pagination/ElectricPagination';
import ElectricSpinner from '@/components/ui/Spinner/ElectricSpinner';
import { useToast } from '@/components/ui/Toast';
import { ElectricBreadcrumbs } from '@/components/ui/Breadcrumb/ElectricBreadcrumbs';
import { SortSelect, SORT_OPTIONS } from '@/components/ui/SortSelect/SortSelect';
import { ElectricCategoryTree } from '@/components/ui/CategoryTree/ElectricCategoryTree';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import { ElectricDrawer } from '@/components/ui/Drawer/ElectricDrawer';
import { SlidersHorizontal } from 'lucide-react';

// Services & Type Definitions
import productsService, { type ProductFilters } from '@/services/productsService';
import categoriesService from '@/services/categoriesService';
import brandsService from '@/services/brandsService';
import type { Product, CategoryTree as CategoryTreeResponse, Brand } from '@/types/api';
import { useCartStore } from '@/stores/cartStore';

// ============================================
// Types reuse
// ============================================

type PriceRange = {
  min: number;
  max: number;
};

type CategoryNode = {
  id: number;
  label: string;
  slug?: string;
  count?: number; // Added for ElectricSidebar compatibility
  children?: CategoryNode[];
};

// ============================================
// Constants
// ============================================

const PRICE_MIN = 1;
const PRICE_MAX = 50000;
const DEFAULT_PRICE_RANGE: PriceRange = { min: PRICE_MIN, max: PRICE_MAX };
const PAGE_SIZE = 12;
const DEFAULT_ORDERING = '-created_at';
const DEFAULT_CATEGORY_LABEL = 'Спорт';

const mapCategoryTreeNode = (node: CategoryTreeResponse): CategoryNode => ({
  id: node.id,
  label: node.name,
  slug: node.slug,
  children: node.children?.map(mapCategoryTreeNode),
});

const findCategoryBySlug = (nodes: CategoryNode[], targetSlug: string): CategoryNode | null => {
  for (const node of nodes) {
    if (node.slug === targetSlug) return node;
    if (node.children) {
      const child = findCategoryBySlug(node.children, targetSlug);
      if (child) return child;
    }
  }
  return null;
};

const findCategoryByLabel = (nodes: CategoryNode[], targetLabel: string): CategoryNode | null => {
  for (const node of nodes) {
    if (node.label === targetLabel) return node;
    if (node.children) {
      const child = findCategoryByLabel(node.children, targetLabel);
      if (child) return child;
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

// ============================================
// Main Component
// ============================================

const ElectricCatalogPage: React.FC = () => {
  const searchParams = useSearchParams();

  // State
  const [activeCategoryId, setActiveCategoryId] = useState<number | null>(null);

  const [brands, setBrands] = useState<Brand[]>([]);
  const [selectedBrandIds, setSelectedBrandIds] = useState<Set<number>>(new Set());

  const [priceRange, setPriceRange] = useState<PriceRange>(DEFAULT_PRICE_RANGE);
  const [searchQuery, setSearchQuery] = useState('');

  const [categoriesTree, setCategoriesTree] = useState<CategoryNode[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [totalProducts, setTotalProducts] = useState(0);
  const [page, setPage] = useState(1);
  const [ordering, setOrdering] = useState(DEFAULT_ORDERING);

  // Quick filters: 'all' | 'new' | 'sale'
  const [quickFilter, setQuickFilter] = useState<'all' | 'new' | 'sale'>('all');

  const [isProductsLoading, setIsProductsLoading] = useState(false);
  const [productsError, setProductsError] = useState<string | null>(null);

  // Mobile filter drawer state
  const [isFilterDrawerOpen, setIsFilterDrawerOpen] = useState(false);

  // Cart
  const { addItem } = useCartStore();
  const { success, error: toastError } = useToast();

  // Computed: Active category path (for breadcrumbs)
  const activePathNodes = useMemo(() => {
    if (!activeCategoryId || categoriesTree.length === 0) return [];
    return findCategoryPathById(categoriesTree, activeCategoryId);
  }, [categoriesTree, activeCategoryId]);

  // Computed: Check if any filters are active (to show reset button)
  const hasActiveFilters = useMemo(() => {
    return (
      selectedBrandIds.size > 0 ||
      priceRange.min !== DEFAULT_PRICE_RANGE.min ||
      priceRange.max !== DEFAULT_PRICE_RANGE.max ||
      quickFilter !== 'all' ||
      searchQuery.trim().length > 0
    );
  }, [selectedBrandIds, priceRange, quickFilter, searchQuery]);

  // Computed: Count of active filters for badge
  const activeFiltersCount = useMemo(() => {
    let count = 0;
    if (selectedBrandIds.size > 0) count += selectedBrandIds.size;
    if (priceRange.min !== DEFAULT_PRICE_RANGE.min || priceRange.max !== DEFAULT_PRICE_RANGE.max)
      count += 1;
    if (quickFilter !== 'all') count += 1;
    return count;
  }, [selectedBrandIds, priceRange, quickFilter]);

  // Breadcrumb items (excluding "СПОРТ")
  const breadcrumbItems = useMemo(() => {
    const base = [
      { label: 'Главная', href: '/electric' },
      { label: 'Каталог', href: '/electric/catalog' },
    ];

    // Filter out "СПОРТ" (case-insensitive) and add remaining path
    const categoryPath = activePathNodes
      .filter(node => node.label.toLowerCase() !== DEFAULT_CATEGORY_LABEL.toLowerCase())
      .map((node: CategoryNode, index: number, arr: CategoryNode[]) => ({
        label: node.label,
        href: index < arr.length - 1 ? `/electric/catalog?category=${node.slug}` : undefined,
      }));

    return [...base, ...categoryPath];
  }, [activePathNodes]);

  // --------------------------------------------
  // Data Fetching: Categories & Brands
  // --------------------------------------------

  useEffect(() => {
    let isMounted = true;

    const fetchCategories = async () => {
      try {
        const tree = await categoriesService.getTree();
        if (!isMounted) return;
        const mapped = tree.map(mapCategoryTreeNode);
        setCategoriesTree(mapped);

        const categorySlug = searchParams.get('category');
        let initialCategory: CategoryNode | null = null;

        if (categorySlug) {
          initialCategory = findCategoryBySlug(mapped, categorySlug);
        }
        if (!initialCategory) {
          initialCategory =
            findCategoryByLabel(mapped, DEFAULT_CATEGORY_LABEL) ?? mapped[0] ?? null;
        }

        if (initialCategory) {
          setActiveCategoryId(initialCategory.id);
        }
      } catch (error) {
        console.error('Failed to load categories', error);
      }
    };

    fetchCategories();
    return () => {
      isMounted = false;
    };
  }, [searchParams]);

  useEffect(() => {
    let isMounted = true;
    const fetchBrands = async () => {
      try {
        const data = await brandsService.getAll();
        if (isMounted) setBrands(data);
      } catch (error) {
        console.error('Failed to load brands', error);
      }
    };
    fetchBrands();
    return () => {
      isMounted = false;
    };
  }, []);

  // --------------------------------------------
  // URL & Filters Sync
  // --------------------------------------------

  useEffect(() => {
    const searchFromUrl = searchParams.get('search');
    if (searchFromUrl) setSearchQuery(searchFromUrl);
  }, [searchParams]);

  // --------------------------------------------
  // Products Fetching
  // --------------------------------------------

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
        in_stock: true,
      };

      if (activeCategoryId) filters.category_id = activeCategoryId;
      if (selectedBrandIds.size > 0) filters.brand = Array.from(selectedBrandIds).join(',');
      if (searchQuery.trim().length >= 2) filters.search = searchQuery.trim();

      // Quick filters
      if (quickFilter === 'new') filters.is_new = true;
      if (quickFilter === 'sale') filters.is_sale = true;

      const response = await productsService.getAll(filters);
      setProducts(response.results);
      setTotalProducts(response.count);
    } catch (error) {
      console.error('Failed to load products', error);
      setProductsError('Не удалось загрузить товары');
    } finally {
      setIsProductsLoading(false);
    }
  }, [activeCategoryId, ordering, page, priceRange, selectedBrandIds, searchQuery, quickFilter]);

  useEffect(() => {
    if (activeCategoryId !== null) {
      fetchProducts();
    }
  }, [fetchProducts, activeCategoryId]);

  // --------------------------------------------
  // Handlers
  // --------------------------------------------

  const handleFilterChange = (groupId: string, optionId: string, checked: boolean) => {
    // Categories
    if (groupId === 'categories') {
      // Handled via link-list click which might just navigate or set filter
      // For now, if we want to filter by category ID client side:
      const catId = Number(optionId);
      if (!isNaN(catId)) {
        setActiveCategoryId(catId);
        setPage(1);
      }
    }

    // Brands
    if (groupId === 'brands') {
      const brandId = Number(optionId);
      if (!isNaN(brandId)) {
        setSelectedBrandIds(prev => {
          const next = new Set(prev);
          if (checked) next.add(brandId);
          else next.delete(brandId);
          return next;
        });
        setPage(1);
      }
    }
  };

  const handlePriceChange = (range: { min: number; max: number }) => {
    setPriceRange(range);
    setPage(1);
  };

  // Reset all filters to default values
  const handleResetFilters = useCallback(() => {
    setSelectedBrandIds(new Set());
    setPriceRange(DEFAULT_PRICE_RANGE);
    setQuickFilter('all');
    setSearchQuery('');
    setPage(1);
  }, []);

  const handleAddToCart = useCallback(
    async (productId: number) => {
      // Reuse existing logic from original page
      const product = products.find(p => p.id === productId);
      if (!product) return;

      try {
        const productDetail = await productsService.getProductBySlug(product.slug);
        const availableVariant = productDetail.variants?.find(v => v.is_in_stock);

        if (!availableVariant) {
          toastError('Товар недоступен');
          return;
        }

        const result = await addItem(availableVariant.id, 1);
        if (result.success) success(`${product.name} добавлен`);
        else toastError(result.error || 'Ошибка');
      } catch {
        toastError('Ошибка добавления');
      }
    },
    [products, addItem, success, toastError]
  );

  // --------------------------------------------
  // Adapters for Sidebar
  // --------------------------------------------

  // Transform Category Tree for Sidebar
  // We flatten the tree or just show top levels for the filter?
  // Let's emulate the visual style: Categories as a checklist or radio.
  // Original catalog uses a tree. ElectricSidebar uses `filterGroups`.

  // Let's create a custom adapter to convert the tree active path into sidebar options if needed.
  // Or, simply pass the relevant categories.

  const brandFilterOptions = brands.map(brand => ({
    id: String(brand.id),
    label: brand.name,
  }));

  // Flatten categories or use direct children of active category?
  // For 'link-list', we ideally want to show the current level siblings or children.
  // For simplicity, let's show top-level categories if no category selected,
  // or children of current category.
  // We need access to the full tree 'mapped' which is inside useEffect.
  // Better to move 'categories' state up or fetch it differently.
  // For this "Retro-Spec" implementation, let's just use a hardcoded list or empty for now if complexities arise,
  // BUT user asked for "Categories in Sidebar".
  // Let's rely on `categoriesService.getTree` being cached or fast enough.
  // Actually, we can just use `activeCategoryId` to decide what to show?
  // Since `mapped` is local to useEffect, we can't access it here.
  // Let's add `categories` state.

  // NOTE: Ideally we refactor data fetching, but for now let's assume we have categories.
  // I will add `categoriesTree` state in a separate chunk.

  // --------------------------------------------
  // Render
  // --------------------------------------------

  const totalPages = Math.max(1, Math.ceil(totalProducts / PAGE_SIZE));

  return (
    <div className="min-h-screen bg-[var(--bg-body)] text-[var(--color-text-primary)] font-body selection:bg-[var(--color-primary)] selection:text-[var(--color-text-inverse)] pt-20 md:pt-24">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {/* Breadcrumbs */}
        <div className="mb-6">
          <ElectricBreadcrumbs items={breadcrumbItems} />
        </div>

        {/* Controls Bar: Aligned with Sidebar (Count) and Content (Tabs + Sort) */}
        <div className="flex flex-col lg:flex-row lg:gap-8 mb-6">
          {/* Left Column: Aligned with Sidebar (280px) */}
          <div className="lg:w-[280px] lg:flex-shrink-0 flex items-center mb-4 lg:mb-0">
            <span className="text-xs md:text-sm text-[var(--color-text-secondary)] whitespace-nowrap">
              Найдено {totalProducts} товаров
            </span>
          </div>

          {/* Right Column: Aligned with Product Grid */}
          <div className="flex-1 min-w-0 flex flex-col md:flex-row justify-between items-start md:items-center gap-4 md:gap-0">
            {/* Quick Filter Tabs */}
            {/* Added px-4 to prevent first and last skewed buttons from being cut off */}
            <div className="flex gap-2 overflow-x-auto pb-2 lg:pb-0 px-4 scrollbar-hide max-w-full -ml-4">
              {[
                { key: 'all' as const, label: 'Все товары' },
                { key: 'new' as const, label: 'Новинки' },
                { key: 'sale' as const, label: 'Акция' },
              ].map(({ key, label }) => (
                <button
                  key={key}
                  onClick={() => {
                    setQuickFilter(key);
                    setPage(1);
                  }}
                  className={`
                    px-3 py-1.5 md:px-4 md:py-2 text-xs md:text-sm font-medium uppercase tracking-wide whitespace-nowrap
                    border transition-all duration-200 flex-shrink-0
                    ${
                      quickFilter === key
                        ? 'bg-[var(--color-primary)] text-[var(--color-text-inverse)] border-[var(--color-primary)]'
                        : 'bg-transparent text-[var(--color-text-secondary)] border-[var(--border-default)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]'
                    }
                  `}
                  style={{ transform: 'skewX(-12deg)' }}
                >
                  <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>
                    {label}
                  </span>
                </button>
              ))}
            </div>

            {/* Sort & Mobile Filters */}
            <div className="flex items-center gap-3 w-full md:w-auto justify-between md:justify-end">
              {/* Mobile Filter Button */}
              <button
                onClick={() => setIsFilterDrawerOpen(true)}
                className="lg:hidden flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 text-xs md:text-sm border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200"
                style={{ transform: 'skewX(-12deg)' }}
              >
                <span
                  style={{
                    transform: 'skewX(12deg)',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '8px',
                  }}
                >
                  <SlidersHorizontal className="w-4 h-4" />
                  Фильтры
                  {activeFiltersCount > 0 && (
                    <span className="bg-[var(--color-primary)] text-black text-xs font-bold w-5 h-5 flex items-center justify-center">
                      {activeFiltersCount}
                    </span>
                  )}
                </span>
              </button>

              <SortSelect
                value={ordering}
                onChange={val => {
                  setOrdering(val);
                  setPage(1);
                }}
                options={SORT_OPTIONS}
              />
            </div>
          </div>
        </div>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Sidebar - Hidden on mobile */}
          <aside className="hidden lg:block w-[280px] flex-shrink-0 space-y-6">
            {/* Category Tree */}
            <div className="bg-[var(--bg-card)] p-6 border border-[var(--border-default)]">
              <h3
                className="text-xl mb-5 pb-3 border-b border-[var(--border-default)] uppercase tracking-wide"
                style={{
                  fontFamily: "'Roboto Condensed', sans-serif",
                  fontWeight: 900,
                  transform: 'skewX(-12deg)',
                  transformOrigin: 'left',
                }}
              >
                <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>
                  КАТЕГОРИИ
                </span>
              </h3>
              <ElectricCategoryTree
                nodes={categoriesTree}
                activeCategoryId={activeCategoryId}
                onSelectCategory={node => {
                  setActiveCategoryId(node.id);
                  setPage(1);
                }}
              />
            </div>

            {/* Filters (Brands + Price) */}
            <ElectricSidebar
              filterGroups={[
                {
                  id: 'brands',
                  title: 'БРЕНДЫ',
                  type: 'checkbox',
                  options: brandFilterOptions,
                },
                {
                  id: 'price',
                  title: 'ЦЕНА (₽)',
                  type: 'price',
                  options: [],
                },
              ]}
              priceRange={{ min: PRICE_MIN, max: PRICE_MAX }}
              currentPrice={priceRange}
              selectedFilters={{
                brands: Array.from(selectedBrandIds).map(String),
              }}
              onFilterChange={handleFilterChange}
              onPriceChange={handlePriceChange}
              className="w-full"
            />

            {/* Reset Filters Button */}
            {hasActiveFilters && (
              <ElectricButton
                variant="outline"
                size="sm"
                onClick={handleResetFilters}
                className="w-full"
              >
                Сбросить фильтры
              </ElectricButton>
            )}
          </aside>

          {/* Product Grid */}
          <main className="flex-1 min-w-0">
            {isProductsLoading ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
                {Array.from({ length: 8 }).map((_, i) => (
                  <div
                    key={i}
                    className="aspect-square bg-[var(--bg-card)] flex items-center justify-center transform -skew-x-12 border border-[var(--border-default)]"
                  >
                    <ElectricSpinner size="md" />
                  </div>
                ))}
              </div>
            ) : productsError ? (
              <div className="p-8 text-center border border-[var(--color-danger)] bg-[var(--color-danger-bg)] text-[var(--color-danger)]">
                {productsError}
              </div>
            ) : products.length === 0 ? (
              <div className="p-12 text-center text-[var(--color-text-secondary)]">
                Товары не найдены
              </div>
            ) : (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
                {products.map(product => {
                  // Badge logic
                  let badge: 'primary' | 'sale' | 'hit' | 'new' | undefined;
                  if (product.is_sale) badge = 'sale';
                  else if (product.is_hit) badge = 'hit';
                  else if (product.is_new) badge = 'new';

                  // Image logic
                  const imageUrl =
                    product.main_image ||
                    product.image ||
                    product.images?.[0]?.image ||
                    '/placeholder.png';

                  return (
                    <ElectricProductCard
                      key={product.id}
                      image={imageUrl}
                      title={product.name}
                      brand={product.brand?.name}
                      price={product.retail_price}
                      // Calculate old price if discount exists, or just pass undefined if not available in API
                      oldPrice={
                        product.is_sale && product.discount_percent
                          ? Math.round(product.retail_price / (1 - product.discount_percent / 100))
                          : undefined
                      }
                      badge={badge}
                      inStock={product.is_in_stock}
                      onAddToCart={() => handleAddToCart(product.id)}
                      isFavorite={false}
                      onToggleFavorite={() => {}}
                    />
                  );
                })}
              </div>
            )}

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-16">
                <ElectricPagination
                  currentPage={page}
                  totalPages={totalPages}
                  onPageChange={setPage}
                />
              </div>
            )}
          </main>
        </div>
      </div>

      {/* Mobile Filter Drawer */}
      <ElectricDrawer
        isOpen={isFilterDrawerOpen}
        onClose={() => setIsFilterDrawerOpen(false)}
        title="ФИЛЬТРЫ"
        width="md"
        footer={
          hasActiveFilters ? (
            <ElectricButton
              variant="outline"
              size="sm"
              onClick={() => {
                handleResetFilters();
                setIsFilterDrawerOpen(false);
              }}
              className="w-full"
            >
              Сбросить фильтры
            </ElectricButton>
          ) : undefined
        }
      >
        <div className="space-y-6">
          {/* Category Tree in Drawer */}
          <div>
            <h3
              className="text-base md:text-lg mb-4 pb-2 border-b border-[var(--border-default)] uppercase tracking-wide"
              style={{
                fontFamily: "'Roboto Condensed', sans-serif",
                fontWeight: 900,
                transform: 'skewX(-12deg)',
                transformOrigin: 'left',
              }}
            >
              <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>КАТЕГОРИИ</span>
            </h3>
            <ElectricCategoryTree
              nodes={categoriesTree}
              activeCategoryId={activeCategoryId}
              onSelectCategory={node => {
                setActiveCategoryId(node.id);
                setPage(1);
              }}
            />
          </div>

          {/* Filters in Drawer */}
          <ElectricSidebar
            filterGroups={[
              {
                id: 'brands',
                title: 'БРЕНДЫ',
                type: 'checkbox',
                options: brandFilterOptions,
              },
              {
                id: 'price',
                title: 'ЦЕНА (₽)',
                type: 'price',
                options: [],
              },
            ]}
            priceRange={{ min: PRICE_MIN, max: PRICE_MAX }}
            currentPrice={priceRange}
            selectedFilters={{
              brands: Array.from(selectedBrandIds).map(String),
            }}
            onFilterChange={handleFilterChange}
            onPriceChange={handlePriceChange}
            className="w-full"
          />
        </div>
      </ElectricDrawer>
    </div>
  );
};

export default function Page() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[var(--bg-body)] flex items-center justify-center text-[var(--color-primary)]">
          Loading...
        </div>
      }
    >
      <ElectricCatalogPage />
    </Suspense>
  );
}
