/**
 * Unit тесты для ProductInfo (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import ProductInfo from '../ProductInfo';
import type { ProductDetail } from '@/types/api';

describe('ProductInfo', () => {
  const mockProduct: ProductDetail = {
    id: 101,
    slug: 'asics-gel-blast-ff',
    name: 'ASICS Gel-Blast FF',
    sku: 'AS-GB-FF-2025',
    brand: 'ASICS',
    description: 'Профессиональные кроссовки для интенсивных тренировок',
    full_description: 'Расширенное описание с технологическими особенностями',
    price: {
      retail: 12990,
      wholesale: {
        level1: 11890,
        level2: 11290,
        level3: 10790,
      },
      trainer: 10990,
      federation: 9990,
      currency: 'RUB',
    },
    stock_quantity: 34,
    images: [],
    rating: 4.7,
    reviews_count: 38,
    category: {
      id: 1,
      name: 'Обувь',
      slug: 'obuv',
      breadcrumbs: [
        { id: 100, name: 'Главная', slug: 'home' },
        { id: 101, name: 'Обувь', slug: 'shoes' },
      ],
    },
    is_in_stock: true,
    can_be_ordered: true,
  };

  it('рендерит название товара', () => {
    render(<ProductInfo product={mockProduct} />);
    expect(screen.getByText('ASICS Gel-Blast FF')).toBeInTheDocument();
  });

  it('рендерит бренд', () => {
    render(<ProductInfo product={mockProduct} />);
    expect(screen.getByText(/Бренд:/)).toBeInTheDocument();
    const brandElements = screen.getAllByText('ASICS');
    expect(brandElements.length).toBeGreaterThan(0);
  });

  it('отображает retail цену для гостя', () => {
    const { container } = render(<ProductInfo product={mockProduct} userRole="guest" />);
    const priceDiv = container.querySelector('.text-4xl.font-bold');
    expect(priceDiv).toHaveTextContent('12 990 ₽');
  });

  it('отображает wholesale level1 цену для wholesale_level1', () => {
    const { container } = render(<ProductInfo product={mockProduct} userRole="wholesale_level1" />);
    const priceDiv = container.querySelector('.text-4xl.font-bold');
    expect(priceDiv).toHaveTextContent('11 890 ₽');
  });

  it('отображает trainer цену для trainer', () => {
    const { container } = render(<ProductInfo product={mockProduct} userRole="trainer" />);
    const priceDiv = container.querySelector('.text-4xl.font-bold');
    expect(priceDiv).toHaveTextContent('10 990 ₽');
  });

  it('отображает federation цену для federation_rep', () => {
    const { container } = render(<ProductInfo product={mockProduct} userRole="federation_rep" />);
    const priceDiv = container.querySelector('.text-4xl.font-bold');
    expect(priceDiv).toHaveTextContent('9 990 ₽');
  });

  it('отображает статус "В наличии" для товара в наличии', () => {
    render(<ProductInfo product={mockProduct} />);
    expect(screen.getByText('В наличии')).toBeInTheDocument();
  });

  it('отображает статус "Под заказ" для товара под заказ', () => {
    const outOfStockProduct = {
      ...mockProduct,
      stock_quantity: 0,
      is_in_stock: false,
      can_be_ordered: true,
    };
    render(<ProductInfo product={outOfStockProduct} />);
    expect(screen.getByText('Под заказ')).toBeInTheDocument();
  });

  it('отображает статус "Нет в наличии" для недоступного товара', () => {
    const unavailableProduct = {
      ...mockProduct,
      stock_quantity: 0,
      is_in_stock: false,
      can_be_ordered: false,
    };
    render(<ProductInfo product={unavailableProduct} />);
    expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
  });

  it('рендерит рейтинг звездами', () => {
    const { container } = render(<ProductInfo product={mockProduct} />);
    const stars = container.querySelectorAll('svg');
    // Должно быть 5 звезд (4 полных + 1 половина + 0 пустых для рейтинга 4.7)
    expect(stars.length).toBeGreaterThanOrEqual(5);
  });

  it('рендерит количество отзывов', () => {
    render(<ProductInfo product={mockProduct} />);
    expect(screen.getByText(/38.*отзывов/i)).toBeInTheDocument();
  });

  it('не отображает рейтинг если он отсутствует', () => {
    const productWithoutRating = { ...mockProduct, rating: undefined, reviews_count: undefined };
    const { container } = render(<ProductInfo product={productWithoutRating} />);
    const stars = container.querySelectorAll('svg');
    // Не должно быть звезд рейтинга
    expect(stars.length).toBe(0);
  });

  it('применяет корректный CSS класс для статуса "В наличии"', () => {
    render(<ProductInfo product={mockProduct} />);
    const badge = screen.getByText('В наличии');
    expect(badge).toHaveClass('bg-green-50', 'text-green-700');
  });

  it('применяет корректный CSS класс для статуса "Под заказ"', () => {
    const outOfStockProduct = {
      ...mockProduct,
      stock_quantity: 0,
      is_in_stock: false,
      can_be_ordered: true,
    };
    render(<ProductInfo product={outOfStockProduct} />);
    const badge = screen.getByText('Под заказ');
    expect(badge).toHaveClass('bg-yellow-50', 'text-yellow-700');
  });

  it('применяет корректный CSS класс для статуса "Нет в наличии"', () => {
    const unavailableProduct = {
      ...mockProduct,
      stock_quantity: 0,
      is_in_stock: false,
      can_be_ordered: false,
    };
    render(<ProductInfo product={unavailableProduct} />);
    const badge = screen.getByText('Нет в наличии');
    expect(badge).toHaveClass('bg-red-50', 'text-red-700');
  });
});
