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
import { buildMetadata } from '@/utils/seo';

interface SearchPageProps {
  searchParams: Promise<{ q?: string; page?: string }>;
}

/**
 * Генерирует динамические метатеги для SEO
 */
export async function generateMetadata({ searchParams }: SearchPageProps): Promise<Metadata> {
  const params = await searchParams;
  const query = params.q || '';

  // Страницы результатов поиска закрыты от индексации (и в robots.txt тоже):
  // они дублируют каталог и плодят мусорные URL с query-параметрами
  return buildMetadata({
    title: query ? `Поиск: ${query}` : 'Поиск товаров',
    description: query
      ? `Результаты поиска по запросу "${query}" в магазине OPTISPORT. Найдите спортивные товары по лучшим ценам.`
      : 'Поиск спортивных товаров в магазине OPTISPORT',
    path: '/search',
    noIndex: true,
  });
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
