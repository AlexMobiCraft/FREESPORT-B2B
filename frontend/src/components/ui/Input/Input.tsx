'use client';

/**
 * Input Component
 * Текстовое поле с поддержкой label, helper, error/success состояний
 *
 * @see frontend/docs/design-system.json#components.Input
 */

import React, { useState } from 'react';
import { AlertCircle, CheckCircle2, Eye, EyeOff } from 'lucide-react';
import { cn } from '@/utils/cn';

export interface InputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  /** Метка поля */
  label: string;
  /** Текст подсказки */
  helper?: string;
  /** Сообщение об ошибке */
  error?: string;
  /** Сообщение об успехе */
  success?: string;
  /** Иконка слева */
  icon?: React.ReactNode;
}

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    { label, helper, error, success, icon, className, disabled, id, type = 'text', ...props },
    ref
  ) => {
    // Edge Case: Если переданы одновременно error и success - приоритет у error
    const hasError = Boolean(error);
    const hasSuccess = Boolean(success) && !hasError;

    // State for password visibility toggle
    const [isPasswordVisible, setIsPasswordVisible] = useState(false);
    const isPasswordType = type === 'password';
    const currentType = isPasswordType ? (isPasswordVisible ? 'text' : 'password') : type;

    const inputId =
      id ||
      `input-${label
        .toLowerCase()
        .replace(/[^a-z0-9а-яё\s]/g, '')
        .trim()
        .replace(/\s+/g, '-')}`;

    const togglePasswordVisibility = () => {
      setIsPasswordVisible(prev => !prev);
    };

    return (
      <div className="w-full">
        {/* Label */}
        <label
          htmlFor={inputId}
          className={cn(
            'block text-body-s font-medium text-[var(--color-text-primary)] mb-1',
            // Edge Case: Label длиннее 50 символов - перенос
            label.length > 50 && 'whitespace-normal break-words'
          )}
        >
          {label}
        </label>

        {/* Input Container */}
        <div className="relative">
          {/* Icon (если передан) */}
          {icon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--color-neutral-600)] w-5 h-5 flex items-center justify-center pointer-events-none">
              {icon}
            </div>
          )}

          {/* Input */}
          <input
            ref={ref}
            id={inputId}
            type={currentType}
            className={cn(
              // Базовые стили
              'w-full h-10 px-4 rounded-sm',
              'text-body-m text-[var(--color-text-primary)]',
              'bg-[var(--color-neutral-100)]',
              'border border-[var(--color-neutral-400)]',
              'transition-colors duration-[var(--duration-short)]',
              'placeholder:text-[var(--color-neutral-500)] placeholder:truncate',
              'focus:outline-none focus:ring-4 focus:ring-primary/12 focus:outline-primary/60',

              // Edge Case: Иконка слева - добавляем отступ
              icon && 'pl-10',

              // Edge Case: Иконка справа (статус или пароль) - добавляем отступ
              (hasError || hasSuccess || isPasswordType) && 'pr-10',

              // Состояния
              hasError && [
                'border-[var(--color-accent-danger)]',
                'bg-[var(--color-accent-danger)]/8',
                'focus:ring-[var(--color-accent-danger)] focus:border-[var(--color-accent-danger)]',
              ],
              hasSuccess && [
                'border-[var(--color-accent-success)]',
                'focus:ring-[var(--color-accent-success)] focus:border-[var(--color-accent-success)]',
              ],

              // Disabled
              disabled && 'opacity-50 cursor-not-allowed bg-[var(--color-neutral-200)]',

              className
            )}
            disabled={disabled}
            aria-invalid={hasError}
            aria-describedby={
              hasError || hasSuccess || helper ? `${inputId}-description` : undefined
            }
            {...props}
          />

          {/* Right Icon Container */}
          <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center">
            {/* Password Toggle Button */}
            {isPasswordType && !disabled && (
              <button
                type="button"
                onClick={togglePasswordVisibility}
                className="text-[var(--color-neutral-600)] hover:text-[var(--color-text-primary)] focus:outline-none focus:text-[var(--color-text-primary)]"
                aria-label={isPasswordVisible ? 'Скрыть пароль' : 'Показать пароль'}
                tabIndex={-1} // Skip tab focus for better AX flow usually, or 0 if explicit nav needed
              >
                {isPasswordVisible ? (
                  <EyeOff className="w-5 h-5" aria-hidden="true" />
                ) : (
                  <Eye className="w-5 h-5" aria-hidden="true" />
                )}
              </button>
            )}

            {/* Error/Success Icons (только если не поле пароля, чтобы не перекрывать глаз) */}
            {/* Если нужно и то и то, то нужно двигать глаз левее или статус убирать. 
                Обычно статус важнее, но в пароле важнее глаз. 
                Решение: Если это пароль, не показываем иконки статуса внутри поля, 
                или показываем их, но смещаем глаз. 
                В данном дизайне просто скроем статус иконки для пароля, 
                так как подсветка рамки и текст ошибки уже есть.
            */}
            {!isPasswordType && (hasError || hasSuccess) && (
              <>
                {hasError && (
                  <AlertCircle
                    className="w-5 h-5 text-[var(--color-accent-danger)]"
                    aria-hidden="true"
                  />
                )}
                {hasSuccess && (
                  <CheckCircle2
                    className="w-5 h-5 text-[var(--color-accent-success)]"
                    aria-hidden="true"
                  />
                )}
              </>
            )}
          </div>
        </div>

        {/* Helper/Error/Success Text */}
        {(helper || error || success) && (
          <p
            id={`${inputId}-description`}
            className={cn(
              'mt-1 text-caption',
              // Edge Case: Текст длиннее 100 символов - перенос на несколько строк
              (helper && helper.length > 100) ||
                (error && error.length > 100) ||
                (success && success.length > 100)
                ? 'whitespace-normal break-words'
                : '',
              hasError && 'text-[var(--color-accent-danger)]',
              hasSuccess && 'text-[var(--color-accent-success)]',
              !hasError && !hasSuccess && 'text-[var(--color-text-muted)]'
            )}
          >
            {error || success || helper}
          </p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
