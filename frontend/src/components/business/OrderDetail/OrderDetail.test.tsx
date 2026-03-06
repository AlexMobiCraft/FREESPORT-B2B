/**
 * OrderDetail Component Tests
 * Story 16.2 - AC: 7
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OrderDetail } from './OrderDetail';
import type { Order } from '@/types/order';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockOrder: Order = {
  id: 1,
  order_number: 'ORD-2025-001',
  user: 1,
  customer_display_name: 'Иван Иванов',
  customer_name: 'Иван Иванов',
  customer_email: 'ivan@example.com',
  customer_phone: '+7 999 123 45 67',
  status: 'pending',
  total_amount: '15500',
  discount_amount: '500',
  delivery_cost: '500',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1, кв. 10',
  delivery_method: 'courier',
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'pending',
  payment_id: '',
  notes: 'Позвонить за час до доставки',
  created_at: '2025-01-15T10:30:00Z',
  updated_at: '2025-01-15T10:30:00Z',
  items: [
    {
      id: 1,
      product: 101,
      product_name: 'Кроссовки Nike Air Max',
      product_sku: 'NIKE-AM-001',
      variant_info: 'Размер: 42, Цвет: Белый',
      variant: {
        id: 201,
        sku: 'NIKE-AM-001-WH-42',
        color_name: 'Белый',
        size_value: '42',
        is_active: true,
      },
      quantity: 2,
      unit_price: '5000',
      total_price: '10000',
    },
    {
      id: 2,
      product: 102,
      product_name: 'Футболка Adidas',
      product_sku: 'ADIDAS-TS-002',
      variant_info: 'Размер: XL, Цвет: Чёрный',
      variant: {
        id: 202,
        sku: 'ADIDAS-TS-002-BK-XL',
        color_name: 'Чёрный',
        size_value: 'XL',
        is_active: true,
      },
      quantity: 1,
      unit_price: '5500',
      total_price: '5500',
    },
  ],
  subtotal: '15500',
  total_items: 3,
  calculated_total: '15500',
  can_be_cancelled: true,
};

describe('OrderDetail', () => {
  const defaultProps = {
    order: mockOrder,
    onRepeatOrder: vi.fn(),
    onExportPDF: vi.fn(),
  };

  it('renders order number and status', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Заказ №ORD-2025-001')).toBeInTheDocument();
    expect(screen.getByText('Новый')).toBeInTheDocument();
  });

  it('renders formatted date', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText(/15 января 2025/i)).toBeInTheDocument();
  });

  it('renders order items table', () => {
    render(<OrderDetail {...defaultProps} />);
    // Product names may appear multiple times in the DOM (e.g., in table and summary)
    expect(screen.getAllByText('Кроссовки Nike Air Max').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Футболка Adidas').length).toBeGreaterThan(0);
    expect(screen.getByText('NIKE-AM-001')).toBeInTheDocument();
    expect(screen.getByText('ADIDAS-TS-002')).toBeInTheDocument();
  });

  it('renders delivery information', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Курьерская доставка')).toBeInTheDocument();
    expect(screen.getByText('г. Москва, ул. Тестовая, д. 1, кв. 10')).toBeInTheDocument();
  });

  it('renders payment information', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Банковская карта')).toBeInTheDocument();
    expect(screen.getByText('Ожидает оплаты')).toBeInTheDocument();
  });

  it('renders order totals', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Подытог:')).toBeInTheDocument();
    expect(screen.getByText('Скидка:')).toBeInTheDocument();
    expect(screen.getByText('Доставка:')).toBeInTheDocument();
    expect(screen.getByText('Итого:')).toBeInTheDocument();
  });

  it('renders notes section when notes exist', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Примечания')).toBeInTheDocument();
    expect(screen.getByText('Позвонить за час до доставки')).toBeInTheDocument();
  });

  it('renders repeat order button', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.getByText('Повторить заказ')).toBeInTheDocument();
  });

  it('calls onRepeatOrder when repeat button is clicked', () => {
    const onRepeatOrder = vi.fn();
    render(<OrderDetail {...defaultProps} onRepeatOrder={onRepeatOrder} />);
    fireEvent.click(screen.getByText('Повторить заказ'));
    expect(onRepeatOrder).toHaveBeenCalled();
  });

  it('does not render export PDF button by default', () => {
    render(<OrderDetail {...defaultProps} />);
    expect(screen.queryByText('Экспорт в PDF')).not.toBeInTheDocument();
  });

  it('renders export PDF button for B2B users', () => {
    render(<OrderDetail {...defaultProps} showExportPDF={true} />);
    expect(screen.getByText('Экспорт в PDF')).toBeInTheDocument();
  });

  it('calls onExportPDF when export button is clicked', () => {
    const onExportPDF = vi.fn();
    render(<OrderDetail {...defaultProps} showExportPDF={true} onExportPDF={onExportPDF} />);
    fireEvent.click(screen.getByText('Экспорт в PDF'));
    expect(onExportPDF).toHaveBeenCalled();
  });

  it('shows loading state on repeat button', () => {
    render(<OrderDetail {...defaultProps} isRepeatLoading={true} />);
    expect(screen.getByText('Добавление...')).toBeInTheDocument();
  });

  it('shows loading state on export button', () => {
    render(<OrderDetail {...defaultProps} showExportPDF={true} isExportLoading={true} />);
    expect(screen.getByText('Экспорт...')).toBeInTheDocument();
  });

  it('renders back link to orders list', () => {
    render(<OrderDetail {...defaultProps} />);
    const backLink = screen.getByText('Вернуться к списку заказов');
    expect(backLink.closest('a')).toHaveAttribute('href', '/profile/orders');
  });

  it('renders tracking number when available', () => {
    const orderWithTracking = {
      ...mockOrder,
      tracking_number: 'TRACK-123456',
    };
    render(<OrderDetail {...defaultProps} order={orderWithTracking} />);
    expect(screen.getByText('Номер отслеживания')).toBeInTheDocument();
    expect(screen.getByText('TRACK-123456')).toBeInTheDocument();
  });
});
