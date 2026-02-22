/**
 * SearchAutocomplete Component
 * Бизнес-компонент для поиска товаров с автодополнением
 *
 * Интегрирует SearchField с productsService для live-поиска
 * и навигации к товарам или странице результатов поиска.
 *
 * @see Story 18.1 - Интеграция поиска в Header
 * @see Story 18.3 - История и автодополнение поиска
 */

'use client';

import React, { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { SearchField } from '@/components/ui/SearchField/SearchField';
import { SearchHistory } from '@/components/business/SearchHistory';
import { useSearchHistory } from '@/hooks/useSearchHistory';
import productsService from '@/services/productsService';
import type { Product } from '@/types/api';
import { cn } from '@/utils/cn';

/**
 * Props для компонента SearchAutocomplete
 */
export interface SearchAutocompleteProps {
  /** Дополнительные CSS классы */
  className?: string;
  /** Мобильный режим отображения */
  isMobile?: boolean;
  /** Callback для закрытия мобильного меню после навигации */
  onNavigate?: () => void;
  /** Placeholder для поля ввода */
  placeholder?: string;
  /** Callback при поиске (вызывается после debounce) */
  onSearch?: (query: string) => void;
  /** Минимальная длина запроса */
  minLength?: number;
  /** Задержка bounce */
  debounceMs?: number;
}

/**
 * Формат товара для SearchField dropdown
 */
interface SearchFieldProduct {
  id: number;
  name: string;
  price: number;
  slug: string;
}

/**
 * SearchAutocomplete - компонент поиска с автодополнением
 *
 * Функциональность:
 * - Live-поиск товаров через productsService.search()
 * - Autocomplete dropdown с лимитом 5 товаров
 * - Клик по товару → переход на страницу товара
 * - Enter или клик по иконке → переход на /search?q=...
 * - Поддержка desktop и mobile режимов
 */
export const SearchAutocomplete: React.ForwardRefExoticComponent<
  SearchAutocompleteProps & React.RefAttributes<HTMLInputElement>
> = React.forwardRef<HTMLInputElement, SearchAutocompleteProps>(
  (
    {
      className,
      isMobile = false,
      onNavigate,
      placeholder = 'Поиск товаров...',
      onSearch,
      minLength = 2,
      debounceMs = 300,
    },
    ref
  ) => {
    const router = useRouter();
    const { history, addSearch, removeSearch, clearHistory } = useSearchHistory();
    const [products, setProducts] = useState<SearchFieldProduct[]>([]);
    const [query, setQuery] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [isFocused, setIsFocused] = useState(false);

    /**
     * Обработчик изменения input - обновляет query сразу
     */
    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      setQuery(e.target.value);
    }, []);

    /**
     * Обработчик поиска - вызывается из SearchField после debounce
     * Ограничивает результаты до 5 товаров для performance
     */
    const handleSearch = useCallback(
      async (searchQuery: string) => {
        // Вызываем внешний обработчик
        if (onSearch) {
          onSearch(searchQuery);
        }

        if (!searchQuery || searchQuery.length < minLength) {
          setProducts([]);
          return;
        }

        setIsLoading(true);
        try {
          const response = await productsService.search(searchQuery);
          // Ограничиваем до 5 товаров для оптимизации (per Story requirements)
          const limitedProducts = response.results.slice(0, 5).map((product: Product) => ({
            id: product.id,
            name: product.name,
            price: product.retail_price,
            slug: product.slug,
          }));
          setProducts(limitedProducts);
        } catch (error) {
          console.error('Search error:', error);
          setProducts([]);
        } finally {
          setIsLoading(false);
        }
      },
      [onSearch, minLength]
    );

    /**
     * Обработчик клика по товару - навигация на страницу товара
     * Добавляет запрос в историю при клике на товар
     */
    const handleProductClick = useCallback(
      (productId: number) => {
        const product = products.find(p => p.id === productId);
        if (product && query.trim().length >= 2) {
          addSearch(query.trim()); // Добавить запрос в историю
          router.push(`/product/${product.slug}`);
          onNavigate?.(); // Закрыть мобильное меню если открыто
          setProducts([]);
          setQuery('');
          setIsFocused(false);
        }
      },
      [products, query, router, onNavigate, addSearch]
    );

    /**
     * Обработчик нажатия клавиши Enter или submit формы
     * Навигация на страницу результатов поиска
     * Добавляет запрос в историю при успешном поиске
     */
    const handleKeyDown = useCallback(
      (e: React.KeyboardEvent<HTMLInputElement>) => {
        if (e.key === 'Enter' && query.trim().length >= 2) {
          e.preventDefault();
          const trimmedQuery = query.trim();
          addSearch(trimmedQuery); // Добавить в историю
          router.push(`/search?q=${encodeURIComponent(trimmedQuery)}`);
          onNavigate?.(); // Закрыть мобильное меню если открыто
          setProducts([]);
          setIsFocused(false);
        } else if (e.key === 'Escape') {
          setIsFocused(false);
        }
      },
      [query, router, onNavigate, addSearch]
    );

    /**
     * Обработчик выбора элемента из истории
     */
    const handleHistorySelect = useCallback(
      (selectedQuery: string) => {
        setQuery(selectedQuery);
        addSearch(selectedQuery);
        router.push(`/search?q=${encodeURIComponent(selectedQuery)}`);
        onNavigate?.();
        setProducts([]);
        setIsFocused(false);
      },
      [router, onNavigate, addSearch]
    );

    /**
     * Обработчик фокуса на поле поиска
     */
    const handleFocus = useCallback(() => {
      setIsFocused(true);
    }, []);

    /**
     * Обработчик потери фокуса
     */
    const handleBlur = useCallback(() => {
      // Задержка для обработки кликов по истории
      setTimeout(() => setIsFocused(false), 200);
    }, []);

    return (
      // eslint-disable-next-line jsx-a11y/no-static-element-interactions
      <div
        className={cn(
          'relative',
          // Desktop: ограниченная ширина для гармоничного UI
          !isMobile && 'w-full max-w-[300px]',
          // Mobile: полная ширина
          isMobile && 'w-full',
          className
        )}
        data-testid="search-autocomplete"
        onKeyDown={e => {
          if (e.key === 'Escape') {
            setIsFocused(false);
          }
        }}
      >
        <SearchField
          ref={ref}
          placeholder={placeholder}
          onSearch={handleSearch}
          onChange={handleChange}
          isLoading={isLoading}
          products={products.map(p => ({
            id: p.id,
            name: p.name,
            price: p.price,
          }))}
          onProductClick={handleProductClick}
          minLength={minLength}
          debounceMs={debounceMs}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          aria-label="Поиск товаров"
          data-testid="search-field"
        />

        {/* История поиска - показывается при фокусе на пустом поле */}
        {isFocused && query.trim().length === 0 && history.length > 0 && (
          <SearchHistory
            history={history}
            onSelect={handleHistorySelect}
            onRemove={removeSearch}
            onClear={clearHistory}
          />
        )}

        {/* 
        Обработчик клика по товарам из SearchField dropdown
        SearchField использует onClick на кнопках товаров, нужно перехватить 
      */}
        {products.length > 0 && (
          <div className="sr-only" aria-live="polite" aria-atomic="true">
            Найдено {products.length} товаров
          </div>
        )}

        {isLoading && (
          <div className="sr-only" aria-live="polite">
            Загрузка результатов поиска...
          </div>
        )}
      </div>
    );
  }
);

SearchAutocomplete.displayName = 'SearchAutocomplete';

export default SearchAutocomplete;
