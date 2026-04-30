/**
 * Button Component
 * Базовый компонент кнопки согласно FREESPORT Design System
 *
 * @see frontend/docs/design-system.json#components.Button
 */

import React from 'react';
import { cn } from '@/utils/cn';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  /** Вариант кнопки */
  variant?: 'primary' | 'secondary' | 'tertiary' | 'subtle' | 'danger';
  /** Размер кнопки */
  size?: 'small' | 'medium' | 'large';
  /** Состояние загрузки */
  loading?: boolean;
  /** Дочерние элементы */
  children: React.ReactNode;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'medium',
      loading = false,
      className,
      children,
      disabled,
      ...props
    },
    ref
  ) => {
    const isDisabled = disabled || loading;

    return (
      <button
        ref={ref}
        className={cn(
          // Базовые стили
          'inline-flex items-center justify-center gap-2',
          'font-medium transition-all',
          'focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',

          // Варианты
          variant === 'primary' && [
            'bg-primary text-white border border-transparent',
            'shadow-primary',
            'hover:bg-primary-hover hover:-translate-y-0.5',
            'active:bg-primary-active active:translate-y-0',
            'focus:ring-primary',
          ],
          variant === 'secondary' && [
            'bg-neutral-100 text-primary border border-primary',
            'shadow-default',
            'hover:bg-primary hover:text-white hover:-translate-y-0.5 hover:shadow-hover',
            'active:bg-primary-active active:translate-y-0',
            'focus:ring-primary',
          ],
          variant === 'tertiary' && [
            'bg-transparent text-primary',
            'hover:bg-primary-subtle hover:-translate-y-0.5',
            'active:translate-y-0',
          ],
          variant === 'subtle' && [
            'bg-primary-subtle text-primary',
            'shadow-default',
            'hover:bg-primary-subtle/80 hover:-translate-y-0.5',
            'active:translate-y-0',
          ],
          variant === 'danger' && [
            'bg-accent-danger text-white',
            'shadow-primary',
            'hover:bg-[#d32f2f] hover:-translate-y-0.5',
            'active:bg-[#b71c1c] active:translate-y-0',
            'focus:ring-accent-danger',
          ],

          // Размеры
          size === 'small' && 'h-10 px-6 typo-body-s rounded-2xl',
          size === 'medium' && 'h-11 px-6 typo-body-m rounded-2xl',
          size === 'large' && 'h-12 px-6 typo-body-l rounded-2xl',

          className
        )}
        disabled={isDisabled}
        {...props}
      >
        {loading && (
          <svg
            className="animate-spin h-4 w-4"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
            />
          </svg>
        )}
        {children}
      </button>
    );
  }
);

Button.displayName = 'Button';

export default Button;
