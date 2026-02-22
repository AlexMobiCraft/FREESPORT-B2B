/**
 * HitsSection Component
 *
 * Блок "Хиты продаж" на главной странице (Story 12.7).
 * Отображает товары с флагом is_hit=true в горизонтальной ленте.
 *
 * Поддерживает два варианта дизайна:
 * - default: Стандартный светлый дизайн
 * - electric: Electric Orange Design System
 *
 * @example
 * ```tsx
 * <HitsSection />                    // default design
 * <HitsSection variant="electric" /> // Electric Orange design
 * ```
 */

'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import Link from 'next/link';
import { ProductCard } from '@/components/business/ProductCard/ProductCard';
import ElectricProductCard from '@/components/ui/ProductCard/ElectricProductCard';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';
import { useCartStore } from '@/stores/cartStore';
import { useAuthStore } from '@/stores/authStore';
import { useToast } from '@/components/ui/Toast';
import productsService from '@/services/productsService';
import type { Product } from '@/types/api';
import { ChevronLeft, ChevronRight } from 'lucide-react';

export interface HitsSectionProps {
  /** Design variant: 'default' | 'electric' */
  variant?: 'default' | 'electric';
  /** Custom title (defaults to "Хиты продаж") */
  title?: string;
  /** Link for "View all" button */
  viewAllLink?: string;
}

// Style configurations for variants
const VARIANT_STYLES = {
  default: {
    section: 'max-w-[1316px] mx-auto px-3 md:px-4 lg:px-6 py-12 relative',
    heading: 'text-3xl font-bold mb-8 text-text-primary',
    headingStyle: {},
    navButton:
      'absolute top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-12 h-12 bg-transparent text-primary focus:outline-none',
    navButtonStyle: {},
    skeleton:
      'flex-shrink-0 w-[calc(50%-4px)] md:w-[200px] snap-start rounded-2xl bg-white p-3 shadow-default animate-pulse',
    skeletonInner: 'h-40 rounded-xl bg-neutral-200 mb-4',
    errorButton: 'px-6 py-2 rounded-lg bg-[#0b1220] text-white hover:bg-[#070d19] transition',
    productList: 'flex gap-2 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-4',
    productItem: 'flex-shrink-0 w-[calc(50%-4px)] md:w-[200px] snap-start',
    cardWidth: 200,
    gap: 8,
  },
  electric: {
    section: 'max-w-[1400px] mx-auto px-4 sm:px-6 lg:px-8 py-12 relative',
    heading:
      'text-2xl md:text-3xl font-black uppercase tracking-tight text-[var(--color-text-primary)]',
    headingStyle: {
      fontFamily: "'Roboto Condensed', sans-serif",
      transform: 'skewX(-12deg)',
      transformOrigin: 'left',
    },
    navButton:
      'absolute top-1/2 z-10 hidden lg:flex items-center justify-center w-10 h-10 border border-[var(--border-default)] text-[var(--color-text-secondary)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)] transition-all duration-200 bg-[var(--bg-body)]',
    navButtonStyle: { transform: 'translateY(-50%) skewX(-12deg)' },
    skeleton:
      'flex-shrink-0 w-[220px] aspect-[3/4] bg-[var(--bg-card)] animate-pulse border border-[var(--border-default)]',
    skeletonInner: '',
    errorButton: '',
    productList: 'flex gap-5 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-6',
    productItem: 'flex-shrink-0 w-[220px] snap-start',
    cardWidth: 220,
    gap: 20,
  },
};

/**
 * Компонент блока "Хиты продаж"
 */
