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

  // Результаты поиска дублируют каталог и плодят URL с query-параметрами, поэтому
  // адрес закрыт Disallow в robots.txt. noindex не ставится: адреса под Disallow
  // meta noindex не несут (решение D4) — робот страницу не читает и тег не увидит.
  return buildMetadata({
    title: query ? `Поиск: ${query}` : 'Поиск товаров',
    description: query
      ? `Результаты поиска по запросу "${query}" в магазине OPTISPORT.`
      : 'Поиск спортивных товаров в магазине OPTISPORT',
    path: '/search',
  });
}

/**
 * Серверный компонент страницы поиска
 */
export default async function SearchPage({ searchParams }: SearchPageProps) {
  const params = await searchParams;
  const initialQuery = params.q || '';
  const initialPage = parseInt(params.page || '1', 10);

  // Единственный <main> страницы рендерит LayoutWrapper; имя результатов несёт регион
  return (
    <section className="min-h-screen bg-canvas" aria-label="Результаты поиска">
      <SearchPageClient initialQuery={initialQuery} initialPage={initialPage} />
    </section>
  );
}
