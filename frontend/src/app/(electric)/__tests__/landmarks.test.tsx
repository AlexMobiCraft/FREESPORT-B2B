/**
 * Тема electric — landmark-разметка страниц
 *
 * Единственный main страницы рендерит ElectricLayout, страницы /electric
 * и /electric/catalog отдают внутри него обычные контейнеры.
 */

import React from 'react';
import { act, render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { axe } from 'vitest-axe';
import ElectricLayout from '../layout';
import ElectricHomePage from '../electric/page';
import CatalogPage from '../electric/catalog/page';
import productsService from '@/services/productsService';
import categoriesService from '@/services/categoriesService';
import brandsService from '@/services/brandsService';
import type { CategoryTree } from '@/types/api';

// ==================== Mocks ====================

vi.mock('@/components/layout/ElectricHeader', () => ({ default: () => <header>Шапка</header> }));
vi.mock('@/components/layout/ElectricFooter', () => ({ default: () => <footer>Подвал</footer> }));

vi.mock('@/providers/AuthProvider', () => ({
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

// Один экземпляр на весь файл: каталог перезапрашивает категории при смене searchParams
const { searchParams } = vi.hoisted(() => ({ searchParams: new URLSearchParams() }));

vi.mock('next/navigation', async importOriginal => ({
  ...(await importOriginal<typeof import('next/navigation')>()),
  useSearchParams: () => searchParams,
}));

vi.mock('@/components/home/ElectricHeroSection', () => ({
  ElectricHeroSection: () => <div data-testid="electric-hero-section" />,
}));
vi.mock('@/components/home/HitsSection', () => ({
  HitsSection: () => <div data-testid="hits-section" />,
}));
vi.mock('@/components/home/ElectricProductSection', () => ({
  ElectricProductSection: () => <div data-testid="electric-product-section" />,
}));
vi.mock('@/components/home/ElectricCategorySection', () => ({
  ElectricCategorySection: () => <div data-testid="electric-category-section" />,
}));
vi.mock('@/components/home/NewsSection', () => ({
  NewsSection: () => <div data-testid="news-section" />,
}));
vi.mock('@/components/home/BlogSection', () => ({
  BlogSection: () => <div data-testid="blog-section" />,
}));
vi.mock('@/components/home/ElectricSubscribeSection', () => ({
  ElectricSubscribeSection: () => <div data-testid="electric-subscribe-section" />,
}));

vi.mock('@/services/productsService', () => ({
  default: { getAll: vi.fn(), getProductBySlug: vi.fn() },
}));
vi.mock('@/services/categoriesService', () => ({ default: { getTree: vi.fn() } }));
vi.mock('@/services/brandsService', () => ({ default: { getAll: vi.fn() } }));

// ==================== Tests ====================

// Тот же набор, что у стража темы blue (cart/__tests__/accessibility.test.tsx)
const LANDMARK_RULES = {
  runOnly: {
    type: 'rule' as const,
    values: [
      'landmark-main-is-top-level',
      'landmark-no-duplicate-main',
      'landmark-banner-is-top-level',
      'landmark-contentinfo-is-top-level',
      'landmark-complementary-is-top-level',
      'landmark-unique',
      'aria-prohibited-attr',
    ],
  },
};

const sportCategory: CategoryTree = {
  id: 1,
  name: 'Спорт',
  slug: 'sport',
  parent_id: null,
  level: 0,
  icon: null,
  products_count: 0,
  children: [],
};

describe('Electric: landmarks inside ElectricLayout', () => {
  beforeEach(() => {
    vi.mocked(categoriesService.getTree).mockResolvedValue([sportCategory]);
    vi.mocked(brandsService.getAll).mockResolvedValue([]);
    vi.mocked(productsService.getAll).mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
  });

  it('/electric: один main из layout, все секции внутри него, axe без landmark-нарушений', async () => {
    const { container } = render(
      <ElectricLayout>
        <ElectricHomePage />
      </ElectricLayout>
    );

    const mains = screen.getAllByRole('main');
    expect(mains).toHaveLength(1);

    // 9 секций: hero, хиты, 3 подборки товаров, категории, новости, блог, подписка
    const sections = screen.getAllByTestId(/-section$/);
    expect(sections).toHaveLength(9);
    for (const section of sections) {
      expect(mains[0]).toContainElement(section);
    }

    const results = await axe(container, LANDMARK_RULES);
    expect(results.violations.map(v => v.id)).toEqual([]);
  });

  it('/electric/catalog: один main из layout, колонка фильтров и товары внутри него, axe без landmark-нарушений', async () => {
    const { container } = render(
      <ElectricLayout>
        <CatalogPage />
      </ElectricLayout>
    );

    // Товары запрашиваются только после выбора категории. Пустое состояние есть
    // и в первом рендере, до запроса, поэтому ждём ответ, а узлы ищем после него
    await waitFor(() => expect(productsService.getAll).toHaveBeenCalled());
    await act(async () => {
      await vi.mocked(productsService.getAll).mock.results[0].value;
    });

    const mains = screen.getAllByRole('main');
    expect(mains).toHaveLength(1);
    expect(mains[0]).toContainElement(screen.getByText('Товары не найдены'));

    // Колонка фильтров — единственный complementary: дерево категорий и панель фильтров в ней
    const filtersColumn = screen.getByRole('complementary');
    expect(mains[0]).toContainElement(filtersColumn);
    expect(filtersColumn).toContainElement(screen.getByRole('navigation', { name: 'Категории' }));
    expect(filtersColumn).toContainElement(screen.getByText('БРЕНДЫ'));

    const results = await axe(container, LANDMARK_RULES);
    expect(results.violations.map(v => v.id)).toEqual([]);
  });
});
