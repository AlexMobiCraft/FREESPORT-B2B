/**
 * SearchField Component Tests
 * Покрытие минимальной длины запроса, пустого результата и edge cases
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SearchField } from '../SearchField';

describe('SearchField', () => {
  // Базовый рендеринг
  it('renders search field with default placeholder', () => {
    render(<SearchField />);

    const input = screen.getByRole('combobox');
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('placeholder', 'Поиск');
  });

  it('renders with custom placeholder', () => {
    render(<SearchField placeholder="Search products..." />);

    const input = screen.getByRole('combobox');
    expect(input).toHaveAttribute('placeholder', 'Search products...');
  });

  // onChange callback
  it('calls onChange handler when value changes', () => {
    const handleChange = vi.fn();
    render(<SearchField onChange={handleChange} />);

    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'test query' } });

    expect(handleChange).toHaveBeenCalledTimes(1);
  });

  // Edge Case: Минимальная длина запроса
  describe('Minimum Length Validation', () => {
    it('shows warning when input is less than minLength (default 2)', () => {
      render(<SearchField />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: 'a' } });

      expect(screen.getByText(/введите минимум 2 символа/i)).toBeInTheDocument();
      expect(screen.getByText(/введите минимум 2 символа/i)).toHaveClass('text-accent-warning');
    });

    it('hides warning when input meets minLength', () => {
      render(<SearchField />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: 'a' } });
      expect(screen.getByText(/введите минимум 2 символа/i)).toBeInTheDocument();

      fireEvent.change(input, { target: { value: 'ab' } });
      expect(screen.queryByText(/введите минимум 2 символа/i)).not.toBeInTheDocument();
    });

    it('respects custom minLength prop', () => {
      render(<SearchField minLength={3} />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: 'ab' } });

      expect(screen.getByText(/введите минимум 3 символа/i)).toBeInTheDocument();
    });

    it('does not show warning for empty input', () => {
      render(<SearchField />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: '' } });

      expect(screen.queryByText(/введите минимум/i)).not.toBeInTheDocument();
    });
  });

  // onSearch callback (с debounce)
  describe('onSearch Callback', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it('calls onSearch when input meets minLength after debounce', () => {
      const handleSearch = vi.fn();
      render(<SearchField onSearch={handleSearch} debounceMs={300} />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: 'ab' } });

      // onSearch вызывается после debounce (300ms)
      expect(handleSearch).not.toHaveBeenCalled();

      vi.advanceTimersByTime(300);
      expect(handleSearch).toHaveBeenCalledWith('ab');
    });

    it('does not call onSearch when input is below minLength', () => {
      const handleSearch = vi.fn();
      render(<SearchField onSearch={handleSearch} />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: 'a' } });

      vi.advanceTimersByTime(300);
      expect(handleSearch).not.toHaveBeenCalled();
    });

    it('does not call onSearch for empty input', () => {
      const handleSearch = vi.fn();
      render(<SearchField onSearch={handleSearch} />);

      const input = screen.getByRole('combobox');
      fireEvent.change(input, { target: { value: '' } });

      vi.advanceTimersByTime(300);
      expect(handleSearch).not.toHaveBeenCalled();
    });
  });

  // Warning state styling
  it('applies warning border when showing warning', () => {
    render(<SearchField />);

    const input = screen.getByRole('combobox');
    fireEvent.change(input, { target: { value: 'a' } });

    expect(input).toHaveClass('border-accent-warning');
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has aria-label for screen readers', () => {
      render(<SearchField />);

      const input = screen.getByRole('combobox');
      expect(input).toHaveAttribute('aria-label', 'Поиск');
    });

    it('has focus ring on focus', () => {
      render(<SearchField />);

      const input = screen.getByRole('combobox');
      // SearchField использует focus:border-primary вместо focus:ring
      expect(input).toHaveClass('focus:border-primary');
    });

    it('forwards ref correctly', () => {
      const ref = React.createRef<HTMLInputElement>();
      render(<SearchField ref={ref} />);

      expect(ref.current).toBeInstanceOf(HTMLInputElement);
    });

    it('has aria-hidden on search icon', () => {
      const { container } = render(<SearchField />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });
  });

  // Custom className
  it('accepts custom className', () => {
    render(<SearchField className="custom-class" />);

    const input = screen.getByRole('combobox');
    expect(input).toHaveClass('custom-class');
  });

  // Controlled value
  it('updates value when typing', () => {
    render(<SearchField />);

    const input = screen.getByRole('combobox') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'test' } });

    expect(input.value).toBe('test');
  });
});
