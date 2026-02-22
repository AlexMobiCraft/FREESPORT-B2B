/**
 * OrderCard Component Tests
 * Story 16.2 - AC: 7
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OrderCard } from './OrderCard';
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
  total_amount: '15000',
  discount_amount: '0',
  delivery_cost: '500',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1',
  delivery_method: 'courier',
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'pending',
  payment_id: '',
  notes: '',
  created_at: '2025-01-15T10:30:00Z',
  updated_at: '2025-01-15T10:30:00Z',
  items: [
    {
      id: 1,
      product: 101,
      product_name: 'Товар 1',
      product_sku: 'SKU-001',
      quantity: 2,
      unit_price: '5000',
      total_price: '10000',
      variant: null,
      variant_info: '',
    },
    {
      id: 2,
      product: 102,
      product_name: 'Товар 2',
      product_sku: 'SKU-002',
      quantity: 1,
      unit_price: '5000',
      total_price: '5000',
      variant: null,
      variant_info: '',
    },
  ],
  subtotal: '15000',
  total_items: 3,
  calculated_total: '15500',
  can_be_cancelled: true,
};

describe('OrderCard', () => {
  it('renders order number correctly', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText('Заказ №ORD-2025-001')).toBeInTheDocument();
  });

  it('renders formatted date', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText(/15 января 2025/i)).toBeInTheDocument();
  });

  it('renders order status badge', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText('Новый')).toBeInTheDocument();
  });

  it('renders items count with correct declension', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText(/3 товара/i)).toBeInTheDocument();
  });

  it('renders formatted total amount', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText(/15[\s\u00A0]?000/)).toBeInTheDocument();
  });

  it('links to order detail page', () => {
    render(<OrderCard order={mockOrder} />);
    const link = screen.getByRole('link');
    expect(link).toHaveAttribute('href', '/profile/orders/1');
  });

  it('applies hover class to card', () => {
    render(<OrderCard order={mockOrder} />);
    const card = screen.getByRole('link').firstChild;
    expect(card).toHaveClass('group');
  });

  it('renders different statuses correctly', () => {
    const deliveredOrder = { ...mockOrder, status: 'delivered' as const };
    render(<OrderCard order={deliveredOrder} />);
    expect(screen.getByText('Доставлен')).toBeInTheDocument();
  });
});
