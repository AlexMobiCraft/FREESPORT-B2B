/**
 * OrderSummary Component Tests
 *
 * Story 41.4:
 * - AC3 (FR-41-20): информирование о политике ПДн со ссылкой, без чекбокса
 * - AC5 (FR-41-16): состав, итог и кнопка подтверждения в одном блоке
 * - AC6 (FR-41-16): пустая корзина не показывает нулевой итог
 * - AC1 (FR-41-15): блок условий возврата и поддержки привязан к оплате
 */

import React from 'react';
import { render, screen, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OrderSummary } from '../OrderSummary';

// Mock cartStore — образец из CartSummary.test.tsx
const mockCartStore = {
  items: [] as Array<Record<string, unknown>>,
  totalPrice: 0,
  totalItems: 0,
};

vi.mock('@/stores/cartStore', () => ({
  useCartStore: vi.fn(() => mockCartStore),
}));

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const mockItem = {
  id: 1,
  variant_id: 100,
  product: { id: 10, name: 'Кроссовки Nike Air Max', slug: 'nike-air-max', image: null },
  variant: { sku: 'NK-AM-001', color_name: 'Чёрный', size_value: '42' },
  quantity: 2,
  unit_price: '100.00',
  total_price: '200.00',
  added_at: '2026-09-05T12:00:00Z',
};

const setCart = (state: Partial<typeof mockCartStore>) => {
  Object.assign(mockCartStore, { items: [], totalPrice: 0, totalItems: 0 }, state);
};

describe('OrderSummary', () => {
  beforeEach(() => {
    setCart({});
  });

  // ================== AC5: состав + итог + кнопка в одном блоке ==================
  describe('AC5 — сумма и состав видны до подтверждения', () => {
    beforeEach(() => {
      setCart({ items: [mockItem], totalPrice: 200, totalItems: 2 });
    });

    it('держит список товаров, итог и кнопку внутри одного order-summary', () => {
      render(<OrderSummary isSubmitting={false} />);

      const summary = screen.getByTestId('order-summary');
      expect(within(summary).getByTestId('order-summary-items')).toBeInTheDocument();
      expect(within(summary).getByTestId('total-price')).toBeInTheDocument();
      expect(within(summary).getByTestId('checkout-submit-button')).toBeInTheDocument();
    });

    it('выводит итоговую сумму с символом рубля', () => {
      render(<OrderSummary isSubmitting={false} />);

      expect(screen.getByTestId('total-price')).toHaveTextContent('200 ₽');
      expect(screen.getByTestId('total-price-items')).toHaveTextContent('200 ₽');
    });
  });

  // ================== AC3: политика ПДн ==================
  describe('AC3 — ссылка на политику обработки персональных данных', () => {
    beforeEach(() => {
      setCart({ items: [mockItem], totalPrice: 200, totalItems: 2 });
    });

    it('показывает строку согласия дословно', () => {
      render(<OrderSummary isSubmitting={false} />);

      expect(
        screen.getByText(
          (_, element) =>
            element?.tagName === 'P' &&
            element.textContent ===
              'Нажимая кнопку, вы соглашаетесь с условиями обработки персональных данных в соответствии с «Политикой обработки персональных данных»'
        )
      ).toBeInTheDocument();
    });

    it('открывает политику в новой вкладке с rel="noopener noreferrer"', () => {
      render(<OrderSummary isSubmitting={false} />);

      const link = screen.getByRole('link', { name: '«Политикой обработки персональных данных»' });
      expect(link).toHaveAttribute('href', '/privacy-policy');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    });

    it('не добавляет чекбокс согласия в форму заказа', () => {
      render(<OrderSummary isSubmitting={false} />);

      expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    });
  });

  // ================== AC1: блок возврата и поддержки ==================
  describe('AC1 — условия возврата и поддержка', () => {
    it('рендерит блок внутри order-summary при непустой корзине', () => {
      setCart({ items: [mockItem], totalPrice: 200, totalItems: 2 });
      render(<OrderSummary isSubmitting={false} />);

      const summary = screen.getByTestId('order-summary');
      expect(within(summary).getByTestId('returns-support-notice')).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Условия возврата и рекламаций' })).toHaveAttribute(
        'href',
        '/partners#returns'
      );
    });
  });

  // ================== AC6: пустая корзина ==================
  describe('AC6 — пустая корзина не показывает нулевой итог', () => {
    beforeEach(() => {
      setCart({ items: [], totalPrice: 0, totalItems: 0 });
    });

    it('показывает сообщение о пустой корзине', () => {
      render(<OrderSummary isSubmitting={false} isCartEmpty />);

      expect(screen.getByTestId('empty-cart-message')).toHaveTextContent('Корзина пуста');
    });

    it('не выводит ни total-price, ни total-price-items', () => {
      render(<OrderSummary isSubmitting={false} isCartEmpty />);

      expect(screen.queryByTestId('total-price')).not.toBeInTheDocument();
      expect(screen.queryByTestId('total-price-items')).not.toBeInTheDocument();
    });

    it('не показывает кнопку подтверждения и блок возврата', () => {
      render(<OrderSummary isSubmitting={false} isCartEmpty />);

      expect(screen.queryByTestId('checkout-submit-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('returns-support-notice')).not.toBeInTheDocument();
    });
  });
});
