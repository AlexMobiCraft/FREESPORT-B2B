/**
 * ElectricProductCard — разделение текста бейджа, бренда и названия
 * Story 41.8 — AC1, AC3 (FR-41-19)
 *
 * Зачем отдельный файл. Стори 41.8 правит две разные карточки: `ProductCard`
 * (синяя тема, три layout'а) и `ElectricProductCard` (маршруты `/electric`
 * и `/electric/catalog`). Тестами была закрыта только первая, поэтому
 * исчезновение любого из двух разделителей во второй — или вынос его наружу
 * из условия `{badge && ...}` / `{brand && ...}` — CI не заметил бы вовсе
 * (находка четвёртого ревью, 2026-09-08).
 *
 * Моков компонентов здесь нет намеренно: рендерится настоящая цепочка
 * ElectricProductCard → ElectricBadge / ElectricButton. Карточка использует
 * обычный `<img>`, а не `next/image`, поэтому глобальный мок из
 * `vitest.setup.ts` к ней отношения не имеет.
 *
 * Что тест НЕ проверяет: раскладку и внешний вид — в `vitest.config.mts`
 * стоит `css: false`, `sr-only` в тестах ничего не скрывает. AC2 закрывается
 * осмотром в браузере (Task 8 стори).
 *
 * Известная граница, за которую тест не заходит: между разделителем бейджа
 * и брендом в DOM стоят кнопка избранного (`♡`/`♥`) и оверлей «Нет в наличии»,
 * поэтому `textContent` карточки по-прежнему содержит склейки вида `♡Nike`.
 * Это дефект того же класса, но вне FR-41-19 — вынесен в `deferred-work.md`
 * и здесь сознательно не фиксируется ожиданием ни в одну сторону.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ElectricProductCard } from '../ElectricProductCard';
import type { ElectricProductCardProps } from '../ElectricProductCard';

const baseProps: ElectricProductCardProps = {
  image: '/test-image.jpg',
  title: 'Test Product',
  brand: 'Nike',
  price: 1200,
  badge: 'hit', // → текст бейджа «Хит»
};

const separators = (container: HTMLElement) => Array.from(container.querySelectorAll('span.sr-only'));

describe('ElectricProductCard: разделение текста бейджа, бренда и названия (AC1)', () => {
  it('текст бейджа и название бренда не склеиваются с соседними узлами', () => {
    const { container } = render(<ElectricProductCard {...baseProps} />);
    const text = container.textContent ?? '';

    // Стык «бейдж → следующий узел»: без разделителя было бы «Хит♡»
    expect(text).not.toMatch(/Хит♡/);
    expect(text).toMatch(/Хит\s+♡/);
    // Стык «бренд → название»: без разделителя было бы «NikeTest Product»
    expect(text).not.toMatch(/NikeTest Product/);
    expect(text).toMatch(/Nike\s+Test Product/);
  });

  it('у полной карточки ровно два разделителя, и каждый стоит на своём стыке', () => {
    const { container } = render(<ElectricProductCard {...baseProps} />);

    const found = separators(container);
    expect(found).toHaveLength(2);
    // Первый — сразу за контейнером бейджа
    expect(found[0].previousElementSibling?.textContent).toBe('Хит');
    // Второй — сразу за абзацем бренда
    expect(found[1].previousElementSibling?.tagName).toBe('P');
    expect(found[1].previousElementSibling?.textContent).toBe('Nike');
  });

  // Разделитель стоит вне тернарника, выбирающего текст бейджа, — проверяем,
  // что он не привязан к одному варианту
  it.each([
    ['hit', 'Хит', {}],
    ['new', 'New', {}],
    ['sale', '-25%', { oldPrice: 1600 }],
  ] as const)('badge=%s: разделитель после бейджа есть, текст «%s» не склеен', (badge, label, extra) => {
    const { container } = render(<ElectricProductCard {...baseProps} badge={badge} {...extra} />);

    const found = separators(container);
    expect(found).toHaveLength(2);
    expect(found[0].previousElementSibling?.textContent).toBe(label);
    // Пробел между текстом бейджа и следующим узлом — это и есть разделитель
    expect(container.textContent).toContain(`${label} ♡`);
  });
});

describe('ElectricProductCard: отсутствие лишних разделителей (AC3)', () => {
  it('без бейджа остаётся ровно один разделитель — брендовый', () => {
    const { container } = render(<ElectricProductCard {...baseProps} badge={undefined} />);
    const text = container.textContent ?? '';

    expect(text).not.toContain('Хит');
    // Число, а не только отсутствие текста: иначе вынос разделителя
    // из блока `{badge && ...}` остался бы незамеченным
    const remaining = separators(container);
    expect(remaining).toHaveLength(1);
    expect(remaining[0].previousElementSibling?.tagName).toBe('P');
    expect(remaining[0].previousElementSibling?.textContent).toBe('Nike');
  });

  it('без бренда остаётся ровно один разделитель — бейджевый', () => {
    const { container } = render(<ElectricProductCard {...baseProps} brand={undefined} />);
    const text = container.textContent ?? '';

    expect(text).not.toContain('Nike');
    const remaining = separators(container);
    expect(remaining).toHaveLength(1);
    expect(remaining[0].previousElementSibling?.textContent).toBe('Хит');
  });

  it('без бейджа и без бренда разделителей не остаётся вовсе', () => {
    const { container } = render(
      <ElectricProductCard {...baseProps} badge={undefined} brand={undefined} />
    );

    expect(separators(container)).toHaveLength(0);
    expect(container.textContent).toContain('Test Product');
  });

  it('разделители не попадают в tab-порядок: новых интерактивных элементов нет', () => {
    const { container } = render(<ElectricProductCard {...baseProps} />);

    separators(container).forEach(el => {
      expect(el.hasAttribute('tabindex')).toBe(false);
      expect(el.getAttribute('role')).toBeNull();
    });
  });
});
