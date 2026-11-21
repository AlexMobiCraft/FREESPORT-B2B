/**
 * Electric Orange Input Component
 *
 * Text input field for Electric Orange design system
 * Features:
 * - Rectangular geometry (NO skew - inputs stay straight)
 * - Dark transparent background
 * - Orange border on focus
 * - Error state with red border
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md#input
 */

'use client';

import React, { forwardRef } from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricInputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** Input size variant */
  size?: 'sm' | 'md' | 'lg';
  /** Error state */
  error?: boolean;
  /** Error message to display */
  errorMessage?: string;
  /** Label for the input */
  label?: string;
  /** Full width mode */
  fullWidth?: boolean;
}

// ============================================
// Size Configurations
// ============================================

const sizeStyles = {
  sm: 'h-9 px-3 text-sm',
  md: 'h-11 px-4 text-base',
  lg: 'h-13 px-5 text-lg',
};

// ============================================
// Input Component
// ============================================

export const ElectricInput = forwardRef<HTMLInputElement, ElectricInputProps>(
  (
    { size = 'md', error = false, errorMessage, label, fullWidth = false, className, id, ...props },
    ref
  ) => {
    const inputId = id || `input-${Math.random().toString(36).substr(2, 9)}`;

    return (
      <div className={cn('flex flex-col', fullWidth && 'w-full')}>
        {/* Label */}
        {label && (
          <label
            htmlFor={inputId}
            className="text-[var(--color-text-secondary)] text-sm mb-2"
            style={{ fontFamily: "'Inter', sans-serif" }}
          >
            {label}
          </label>
        )}

        {/* Input */}
        <input
          ref={ref}
          id={inputId}
          className={cn(
            // Base styles - Rectangular, NO skew
            'bg-transparent border text-[var(--foreground)]',
            'placeholder-[var(--color-text-muted)]',
            'transition-all duration-150',
            'outline-none',

            // Size
            sizeStyles[size],

            // States
            error
              ? 'border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-1 focus:ring-[var(--color-danger)]'
              : 'border-[var(--border-default)] hover:border-[var(--border-hover)] focus:border-[var(--color-primary)] focus:ring-1 focus:ring-[var(--color-primary)]',

            // Disabled
            'disabled:opacity-50 disabled:cursor-not-allowed',

            // Full width
            fullWidth && 'w-full',

            className
          )}
          style={{ fontFamily: "'Inter', sans-serif" }}
          {...props}
        />

        {/* Error Message */}
        {error && errorMessage && (
          <p className="text-[var(--color-danger)] text-sm mt-1">{errorMessage}</p>
        )}
      </div>
    );
  }
);

ElectricInput.displayName = 'ElectricInput';

export default ElectricInput;
