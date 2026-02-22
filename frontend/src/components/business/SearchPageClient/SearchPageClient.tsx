/**
 * SearchPageClient Component
 *
 * Клиентский компонент для страницы результатов поиска.
 * Управляет состоянием поиска, загрузкой данных и пагинацией.
 *
 * Features:
 * - Интеграция с productsService.getAll() для пагинированного поиска
 * - Отображение заголовка с запросом и количеством результатов
 * - Loading skeleton во время загрузки
 * - Поддержка пагинации (24 товара на страницу)
 * - Обновление URL при смене страницы
 * - Состояние "Ничего не найдено" с рекомендациями
 * - WCAG 2.1 AA accessibility
 *
 * @see docs/stories/epic-18/18.2.search-results-page.md
 *
 * @example
 * ```tsx
 * <SearchPageClient
 *   initialQuery="nike"
 *   initialPage={1}
 * />
 * ```
 */

'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { SearchResults } from '@/components/business/SearchResults';
import { EmptySearchResults } from '@/components/business/EmptySearchResults';
import { Pagination } from '@/components/ui/Pagination';
import productsService from '@/services/productsService';
import type { Product } from '@/types/api';

export interface SearchPageClientProps {
  /** Начальный поисковый запрос */
  initialQuery: string;
  /** Начальная страница (по умолчанию 1) */
  initialPage?: number;
}

const PAGE_SIZE = 24;

/**
 * Компонент SearchPageClient
 */
export const SearchPageClient: React.FC<SearchPageClientProps> = ({
  initialQuery,
  initialPage = 1,
}) => {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [query, setQuery] = useState(initialQuery);
  const [currentPage, setCurrentPage] = useState(initialPage);
  const [products, setProducts] = useState<Product[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [recommendedProducts, setRecommendedProducts] = useState<Product[]>([]);

  // Вычисляем общее количество страниц
  const totalPages = Math.ceil(totalCount / PAGE_SIZE);

  /**
   * Загружает результаты поиска с сервера
   */
  const fetchSearchResults = async (searchQuery: string, page: number) => {
    if (!searchQuery.trim()) {
      setProducts([]);
      setTotalCount(0);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);

    try {
      // Используем productsService.getAll() с параметром search для пагинированного поиска
      const response = await productsService.getAll({
        search: searchQuery,
        page,
        page_size: PAGE_SIZE,
      });

      setProducts(response.results);
      setTotalCount(response.count);

      // Если нет результатов, загружаем популярные товары для рекомендаций
      if (response.count === 0) {
        const popularProducts = await productsService.getHits({ page_size: 4 });
        setRecommendedProducts(popularProducts);
      }
    } catch (error) {
      console.error('Error fetching search results:', error);
      setProducts([]);
      setTotalCount(0);
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Обработчик смены страницы
   */
  const handlePageChange = (page: number) => {
    setCurrentPage(page);

    // Обновляем URL с новым номером страницы
    const params = new URLSearchParams(searchParams.toString());
    params.set('page', page.toString());

    router.push(`/search?${params.toString()}`, { scroll: true });

    // Прокручиваем страницу вверх
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  /**
   * Эффект для загрузки результатов при изменении query или page
   */
  useEffect(() => {
    const currentQuery = searchParams.get('q') || '';
    const currentPageParam = parseInt(searchParams.get('page') || '1', 10);

    setQuery(currentQuery);
    setCurrentPage(currentPageParam);

    fetchSearchResults(currentQuery, currentPageParam);
  }, [searchParams]);

  return (
    <div className="w-full max-w-[1280px] mx-auto px-6 py-12">
      {/* Заголовок и счётчик результатов */}
      {query && (
        <header className="mb-8">
          <h1 className="text-title-l font-semibold text-primary mb-4">
            Результаты поиска: «{query}»
          </h1>

          {!isLoading && (
            <p className="text-body-m text-secondary" aria-live="polite">
              {totalCount > 0
                ? `Найдено ${totalCount} ${totalCount === 1 ? 'товар' : totalCount < 5 ? 'товара' : 'товаров'}`
                : 'Ничего не найдено'}
            </p>
          )}
        </header>
      )}

      {/* Результаты поиска или пустое состояние */}
      {!query ? (
        <div className="text-center py-16">
          <p className="text-body-l text-secondary">Введите запрос для поиска товаров</p>
        </div>
      ) : totalCount === 0 && !isLoading ? (
        <EmptySearchResults query={query} recommendedProducts={recommendedProducts} />
      ) : (
        <>
          {/* Результаты */}
          <SearchResults products={products} isLoading={isLoading} />

          {/* Пагинация */}
          {!isLoading && totalPages > 1 && (
            <div className="mt-12" aria-label={`Страница ${currentPage} из ${totalPages}`}>
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                onPageChange={handlePageChange}
                maxVisiblePages={5}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
};

SearchPageClient.displayName = 'SearchPageClient';
