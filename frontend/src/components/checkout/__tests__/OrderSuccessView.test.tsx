/**
 * Unit-тесты для OrderSuccessView
 * Story 15.4: Страница подтверждения заказа
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { OrderSuccessView } from '../OrderSuccessView';
import type { Order } from '@/types/order';

/**
 * Мок-данные заказа для тестов (контракт backend OrderDetailSerializer)
 */
const mockOrder: Order = {
  id: 123,
  order_number: 'FS-2024-001',
  user: 1,
  customer_display_name: 'Иван Иванов',
  customer_name: 'Иван Иванов',
  customer_email: 'ivan@example.com',
  customer_phone: '+7 999 123-45-67',
  status: 'pending',
  total_amount: '15000.00',
  discount_amount: '0.00',
  delivery_cost: '0.00',
  delivery_address: 'Москва, ул. Ленина, д. 10, кв. 25, 123456',
  delivery_method: 'courier',
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'pending',
  payment_id: '',
  notes: '',
  created_at: '2024-12-14T12:00:00Z',
  updated_at: '2024-12-14T12:00:00Z',
  items: [
    {
      id: 1,
      product: 101,
      product_name: 'Кроссовки Nike Air Max',
      product_sku: 'NIKE-AM-001',
      quantity: 2,
      unit_price: '5000.00',
      total_price: '10000.00',
      variant: null,
      variant_info: '',
    },
    {
      id: 2,
      product: 102,
      product_name: 'Футболка Adidas',
      product_sku: 'ADIDAS-TS-001',
      quantity: 1,
      unit_price: '5000.00',
      total_price: '5000.00',
      variant: null,
      variant_info: '',
    },
  ],
  subtotal: '15000.00',
  total_items: 3,
  calculated_total: '15000.00',
  can_be_cancelled: true,
};

