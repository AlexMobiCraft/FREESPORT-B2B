/**
 * TextSeparator Component Tests
 * Story 41.8 — AC1, AC2, AC5
 *
 * Компонент — единственная гарантия того, что соседние узлы карточки
 * не склеиваются в `textContent`. Тест охраняет три его свойства:
 * содержимое (пробел), класс (`sr-only` = вне потока) и тег (`span`).
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { TextSeparator } from '../TextSeparator';

describe('TextSeparator', () => {
  it('содержит ровно один пробельный символ', () => {
    const { container } = render(<TextSeparator />);

    expect(container.textContent).toBe(' ');
  });

  it('рендерится как span с классом sr-only (вне потока, вёрстка не меняется)', () => {
    const { container } = render(<TextSeparator />);

    const separator = container.querySelector('span');
    expect(separator).not.toBeNull();
    expect(separator?.tagName).toBe('SPAN');
    expect(separator?.classList.contains('sr-only')).toBe(true);
  });

  it('задаёт координаты left-0 top-0 — без них absolute-элемент растягивает документ', () => {
    // Регрессия, найденная замером на /electric 2026-09-08: sr-only даёт
    // position: absolute без координат, элемент встаёт в статическую позицию,
    // и в горизонтальной ленте товаров последняя карточка выносила разделитель
    // за правый край окна (x≈1532 при ширине 1440) — появлялась горизонтальная
    // полоса прокрутки. Координаты прижимают элемент к углу предка. Не удалять.
    const { container } = render(<TextSeparator />);

    const separator = container.querySelector('span');
    expect(separator?.classList.contains('left-0')).toBe(true);
    expect(separator?.classList.contains('top-0')).toBe(true);
  });

  it('не добавляет никаких других узлов в DOM', () => {
    const { container } = render(<TextSeparator />);

    expect(container.childNodes).toHaveLength(1);
    expect(container.querySelectorAll('*')).toHaveLength(1);
  });

  it('не принимает фокус: у элемента нет tabindex и он не интерактивный', () => {
    const { container } = render(<TextSeparator />);

    const separator = container.querySelector('span');
    expect(separator?.hasAttribute('tabindex')).toBe(false);
    expect(separator?.getAttribute('role')).toBeNull();
  });
});
