/**
 * PriceRangeSlider Component Tests
 * Тесты для dual-thumb range slider
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { PriceRangeSlider } from '../PriceRangeSlider';

describe('PriceRangeSlider', () => {
  const defaultProps = {
    min: 0,
    max: 10000,
    value: [1000, 5000] as [number, number],
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders with min and max inputs', () => {
    render(<PriceRangeSlider {...defaultProps} />);

    const inputs = screen.getAllByRole('textbox');
    expect(inputs).toHaveLength(2);
    // Компонент использует неразрывный пробел (\u00A0)
    expect(inputs[0]).toHaveValue('1\u00A0000');
    expect(inputs[1]).toHaveValue('5\u00A0000');
  });

  it('renders slider thumbs', () => {
    render(<PriceRangeSlider {...defaultProps} />);

    const sliders = screen.getAllByRole('slider');
    expect(sliders).toHaveLength(2);
    expect(sliders[0]).toHaveAttribute('aria-valuenow', '1000');
    expect(sliders[1]).toHaveAttribute('aria-valuenow', '5000');
  });

  it('updates min value via input', () => {
    const handleChange = vi.fn();
    render(<PriceRangeSlider {...defaultProps} onChange={handleChange} />);

    // Первый элемент - input, второй - slider thumb
    const [minInput] = screen.getAllByLabelText('Минимальная цена');
    fireEvent.change(minInput, { target: { value: '2000' } });

    expect(handleChange).toHaveBeenCalledWith([2000, 5000]);
  });

  it('updates max value via input', () => {
    const handleChange = vi.fn();
    render(<PriceRangeSlider {...defaultProps} onChange={handleChange} />);

    // Первый элемент - input, второй - slider thumb
    const [maxInput] = screen.getAllByLabelText('Максимальная цена');
    fireEvent.change(maxInput, { target: { value: '8000' } });

    expect(handleChange).toHaveBeenCalledWith([1000, 8000]);
  });

  it('validates min cannot be greater than max', () => {
    const handleChange = vi.fn();
    render(<PriceRangeSlider {...defaultProps} value={[1000, 5000]} onChange={handleChange} />);

    const [minInput] = screen.getAllByLabelText('Минимальная цена');
    fireEvent.change(minInput, { target: { value: '6000' } });

    // onChange не должен быть вызван, так как 6000 > max (5000)
    expect(handleChange).not.toHaveBeenCalled();
  });

  it('validates max cannot be less than min', () => {
    const handleChange = vi.fn();
    render(<PriceRangeSlider {...defaultProps} value={[1000, 5000]} onChange={handleChange} />);

    const inputs = screen.getAllByRole('textbox');
    const maxInput = inputs[1]; // Второй input - максимальная цена
    fireEvent.change(maxInput, { target: { value: '500' } });

    // onChange не должен быть вызван, так как 500 < min (1000)
    expect(handleChange).not.toHaveBeenCalled();
  });

  it('formats price with custom formatter', () => {
    const customFormat = (price: number) => `$${price}`;
    render(<PriceRangeSlider {...defaultProps} formatPrice={customFormat} />);

    // Проверяем, что текущие значения отформатированы с помощью customFormat
    expect(screen.getByDisplayValue('$1000')).toBeInTheDocument();
    expect(screen.getByDisplayValue('$5000')).toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(<PriceRangeSlider {...defaultProps} />);

    const sliders = screen.getAllByRole('slider');
    expect(sliders[0]).toHaveAttribute('aria-valuemin', '0');
    expect(sliders[0]).toHaveAttribute('aria-valuemax', '10000');
    expect(sliders[1]).toHaveAttribute('aria-valuemin', '0');
    expect(sliders[1]).toHaveAttribute('aria-valuemax', '10000');
  });
});
