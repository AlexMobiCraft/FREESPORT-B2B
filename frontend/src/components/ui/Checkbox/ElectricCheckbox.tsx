/**
 * Electric Orange Checkbox Component
 *
 * Custom checkbox with skewed geometry
 * Features:
 * - Skewed checkbox container (-12deg)
 * - Counter-skewed checkmark (12deg)
 * - Orange fill when checked
 * - Straight label text
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#checkbox
 */

'use client';

import React, { forwardRef } from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricCheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  /** Checkbox label */
  label?: string;
  /** Checkbox size */
  size?: 'sm' | 'md' | 'lg';
  /** Error state */
  error?: boolean;
}

// ============================================
// Size Configurations
// ============================================

const sizeStyles = {
  sm: { box: 'w-4 h-4', text: 'text-sm', check: 'text-[10px]' },
  md: { box: 'w-5 h-5', text: 'text-base', check: 'text-xs' },
  lg: { box: 'w-6 h-6', text: 'text-lg', check: 'text-sm' },
};

// ============================================
// Checkbox Component
// ============================================

export const ElectricCheckbox = forwardRef<HTMLInputElement, ElectricCheckboxProps>(
  (
    { label, size = 'md', error = false, className, checked, onChange, disabled, ...props },
    ref
  ) => {
    const styles = sizeStyles[size];

    return (
      <label
        className={cn(
          'inline-flex items-center cursor-pointer select-none group',
          disabled && 'opacity-50 cursor-not-allowed',
          className
        )}
      >
        {/* Hidden native checkbox */}
        <input
          ref={ref}
          type="checkbox"
          checked={checked}
          onChange={onChange}
          disabled={disabled}
          className="sr-only"
          {...props}
        />

        {/* Custom skewed checkbox */}
        <span
          className={cn(
            styles.box,
            'border-2 flex items-center justify-center mr-3',
            'transition-all duration-150',
            checked
              ? 'bg-[var(--color-primary)] border-[var(--color-primary)]'
              : error
                ? 'border-[var(--color-danger)] group-hover:border-[var(--color-danger)]'
                : 'border-[var(--color-neutral-500)] group-hover:border-[var(--color-primary)]'
          )}
          style={{ transform: 'skewX(-12deg)' }}
        >
          {checked && (
            <span
              className={cn(styles.check, 'text-black font-bold')}
              style={{ transform: 'skewX(12deg)' }}
            >
              ✓
            </span>
          )}
        </span>

        {/* Label - straight, no skew */}
        {label && (
          <span
            className={cn(
              styles.text,
              'transition-colors duration-150',
              error
                ? 'text-[var(--color-danger)]'
                : 'text-[var(--color-text-secondary)] group-hover:text-[var(--foreground)]'
            )}
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {label}
          </span>
        )}
      </label>
    );
  }
);

ElectricCheckbox.displayName = 'ElectricCheckbox';

export default ElectricCheckbox;
