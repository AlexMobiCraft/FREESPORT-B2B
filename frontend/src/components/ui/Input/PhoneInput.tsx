'use client';

import React, { forwardRef, useCallback } from 'react';
import { Input, InputProps } from './Input';

/**
 * PhoneInput Component
 * Специализированное поле ввода телефона с автоматическим префиксом +7
 */
export const PhoneInput = forwardRef<HTMLInputElement, InputProps>(
  ({ onChange, onFocus, ...props }, ref) => {
    const handleFocus = useCallback(
      (e: React.FocusEvent<HTMLInputElement>) => {
        const input = e.target;
        const value = input.value;

        // Если поле пустое, подставляем +7
        if (!value) {
          input.value = '+7';
          // Уведомляем react-hook-form об изменении
          const event = {
            target: input,
            type: 'change',
          } as React.ChangeEvent<HTMLInputElement>;
          onChange?.(event);
        }

        // Вызываем оригинальный onFocus если есть
        onFocus?.(e);

        // Устанавливаем курсор в конец (с небольшой задержкой, чтобы браузер успел сфокусироваться)
        setTimeout(() => {
          const length = input.value.length;
          input.setSelectionRange(length, length);
        }, 0);
      },
      [onChange, onFocus]
    );

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        let value = e.target.value;

        // Если пользователь пытается удалить +7 полностью
        if (!value.startsWith('+7')) {
          // Если ввел 8 или 7 в начале, заменяем на +7
          if (value.startsWith('8') || value.startsWith('7')) {
            value = '+7' + value.slice(1);
          } else if (value === '' || value === '+') {
            value = '+7';
          } else {
            // Если ввел что-то другое, принудительно добавляем +7
            value = '+7' + value.replace(/^\+?/, '');
          }
        }

        // Ограничиваем только цифрами после +7
        const prefix = '+7';
        const rest = value.slice(prefix.length).replace(/\D/g, '').slice(0, 10);
        e.target.value = prefix + rest;

        onChange?.(e);
      },
      [onChange]
    );

    return (
      <Input
        {...props}
        ref={ref}
        type="tel"
        onChange={handleChange}
        onFocus={handleFocus}
        placeholder="+79001234567"
      />
    );
  }
);

PhoneInput.displayName = 'PhoneInput';
