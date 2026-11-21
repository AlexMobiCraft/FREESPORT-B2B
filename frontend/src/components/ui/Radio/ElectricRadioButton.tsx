/**
 * Electric Orange Radio Button Component
 *
 * Радио-кнопка в стиле Electric Orange
 * Features:
 * - Skewed diamond shape (-12deg)
 * - Orange inner dot when selected
 * - Straight label text
 * - Dark theme
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricRadioOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface ElectricRadioGroupProps {
  /** Radio options */
  options: ElectricRadioOption[];
  /** Group name */
  name: string;
  /** Current value */
  value?: string;
  /** Change callback */
  onChange?: (value: string) => void;
  /** Horizontal layout */
  horizontal?: boolean;
  /** Additional class names */
  className?: string;
}

export interface ElectricRadioButtonProps {
  /** Option value */
  value: string;
  /** Label text */
  label: string;
  /** Radio group name */
  name: string;
  /** Selected state */
  checked?: boolean;
  /** Disabled state */
  disabled?: boolean;
  /** Change callback */
  onChange?: (value: string) => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Radio Button Component
// ============================================

export function ElectricRadioButton({
  value,
  label,
  name,
  checked = false,
  disabled = false,
  onChange,
  className,
}: ElectricRadioButtonProps) {
  const handleClick = () => {
    if (!disabled && onChange) {
      onChange(value);
    }
  };

  return (
    <label
      className={cn(
        'flex items-center cursor-pointer select-none group',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={handleClick}
      onKeyDown={e => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          handleClick();
        }
      }}
    >
      {/* Hidden native input for accessibility */}
      <input
        type="radio"
        name={name}
        value={value}
        checked={checked}
        disabled={disabled}
        onChange={() => onChange?.(value)}
        className="sr-only"
      />

      {/* Skewed Checkbox Style (like Sidebar) */}
      <span
        className={cn(
          'w-5 h-5 mr-4 border-2 flex items-center justify-center',
          'transform -skew-x-12',
          'transition-all duration-200',
          checked
            ? 'bg-[var(--color-primary)] border-[var(--color-primary)]'
            : 'border-[var(--color-neutral-500)] group-hover:border-[var(--color-primary)]'
        )}
      >
        {/* Checkmark when selected */}
        {checked && <span className="text-black text-xs font-bold transform skew-x-12">✓</span>}
      </span>

      {/* Label - Straight */}
      <span className="text-[var(--color-text-secondary)] text-sm transition-colors group-hover:text-[var(--foreground)]">
        {label}
      </span>
    </label>
  );
}

ElectricRadioButton.displayName = 'ElectricRadioButton';

// ============================================
// Radio Group Component
// ============================================

export function ElectricRadioGroup({
  options,
  name,
  value,
  onChange,
  horizontal = false,
  className,
}: ElectricRadioGroupProps) {
  return (
    <div
      role="radiogroup"
      className={cn(horizontal ? 'flex flex-wrap gap-6' : 'flex flex-col gap-3', className)}
    >
      {options.map(option => (
        <ElectricRadioButton
          key={option.value}
          value={option.value}
          label={option.label}
          name={name}
          checked={value === option.value}
          disabled={option.disabled}
          onChange={onChange}
        />
      ))}
    </div>
  );
}

ElectricRadioGroup.displayName = 'ElectricRadioGroup';

export default ElectricRadioButton;
