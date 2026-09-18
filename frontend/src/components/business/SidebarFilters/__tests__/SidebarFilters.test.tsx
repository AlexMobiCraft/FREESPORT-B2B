/**
 * SidebarFilters Component Tests
 * Тесты для боковой панели фильтров
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { SidebarFilters } from '../SidebarFilters';
import type { SidebarFiltersProps } from '../SidebarFilters';

describe('SidebarFilters', () => {
  const mockProps: SidebarFiltersProps = {
    categories: [
      { id: '1', name: 'Мячи' },
      { id: '2', name: 'Бутсы' },
    ],
    brands: [
      { id: 'nike', name: 'Nike' },
      { id: 'adidas', name: 'Adidas' },
    ],
    priceRange: { min: 0, max: 10000 },
    sizes: ['S', 'M', 'L', 'XL'],
    colors: [
      { name: 'Красный', hex: '#FF0000' },
      { name: 'Синий', hex: '#0000FF' },
    ],
    selectedFilters: {
      categories: [],
      brands: [],
      priceRange: [0, 10000],
      sizes: [],
      colors: [],
      inStock: false,
    },
    onFilterChange: vi.fn(),
    onApply: vi.fn(),
    onReset: vi.fn(),
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders all filter sections', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByText('Категории')).toBeInTheDocument();
    expect(screen.getByText('Бренды')).toBeInTheDocument();
    expect(screen.getByText('Цена')).toBeInTheDocument();
    expect(screen.getByText('Размер')).toBeInTheDocument();
    expect(screen.getByText('Цвет')).toBeInTheDocument();
  });

  it('renders categories checkboxes', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByLabelText('Мячи')).toBeInTheDocument();
    expect(screen.getByLabelText('Бутсы')).toBeInTheDocument();
  });

  it('renders brands checkboxes', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByLabelText('Nike')).toBeInTheDocument();
    expect(screen.getByLabelText('Adidas')).toBeInTheDocument();
  });

  it('renders size chips', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByText('S')).toBeInTheDocument();
    expect(screen.getByText('M')).toBeInTheDocument();
    expect(screen.getByText('L')).toBeInTheDocument();
    expect(screen.getByText('XL')).toBeInTheDocument();
  });

  it('renders color swatches', () => {
    render(<SidebarFilters {...mockProps} />);

    const redButton = screen.getByTitle('Красный');
    const blueButton = screen.getByTitle('Синий');

    expect(redButton).toBeInTheDocument();
    expect(blueButton).toBeInTheDocument();
  });

  it('renders "Только в наличии" toggle', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByLabelText('Только в наличии')).toBeInTheDocument();
  });

  it('renders Apply and Reset buttons', () => {
    render(<SidebarFilters {...mockProps} />);

    expect(screen.getByText('Применить')).toBeInTheDocument();
    expect(screen.getByText('Сбросить')).toBeInTheDocument();
  });

  it('calls onFilterChange when category is selected', () => {
    render(<SidebarFilters {...mockProps} />);

    const categoryCheckbox = screen.getByLabelText('Мячи');
    fireEvent.click(categoryCheckbox);

    expect(mockProps.onFilterChange).toHaveBeenCalledWith({
      ...mockProps.selectedFilters,
      categories: ['1'],
    });
  });

  it('calls onFilterChange when brand is selected', () => {
    render(<SidebarFilters {...mockProps} />);

    const brandCheckbox = screen.getByLabelText('Nike');
    fireEvent.click(brandCheckbox);

    expect(mockProps.onFilterChange).toHaveBeenCalledWith({
      ...mockProps.selectedFilters,
      brands: ['nike'],
    });
  });

  it('calls onApply when Apply button is clicked', () => {
    render(<SidebarFilters {...mockProps} />);

    const applyButton = screen.getByText('Применить');
    fireEvent.click(applyButton);

    expect(mockProps.onApply).toHaveBeenCalled();
  });

  it('calls onReset when Reset button is clicked', () => {
    render(<SidebarFilters {...mockProps} />);

    const resetButton = screen.getByText('Сбросить');
    fireEvent.click(resetButton);

    expect(mockProps.onReset).toHaveBeenCalled();
  });

  it('has correct width (280px)', () => {
    const { container } = render(<SidebarFilters {...mockProps} />);

    const sidebar = container.firstChild as HTMLElement;
    expect(sidebar).toHaveClass('w-[280px]');
  });

  // Edge Case: Nested categories
  describe('Nested Categories', () => {
    const nestedProps: SidebarFiltersProps = {
      ...mockProps,
      categories: [
        {
          id: '1',
          name: 'Футбол',
          children: [
            { id: '1-1', name: 'Мячи' },
            { id: '1-2', name: 'Бутсы' },
          ],
        },
        { id: '2', name: 'Баскетбол' },
      ],
    };

    it('renders nested categories', () => {
      render(<SidebarFilters {...nestedProps} />);

      expect(screen.getByLabelText('Футбол')).toBeInTheDocument();
      expect(screen.getByLabelText('Мячи')).toBeInTheDocument();
      expect(screen.getByLabelText('Бутсы')).toBeInTheDocument();
      expect(screen.getByLabelText('Баскетбол')).toBeInTheDocument();
    });

    it('handles nested category selection', () => {
      render(<SidebarFilters {...nestedProps} />);

      const nestedCheckbox = screen.getByLabelText('Мячи');
      fireEvent.click(nestedCheckbox);

      expect(nestedProps.onFilterChange).toHaveBeenCalledWith({
        ...nestedProps.selectedFilters,
        categories: ['1-1'],
      });
    });
  });

  // Edge Case: Empty arrays
  describe('Empty Data Handling', () => {
    it('does not render size section when sizes array is empty', () => {
      const emptyProps = { ...mockProps, sizes: [] };
      render(<SidebarFilters {...emptyProps} />);

      expect(screen.queryByText('Размер')).not.toBeInTheDocument();
    });

    it('does not render color section when colors array is empty', () => {
      const emptyProps = { ...mockProps, colors: [] };
      render(<SidebarFilters {...emptyProps} />);

      expect(screen.queryByText('Цвет')).not.toBeInTheDocument();
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has proper spacing between sections (24px)', () => {
      const { container } = render(<SidebarFilters {...mockProps} />);

      const sectionsContainer = container.querySelector('.space-y-6');
      expect(sectionsContainer).toBeInTheDocument();
    });
  });
});
