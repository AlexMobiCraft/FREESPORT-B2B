/**
 * OrderCard Component Tests
 * Story 16.2 - AC: 7
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OrderCard } from './OrderCard';
import type { OrderListItem } from '@/types/order';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockOrder: OrderListItem = {
  id: 1,
  order_number: '0462026007',
  user: 1,
  customer_display_name: 'Иван Иванов',
  status: 'pending',
  total_amount: '15000',
  delivery_method: 'courier',
  payment_method: 'card',
  payment_status: 'pending',
  is_master: true,
  vat_group: null,
  sent_to_1c: false,
  created_at: '2025-01-15T10:30:00Z',
  total_items: 3,
};

describe('OrderCard', () => {
  it('renders order number correctly', () => {
    render(<OrderCard order={mockOrder} />);
    expect(screen.getByText('Заказ №4620-26007')).toBeInTheDocument();
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
