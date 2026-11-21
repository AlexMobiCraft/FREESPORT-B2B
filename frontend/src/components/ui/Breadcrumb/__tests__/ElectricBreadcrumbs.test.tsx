/**
 * Поведенческий тест реального ElectricBreadcrumbs (Story 41.12 — Task 6.3, AC7).
 *
 * Текстовый grep, тест общего `Breadcrumb` и обновлённые моки cart-тестов не
 * заменяют эту проверку: здесь рендерится production-компонент и проверяются
 * роль `navigation` и точный accessible name.
 */

import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ElectricBreadcrumbs } from '../ElectricBreadcrumbs';

describe('ElectricBreadcrumbs — AC7: русская подпись цепочки', () => {
  const items = [
    { label: 'Главная', href: '/' },
    { label: 'Каталог', href: '/catalog' },
    { label: 'Товар' },
  ];

  it('находится по роли navigation с точным accessible name «Навигационная цепочка»', () => {
    render(<ElectricBreadcrumbs items={items} />);

    const nav = screen.getByRole('navigation', { name: 'Навигационная цепочка' });

    expect(nav).toBeInTheDocument();
    expect(nav).toHaveAttribute('aria-label', 'Навигационная цепочка');
  });
});
