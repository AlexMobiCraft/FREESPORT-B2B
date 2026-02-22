'use client';

/**
 * QuantitySelector - компонент выбора количества товара
 *
 * Поддерживает:
 * - Кнопки +/- для изменения значения
 * - Ручной ввод с debounce (300ms)
 * - Валидация границ (min/max)
 * - Loading state при обновлении
 * - Accessibility (role="spinbutton", aria-атрибуты)
 *
 * @see Story 26.2: Cart Item Card Component (AC: 4-5, 8, 10-11)
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { Minus, Plus, Loader2 } from 'lucide-react';

/**
 * Props для QuantitySelector
 */
interface QuantitySelectorProps {
  /** Текущее значение количества */
  value: number;
  /** Минимальное значение (по умолчанию 1) */
  min?: number;
  /** Максимальное значение (по умолчанию 99) */
  max?: number;
  /** Callback при изменении значения */
  onChange: (value: number) => void;
  /** Индикатор загрузки */
  isLoading?: boolean;
  /** Отключение компонента */
  disabled?: boolean;
}

/**
 * Компонент выбора количества товара
 *
 * Функции:
 * - Кнопка "-": уменьшить quantity (disabled при value <= min)
 * - Input: отображение и ручной ввод quantity с debounce 300ms
 * - Кнопка "+": увеличить quantity (disabled при value >= max)
 * - Loading state: spinner на активной кнопке при isLoading
 */
export function QuantitySelector({
  value,
  min = 1,
  max = 99,
  onChange,
  isLoading = false,
  disabled = false,
}: QuantitySelectorProps) {
  // Внутреннее состояние для input (для debounce)
  const [inputValue, setInputValue] = useState<string>(String(value));
  // Ref для отслеживания какая кнопка была нажата (для отображения spinner)
  const [lastAction, setLastAction] = useState<'increment' | 'decrement' | null>(null);
  // Ref для debounce таймера
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Синхронизация внутреннего значения с внешним
  useEffect(() => {
    setInputValue(String(value));
  }, [value]);

  // Очистка таймера при размонтировании
  useEffect(() => {
    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  /**
   * Валидация и ограничение значения в пределах min/max
   */
  const clampValue = useCallback(
    (val: number): number => {
      return Math.min(Math.max(val, min), max);
    },
    [min, max]
  );

  /**
   * Обработчик уменьшения количества
   */
  const handleDecrement = () => {
    if (value <= min || isLoading || disabled) return;
    setLastAction('decrement');
    onChange(value - 1);
  };

  /**
   * Обработчик увеличения количества
   */
  const handleIncrement = () => {
    if (value >= max || isLoading || disabled) return;
    setLastAction('increment');
    onChange(value + 1);
  };

  /**
   * Обработчик изменения input с debounce
   */
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const rawValue = e.target.value;
    setInputValue(rawValue);

    // Очистка предыдущего таймера
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }

    // Debounce 300ms перед вызовом onChange
    debounceTimerRef.current = setTimeout(() => {
      const numValue = parseInt(rawValue, 10);

      if (!isNaN(numValue)) {
        const clampedValue = clampValue(numValue);
        setLastAction(null);
        onChange(clampedValue);
        // Обновляем input если значение было скорректировано
        if (clampedValue !== numValue) {
          setInputValue(String(clampedValue));
        }
      } else {
        // При некорректном значении возвращаем текущее
        setInputValue(String(value));
      }
    }, 300);
  };

  /**
   * Обработчик blur - немедленная валидация
   */
  const handleBlur = () => {
    // Очистка debounce таймера
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = null;
    }

    const numValue = parseInt(inputValue, 10);

    if (!isNaN(numValue)) {
      const clampedValue = clampValue(numValue);
      if (clampedValue !== value) {
        setLastAction(null);
        onChange(clampedValue);
      }
      setInputValue(String(clampedValue));
    } else {
      setInputValue(String(value));
    }
  };

  /**
   * Обработчик клавиатурной навигации
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      handleIncrement();
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      handleDecrement();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      handleBlur();
    }
  };

  const isDecrementDisabled = value <= min || isLoading || disabled;
  const isIncrementDisabled = value >= max || isLoading || disabled;

  return (
    <div
      className="inline-flex items-center border border-[var(--color-neutral-400)] rounded-[var(--radius-sm)]"
      role="spinbutton"
      aria-valuenow={value}
      aria-valuemin={min}
      aria-valuemax={max}
      aria-label="Количество товара"
    >
      {/* Кнопка уменьшения */}
      <button
        type="button"
        onClick={handleDecrement}
        disabled={isDecrementDisabled}
        className="w-10 h-10 flex items-center justify-center text-[var(--color-text-primary)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--color-neutral-300)] transition-colors rounded-l-[var(--radius-sm)]"
        aria-label="Уменьшить количество"
        data-testid="quantity-decrement"
      >
        {isLoading && lastAction === 'decrement' ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Minus size={16} />
        )}
      </button>

      {/* Input для ввода количества */}
      <input
        type="text"
        inputMode="numeric"
        pattern="[0-9]*"
        value={inputValue}
        onChange={handleInputChange}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        disabled={isLoading || disabled}
        className="w-12 h-10 text-center text-body-m border-x border-[var(--color-neutral-400)] focus:outline-none focus:ring-[var(--focus-ring)] bg-[var(--bg-panel)] disabled:opacity-50 disabled:cursor-not-allowed"
        aria-label="Количество"
        data-testid="quantity-input"
      />

      {/* Кнопка увеличения */}
      <button
        type="button"
        onClick={handleIncrement}
        disabled={isIncrementDisabled}
        className="w-10 h-10 flex items-center justify-center text-[var(--color-text-primary)] disabled:opacity-50 disabled:cursor-not-allowed hover:bg-[var(--color-neutral-300)] transition-colors rounded-r-[var(--radius-sm)]"
        aria-label="Увеличить количество"
        data-testid="quantity-increment"
      >
        {isLoading && lastAction === 'increment' ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Plus size={16} />
        )}
      </button>
    </div>
  );
}
