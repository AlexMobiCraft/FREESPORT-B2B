/**
 * AddressCard Component - Карточка адреса доставки
 * Story 16.3: Управление адресами доставки
 *
 * Отображает:
 * - Имя получателя
 * - Телефон
 * - Полный адрес
 * - Бейдж "По умолчанию"
 * - Кнопки редактирования и удаления
 */

'use client';

import React from 'react';
import { MapPin, Pencil, Trash2 } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { Address } from '@/types/address';

export interface AddressCardProps {
  /** Данные адреса */
  address: Address;
  /** Callback редактирования */
  onEdit: () => void;
  /** Callback удаления */
  onDelete: () => void;
  /** Флаг состояния удаления (для optimistic UI) */
  isDeleting?: boolean;
}

/**
 * Компонент карточки адреса
 */
export const AddressCard: React.FC<AddressCardProps> = ({
  address,
  onEdit,
  onDelete,
  isDeleting = false,
}) => {
  return (
    <div
      className={cn(
        'bg-white rounded-[16px] p-6',
        'shadow-[0_8px_24px_rgba(15,23,42,0.08)]',
        'hover:shadow-[0_10px_32px_rgba(15,23,42,0.12)]',
        'transition-all duration-200',
        isDeleting && 'opacity-50 pointer-events-none'
      )}
      data-testid="address-card"
    >
      {/* Header с бейджем */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-2">
          <MapPin className="w-5 h-5 text-[var(--color-primary)]" />
          <span className="text-[20px] leading-[28px] font-semibold text-[var(--color-text-primary)]">
            {address.full_name}
          </span>
        </div>
        {address.is_default && (
          <span
            className={cn(
              'px-3 py-1 rounded-full',
              'bg-[var(--color-neutral-200)] text-[var(--color-neutral-700)]',
              'text-[12px] font-medium'
            )}
            data-testid="default-badge"
          >
            По умолчанию
          </span>
        )}
      </div>

      {/* Телефон */}
      <p className="text-[14px] leading-[20px] text-[var(--color-text-secondary)] mb-2">
        {address.phone}
      </p>

      {/* Полный адрес */}
      <p className="text-[16px] leading-[24px] text-[var(--color-text-primary)] mb-4">
        {address.full_address}
      </p>

      {/* Тип адреса */}
      <p className="text-[12px] leading-[16px] text-[var(--color-text-muted)] mb-4">
        {address.address_type === 'shipping' ? 'Адрес доставки' : 'Юридический адрес'}
      </p>

      {/* Кнопки действий */}
      <div className="flex items-center gap-3 pt-4 border-t border-[var(--color-neutral-300)]">
        <button
          onClick={onEdit}
          className={cn(
            'flex items-center gap-2 px-4 py-2',
            'text-[14px] font-medium text-[var(--color-primary)]',
            'hover:bg-[var(--color-primary-subtle)] rounded-md',
            'transition-colors duration-150'
          )}
          aria-label="Редактировать адрес"
        >
          <Pencil className="w-4 h-4" />
          Редактировать
        </button>
        <button
          onClick={onDelete}
          className={cn(
            'flex items-center gap-2 px-4 py-2',
            'text-[14px] font-medium text-[var(--color-accent-danger)]',
            'hover:bg-[var(--color-accent-danger-bg)] rounded-md',
            'transition-colors duration-150'
          )}
          aria-label="Удалить адрес"
        >
          <Trash2 className="w-4 h-4" />
          Удалить
        </button>
      </div>
    </div>
  );
};

AddressCard.displayName = 'AddressCard';

export default AddressCard;
