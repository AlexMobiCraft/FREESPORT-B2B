/**
 * AddressCard Component Tests
 * Story 16.3: Управление адресами доставки
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AddressCard } from './AddressCard';
import type { Address } from '@/types/address';

const mockAddress: Address = {
  id: 1,
  address_type: 'shipping',
  full_name: 'Иван Иванов',
  phone: '+79001234567',
  city: 'Москва',
  street: 'Тверская',
  building: '12',
  building_section: '',
  apartment: '45',
  postal_code: '123456',
  is_default: true,
  full_address: '123456, Москва, Тверская 12, кв. 45',
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

describe('AddressCard', () => {
  const mockOnEdit = vi.fn();
  const mockOnDelete = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ARRANGE, ACT, ASSERT pattern

  it('renders address information correctly', () => {
    // ARRANGE
    render(<AddressCard address={mockAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ASSERT
    expect(screen.getByText('Иван Иванов')).toBeInTheDocument();
    expect(screen.getByText('+79001234567')).toBeInTheDocument();
    expect(screen.getByText('123456, Москва, Тверская 12, кв. 45')).toBeInTheDocument();
  });

  it('displays default badge when is_default is true', () => {
    // ARRANGE
    render(<AddressCard address={mockAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ASSERT
    expect(screen.getByTestId('default-badge')).toBeInTheDocument();
    expect(screen.getByText('По умолчанию')).toBeInTheDocument();
  });

  it('does not display default badge when is_default is false', () => {
    // ARRANGE
    const nonDefaultAddress = { ...mockAddress, is_default: false };
    render(<AddressCard address={nonDefaultAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ASSERT
    expect(screen.queryByTestId('default-badge')).not.toBeInTheDocument();
  });

  it('calls onEdit when edit button is clicked', () => {
    // ARRANGE
    render(<AddressCard address={mockAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ACT
    const editButton = screen.getByRole('button', { name: /редактировать/i });
    fireEvent.click(editButton);

    // ASSERT
    expect(mockOnEdit).toHaveBeenCalledTimes(1);
  });

  it('calls onDelete when delete button is clicked', () => {
    // ARRANGE
    render(<AddressCard address={mockAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ACT
    const deleteButton = screen.getByRole('button', { name: /удалить/i });
    fireEvent.click(deleteButton);

    // ASSERT
    expect(mockOnDelete).toHaveBeenCalledTimes(1);
  });

  it('displays address type correctly for shipping', () => {
    // ARRANGE
    render(<AddressCard address={mockAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ASSERT
    expect(screen.getByText('Адрес доставки')).toBeInTheDocument();
  });

  it('displays address type correctly for legal', () => {
    // ARRANGE
    const legalAddress = { ...mockAddress, address_type: 'legal' as const };
    render(<AddressCard address={legalAddress} onEdit={mockOnEdit} onDelete={mockOnDelete} />);

    // ASSERT
    expect(screen.getByText('Юридический адрес')).toBeInTheDocument();
  });

  it('applies opacity when isDeleting is true', () => {
    // ARRANGE
    render(
      <AddressCard
        address={mockAddress}
        onEdit={mockOnEdit}
        onDelete={mockOnDelete}
        isDeleting={true}
      />
    );

    // ASSERT
    const card = screen.getByTestId('address-card');
    expect(card).toHaveClass('opacity-50');
  });
});
