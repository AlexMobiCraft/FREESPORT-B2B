'use client';

import React from 'react';
import { MapPin, Check } from 'lucide-react';
import { cn } from '@/utils/cn';
import type { Address } from '@/types/address';

export interface AddressCardOptionProps {
  address: Address;
  selected: boolean;
  onSelect: (id: number) => void;
}

/**
 * Карточка-опция выбора сохранённого адреса в селекторе чекаута.
 *
 * Отличается от business/AddressCard: нет кнопок edit/delete (управление
 * адресами — на странице /profile/addresses), кликабельна целиком, имеет
 * radio-state выделения.
 */
export const AddressCardOption: React.FC<AddressCardOptionProps> = ({
  address,
  selected,
  onSelect,
}) => {
  const handleClick = () => onSelect(address.id);

  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={handleClick}
      data-testid="address-card-option"
      data-selected={selected ? 'true' : 'false'}
      className={cn(
        'group relative flex w-full flex-col items-start gap-2 rounded-lg border bg-[var(--bg-panel)] p-4 text-left',
        'transition-colors duration-150',
        selected
          ? 'border-primary bg-primary-subtle ring-1 ring-primary'
          : 'border-neutral-300 hover:border-primary/50'
      )}
    >
      <div className="flex w-full items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <MapPin
            className={cn('h-4 w-4 flex-shrink-0', selected ? 'text-primary' : 'text-neutral-500')}
            aria-hidden="true"
          />
          <span className="truncate text-sm font-semibold text-text-primary">
            {address.full_name || 'Без имени'}
          </span>
        </div>
        {address.is_default && (
          <span className="flex-shrink-0 rounded bg-primary-subtle px-2 py-0.5 text-xs font-medium text-primary">
            По умолчанию
          </span>
        )}
      </div>

      <p className="break-words text-sm text-text-secondary">{address.full_address}</p>

      {address.phone && <p className="text-xs text-text-muted">{address.phone}</p>}

      {selected && (
        <span
          className="absolute right-2 top-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary"
          aria-hidden="true"
        >
          <Check className="h-3 w-3 text-text-inverse" strokeWidth={3} />
        </span>
      )}
    </button>
  );
};

AddressCardOption.displayName = 'AddressCardOption';

export default AddressCardOption;
