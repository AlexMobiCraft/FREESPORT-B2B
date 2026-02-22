/**
 * OrderStatusBadge Component Tests
 * Story 16.2 - AC: 7
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { OrderStatusBadge } from './OrderStatusBadge';
import type { OrderStatus } from '@/types/order';

describe('OrderStatusBadge', () => {
  const statuses: { status: OrderStatus; expectedLabel: string }[] = [
    { status: 'pending', expectedLabel: 'Новый' },
    { status: 'confirmed', expectedLabel: 'Подтверждён' },
    { status: 'processing', expectedLabel: 'В обработке' },
    { status: 'shipped', expectedLabel: 'Отправлен' },
    { status: 'delivered', expectedLabel: 'Доставлен' },
    { status: 'cancelled', expectedLabel: 'Отменён' },
    { status: 'refunded', expectedLabel: 'Возвращён' },
  ];

  it.each(statuses)('renders correct label for $status status', ({ status, expectedLabel }) => {
    render(<OrderStatusBadge status={status} />);
    expect(screen.getByText(expectedLabel)).toBeInTheDocument();
  });

  it('applies custom className', () => {
    render(<OrderStatusBadge status="pending" className="custom-class" />);
    const badge = screen.getByText('Новый');
    expect(badge).toHaveClass('custom-class');
  });

  it('renders with correct base styles', () => {
    render(<OrderStatusBadge status="delivered" />);
    const badge = screen.getByText('Доставлен');
    expect(badge).toHaveClass('inline-flex', 'items-center', 'rounded-full');
  });

  it('renders icon with status badge', () => {
    render(<OrderStatusBadge status="delivered" />);
    const badge = screen.getByText('Доставлен');
    const icon = badge.querySelector('svg');
    expect(icon).toBeInTheDocument();
  });

  it('handles unknown status gracefully', () => {
    // @ts-expect-error - Testing unknown status
    render(<OrderStatusBadge status="unknown_status" />);
    expect(screen.getByText('unknown_status')).toBeInTheDocument();
  });
});
