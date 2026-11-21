/**
 * Блок «Описание» карточки товара.
 *
 * Описание приходит из 1С с `<br>` и переводами строк. Выводится простым
 * текстом (не HTML): без буквального «<br>» и с сохранёнными переводами строк.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import ProductSummary, { type ProductDetailWithVariants } from '../ProductSummary';

vi.mock('@/components/ui/Toast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const baseProduct: ProductDetailWithVariants = {
  id: 1,
  slug: 'kovrik',
  name: 'Коврик для йоги',
  sku: 'ES2123',
  brand: 'ESPADO',
  description: '',
  price: { retail: 1000, currency: 'RUB' },
  stock_quantity: 1,
  images: [],
  category: { id: 1, name: 'Йога', slug: 'yoga', breadcrumbs: [] },
  is_in_stock: true,
  can_be_ordered: true,
  variants: [],
};

function renderSummary(description: string) {
  return render(
    <ProductSummary product={{ ...baseProduct, description }} userRole="retail" />
  );
}

describe('ProductSummary — описание', () => {
  it('не показывает буквальный <br> и переносит строки', () => {
    const { container } = renderSummary('Материал: NBR<br>Размер: 183х61 см<br />Цвет: зелёный');

    expect(container.textContent).not.toContain('<br');
    const paragraph = screen.getByText(/Материал: NBR/);
    expect(paragraph.textContent).toBe('Материал: NBR\nРазмер: 183х61 см\nЦвет: зелёный');
    expect(paragraph).toHaveClass('whitespace-pre-line');
  });

  it('не вставляет теги из описания как HTML', () => {
    const { container } = renderSummary('Текст <img src=x onerror=alert(1)> <b>жирный</b>');

    expect(container.querySelector('img[src="x"]')).toBeNull();
    expect(container.querySelector('b')).toBeNull();
    expect(screen.getByText(/Текст/).textContent).toBe('Текст жирный');
  });

  it('не выводит блок, если после очистки текста не осталось', () => {
    renderSummary('<br><br/>');

    expect(screen.queryByRole('heading', { name: 'Описание' })).toBeNull();
  });
});
