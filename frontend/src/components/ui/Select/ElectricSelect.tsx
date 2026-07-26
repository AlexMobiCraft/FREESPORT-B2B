/**
 * Electric Orange Select Component
 *
 * Выпадающий список в стиле Electric Orange
 * Features:
 * - Rectangular container (0deg) - like inputs
 * - Skewed dropdown items (-12deg) on hover
 * - Orange chevron when open
 * - Dark theme
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown, Check } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricSelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface ElectricSelectProps {
  /** Select options */
  options: ElectricSelectOption[];
  /** Current value */
  value?: string;
  /** Placeholder text */
  placeholder?: string;
  /** Change callback */
  onChange?: (value: string) => void;
  /** Disabled state */
  disabled?: boolean;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export const ElectricSelect = React.forwardRef<HTMLDivElement, ElectricSelectProps>(
  ({ options, value, placeholder = 'Выберите...', onChange, disabled = false, className }, ref) => {
    const [isOpen, setIsOpen] = useState(false);
    const internalRef = useRef<HTMLDivElement>(null);

    // Функция для объединения рефов
    const setRefs = (element: HTMLDivElement | null) => {
      internalRef.current = element;
      if (typeof ref === 'function') {
        ref(element);
      } else if (ref) {
        (ref as React.MutableRefObject<HTMLDivElement | null>).current = element;
      }
    };

    const selectedOption = options.find(opt => opt.value === value);

    // Close on outside click
    useEffect(() => {
      const handleClickOutside = (event: MouseEvent) => {
        if (internalRef.current && !internalRef.current.contains(event.target as Node)) {
          setIsOpen(false);
        }
      };

      document.addEventListener('mousedown', handleClickOutside);
      return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    const handleSelect = (optionValue: string) => {
      onChange?.(optionValue);
      setIsOpen(false);
    };

    return (
      <div ref={setRefs} className={cn('relative', className)}>
        {/* Trigger Button - Rectangular */}
        <button
          type="button"
          role="combobox"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-controls="electric-select-listbox"
          onClick={() => !disabled && setIsOpen(!isOpen)}
          disabled={disabled}
          className={cn(
            'w-full h-11 px-4',
            'flex items-center justify-between gap-2',
            'bg-transparent border border-[var(--border-default)]',
            'text-left font-inter text-sm',
            'transition-colors duration-200',
            disabled
              ? 'opacity-50 cursor-not-allowed'
              : 'hover:border-[var(--border-hover)] cursor-pointer',
            isOpen && 'border-[var(--color-primary)]',
            'focus:outline-none focus:border-[var(--color-primary)]'
          )}
        >
          <span
            className={
              selectedOption ? 'text-[var(--foreground)]' : 'text-[var(--color-text-muted)]'
            }
          >
            {selectedOption?.label || placeholder}
          </span>
          <ChevronDown
            className={cn(
              'w-4 h-4 transition-all duration-200',
              isOpen
                ? 'rotate-180 text-[var(--color-primary)]'
                : 'text-[var(--color-text-secondary)]'
            )}
          />
        </button>

        {/* Dropdown Menu */}
        {isOpen && (
          <div
            id="electric-select-listbox"
            role="listbox"
            className={cn(
              'absolute top-full left-0 right-0 z-50 mt-1',
              'bg-[var(--bg-card)] border border-[var(--border-default)]',
              'max-h-60 overflow-y-auto',
              'animate-fadeIn'
            )}
          >
            {options.map(option => (
              <button
                key={option.value}
                role="option"
                aria-selected={value === option.value}
                onClick={() => !option.disabled && handleSelect(option.value)}
                disabled={option.disabled}
                className={cn(
                  'w-full px-4 py-3',
                  'flex items-center justify-between gap-2',
                  'text-left text-sm',
                  'transition-all duration-200',
                  option.disabled
                    ? 'opacity-50 cursor-not-allowed text-[var(--color-text-muted)]'
                    : 'text-[var(--color-text-secondary)] hover:text-[var(--foreground)] hover:bg-[var(--bg-card-hover)] hover:pl-5',
                  option.value === value &&
                    'text-[var(--color-primary)] bg-[var(--color-primary-subtle)]'
                )}
              >
                {/* Skewed highlight on hover is simulated via padding shift */}
                <span>{option.label}</span>
                {option.value === value && (
                  <Check className="w-4 h-4 text-[var(--color-primary)]" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    );
  }
);

ElectricSelect.displayName = 'ElectricSelect';

export default ElectricSelect;
