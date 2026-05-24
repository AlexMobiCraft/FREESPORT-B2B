/**
 * Search Page
 *
 * Страница результатов поиска с SSR для SEO.
 * Отображает результаты поиска товаров по query параметру 'q'.
 *
 * Features:
 * - SSR для оптимизации SEO
 * - Динамические метатеги (title, description)
 * - Пагинация результатов (24 товара на страницу)
 * - Поддержка состояния "Ничего не найдено"
 *
 * @see docs/stories/epic-18/18.2.search-results-page.md
 *
 * @example
 * URL: /search?q=nike&page=1
 */

import type { Metadata } from 'next';
import { SearchPageClient } from '@/components/business/SearchPageClient';

interface SearchPageProps {
  searchParams: Promise<{ q?: string; page?: string }>;
}

/**
 * Генерирует динамические метатеги для SEO
 */
export async function generateMetadata({ searchParams }: SearchPageProps): Promise<Metadata> {
  const params = await searchParams;
  const query = params.q || '';

  return {
    title: query ? `Поиск: ${query}` : 'Поиск товаров',
    description: query
      ? `Результаты поиска по запросу "${query}" в магазине FREESPORT. Найдите спортивные товары по лучшим ценам.`
      : 'Поиск спортивных товаров в магазине FREESPORT',
    robots: {
      index: true,
      follow: true,
    },
    openGraph: {
      title: query ? `Поиск: ${query}` : 'Поиск товаров',
      description: query
        ? `Результаты поиска по запросу "${query}" в магазине FREESPORT`
        : 'Поиск спортивных товаров в магазине FREESPORT',
      type: 'website',
    },
  };
}

/**
 * Серверный компонент страницы поиска
 */
export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const initialQuery = params.q || '';
  const initialPage = parseInt(params.page || '1', 10);

  return (
    <main className="min-h-screen bg-canvas" aria-label="Результаты поиска">
      <SearchPageClient initialQuery={initialQuery} initialPage={initialPage} />
    </main>
  );
}
