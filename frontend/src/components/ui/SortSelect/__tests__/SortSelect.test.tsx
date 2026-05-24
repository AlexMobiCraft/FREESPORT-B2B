/**
 * SortSelect Component Tests
 * Тесты для компонента сортировки товаров
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SortSelect, SORT_OPTIONS } from '../SortSelect';

describe('SortSelect', () => {
  const defaultProps = {
    options: SORT_OPTIONS,
    value: 'price_asc',
    onChange: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders with default sort options', () => {
    render(<SortSelect {...defaultProps} />);

    expect(screen.getByRole('combobox')).toBeInTheDocument();
    // Проверяем отображение выбранного значения (defaultProps.value = 'price_asc')
    expect(screen.getByText('Цена: по возрастанию')).toBeInTheDocument();
  });

  it('displays current selected value', () => {
    render(<SortSelect {...defaultProps} value="price_desc" />);

    const trigger = screen.getByRole('combobox');
    expect(trigger).toHaveTextContent('Цена: по убыванию');
  });

  it('calls onChange when option is selected', () => {
    render(<SortSelect {...defaultProps} />);

    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);

    // Находим опцию в dropdown
    const option = screen.getByText('По бренду (А-Я)');
    fireEvent.click(option);

    expect(defaultProps.onChange).toHaveBeenCalledWith('brand_asc');
  });

  it('renders all default sort options', () => {
    render(<SortSelect {...defaultProps} />);

    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);

    // Проверяем наличие всех опций в dropdown (используем getAllByRole для option элементов)
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(6);

    // Проверяем текст опций
    const optionTexts = options.map(opt => opt.textContent);
    expect(optionTexts).toContain('Цена: по возрастанию');
    expect(optionTexts).toContain('Цена: по убыванию');
    expect(optionTexts).toContain('По наличию');
    expect(optionTexts).toContain('По бренду (А-Я)');
    expect(optionTexts).toContain('По названию (А-Я)');
    expect(optionTexts).toContain('Новинки');
  });

  it('accepts custom options', () => {
    const customOptions = [
      { value: 'custom1', label: 'Custom Sort 1', direction: 'asc' as const },
      { value: 'custom2', label: 'Custom Sort 2', direction: 'desc' as const },
    ];

    render(<SortSelect {...defaultProps} options={customOptions} />);

    const trigger = screen.getByRole('combobox');
    fireEvent.click(trigger);

    expect(screen.getByText('Custom Sort 1')).toBeInTheDocument();
    expect(screen.getByText('Custom Sort 2')).toBeInTheDocument();
  });

  it('supports B2C mode', () => {
    render(<SortSelect {...defaultProps} mode="b2c" />);

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('supports B2B mode', () => {
    render(<SortSelect {...defaultProps} mode="b2b" />);

    expect(screen.getByRole('combobox')).toBeInTheDocument();
  });

  it('forwards ref correctly', () => {
    const ref = React.createRef<HTMLDivElement>();
    render(<SortSelect ref={ref} {...defaultProps} />);

    expect(ref.current).toBeInstanceOf(HTMLDivElement);
  });

  it('accepts custom className', () => {
    const { container } = render(<SortSelect {...defaultProps} className="custom-class" />);

    expect(container.querySelector('.custom-class')).toBeInTheDocument();
  });

  // Edge Case: Проверка структуры SORT_OPTIONS
  it('SORT_OPTIONS contains all required fields', () => {
    SORT_OPTIONS.forEach(option => {
      expect(option).toHaveProperty('value');
      expect(option).toHaveProperty('label');
      expect(option).toHaveProperty('direction');
      expect(['asc', 'desc']).toContain(option.direction);
    });
  });
});