export const HitsSection: React.FC<HitsSectionProps> = ({
  variant = 'default',
  title = 'Хиты продаж',
  viewAllLink = '/catalog?is_hit=true',
}) => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  // Electric variant needs cart functionality
  const { addItem } = useCartStore();
  const { success, error: toastError } = useToast();

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

  const styles = VARIANT_STYLES[variant];
  const isElectric = variant === 'electric';

  const fetchHits = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await productsService.getHits();
      setProducts(data);
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить хиты продаж');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchHits();
  }, [fetchHits]);

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

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    const scrollAmount = (styles.cardWidth + styles.gap) * 2;
    const targetScroll =
      container.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);

    container.scrollTo({
      left: targetScroll,
      behavior: 'smooth',
    });
  };

  // Electric variant: Add to cart handler
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

  if (!isLoading && !error && products.length === 0) {
    return null;
  }

  return (
    <section className={styles.section} aria-labelledby="hits-heading">
      {/* Header */}
      <div className={isElectric ? 'flex items-center justify-between mb-8' : ''}>
        <h2 id="hits-heading" className={styles.heading} style={styles.headingStyle}>
          {isElectric ? (
            <span style={{ display: 'inline-block', transform: 'skewX(12deg)' }}>
              {title.toUpperCase()}
            </span>
          ) : (
            title
          )}
        </h2>

        {isElectric && (
          <Link href={viewAllLink}>
            <ElectricButton variant="outline" size="sm">
              Все хиты
            </ElectricButton>
          </Link>
        )}
      </div>

      {/* Navigation Buttons */}
      {canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          className={`${styles.navButton} ${isElectric ? '-left-2' : 'left-0'}`}
          style={styles.navButtonStyle}
          aria-label="Предыдущие товары"
        >
          <ChevronLeft
            className={isElectric ? 'w-5 h-5' : 'w-7 h-7'}
            style={isElectric ? { transform: 'skewX(12deg)' } : {}}
          />
        </button>
      )}

      {canScrollRight && (
        <button
          onClick={() => scroll('right')}
          className={`${styles.navButton} ${isElectric ? '-right-2' : 'right-0'}`}
          style={styles.navButtonStyle}
          aria-label="Следующие товары"
        >
          <ChevronRight
            className={isElectric ? 'w-5 h-5' : 'w-7 h-7'}
            style={isElectric ? { transform: 'skewX(12deg)' } : {}}
          />
        </button>
      )}

      {/* Loading State */}
      {isLoading && (
        <div
          role="status"
          aria-label="Загрузка хитов продаж"
          className="flex gap-4 overflow-hidden py-2 px-2"
        >
          {Array.from({ length: isElectric ? 5 : 4 }).map((_, index) => (
            <div
              key={index}
              className={styles.skeleton}
              style={isElectric ? { transform: 'skewX(-12deg)' } : {}}
            >
              {!isElectric && (
                <>
                  <div className={styles.skeletonInner} />
                  <div className="h-4 bg-neutral-200 rounded mb-2" />
                  <div className="h-4 bg-neutral-200 rounded w-2/3" />
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Error State */}
      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-4 py-12">
          <p
            className={
              isElectric
                ? 'text-[var(--color-text-secondary)]'
                : 'text-body-m text-text-secondary text-center'
            }
          >
            {error}
          </p>
          {isElectric ? (
            <ElectricButton variant="outline" size="sm" onClick={fetchHits}>
              Повторить
            </ElectricButton>
          ) : (
            <button type="button" onClick={fetchHits} className={styles.errorButton}>
              Повторить попытку
            </button>
          )}
        </div>
      )}

      {/* Product List */}
      {!isLoading && !error && products.length > 0 && (
        <div ref={scrollContainerRef} className={styles.productList} role="list">
          {products.map(product => {
            const imageUrl =
              product.main_image ||
              product.image ||
              product.images?.[0]?.image ||
              '/placeholder.png';

            return (
              <div key={product.id} className={styles.productItem} role="listitem">
                {isElectric ? (
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
                    rrp={isB2B ? product.rrp : undefined}
                    badge="hit"
                    inStock={product.is_in_stock}
                    onAddToCart={() => handleAddToCart(product.id)}
                    isFavorite={false}
                    onToggleFavorite={() => {}}
                  />
                ) : (
                  <ProductCard
                    product={product}
                    layout="compact"
                    userRole={userRole}
                    mode={isB2B ? 'b2b' : 'b2c'}
                  />
                )}
              </div>
            );
          })}
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

HitsSection.displayName = 'HitsSection';
