/**
 * OrdersList Component Tests
 * Story 16.2 - AC: 7
 */

import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OrdersList } from './OrdersList';
import type { Order } from '@/types/order';

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

const mockOrders: Order[] = [
  {
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
    delivery_address: 'г. Москва',
    delivery_method: 'courier',
    delivery_date: null,
    tracking_number: '',
    payment_method: 'card',
    payment_status: 'pending',
    payment_id: '',
    notes: '',
    created_at: '2025-01-15T10:30:00Z',
    updated_at: '2025-01-15T10:30:00Z',
    items: [],
    subtotal: '15000',
    total_items: 3,
    calculated_total: '15500',
    can_be_cancelled: true,
  },
  {
    id: 2,
    order_number: 'ORD-2025-002',
    user: 1,
    customer_display_name: 'Иван Иванов',
    customer_name: 'Иван Иванов',
    customer_email: 'ivan@example.com',
    customer_phone: '+7 999 123 45 67',
    status: 'delivered',
    total_amount: '25000',
    discount_amount: '1000',
    delivery_cost: '0',
    delivery_address: 'г. Санкт-Петербург',
    delivery_method: 'pickup',
    delivery_date: '2025-01-20',
    tracking_number: 'TRK123',
    payment_method: 'card',
    payment_status: 'paid',
    payment_id: 'PAY123',
    notes: '',
    created_at: '2025-01-10T14:00:00Z',
    updated_at: '2025-01-20T16:00:00Z',
    items: [],
    subtotal: '26000',
    total_items: 5,
    calculated_total: '25000',
    can_be_cancelled: false,
  },
];

describe('OrdersList', () => {
  const defaultProps = {
    orders: mockOrders,
    currentPage: 1,
    totalPages: 3,
    totalCount: 50,
    onPageChange: vi.fn(),
    statusFilter: 'all' as const,
    onStatusFilterChange: vi.fn(),
  };

  it('renders list of orders', () => {
    render(<OrdersList {...defaultProps} />);
    expect(screen.getByText('Заказ №ORD-2025-001')).toBeInTheDocument();
    expect(screen.getByText('Заказ №ORD-2025-002')).toBeInTheDocument();
  });

  it('renders total count', () => {
    render(<OrdersList {...defaultProps} />);
    expect(screen.getByText('Найдено заказов: 50')).toBeInTheDocument();
  });

  it('renders status filter tabs', () => {
    render(<OrdersList {...defaultProps} />);
    expect(screen.getByText('Все')).toBeInTheDocument();
    expect(screen.getByText('Новые')).toBeInTheDocument();
    expect(screen.getByText('В обработке')).toBeInTheDocument();
    expect(screen.getByText('Отправлены')).toBeInTheDocument();
    expect(screen.getByText('Доставлены')).toBeInTheDocument();
    expect(screen.getByText('Отменены')).toBeInTheDocument();
  });

  it('calls onStatusFilterChange when filter tab is clicked', () => {
    const onStatusFilterChange = vi.fn();
    render(<OrdersList {...defaultProps} onStatusFilterChange={onStatusFilterChange} />);
    fireEvent.click(screen.getByText('Доставлены'));
    expect(onStatusFilterChange).toHaveBeenCalledWith('delivered');
  });

  it('renders pagination when totalPages > 1', () => {
    render(<OrdersList {...defaultProps} />);
    expect(screen.getByRole('navigation', { name: 'Pagination' })).toBeInTheDocument();
  });

  it('does not render pagination when totalPages === 1', () => {
    render(<OrdersList {...defaultProps} totalPages={1} />);
    expect(screen.queryByRole('navigation', { name: 'Pagination' })).not.toBeInTheDocument();
  });

  it('calls onPageChange when pagination button is clicked', () => {
    const onPageChange = vi.fn();
    render(<OrdersList {...defaultProps} onPageChange={onPageChange} />);
    const nextButton = screen.getByLabelText('Следующая страница');
    fireEvent.click(nextButton);
    expect(onPageChange).toHaveBeenCalledWith(2);
  });

  it('renders empty state when no orders', () => {
    render(<OrdersList {...defaultProps} orders={[]} totalCount={0} />);
    expect(screen.getByText('У вас пока нет заказов')).toBeInTheDocument();
  });

  it('renders empty state with filter message when filtered', () => {
    render(<OrdersList {...defaultProps} orders={[]} totalCount={0} statusFilter="delivered" />);
    expect(screen.getByText('Нет заказов с выбранным статусом')).toBeInTheDocument();
  });

  it('renders loading state', () => {
    render(<OrdersList {...defaultProps} isLoading={true} />);
    expect(screen.getByRole('status')).toBeInTheDocument();
  });

  it('highlights active status filter', () => {
    render(<OrdersList {...defaultProps} statusFilter="pending" />);
    const activeButton = screen.getByText('Новые');
    expect(activeButton).toHaveClass('bg-primary');
  });
});
