/**
 * ProductBadge Component Tests
 * Story 11.2 - AC 1, 2 (Badge Priority Logic)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProductBadge } from '../ProductBadge';
import type { Product } from '@/types/api';

// Base mock product
const baseMockProduct: Product = {
  id: 1,
  name: 'Test Product',
  slug: 'test-product',
  description: 'Test description',
  retail_price: 1000,
  is_in_stock: true,
  category: { id: 1, name: 'Test', slug: 'test' },
  images: [],
  is_hit: false,
  is_new: false,
  is_sale: false,
  is_promo: false,
  is_premium: false,
  discount_percent: null,
};

describe('ProductBadge', () => {
  it('shows sale badge with discount percent (priority 1)', () => {
    const product: Product = {
      ...baseMockProduct,
      is_sale: true,
      discount_percent: 25,
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('25% скидка')).toBeInTheDocument();
  });

  it('shows promo badge (priority 2)', () => {
    const product: Product = {
      ...baseMockProduct,
      is_promo: true,
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Акция')).toBeInTheDocument();
  });

  it('shows new badge (priority 3)', () => {
    const product: Product = {
      ...baseMockProduct,
      is_new: true,
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Новинка')).toBeInTheDocument();
  });

  it('shows hit badge (priority 4)', () => {
    const product: Product = {
      ...baseMockProduct,
      is_hit: true,
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Хит')).toBeInTheDocument();
  });

  it('shows premium badge (priority 5)', () => {
    const product: Product = {
      ...baseMockProduct,
      is_premium: true,
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Премиум')).toBeInTheDocument();
  });

  it('respects priority: sale > promo', () => {
    const product: Product = {
      ...baseMockProduct,
      is_sale: true,
      discount_percent: 30,
      is_promo: true, // Должен быть проигнорирован
    };

    render(<ProductBadge product={product} />);

    // Должен показать sale бейдж (приоритет 1)
    expect(screen.getByText('30% скидка')).toBeInTheDocument();
    // Не должен показать promo бейдж
    expect(screen.queryByText('Акция')).not.toBeInTheDocument();
  });

  it('respects priority: promo > new', () => {
    const product: Product = {
      ...baseMockProduct,
      is_promo: true,
      is_new: true, // Должен быть проигнорирован
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Акция')).toBeInTheDocument();
    expect(screen.queryByText('Новинка')).not.toBeInTheDocument();
  });

  it('respects priority: new > hit', () => {
    const product: Product = {
      ...baseMockProduct,
      is_new: true,
      is_hit: true, // Должен быть проигнорирован
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Новинка')).toBeInTheDocument();
    expect(screen.queryByText('Хит')).not.toBeInTheDocument();
  });

  it('respects priority: hit > premium', () => {
    const product: Product = {
      ...baseMockProduct,
      is_hit: true,
      is_premium: true, // Должен быть проигнорирован
    };

    render(<ProductBadge product={product} />);

    expect(screen.getByText('Хит')).toBeInTheDocument();
    expect(screen.queryByText('Премиум')).not.toBeInTheDocument();
  });

  it('shows nothing when no badge flags are set', () => {
    const product: Product = {
      ...baseMockProduct,
      // Все флаги false
    };

    const { container } = render(<ProductBadge product={product} />);

    // Компонент должен вернуть null
    expect(container.firstChild).toBeNull();
  });

  it('does not show sale badge if discount_percent is null', () => {
    const product: Product = {
      ...baseMockProduct,
      is_sale: true,
      discount_percent: null, // Нет процента
    };

    const { container } = render(<ProductBadge product={product} />);

    // Не должен показать sale бейдж без процента
    expect(screen.queryByText(/скидка/i)).not.toBeInTheDocument();
    // Компонент должен вернуть null (нет других флагов)
    expect(container.firstChild).toBeNull();
  });

  it('applies custom className when provided', () => {
    const product: Product = {
      ...baseMockProduct,
      is_hit: true,
    };

    const { container } = render(<ProductBadge product={product} className="custom-class" />);

    const badge = container.querySelector('.custom-class');
    expect(badge).toBeInTheDocument();
  });
});
