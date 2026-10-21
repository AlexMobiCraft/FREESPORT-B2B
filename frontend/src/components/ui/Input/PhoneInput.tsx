'use client';

import React, { forwardRef, useCallback } from 'react';
import { Input, InputProps } from './Input';
import { getPhoneFormat, normalizePhoneInput } from '@/utils/validators/phone';

export interface PhoneInputProps extends InputProps {
  /**
   * Страна, по которой выбираются префикс и число цифр. Без пропа поле
   * работает как российское (+7): так его используют профиль, чекаут и адреса.
   */
  country?: string;
}

/**
 * PhoneInput Component
 * Специализированное поле ввода телефона с автоматическим префиксом страны
 */
export const PhoneInput = forwardRef<HTMLInputElement, PhoneInputProps>(
  ({ onChange, onFocus, country, ...props }, ref) => {
    const format = getPhoneFormat(country);

    const handleFocus = useCallback(
      (e: React.FocusEvent<HTMLInputElement>) => {
        const input = e.target;
        const value = input.value;

        // Если поле пустое, подставляем префикс страны
        if (!value) {
          input.value = format.prefix;
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
      [onChange, onFocus, format.prefix]
    );

    const handleChange = useCallback(
      (e: React.ChangeEvent<HTMLInputElement>) => {
        // Префикс не стирается, лишние символы отбрасываются, цифр не больше формата
        e.target.value = normalizePhoneInput(e.target.value, country);

        onChange?.(e);
      },
      [onChange, country]
    );

    return (
      <Input
        {...props}
        ref={ref}
        type="tel"
        onChange={handleChange}
        onFocus={handleFocus}
        placeholder={format.sample}
      />
    );
  }
);

PhoneInput.displayName = 'PhoneInput';