describe('OrderSuccessView', () => {
  describe('Rendering', () => {
    it('должен отображать номер заказа', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Заказ успешно оформлен!')).toBeInTheDocument();
      expect(screen.getByText('FS-2024-001')).toBeInTheDocument();
    });

    it('должен отображать статус "Новый" для pending', () => {
      render(<OrderSuccessView order={mockOrder} />);

      // pending -> "Новый"
      expect(screen.getByText('Новый')).toBeInTheDocument();
    });

    it('должен отображать заголовок "Детали заказа"', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Детали заказа')).toBeInTheDocument();
    });
  });

  describe('Items List', () => {
    it('должен отображать список товаров', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Товары:')).toBeInTheDocument();
      expect(screen.getByText('Кроссовки Nike Air Max × 2')).toBeInTheDocument();
      expect(screen.getByText('Футболка Adidas × 1')).toBeInTheDocument();
    });

    it('должен отображать цены товаров', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('10 000 ₽')).toBeInTheDocument();
      expect(screen.getByText('5 000 ₽')).toBeInTheDocument();
    });

    it('должен показывать предупреждение если товаров нет', () => {
      const orderWithoutItems: Order = {
        ...mockOrder,
        items: [],
      };

      render(<OrderSuccessView order={orderWithoutItems} />);

      expect(screen.getByText('Информация о товарах недоступна')).toBeInTheDocument();
    });
  });

  describe('Delivery Address', () => {
    it('должен отображать адрес доставки (строкой)', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Адрес доставки:')).toBeInTheDocument();
      expect(screen.getByText('Москва, ул. Ленина, д. 10, кв. 25, 123456')).toBeInTheDocument();
    });
  });

  describe('Delivery Method', () => {
    it('должен отображать способ доставки (локализованный)', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Способ доставки:')).toBeInTheDocument();
      // courier -> "Курьерская доставка"
      expect(screen.getByText('Курьерская доставка')).toBeInTheDocument();
    });

    it('должен показывать что стоимость уточняется если delivery_cost = 0', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Стоимость: Уточняется администратором')).toBeInTheDocument();
    });

    it('должен показывать стоимость доставки если указана', () => {
      const orderWithDeliveryCost: Order = {
        ...mockOrder,
        delivery_cost: '500.00',
      };
      render(<OrderSuccessView order={orderWithDeliveryCost} />);

      expect(screen.getByText('Стоимость: 500 ₽')).toBeInTheDocument();
    });
  });

  describe('Total Amount', () => {
    it('должен отображать итоговую сумму', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Итого:')).toBeInTheDocument();
      expect(screen.getByText('15 000 ₽')).toBeInTheDocument();
    });
  });

  describe('Info Panel', () => {
    it('должен отображать информационный блок', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Что дальше?')).toBeInTheDocument();
      expect(
        screen.getByText(/Администратор свяжется с вами в течение 24 часов/)
      ).toBeInTheDocument();
    });

    it('должен отображать список уточнений', () => {
      render(<OrderSuccessView order={mockOrder} />);

      expect(screen.getByText('Способа оплаты')).toBeInTheDocument();
      expect(screen.getByText('Точной стоимости доставки')).toBeInTheDocument();
      expect(screen.getByText('Времени доставки')).toBeInTheDocument();
    });
  });

  describe('Navigation Buttons', () => {
    it('должен отображать кнопку "Продолжить покупки"', () => {
      render(<OrderSuccessView order={mockOrder} />);

      const continueButton = screen.getByRole('button', { name: 'Продолжить покупки' });
      expect(continueButton).toBeInTheDocument();
    });

    it('должен отображать кнопку "Личный кабинет"', () => {
      render(<OrderSuccessView order={mockOrder} />);

      const profileButton = screen.getByRole('button', { name: 'Личный кабинет' });
      expect(profileButton).toBeInTheDocument();
    });

    it('кнопка "Продолжить покупки" должна вести на /catalog', () => {
      render(<OrderSuccessView order={mockOrder} />);

      const catalogLink = screen.getByRole('link', { name: 'Продолжить покупки' });
      expect(catalogLink).toHaveAttribute('href', '/catalog');
    });

    it('кнопка "Личный кабинет" должна вести на /profile/orders', () => {
      render(<OrderSuccessView order={mockOrder} />);

      const profileLink = screen.getByRole('link', { name: 'Личный кабинет' });
      expect(profileLink).toHaveAttribute('href', '/profile/orders');
    });
  });

  describe('Status Labels (backend статусы)', () => {
    it('должен отображать статус "Новый" для pending', () => {
      const pendingOrder: Order = { ...mockOrder, status: 'pending' };
      render(<OrderSuccessView order={pendingOrder} />);

      expect(screen.getByText('Новый')).toBeInTheDocument();
    });

    it('должен отображать статус "Подтверждён" для confirmed', () => {
      const confirmedOrder: Order = { ...mockOrder, status: 'confirmed' };
      render(<OrderSuccessView order={confirmedOrder} />);

      expect(screen.getByText('Подтверждён')).toBeInTheDocument();
    });

    it('должен отображать статус "Отправлен" для shipped', () => {
      const shippedOrder: Order = { ...mockOrder, status: 'shipped' };
      render(<OrderSuccessView order={shippedOrder} />);

      expect(screen.getByText('Отправлен')).toBeInTheDocument();
    });

    it('должен отображать статус "Доставлен" для delivered', () => {
      const deliveredOrder: Order = { ...mockOrder, status: 'delivered' };
      render(<OrderSuccessView order={deliveredOrder} />);

      expect(screen.getByText('Доставлен')).toBeInTheDocument();
    });

    it('должен отображать статус "Отменён" для cancelled', () => {
      const cancelledOrder: Order = { ...mockOrder, status: 'cancelled' };
      render(<OrderSuccessView order={cancelledOrder} />);

      expect(screen.getByText('Отменён')).toBeInTheDocument();
    });

    it('должен отображать статус "Возвращён" для refunded', () => {
      const refundedOrder: Order = { ...mockOrder, status: 'refunded' };
      render(<OrderSuccessView order={refundedOrder} />);

      expect(screen.getByText('Возвращён')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    it('должен обрабатывать заказ без адреса (пустая строка)', () => {
      const orderWithoutAddress: Order = {
        ...mockOrder,
        delivery_address: '',
      };

      render(<OrderSuccessView order={orderWithoutAddress} />);

      expect(screen.queryByText('Адрес доставки:')).not.toBeInTheDocument();
    });

    it('должен отображать разные способы доставки', () => {
      const pickupOrder: Order = { ...mockOrder, delivery_method: 'pickup' };
      render(<OrderSuccessView order={pickupOrder} />);
      expect(screen.getByText('Самовывоз')).toBeInTheDocument();
    });

    it('должен обрабатывать строковые Decimal значения', () => {
      const orderWithStringDecimals: Order = {
        ...mockOrder,
        total_amount: '25000.50',
        items: [
          {
            id: 1,
            product: 101,
            product_name: 'Тестовый товар',
            product_sku: 'TEST-001',
            quantity: 1,
            unit_price: '25000.50',
            total_price: '25000.50',
            variant: null,
            variant_info: '',
          },
        ],
      };

      render(<OrderSuccessView order={orderWithStringDecimals} />);

      // toLocaleString('ru-RU') форматирует с пробелами, проверяем что рендерится без ошибок
      expect(screen.getByText('Тестовый товар × 1')).toBeInTheDocument();
      expect(screen.getAllByText(/25.*000/).length).toBeGreaterThan(0);
    });
  });
});
