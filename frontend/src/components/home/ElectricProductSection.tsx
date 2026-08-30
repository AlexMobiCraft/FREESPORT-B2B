/**
 * ElectricProductSection Component
 *
 * Универсальный компонент секции товаров для главной страницы.
 * Используется для: Хиты продаж, Новинки, Акции, Распродажа.
 *
 * Design System: Electric Orange v2.3.0
 * - Skewed headers (-12deg)
 * - Horizontal scroll with ElectricProductCard
 * - Navigation arrows in Electric style
 */

'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import ElectricProductCard from '@/components/ui/ProductCard/ElectricProductCard';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import { useCartStore } from '@/stores/cartStore';
import { useToast } from '@/components/ui/Toast';
import productsService from '@/services/productsService';
import type { Product } from '@/types/api';
import { ChevronLeft, ChevronRight } from 'lucide-react';

type FetchType = 'hits' | 'new' | 'sale' | 'promo';

interface ElectricProductSectionProps {
  /** Section title (uppercase recommended) */
  title: string;
  /** Type of products to fetch */
  fetchType: FetchType;
  /** Badge type for cards */
  badge?: 'primary' | 'sale' | 'hit' | 'new';
  /** Link to "View all" page */
  viewAllLink?: string;
  /** View all button text */
  viewAllText?: string;
}

/**
 * Loading skeleton for products
 */
const ProductsSkeleton = () => (
  <div className="flex gap-5 overflow-hidden py-2">
    {Array.from({ length: 5 }).map((_, i) => (
      <div
        key={i}
        className="flex-shrink-0 w-[220px] aspect-[3/4] bg-[var(--bg-card)] animate-pulse border border-[var(--border-default)]"
        style={{ transform: 'skewX(-12deg)' }}
      />
    ))}
  </div>
);

// Mapping from fetchType to service method
const getFetchFunction = (type: FetchType): (() => Promise<Product[]>) => {
  switch (type) {
    case 'hits':
      return productsService.getHits;
    case 'new':
      return productsService.getNew;
    case 'sale':
      return productsService.getSale;
    case 'promo':
      return productsService.getPromo;
    default:
      return productsService.getHits;
  }
};

export const ElectricProductSection: React.FC<ElectricProductSectionProps> = ({
  title,
  fetchType,
  badge,
  viewAllLink = '/electric/catalog',
  viewAllText = 'Смотреть все',
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const { addItem } = useCartStore();
  const { success, error: toastError } = useToast();

  // Fetch products based on type
  const loadProducts = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const fetchFn = getFetchFunction(fetchType);
      const data = await fetchFn();
      setProducts(data);
    } catch (err) {
      console.error('Failed to load products:', err);
      setError('Не удалось загрузить товары');
    } finally {
      setIsLoading(false);
    }
  }, [fetchType]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  // Scroll state management
  const updateScrollButtons = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCanScrollLeft(scrollLeft > 4);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 4);
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    updateScrollButtons();

    const handleResize = () => updateScrollButtons();
    container.addEventListener('scroll', updateScrollButtons);
    window.addEventListener('resize', handleResize);

    return () => {
      container.removeEventListener('scroll', updateScrollButtons);
      window.removeEventListener('resize', handleResize);
    };
  }, [products.length, isLoading, updateScrollButtons]);

  // Scroll navigation
  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    const cardWidth = 220;
    const gap = 20;
    const scrollAmount = (cardWidth + gap) * 2;
    const targetScroll =
      container.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);

    container.scrollTo({
      left: targetScroll,
      behavior: 'smooth',
    });
  };

  // Add to cart handler
  const handleAddToCart = useCallback(
    async (productId: number) => {
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

  // Don't render if no products after loading
  if (!isLoading && !error && products.length === 0) {
    return null;
  }

  return (
    <section
      className="max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12 relative"
      aria-labelledby={`${title.toLowerCase().replace(/\s/g, '-')}-heading`}
    >
      {/* Header row */}
      <div className="flex items-center justify-between mb-8">
        {/* Skewed title */}
        <h2
          id={`${title.toLowerCase().replace(/\s/g, '-')}-heading`}
          className="text-2xl md:text-3xl font-black uppercase tracking-tight text-[var(--color-text-primary)]"
          style={{
            fontFamily: "'Roboto Condensed', sans-serif",
            transform: 'skewX(-12deg)',
            transformOrigin: 'left',
          }}
        >
          <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>{title}</span>
        </h2>

        {/* View all link */}
        <Link href={viewAllLink}>
          <ElectricButton variant="outline" size="sm">
            {viewAllText}
          </ElectricButton>
        </Link>
      </div>

      {/* Loading state */}
      {isLoading && <ProductsSkeleton />}

      {/* Error state */}
      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <p className="text-[var(--color-text-secondary)]">{error}</p>
          <ElectricButton variant="outline" size="sm" onClick={loadProducts}>
            Повторить
          </ElectricButton>
        </div>
      )}

      {/* Products list */}
      {!isLoading && !error && products.length > 0 && (
        <div className="relative">
          {/* Navigation arrows */}
          {canScrollLeft && (
            <button
              onClick={() => scroll('left')}
              className="absolute -left-2 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-10 h-10 border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200 bg-[var(--bg-body)]"
              style={{ transform: 'translateY(-50%) skewX(-12deg)' }}
              aria-label="Previous products"
            >
              <ChevronLeft className="w-5 h-5" style={{ transform: 'skewX(12deg)' }} />
            </button>
          )}

          {canScrollRight && (
            <button
              onClick={() => scroll('right')}
              className="absolute -right-2 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-10 h-10 border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200 bg-[var(--bg-body)]"
              style={{ transform: 'translateY(-50%) skewX(-12deg)' }}
              aria-label="Next products"
            >
              <ChevronRight className="w-5 h-5" style={{ transform: 'skewX(12deg)' }} />
            </button>
          )}

          {/* Scrollable container */}
          <div
            ref={scrollContainerRef}
            className="flex gap-5 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-6"
            role="list"
          >
            {products.map(product => {
              const imageUrl =
                product.main_image ||
                product.image ||
                product.images?.[0]?.image ||
                '/placeholder.png';

              return (
                <div
                  key={product.id}
                  className="flex-shrink-0 w-[220px] snap-start"
                  role="listitem"
                >
                  <ElectricProductCard
                    image={imageUrl}
                    title={product.name}
                    brand={product.brand?.name}
                    price={product.retail_price}
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
                </div>
              );
            })}
          </div>
        </div>
      )}

      <style jsx>{`
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </section>
  );
};

ElectricProductSection.displayName = 'ElectricProductSection';

export default ElectricProductSection;
