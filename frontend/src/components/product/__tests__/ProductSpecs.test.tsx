/**
 * Unit тесты для ProductSpecs (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProductSpecs from '../ProductSpecs';

describe('ProductSpecs', () => {
  const mockSpecifications = {
    Материал: 'Полиамид + сетка',
    Вес: '310 г',
    Цвета: 'black, lime',
    Размеры: '36-46',
    'Страна производства': 'Китай',
  };

  it('рендерит все характеристики', () => {
    render(<ProductSpecs specifications={mockSpecifications} />);

    expect(screen.getByText('Материал')).toBeInTheDocument();
    expect(screen.getByText('Полиамид + сетка')).toBeInTheDocument();
    expect(screen.getByText('Вес')).toBeInTheDocument();
    expect(screen.getByText('310 г')).toBeInTheDocument();
    expect(screen.getByText('Цвета')).toBeInTheDocument();
    expect(screen.getByText('black, lime')).toBeInTheDocument();
  });

  it('рендерит заголовок "Характеристики"', () => {
    render(<ProductSpecs specifications={mockSpecifications} />);
    expect(screen.getByText('Характеристики')).toBeInTheDocument();
  });

  it('не отображается если specifications пустой', () => {
    const { container } = render(<ProductSpecs specifications={{}} />);
    expect(container.firstChild).toBeNull();
  });

  it('не отображается если specifications undefined', () => {
    const { container } = render(<ProductSpecs specifications={undefined} />);
    expect(container.firstChild).toBeNull();
  });

  it('рендерит таблицу с корректной структурой', () => {
    const { container } = render(<ProductSpecs specifications={mockSpecifications} />);

    const definitionList = container.querySelector('dl');
    expect(definitionList).toBeInTheDocument();

    const definitionTerms = container.querySelectorAll('dt');
    const definitionDescriptions = container.querySelectorAll('dd');

    expect(definitionTerms).toHaveLength(5);
    expect(definitionDescriptions).toHaveLength(5);
  });

  it('применяет корректные CSS классы для ключей', () => {
    const { container } = render(<ProductSpecs specifications={mockSpecifications} />);

    const firstKey = container.querySelector('dt');
    expect(firstKey).toHaveClass('text-sm', 'font-medium', 'text-neutral-600');
  });

  it('применяет корректные CSS классы для значений', () => {
    const { container } = render(<ProductSpecs specifications={mockSpecifications} />);

    const firstValue = container.querySelector('dd');
    expect(firstValue).toHaveClass('text-sm', 'text-neutral-900');
  });

  it('рендерит одну характеристику корректно', () => {
    const singleSpec = { Цвет: 'Красный' };
    render(<ProductSpecs specifications={singleSpec} />);

    expect(screen.getByText('Цвет')).toBeInTheDocument();
    expect(screen.getByText('Красный')).toBeInTheDocument();
  });

  it('корректно обрабатывает спецсимволы в характеристиках', () => {
    const specsWithSpecialChars = {
      'Размер (см)': '42 × 28 × 15',
      'Температура использования': '-20°C ... +40°C',
    };
    render(<ProductSpecs specifications={specsWithSpecialChars} />);

    expect(screen.getByText('Размер (см)')).toBeInTheDocument();
    expect(screen.getByText('42 × 28 × 15')).toBeInTheDocument();
    expect(screen.getByText('Температура использования')).toBeInTheDocument();
    expect(screen.getByText('-20°C ... +40°C')).toBeInTheDocument();
  });

  it('использует grid layout с правильными пропорциями', () => {
    const { container } = render(<ProductSpecs specifications={mockSpecifications} />);

    const gridItems = container.querySelectorAll('.grid');
    expect(gridItems[0]).toHaveClass('grid-cols-3');
  });
});
