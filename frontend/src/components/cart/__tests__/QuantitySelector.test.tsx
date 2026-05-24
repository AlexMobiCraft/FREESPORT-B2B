/**
 * QuantitySelector Component Tests
 *
 * Покрытие:
 * - Рендеринг кнопок +/- и input
 * - Increment/decrement логика
 * - Валидация границ (min/max)
 * - Debounce на input (300ms)
 * - Loading state с spinner
 * - Disabled state
 * - Keyboard navigation
 * - Accessibility (role="spinbutton", aria-атрибуты)
 *
 * @see Story 26.2: Cart Item Card Component (AC: 4-5, 8, 10-11, 13)
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { QuantitySelector } from '../QuantitySelector';

describe('QuantitySelector', () => {
  const mockOnChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders decrement button', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);
      expect(screen.getByTestId('quantity-decrement')).toBeInTheDocument();
    });

    it('renders increment button', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);
      expect(screen.getByTestId('quantity-increment')).toBeInTheDocument();
    });

    it('renders input with correct value', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);
      expect(screen.getByTestId('quantity-input')).toHaveValue('5');
    });

    it('renders with default min=1 and max=99', () => {
      render(<QuantitySelector value={50} onChange={mockOnChange} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuemin', '1');
      expect(spinbutton).toHaveAttribute('aria-valuemax', '99');
    });
  });

  // Increment логика
  describe('Increment', () => {
    it('calls onChange with incremented value on click', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      fireEvent.click(incrementButton);

      expect(mockOnChange).toHaveBeenCalledWith(6);
    });

    it('does not increment beyond max', () => {
      render(<QuantitySelector value={99} max={99} onChange={mockOnChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      fireEvent.click(incrementButton);

      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('increment button is disabled at max value', () => {
      render(<QuantitySelector value={99} max={99} onChange={mockOnChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      expect(incrementButton).toBeDisabled();
    });

    it('respects custom max value', () => {
      render(<QuantitySelector value={10} max={10} onChange={mockOnChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      expect(incrementButton).toBeDisabled();
    });
  });

  // Decrement логика
  describe('Decrement', () => {
    it('calls onChange with decremented value on click', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      fireEvent.click(decrementButton);

      expect(mockOnChange).toHaveBeenCalledWith(4);
    });

    it('does not decrement below min', () => {
      render(<QuantitySelector value={1} min={1} onChange={mockOnChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      fireEvent.click(decrementButton);

      expect(mockOnChange).not.toHaveBeenCalled();
    });

    it('decrement button is disabled at min value', () => {
      render(<QuantitySelector value={1} min={1} onChange={mockOnChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      expect(decrementButton).toBeDisabled();
    });

    it('respects custom min value', () => {
      render(<QuantitySelector value={5} min={5} onChange={mockOnChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      expect(decrementButton).toBeDisabled();
    });
  });

  // Debounce на input
  describe('Debounce Input', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it('debounces input changes by 300ms', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: '10' } });

      // Сразу после изменения - onChange не вызван
      expect(mockOnChange).not.toHaveBeenCalled();

      // Продвигаем таймер на 300ms
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // После debounce - onChange вызван
      expect(mockOnChange).toHaveBeenCalledWith(10);
    });

    it('cancels previous debounce on new input', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');

      // Первое изменение
      fireEvent.change(input, { target: { value: '8' } });

      // Через 200ms - второе изменение
      act(() => {
        vi.advanceTimersByTime(200);
      });
      fireEvent.change(input, { target: { value: '10' } });

      // Продвигаем на 300ms после последнего изменения
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // onChange должен быть вызван только с последним значением
      expect(mockOnChange).toHaveBeenCalledTimes(1);
      expect(mockOnChange).toHaveBeenCalledWith(10);
    });

    it('clamps input value to min/max on debounce', () => {
      render(<QuantitySelector value={5} min={1} max={99} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: '150' } });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Значение должно быть ограничено max=99
      expect(mockOnChange).toHaveBeenCalledWith(99);
    });

    it('handles invalid input gracefully', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: 'abc' } });

      act(() => {
        vi.advanceTimersByTime(300);
      });

      // Должен вернуться к текущему значению, onChange не вызван с новым значением
      expect(input).toHaveValue('5');
    });
  });

  // Input blur
  describe('Input Blur', () => {
    it('immediately applies value on blur', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: '8' } });
      fireEvent.blur(input);

      // Значение должно примениться сразу без ожидания debounce
      expect(mockOnChange).toHaveBeenCalledWith(8);
    });

    it('clamps value on blur', () => {
      render(<QuantitySelector value={5} min={1} max={10} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: '20' } });
      fireEvent.blur(input);

      expect(mockOnChange).toHaveBeenCalledWith(10);
    });
  });

  // Loading state
  describe('Loading State', () => {
    it('disables all controls when isLoading', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} isLoading={true} />);

      expect(screen.getByTestId('quantity-decrement')).toBeDisabled();
      expect(screen.getByTestId('quantity-increment')).toBeDisabled();
      expect(screen.getByTestId('quantity-input')).toBeDisabled();
    });

    it('shows spinner on increment button when loading after increment', () => {
      const { rerender } = render(
        <QuantitySelector value={5} onChange={mockOnChange} isLoading={false} />
      );

      // Клик на increment
      const incrementButton = screen.getByTestId('quantity-increment');
      fireEvent.click(incrementButton);

      // Перерендер с isLoading=true
      rerender(<QuantitySelector value={6} onChange={mockOnChange} isLoading={true} />);

      // Проверяем что есть анимация spinner (Loader2 имеет класс animate-spin)
      const spinner = incrementButton.querySelector('.animate-spin');
      expect(spinner).toBeInTheDocument();
    });
  });

  // Disabled state
  describe('Disabled State', () => {
    it('disables all controls when disabled prop is true', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} disabled={true} />);

      expect(screen.getByTestId('quantity-decrement')).toBeDisabled();
      expect(screen.getByTestId('quantity-increment')).toBeDisabled();
      expect(screen.getByTestId('quantity-input')).toBeDisabled();
    });

    it('does not call onChange when disabled', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} disabled={true} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      fireEvent.click(incrementButton);

      expect(mockOnChange).not.toHaveBeenCalled();
    });
  });

  // Keyboard navigation
  describe('Keyboard Navigation', () => {
    it('increments on ArrowUp key', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.keyDown(input, { key: 'ArrowUp' });

      expect(mockOnChange).toHaveBeenCalledWith(6);
    });

    it('decrements on ArrowDown key', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.keyDown(input, { key: 'ArrowDown' });

      expect(mockOnChange).toHaveBeenCalledWith(4);
    });

    it('applies value immediately on Enter key', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      fireEvent.change(input, { target: { value: '8' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      expect(mockOnChange).toHaveBeenCalledWith(8);
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has role="spinbutton"', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);
      expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    });

    it('has aria-valuenow', () => {
      render(<QuantitySelector value={7} onChange={mockOnChange} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuenow', '7');
    });

    it('has aria-valuemin', () => {
      render(<QuantitySelector value={5} min={2} onChange={mockOnChange} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuemin', '2');
    });

    it('has aria-valuemax', () => {
      render(<QuantitySelector value={5} max={50} onChange={mockOnChange} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuemax', '50');
    });

    it('has aria-label on container', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-label', 'Количество товара');
    });

    it('decrement button has aria-label', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const button = screen.getByTestId('quantity-decrement');
      expect(button).toHaveAttribute('aria-label', 'Уменьшить количество');
    });

    it('increment button has aria-label', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const button = screen.getByTestId('quantity-increment');
      expect(button).toHaveAttribute('aria-label', 'Увеличить количество');
    });

    it('input has aria-label', () => {
      render(<QuantitySelector value={5} onChange={mockOnChange} />);

      const input = screen.getByTestId('quantity-input');
      expect(input).toHaveAttribute('aria-label', 'Количество');
    });
  });

  // Value synchronization
  describe('Value Synchronization', () => {
    it('updates input when external value changes', () => {
      const { rerender } = render(<QuantitySelector value={5} onChange={mockOnChange} />);

      expect(screen.getByTestId('quantity-input')).toHaveValue('5');

      rerender(<QuantitySelector value={10} onChange={mockOnChange} />);

      expect(screen.getByTestId('quantity-input')).toHaveValue('10');
    });
  });
});
