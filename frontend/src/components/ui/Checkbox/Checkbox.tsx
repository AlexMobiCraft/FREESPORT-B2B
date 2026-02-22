/**
 * Checkbox Component
 * Square чекбокс с анимацией масштаба и иконкой Check
 *
 * @see frontend/docs/design-system.json#components.Checkbox
 */

import React from 'react';
import { Check, Minus } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface CheckboxProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type' | 'size'> {
  /** Метка */
  label?: string;
  /** Indeterminate состояние (для "select all") */
  indeterminate?: boolean;
}

export const Checkbox = React.forwardRef<HTMLInputElement, CheckboxProps>(
  ({ label, indeterminate = false, checked, disabled, className, id, ...props }, ref) => {
    const checkboxId = id || `checkbox-${label?.toLowerCase().replace(/\s+/g, '-') || 'item'}`;

    // Обработка indeterminate состояния
    React.useEffect(() => {
      if (ref && typeof ref === 'object' && ref.current) {
        ref.current.indeterminate = indeterminate;
      }
    }, [ref, indeterminate]);

    return (
      <div className="inline-flex items-start gap-3">
        <div className="relative flex items-center">
          {/* Native Checkbox (hidden) */}
          <input
            ref={ref}
            id={checkboxId}
            type="checkbox"
            checked={checked}
            disabled={disabled}
            className="sr-only peer"
            {...props}
          />

          {/* Custom Checkbox Box */}
          <label
            htmlFor={checkboxId}
            className={cn(
              // Базовые стили
              'relative flex items-center justify-center',
              'w-5 h-5 rounded-sm', // 6px radius
              'border-[1.5px] border-[#B9C3D6]', // Design System v2.0 border
              'bg-white',
              'cursor-pointer',
              'transition-all duration-[180ms]', // Design System v2.0 timing

              // States
              'peer-focus:ring-2 peer-focus:ring-primary/12 peer-focus:ring-offset-2',

              // Checked state
              'peer-checked:bg-primary peer-checked:border-primary',
              'peer-checked:scale-100',

              // Hover state
              'peer-hover:border-primary-hover',

              // Indeterminate state
              indeterminate && 'bg-primary border-primary',

              // Disabled state
              disabled && 'opacity-50 cursor-not-allowed',

              // Edge Case: prefers-reduced-motion
              'motion-reduce:transition-none',

              className
            )}
          >
            {/* Check Icon - Design System v2.0: 18px, strokeWidth 3 */}
            {checked && !indeterminate && (
              <Check
                className={cn(
                  'w-[18px] h-[18px] text-white',
                  'scale-100 transition-transform duration-[180ms]',
                  'motion-reduce:transition-none'
                )}
                strokeWidth={3}
                aria-hidden="true"
              />
            )}

            {/* Indeterminate Icon */}
            {indeterminate && (
              <Minus className="w-[18px] h-[18px] text-white" strokeWidth={3} aria-hidden="true" />
            )}
          </label>
        </div>

        {/* Label */}
        {label && (
          <label
            htmlFor={checkboxId}
            className={cn(
              'text-body-m text-text-primary select-none',
              disabled ? 'cursor-not-allowed opacity-50' : 'cursor-pointer'
            )}
          >
            {label}
          </label>
        )}
      </div>
    );
  }
);

Checkbox.displayName = 'Checkbox';
