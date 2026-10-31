/**
 * AddressList Component - Список адресов доставки
 * Story 16.3: Управление адресами доставки
 *
 * Отображает:
 * - Grid карточек адресов
 * - Кнопку "Добавить адрес"
 * - Пустое состояние
 */

'use client';

import React from 'react';
import { Plus, MapPin } from 'lucide-react';
import { cn } from '@/utils/cn';
import { AddressCard } from '../AddressCard';
import type { Address } from '@/types/address';

export interface AddressListProps {
  /** Список адресов */
  addresses: Address[];
  /** Callback редактирования адреса */
  onEdit: (address: Address) => void;
  /** Callback удаления адреса */
  onDelete: (addressId: number) => void;
  /** Callback добавления нового адреса */
  onAddNew: () => void;
  /** ID адреса в процессе удаления (для optimistic UI) */
  deletingId?: number | null;
  /** Флаг загрузки */
  isLoading?: boolean;
}

/**
 * Компонент списка адресов
 */
export const AddressList: React.FC<AddressListProps> = ({
  addresses,
  onEdit,
  onDelete,
  onAddNew,
  deletingId = null,
  isLoading = false,
}) => {
  // Пустое состояние
  if (!isLoading && addresses.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 px-4">
        <div className="w-16 h-16 rounded-full bg-[var(--color-neutral-200)] flex items-center justify-center mb-4">
          <MapPin className="w-8 h-8 text-[var(--color-text-muted)]" />
        </div>
        <h3 className="text-[20px] leading-[28px] font-semibold text-[var(--color-text-primary)] mb-2">
          Нет сохранённых адресов
        </h3>
        <p className="text-[16px] leading-[24px] text-[var(--color-text-muted)] text-center mb-6 max-w-md">
          Добавьте адрес доставки, чтобы быстрее оформлять заказы
        </p>
        <button
          onClick={onAddNew}
          className={cn(
            'flex items-center gap-2 px-6 py-3',
            'bg-[var(--color-primary)] text-white',
            'rounded-md font-medium',
            'hover:bg-[var(--color-primary-hover)]',
            'transition-colors duration-150'
          )}
        >
          <Plus className="w-5 h-5" />
          Добавить адрес
        </button>
      </div>
    );
  }

  // Скелетон загрузки
  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {[1, 2].map(i => (
          <div
            key={i}
            className="bg-white rounded-[16px] p-6 shadow-[0_8px_24px_rgba(15,23,42,0.08)] animate-pulse"
          >
            <div className="h-6 bg-[var(--color-neutral-300)] rounded w-1/2 mb-4" />
            <div className="h-4 bg-[var(--color-neutral-300)] rounded w-1/3 mb-2" />
            <div className="h-4 bg-[var(--color-neutral-300)] rounded w-3/4 mb-4" />
            <div className="h-10 bg-[var(--color-neutral-300)] rounded w-full mt-4" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div>
      {/* Кнопка добавления */}
      <div className="mb-6">
        <button
          onClick={onAddNew}
          className={cn(
            'flex items-center gap-2 px-6 py-3',
            'bg-[var(--color-primary)] text-white',
            'rounded-md font-medium',
            'hover:bg-[var(--color-primary-hover)]',
            'transition-colors duration-150'
          )}
        >
          <Plus className="w-5 h-5" />
          Добавить адрес
        </button>
      </div>

      {/* Grid адресов */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {addresses.map(address => (
          <AddressCard
            key={address.id}
            address={address}
            onEdit={() => onEdit(address)}
            onDelete={() => onDelete(address.id)}
            isDeleting={deletingId === address.id}
          />
        ))}
      </div>
    </div>
  );
};

AddressList.displayName = 'AddressList';

export default AddressList;
