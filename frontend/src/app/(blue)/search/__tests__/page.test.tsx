/**
 * Search Page — landmark-разметка
 *
 * Единственный main страницы рендерит LayoutWrapper темы blue,
 * страница поиска отдаёт именованный регион «Результаты поиска».
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SearchPage, { generateMetadata } from '../page';

vi.mock('@/components/business/SearchPageClient', () => ({
  SearchPageClient: ({ initialQuery }: { initialQuery: string }) => (
    <div data-testid="search-page-client">{initialQuery}</div>
  ),
}));

describe('SearchPage', () => {
  it('не рендерит собственный main, результаты — в регионе «Результаты поиска»', async () => {
    render(await SearchPage({ searchParams: Promise.resolve({ q: 'nike' }) }));

    expect(screen.queryByRole('main')).not.toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Результаты поиска' })).toContainElement(
      screen.getByTestId('search-page-client')
    );
  });

  // Стори 41.21, AC6: без «по лучшим ценам» (38-ФЗ, ст. 5 ч. 3 п. 1).
  it('description при непустом q — без превосходной степени', async () => {
    const metadata = await generateMetadata({ searchParams: Promise.resolve({ q: 'мяч' }) });

    expect(metadata.description).toBe('Результаты поиска по запросу "мяч" в магазине OPTISPORT.');
    expect(metadata.description).not.toMatch(/лучш/i);
  });
});
