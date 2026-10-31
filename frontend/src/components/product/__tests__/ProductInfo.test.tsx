/**
 * Unit тесты для ProductInfo (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import ProductInfo from '../ProductInfo';
import type { ProductDetail, ProductVariant } from '@/types/api';

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
  describe('роли VIP и «Спец цена»', () => {
    // В ProductPrice полей этих ролей нет: цену отдаёт API итогом
    const rolePriced: ProductDetail = {
      ...mockProduct,
      current_price: '10000.00',
      regular_price: '10000.00',
      promo_price: null,
    };
    const roles = ['vip', 'special_price'] as const;

    it.each(roles)('без варианта показывает цену из API, а не розницу для %s', role => {
      const { container } = render(<ProductInfo product={rolePriced} userRole={role} />);

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('10 000 ₽');
    });

    it.each(roles)('выбранный вариант задаёт цену для %s', role => {
      const variant: ProductVariant = {
        id: 5,
        sku: 'AS-GB-FF-44',
        current_price: '9500.00',
        regular_price: '9500.00',
        promo_price: null,
        rrp: '13000.00',
        stock_quantity: 5,
        is_in_stock: true,
        available_quantity: 5,
      };
      const { container } = render(
        <ProductInfo product={rolePriced} userRole={role} selectedVariant={variant} />
      );

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('9 500 ₽');
      // РРЦ видят и эти роли
      expect(screen.getByText(/РРЦ:/)).toHaveTextContent('13 000 ₽');
    });

    it.each(roles)('акция ниже цены роли: стикер, подпись и зачёркнутая цена для %s', role => {
      const promoProduct: ProductDetail = {
        ...rolePriced,
        current_price: '8000.00',
        promo_price: '8000.00',
      };
      render(<ProductInfo product={promoProduct} userRole={role} />);

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('8 000 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('10 000 ₽');
    });
  });

  describe('акционная цена', () => {
    const variant = (regular: string): ProductVariant => ({
      id: 1,
      sku: 'AS-GB-FF-42',
      current_price: '800.00',
      regular_price: regular,
      promo_price: '800.00',
      stock_quantity: 5,
      is_in_stock: true,
      available_quantity: 5,
    });

    it('по выбранному варианту: акционная цена и зачёркнутая цена клиента выше неё', () => {
      const { container } = render(
        <ProductInfo
          product={mockProduct}
          userRole="wholesale_level2"
          selectedVariant={variant('1000.00')}
        />
      );

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('800 ₽');
      const regular = screen.getByTestId('regular-price');
      expect(regular).toHaveTextContent('1 000 ₽');
      expect(regular).toHaveClass('line-through');
    });

    it('без зачёркнутой цены, когда цена клиента равна акционной', () => {
      render(<ProductInfo product={mockProduct} selectedVariant={variant('800.00')} />);

      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
    });

    it('акция выше цены клиента: страница выглядит как без акции', () => {
      // Клиент платит меньшую из цен — своей 700 и акционной 800: акция ему не выгодна
      const ownPrice: ProductVariant = { ...variant('700.00'), current_price: '700.00' };
      const { container } = render(
        <ProductInfo product={mockProduct} userRole="wholesale_level1" selectedVariant={ownPrice} />
      );

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('700 ₽');
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
      expect(screen.queryByText(/Акционная цена/)).not.toBeInTheDocument();
      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
    });

    it('при цене клиента 900 и акции 800 стикер, зачёркнутая цена и подпись на месте', () => {
      render(
        <ProductInfo
          product={mockProduct}
          userRole="wholesale_level1"
          selectedVariant={variant('900.00')}
        />
      );

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('900 ₽');
      expect(screen.getByText(/Акционная цена/)).toBeInTheDocument();
    });

    it('цена клиента равна акционной: акция применена, зачёркнутой цены нет', () => {
      render(
        <ProductInfo
          product={mockProduct}
          userRole="wholesale_level3"
          selectedVariant={variant('800.00')}
        />
      );

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
    });

    it('без выбранного варианта невыгодная акция товара не показывается', () => {
      const unappliedProduct: ProductDetail = {
        ...mockProduct,
        current_price: '9000.00',
        regular_price: '9000.00',
        promo_price: '9500.00',
      };
      const { container } = render(
        <ProductInfo product={unappliedProduct} userRole="wholesale_level1" />
      );

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('9 000 ₽');
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
    });

    it('без выбранного варианта — по полям товара', () => {
      const promoProduct: ProductDetail = {
        ...mockProduct,
        current_price: '9000.00',
        regular_price: '12990.00',
        promo_price: '9000.00',
      };
      const { container } = render(<ProductInfo product={promoProduct} userRole="guest" />);

      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('9 000 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('12 990 ₽');
      expect(screen.getByText('Акция')).toBeInTheDocument();
    });

    it('подписывает назначение обеих цен для скринридера', () => {
      render(<ProductInfo product={mockProduct} selectedVariant={variant('1000.00')} />);

      const promoLabel = within(screen.getByTestId('promo-price')).getByText(/Акционная цена/);
      expect(promoLabel).toHaveClass('sr-only');
      const regularLabel = within(screen.getByTestId('regular-price')).getByText(/Цена без акции/);
      expect(regularLabel).toHaveClass('sr-only');
    });

    it('без зачёркнутой цены подписана только акционная', () => {
      render(<ProductInfo product={mockProduct} selectedVariant={variant('800.00')} />);

      expect(
        within(screen.getByTestId('promo-price')).getByText(/Акционная цена/)
      ).toBeInTheDocument();
      expect(screen.queryByText(/Цена без акции/)).not.toBeInTheDocument();
    });

    it('обычная цена без акции остаётся без подписей', () => {
      render(<ProductInfo product={mockProduct} />);

      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.queryByText(/Акционная цена/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Цена без акции/)).not.toBeInTheDocument();
    });

    it('сохраняет копейки: близкие цены не выглядят одинаковыми', () => {
      const closePair: ProductVariant = {
        ...variant('800.49'),
        current_price: '800.40',
        promo_price: '800.40',
      };
      render(<ProductInfo product={mockProduct} selectedVariant={closePair} />);

      expect(screen.getByTestId('promo-price')).toHaveTextContent('800,40 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('800,49 ₽');
    });

    it('целые суммы акции остаются без копеек', () => {
      render(<ProductInfo product={mockProduct} selectedVariant={variant('1000.00')} />);

      expect(screen.getByTestId('promo-price')).toHaveTextContent(/^Акционная цена:\s*800 ₽$/);
      expect(screen.getByTestId('regular-price')).toHaveTextContent(
        /^Цена без акции:\s*1 000 ₽$/
      );
    });

    it('показывает стикер по акционной цене выбранного варианта', () => {
      render(<ProductInfo product={mockProduct} selectedVariant={variant('1000.00')} />);

      expect(screen.getByText('Акция')).toBeInTheDocument();
    });

    it('не показывает стикер для обычного товара', () => {
      render(<ProductInfo product={mockProduct} />);

      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
    });

    it('вариант без акции у акционного товара: акция другого варианта не показывается', () => {
      // У товара акция по первому варианту (поля списка), у выбранного варианта её нет
      const promoProduct: ProductDetail = {
        ...mockProduct,
        current_price: '9000.00',
        regular_price: '12990.00',
        promo_price: '9000.00',
      };
      const plainVariant: ProductVariant = {
        id: 2,
        sku: 'AS-GB-FF-43',
        current_price: '12990.00',
        regular_price: '12990.00',
        promo_price: null,
        stock_quantity: 5,
        is_in_stock: true,
        available_quantity: 5,
      };

      const { container, rerender } = render(
        <ProductInfo product={promoProduct} userRole="guest" selectedVariant={variant('12990.00')} />
      );
      expect(container.querySelector('.text-4xl.font-bold')).toHaveTextContent('800 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('12 990 ₽');
      expect(screen.getByText('Акция')).toBeInTheDocument();

      // Покупатель переключил вариант на тот, где акции нет
      rerender(<ProductInfo product={promoProduct} userRole="guest" selectedVariant={plainVariant} />);

      const price = container.querySelector('.text-4xl.font-bold');
      expect(price).toHaveTextContent('12 990 ₽');
      expect(price).not.toHaveTextContent('9 000');
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
    });
  });
});
