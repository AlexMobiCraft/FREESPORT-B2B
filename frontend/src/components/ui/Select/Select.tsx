/**
 * Select Component
 * Нативный select со стилизованной стрелкой
 *
 * @see frontend/docs/design-system.json#components.Select
 */

import React from 'react';
import { ChevronDown } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'size'> {
  /** Метка поля */
  label: string;
  /** Плейсхолдер */
  placeholder?: string;
  /** Опции выбора */
  options: SelectOption[];
  /** Текст подсказки */
  helper?: string;
  /** Сообщение об ошибке */
  error?: string;
}

export const Select = React.forwardRef<HTMLSelectElement, SelectProps>(
  (
    { label, placeholder, options, helper, error, className, disabled, id, onChange, ...props },
    ref
  ) => {
    const selectId = id || `select-${label.toLowerCase().replace(/\s+/g, '-')}`;
    const hasError = Boolean(error);

    // Обработчик onChange с защитой от двойных вызовов
    const handleChange = React.useCallback(
      (e: React.ChangeEvent<HTMLSelectElement>) => {
        onChange?.(e);
      },
      [onChange]
    );

    return (
      <div className="w-full">
        {/* Label */}
        <label htmlFor={selectId} className="block text-body-s font-medium text-text-primary mb-1">
          {label}
        </label>

        {/* Select Container */}
        <div className="relative">
          <select
            ref={ref}
            id={selectId}
            className={cn(
              // Базовые стили
              'w-full h-10 px-4 pr-10 rounded-sm',
              'text-body-m text-text-primary',
              'bg-neutral-100',
              'border border-neutral-400',
              'transition-colors duration-short',
              'appearance-none', // Убираем нативную стрелку
              'focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary',

              // Состояния
              hasError && [
                'border-accent-danger',
                'bg-accent-danger/8',
                'focus:ring-accent-danger focus:border-accent-danger',
              ],

              // Disabled
              disabled && 'opacity-50 cursor-not-allowed bg-neutral-200',

              className
            )}
            disabled={disabled}
            aria-invalid={hasError}
            aria-describedby={hasError || helper ? `${selectId}-description` : undefined}
            onChange={handleChange}
            {...props}
          >
            {placeholder && (
              <option value="" disabled>
                {placeholder}
              </option>
            )}
            {/* Edge Case: Если опций больше 10 - браузер добавит scroll автоматически */}
            {options.map(option => (
              <option
                key={option.value}
                value={option.value}
                className="truncate" // Edge Case: Обрезка длинного текста
              >
                {option.label}
              </option>
            ))}
          </select>

          {/* Стилизованная стрелка */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none">
            <ChevronDown className="w-5 h-5 text-neutral-600" aria-hidden="true" />
          </div>
        </div>

        {/* Helper/Error Text */}
        {(helper || error) && (
          <p
            id={`${selectId}-description`}
            className={cn('mt-1 text-caption', hasError ? 'text-accent-danger' : 'text-text-muted')}
          >
            {error || helper}
          </p>
        )}
      </div>
    );
  }
);

Select.displayName = 'Select';
