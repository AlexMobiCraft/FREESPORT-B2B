/**
 * Search Page — landmark-разметка
 *
 * Единственный main страницы рендерит LayoutWrapper темы blue,
 * страница поиска отдаёт именованный регион «Результаты поиска».
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import SearchPage from '../page';

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
});
