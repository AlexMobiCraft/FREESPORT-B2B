/**
 * Spinner Component
 * Компонент загрузки с поддержкой разных размеров
 *
 * @see frontend/docs/design-system.json (implicit spinner component)
 */

import React from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '@/utils/cn';

export type SpinnerSize = 'small' | 'medium' | 'large';

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Размер спиннера */
  size?: SpinnerSize;
  /** Текст для aria-label */
  label?: string;
}

const sizeConfig: Record<SpinnerSize, string> = {
  small: 'w-4 h-4',
  medium: 'w-6 h-6',
  large: 'w-8 h-8',
};

export const Spinner = React.forwardRef<HTMLDivElement, SpinnerProps>(
  ({ size = 'medium', label = 'Loading', className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        role="status"
        aria-live="polite"
        aria-label={label}
        className={cn('flex items-center justify-center', className)}
        {...props}
      >
        {/* Edge Case: prefers-reduced-motion - статичная иконка */}
        <Loader2
          className={cn(
            sizeConfig[size],
            'text-primary',
            'animate-spin',
            // Edge Case: prefers-reduced-motion
            'motion-reduce:animate-none'
          )}
          aria-hidden="true"
        />
        <span className="sr-only">{label}</span>
      </div>
    );
  }
);

Spinner.displayName = 'Spinner';
