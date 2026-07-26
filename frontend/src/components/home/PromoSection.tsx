/**
 * PromoSection Component
 *
 * Блок "Акция" на главной странице.
 * Отображает товары с флагом is_promo=true в горизонтальной ленте.
 *
 * Features:
 * - Горизонтальная лента с scroll-snap
 * - Использует ProductCard из Story 12.4
 * - Кнопки навигации prev/next
 *
 * @example
 * ```tsx
 * <PromoSection />
 * ```
 */

'use client';

import React, { useEffect, useRef, useState } from 'react';
import { ProductCard } from '@/components/business/ProductCard/ProductCard';
import productsService from '@/services/productsService';
import { useAuthStore } from '@/stores/authStore';
import type { Product } from '@/types/api';
import { ChevronLeft, ChevronRight } from 'lucide-react';

/**
 * Компонент блока "Акция"
 */
export const PromoSection: React.FC = () => {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [products, setProducts] = useState<Product[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

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

  const fetchPromo = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const data = await productsService.getPromo();
      setProducts(data);
    } catch (err) {
      console.error(err);
      setError('Не удалось загрузить акционные товары');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    void fetchPromo();
  }, []);

  const updateScrollButtons = () => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const { scrollLeft, scrollWidth, clientWidth } = container;
    setCanScrollLeft(scrollLeft > 4);
    setCanScrollRight(scrollLeft + clientWidth < scrollWidth - 4);
  };

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
  }, [products.length, isLoading]);

  const scroll = (direction: 'left' | 'right') => {
    if (!scrollContainerRef.current) return;

    const container = scrollContainerRef.current;
    // Ширина карточки (200px) + gap (8px = gap-2)
    const cardWidth = 200;
    const gap = 8;
    const scrollAmount = cardWidth + gap;
    const targetScroll =
      container.scrollLeft + (direction === 'right' ? scrollAmount : -scrollAmount);

    container.scrollTo({
      left: targetScroll,
      behavior: 'smooth',
    });
  };

  if (!isLoading && !error && products.length === 0) {
    return null;
  }

  return (
    <section
      className="max-w-[1316px] mx-auto px-3 md:px-4 lg:px-6 py-12 relative"
      aria-labelledby="promo-heading"
    >
      {/* Заголовок секции */}
      <h2 id="promo-heading" className="text-3xl font-bold mb-8 text-text-primary">
        Акция
      </h2>

      {/* Кнопки навигации */}
      {canScrollLeft && (
        <button
          onClick={() => scroll('left')}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-12 h-12 bg-transparent text-primary focus:outline-none"
          aria-label="Предыдущие товары"
        >
          <ChevronLeft className="w-7 h-7" />
        </button>
      )}

      {canScrollRight && (
        <button
          onClick={() => scroll('right')}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 hidden lg:flex items-center justify-center w-12 h-12 bg-transparent text-primary focus:outline-none"
          aria-label="Следующие товары"
        >
          <ChevronRight className="w-7 h-7" />
        </button>
      )}

      {/* Состояние загрузки */}
      {isLoading && (
        <div
          role="status"
          aria-label="Загрузка акционных товаров"
          className="flex gap-2 overflow-hidden py-2 px-2"
        >
          {Array.from({ length: 4 }).map((_, index) => (
            <div
              key={index}
              className="flex-shrink-0 w-[calc(50%-4px)] md:w-[200px] snap-start rounded-2xl bg-white p-3 shadow-default animate-pulse"
            >
              <div className="h-40 rounded-xl bg-neutral-200 mb-4" />
              <div className="h-4 bg-neutral-200 rounded mb-2" />
              <div className="h-4 bg-neutral-200 rounded w-2/3" />
            </div>
          ))}
        </div>
      )}

      {/* Ошибка загрузки */}
      {error && !isLoading && (
        <div className="flex flex-col items-center justify-center gap-3 py-8">
          <p className="text-body-m text-text-secondary text-center">{error}</p>
          <button
            type="button"
            onClick={fetchPromo}
            className="px-6 py-2 rounded-lg bg-[#0b1220] text-white hover:bg-[#070d19] transition"
          >
            Повторить попытку
          </button>
        </div>
      )}

      {/* Горизонтальная лента товаров */}
      {!isLoading && !error && products.length > 0 && (
        <div
          ref={scrollContainerRef}
          className="flex gap-2 overflow-x-auto snap-x snap-mandatory scrollbar-hide py-2 lg:mx-4"
          role="list"
        >
          {products.map(product => (
            <div
              key={product.id}
              className="flex-shrink-0 w-[calc(50%-4px)] md:w-[200px] snap-start"
              role="listitem"
            >
              <ProductCard
                product={product}
                layout="compact"
                userRole={userRole}
                mode={isB2B ? 'b2b' : 'b2c'}
              />
            </div>
          ))}
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

PromoSection.displayName = 'PromoSection';
