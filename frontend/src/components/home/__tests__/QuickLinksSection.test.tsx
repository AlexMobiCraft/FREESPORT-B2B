/**
 * QuickLinksSection Component Tests
 *
 * Тесты для секции быстрых ссылок на главной странице.
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../../../__mocks__/api/server';
import { QuickLinksSection } from '../QuickLinksSection';

// Mock next/link
vi.mock('next/link', () => ({
    default: ({
        children,
        href,
        ...props
    }: {
        children: React.ReactNode;
        href: string;
        [key: string]: unknown;
    }) => (
        <a href={href} {...props}>
            {children}
        </a>
    ),
}));

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

// Mock categories data
const mockCategories = [
    { id: 1, name: 'Футбол', slug: 'football', parent_id: null, level: 0, icon: '⚽', products_count: 150 },
    { id: 2, name: 'Бег', slug: 'running', parent_id: null, level: 0, icon: '🏃', products_count: 230 },
    { id: 3, name: 'Теннис', slug: 'tennis', parent_id: null, level: 0, icon: '🎾', products_count: 95 },
];

describe('QuickLinksSection', () => {
    it('renders 3 static quick links', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json([]))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Новинки')).toBeInTheDocument();
            expect(screen.getByText('Хиты продаж')).toBeInTheDocument();
            expect(screen.getByText('Скидки')).toBeInTheDocument();
        });
    });

    it('static links have correct hrefs', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json([]))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Новинки')).toBeInTheDocument();
        });

        const novinki = screen.getByText('Новинки').closest('a');
        const hits = screen.getByText('Хиты продаж').closest('a');
        const sale = screen.getByText('Скидки').closest('a');

        expect(novinki).toHaveAttribute('href', '/catalog?is_new=true');
        expect(hits).toHaveAttribute('href', '/catalog?is_hit=true');
        expect(sale).toHaveAttribute('href', '/catalog?is_sale=true');
    });

    it('loads and displays categories from API', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json(mockCategories))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Футбол')).toBeInTheDocument();
            expect(screen.getByText('Бег')).toBeInTheDocument();
            expect(screen.getByText('Теннис')).toBeInTheDocument();
        });
    });

    it('category links point to /catalog/{slug}', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json(mockCategories))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Футбол')).toBeInTheDocument();
        });

        // В QuickLinksSection ссылки на категории теперь имеют формат /catalog?category={slug}
        // на основе кода: href={`/catalog?category=${category.slug}`}
        const footballLink = screen.getByText('Футбол').closest('a');
        const runningLink = screen.getByText('Бег').closest('a');

        expect(footballLink).toHaveAttribute('href', '/catalog?category=football');
        expect(runningLink).toHaveAttribute('href', '/catalog?category=running');
    });

    it('shows only static links on API error (graceful degradation)', async () => {
        server.use(
            http.get('*/categories-tree/', () => {
                return new HttpResponse(null, { status: 500 });
            })
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            // Static links still visible
            expect(screen.getByText('Новинки')).toBeInTheDocument();
            expect(screen.getByText('Хиты продаж')).toBeInTheDocument();
            expect(screen.getByText('Скидки')).toBeInTheDocument();
        });

        // No categories should be rendered
        expect(screen.queryByText('Футбол')).not.toBeInTheDocument();
    });

    it('renders section with correct aria label', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json(mockCategories))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Футбол')).toBeInTheDocument();
        });

        const section = screen.getByLabelText('Быстрые ссылки');
        expect(section).toBeInTheDocument();
    });

    it('renders fixed and scrollable zones separately', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json([]))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Новинки')).toBeInTheDocument();
        });

        // Фиксированная зона
        const fixedList = screen.getByLabelText('Быстрые фильтры');
        expect(fixedList).toBeInTheDocument();

        // Прокручиваемая зона категорий
        const categoriesList = screen.getByLabelText('Категории товаров');
        expect(categoriesList).toBeInTheDocument();
    });

    it('renders both static and dynamic items as listitems', async () => {
        server.use(
            http.get('*/categories-tree/', () => HttpResponse.json(mockCategories))
        );

        render(<QuickLinksSection />);

        await waitFor(() => {
            expect(screen.getByText('Футбол')).toBeInTheDocument();
        });

        const items = screen.getAllByRole('listitem');
        // 3 static + 3 categories = 6
        expect(items.length).toBe(6);
    });
});
