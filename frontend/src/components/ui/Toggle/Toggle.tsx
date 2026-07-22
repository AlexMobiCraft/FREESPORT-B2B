/**
 * Toggle (Switch) Component
 * Switch с плавным движением бегунка
 *
 * @see frontend/docs/design-system.json#components.Toggle
 */

import React from 'react';
import { cn } from '@/utils/cn';

export interface ToggleProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
  /** Метка */
  label?: string;
}

export const Toggle = React.forwardRef<HTMLInputElement, ToggleProps>(
  ({ label, checked, disabled, className, id, onChange, ...props }, ref) => {
    const toggleId = id || `toggle-${label?.toLowerCase().replace(/\s+/g, '-') || 'switch'}`;

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (!disabled && onChange) {
        onChange(e);
      }
    };

    return (
      <div className="inline-flex items-center gap-3">
        <div className="relative">
          {/* Native Checkbox (hidden) */}
          <input
            ref={ref}
            id={toggleId}
            type="checkbox"
            role="switch"
            checked={checked}
            disabled={disabled}
            aria-checked={checked ? 'true' : 'false'}
            aria-label={label}
            className="sr-only peer"
            onChange={handleChange}
            {...props}
          />

          {/* Toggle Track */}
          <label
            htmlFor={toggleId}
            className={cn(
              // Track (контейнер)
              'relative block',
              'w-11 h-6 rounded-full', // 44x24px, radius 999
              'cursor-pointer',
              'transition-colors duration-[180ms]', // Design System v2.0 timing
              '[transition-timing-function:cubic-bezier(0.4,0,0.2,1)]', // Design System v2.0 easing

              // Unchecked state
              'bg-neutral-300',

              // Checked state
              'peer-checked:bg-primary',

              // Focus state
              'peer-focus:ring-2 peer-focus:ring-primary peer-focus:ring-offset-2',

              // Disabled state
              disabled && 'opacity-50 cursor-not-allowed',

              // Edge Case: prefers-reduced-motion
              'motion-reduce:transition-none',

              className
            )}
          >
            {/* Toggle Thumb (бегунок) - Design System v2.0 */}
            <span
              className={cn(
                // Thumb
                'absolute top-0.5 left-0.5',
                'w-5 h-5', // 20px
                'bg-white rounded-full', // #FFFFFF
                'shadow-[0_2px_8px_rgba(0,0,0,0.16)]', // Design System v2.0 shadow
                'transition-transform duration-[180ms]', // Design System v2.0 timing
                '[transition-timing-function:cubic-bezier(0.4,0,0.2,1)]', // Design System v2.0 easing

                // Checked state - движение вправо (22px from left)
                checked && 'translate-x-5',

                // Edge Case: prefers-reduced-motion
                'motion-reduce:transition-none'
              )}
            />
          </label>
        </div>

        {/* Label */}
        {label && (
          <label
            htmlFor={toggleId}
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

Toggle.displayName = 'Toggle';
