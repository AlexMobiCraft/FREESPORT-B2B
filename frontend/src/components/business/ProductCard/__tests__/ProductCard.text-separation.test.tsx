/**
 * ProductCard — разделение текста бейджа, бренда и названия
 * Story 41.8 — AC1, AC3, AC4, AC5 (FR-41-19, NFR-41-06)
 *
 * Отдельный файл, а не дополнение к `ProductCard.test.tsx`, намеренно:
 * там `ProductBadge` и `@/components/ui` замоканы, и проверка разделителя
 * проверяла бы мок, а не код. Здесь моков компонентов нет — рендерится
 * настоящая цепочка ProductCard → ProductBadge → Badge.
 *
 * Что тест НЕ проверяет: раскладку и внешний вид. В `vitest.config.mts`
 * стоит `css: false`, поэтому `sr-only` в тестах ничего не скрывает.
 * AC2 закрывается только осмотром в браузере (Task 8 стори).
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { ProductCard } from '../ProductCard';
import type { Product } from '@/types/api';

const mockProduct: Product = {
  id: 1,
  name: 'Test Product',
  slug: 'test-product',
  description: 'Test description',
  retail_price: 1200,
  opt1_price: 1000,
  opt2_price: 900,
  opt3_price: 800,
  opt4_price: 700,
  is_in_stock: true,
  stock_quantity: 50,
  category: {
    id: 1,
    name: 'Test Category',
    slug: 'test-category',
  },
  brand: {
    id: 1,
    name: 'Nike',
    slug: 'nike',
    is_featured: false,
  },
  images: [
    {
      id: 1,
      image: '/test-image.jpg',
      is_primary: true,
    },
  ],
  is_hit: false,
  is_new: true, // → бейдж «Новинка»
  is_sale: false,
  is_promo: false,
  is_premium: false,
  discount_percent: null,
};

describe('ProductCard: разделение текста бейджа, бренда и названия (AC1)', () => {
  // В grid и compact порядок в DOM: бейдж → бренд → название
  it.each(['grid', 'compact'] as const)(
    'layout=%s: текст не склеен, слова разделены пробелом',
    layout => {
      const { container } = render(<ProductCard product={mockProduct} layout={layout} />);
      const text = container.textContent ?? '';

      expect(text).not.toMatch(/НовинкаNike/);
      expect(text).not.toMatch(/NikeTest Product/);
      expect(text).toMatch(/Новинка\s+Nike\s+Test Product/);
    }
  );

  // В list порядок другой: бренд → бейдж → название
  it('layout=list: текст не склеен при обратном порядке бренд → бейдж', () => {
    const { container } = render(<ProductCard product={mockProduct} layout="list" />);
    const text = container.textContent ?? '';

    expect(text).not.toMatch(/NikeНовинка/);
    expect(text).not.toMatch(/НовинкаTest Product/);
    expect(text).toMatch(/Nike\s+Новинка\s+Test Product/);
  });

  it('рендерится настоящий ProductBadge, а не мок: бейдж лежит внутри Badge-элемента', () => {
    const { container } = render(<ProductCard product={mockProduct} layout="grid" />);

    // Badge из дизайн-системы — span с inline-flex и rounded-full,
    // тестовый мок из ProductCard.test.tsx этих классов не имеет
    const badge = Array.from(container.querySelectorAll('span')).find(el =>
      el.textContent?.includes('Новинка')
    );
    expect(badge).toBeDefined();
    expect(badge?.className).toContain('inline-flex');
  });
});

describe('ProductCard: отсутствие лишних разделителей (AC3)', () => {
  const productNoBadge: Product = { ...mockProduct, is_new: false };
  const productNoBrand: Product = { ...mockProduct, brand: undefined };
  const productBare: Product = { ...mockProduct, is_new: false, brand: undefined };

  const separators = (container: HTMLElement) =>
    Array.from(container.querySelectorAll('span.sr-only'));

  // Опорное число для трёх проверок ниже: у полной карточки разделителя ровно два —
  // один внутри ProductBadge (после бейджа), второй внутри блока {brand && ...}.
  it.each(['grid', 'list', 'compact'] as const)(
    'layout=%s: у полной карточки ровно два разделителя — бейджа и бренда',
    layout => {
      const { container } = render(<ProductCard product={mockProduct} layout={layout} />);

      expect(separators(container)).toHaveLength(2);
    }
  );

  it.each(['grid', 'list', 'compact'] as const)(
    'layout=%s: без маркетинговых флагов разделитель бейджа не появляется',
    layout => {
      const { container } = render(<ProductCard product={productNoBadge} layout={layout} />);
      const text = container.textContent ?? '';

      expect(text).not.toContain('Новинка');
      // Разделитель бейджа исчез вместе с самим бейджем: ProductBadge вернул null
      // целиком. Явная проверка числа, а не только отсутствия текста, — иначе тест
      // остался бы зелёным, вынеси кто-нибудь TextSeparator наружу компонента.
      const remaining = separators(container);
      expect(remaining).toHaveLength(1);
      // Уцелевший разделитель — именно брендовый: стоит сразу за абзацем бренда
      expect(remaining[0].previousElementSibling?.tagName).toBe('P');
      expect(remaining[0].previousElementSibling?.textContent).toBe('Nike');
      // бренд на месте, разделитель бренда остаётся — он живёт в блоке бренда
      expect(text).toMatch(/Nike\s+Test Product/);
    }
  );

  it.each(['grid', 'list', 'compact'] as const)(
    'layout=%s: без бренда разделитель бренда не появляется',
    layout => {
      const { container } = render(<ProductCard product={productNoBrand} layout={layout} />);
      const text = container.textContent ?? '';

      expect(text).not.toContain('Nike');
      // Разделитель бренда исчез вместе с блоком {brand && ...}; остался только
      // разделитель бейджа. Проверка числа страхует от выноса разделителя из условия.
      const remaining = separators(container);
      expect(remaining).toHaveLength(1);
      // Уцелевший разделитель — именно бейджевый: стоит сразу за элементом Badge
      expect(remaining[0].previousElementSibling?.textContent).toBe('Новинка');
      expect(text).toMatch(/Новинка\s+Test Product/);
    }
  );

  it.each(['grid', 'list', 'compact'] as const)(
    'layout=%s: без бейджа и без бренда пустых span.sr-only не остаётся',
    layout => {
      const { container } = render(<ProductCard product={productBare} layout={layout} />);

      expect(container.querySelectorAll('span.sr-only')).toHaveLength(0);
      expect(container.textContent).toContain('Test Product');
    }
  );
});

describe('ProductCard: доступность (AC4)', () => {
  it('список из трёх карточек не добавляет нарушений axe сверх базиса', async () => {
    const { container } = render(
      <div>
        <ProductCard product={mockProduct} layout="grid" />
        <ProductCard product={{ ...mockProduct, id: 2 }} layout="list" />
        <ProductCard product={{ ...mockProduct, id: 3 }} layout="compact" />
      </div>
    );

    const results = await axe(container);
    // Базис снят этим же тестом ДО правок стори 41.8 и равен 0 (см. Debug Log).
    expect(results.violations).toHaveLength(0);
  });

  it('разделитель не попадает в tab-порядок: новых интерактивных элементов нет', () => {
    const { container } = render(<ProductCard product={mockProduct} layout="grid" />);

    const separators = container.querySelectorAll('span.sr-only');
    separators.forEach(el => {
      expect(el.hasAttribute('tabindex')).toBe(false);
      expect(el.getAttribute('role')).toBeNull();
    });
  });
});
