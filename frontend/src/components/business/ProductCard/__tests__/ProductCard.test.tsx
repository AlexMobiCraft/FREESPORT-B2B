/**
 * ProductCard Component Tests
 *
 * Comprehensive test suite covering:
 * - Grid/List/Compact layouts
 * - Role-based pricing
 * - Badge logic
 * - Interactivity (add to cart, favorite)
 * - Accessibility attributes
 *
 * Target coverage: >= 80%
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import type { ButtonHTMLAttributes, ComponentProps, ReactNode } from 'react';
import { ProductCard } from '../ProductCard';
import type { Product } from '@/types/api';
import type { ProductBadgeProps } from '@/components/common/ProductBadge';

type MockImageProps = ComponentProps<'img'> & { src: string; alt: string; fill?: boolean };
type MockHeartProps = ComponentProps<'svg'> & { fill?: string };
type MockButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { children: ReactNode };
type MockCnArgs = Array<string | false | null | undefined>;

// Mock Next.js Image component
// Mock Next.js Image component
vi.mock('next/image', () => ({
  default: ({ src, alt, fill, ...rest }: MockImageProps) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} {...rest} data-fill={fill} />
  ),
}));

// Mock lucide-react icons
vi.mock('lucide-react', async importOriginal => ({
  ...(await importOriginal<typeof import('lucide-react')>()),
  Heart: ({ className, fill }: MockHeartProps) => (
    <svg data-testid="heart-icon" className={className} data-fill={fill ?? undefined} />
  ),
}));

// Mock ProductBadge component
vi.mock('@/components/common/ProductBadge', () => ({
  ProductBadge: ({ product }: ProductBadgeProps) => {
    if (product.is_sale && product.discount_percent) {
      return <span data-testid="badge-sale">{product.discount_percent}% скидка</span>;
    }
    // Как настоящий ProductBadge: флаг is_promo — второй по приоритету стикер. Карточка обязана
    // не отдавать ему флаг, пока акция клиенту не выгодна
    if (product.is_promo) {
      return <span data-testid="badge-promo">Акция</span>;
    }
    if (product.is_new) {
      return <span data-testid="badge-new">Новинка</span>;
    }
    if (product.is_hit) {
      return <span data-testid="badge-hit">Лидер продаж</span>;
    }
    return null;
  },
}));

// Mock Button component
vi.mock('@/components/ui', () => ({
  Button: ({ children, onClick, type = 'button', ...props }: MockButtonProps) => (
    <button type={type} onClick={onClick} {...props}>
      {children}
    </button>
  ),
}));

// Mock cn utility
vi.mock('@/utils/cn', () => ({
  cn: (...classes: MockCnArgs) => classes.filter(Boolean).join(' '),
}));

describe('ProductCard', () => {
  const mockProduct: Product = {
    id: 1,
    name: 'Test Product',
    slug: 'test-product',
    description: 'Test description',
    retail_price: 1200,
    opt1_price: 1000,
    opt2_price: 900,
    opt3_price: 800,
    opt4_price: 700,
    is_in_stock: true,
    stock_quantity: 50,
    category: {
      id: 1,
      name: 'Test Category',
      slug: 'test-category',
    },
    brand: {
      id: 1,
      name: 'Nike',
      slug: 'nike',
      is_featured: false,
    },
    images: [
      {
        id: 1,
        image: '/test-image.jpg',
        is_primary: true,
      },
    ],
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    discount_percent: null,
  };

  const mockOnToggleFavorite = vi.fn();

  beforeEach(() => {
    mockOnToggleFavorite.mockClear();
  });

  describe('Grid Layout', () => {
    it('renders grid layout correctly', () => {
      render(<ProductCard product={mockProduct} layout="grid" showSelectButton />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
      expect(screen.getByText('Выбрать')).toBeInTheDocument();
      expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
    });

    it('displays product image with correct alt text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const image = screen.getByRole('img', { name: 'Test Product' });
      expect(image).toBeInTheDocument();
      // resolveImageUrl добавляет MEDIA_BASE_URL к относительным путям
      expect(image).toHaveAttribute('src', 'http://localhost:8001/test-image.jpg');
    });

    it('shows placeholder when no image available', () => {
      const productWithoutImage = { ...mockProduct, images: [] };
      render(<ProductCard product={productWithoutImage} layout="grid" />);

      // Placeholder SVG should be rendered
      const svg = screen.getByRole('article').querySelector('svg');
      expect(svg).toBeInTheDocument();
    });

    it('«Выбрать» ведёт на страницу товара, а не в корзину', () => {
      render(<ProductCard product={mockProduct} layout="grid" showSelectButton />);

      const selectButton = screen.getByText('Выбрать');
      // Не кнопка: интерактивный элемент внутри ссылки карточки недопустим
      expect(selectButton.closest('button')).toBeNull();
      expect(selectButton.closest('a')).toHaveAttribute('href', '/product/test-product');
    });

    it('does not show select button when out of stock', () => {
      const outOfStockProduct = { ...mockProduct, is_in_stock: false };
      render(<ProductCard product={outOfStockProduct} layout="grid" showSelectButton />);

      expect(screen.queryByText('Выбрать')).not.toBeInTheDocument();
      expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
    });
  });

  describe('List Layout', () => {
    it('renders list layout correctly', () => {
      render(<ProductCard product={mockProduct} layout="list" showSelectButton />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('Test description')).toBeInTheDocument();
      expect(screen.getByText('Выбрать').closest('a')).toHaveAttribute(
        'href',
        '/product/test-product'
      );
    });

    it('displays description in list layout', () => {
      render(<ProductCard product={mockProduct} layout="list" />);

      expect(screen.getByText('Test description')).toBeInTheDocument();
    });
  });

  describe('Compact Layout', () => {
    it('renders compact layout correctly', () => {
      const mockOnClick = vi.fn();
      render(<ProductCard product={mockProduct} layout="compact" onClick={mockOnClick} />);

      expect(screen.getByText('Nike')).toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
      expect(screen.queryByText('В корзину')).not.toBeInTheDocument();
    });

    it('calls onClick when card is clicked in compact layout', () => {
      const mockOnClick = vi.fn();
      render(<ProductCard product={mockProduct} layout="compact" onClick={mockOnClick} />);

      const card = screen.getByRole('article');
      fireEvent.click(card);

      expect(mockOnClick).toHaveBeenCalledTimes(1);
    });

    it('shows out of stock message in compact layout', () => {
      const outOfStockProduct = { ...mockProduct, is_in_stock: false };
      render(<ProductCard product={outOfStockProduct} layout="compact" />);

      expect(screen.getByText('Нет в наличии')).toBeInTheDocument();
    });
  });

  describe('Role-based Pricing', () => {
    it('displays retail pricing for B2C users', () => {
      render(<ProductCard product={mockProduct} userRole="retail" mode="b2c" layout="grid" />);

      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 1 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level1" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('1 000 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 2 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level2" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('900 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 3 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level3" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('800 ₽')).toBeInTheDocument();
    });

    it('displays wholesale level 4 pricing', () => {
      render(
        <ProductCard product={mockProduct} userRole="wholesale_level4" mode="b2b" layout="grid" />
      );

      expect(screen.getByText('700 ₽')).toBeInTheDocument();
    });

    it('falls back to level 3 price when opt4 is missing', () => {
      const productWithoutOpt4 = { ...mockProduct, opt4_price: undefined };
      render(
        <ProductCard
          product={productWithoutOpt4}
          userRole="wholesale_level4"
          mode="b2b"
          layout="grid"
        />
      );

      expect(screen.getByText('800 ₽')).toBeInTheDocument();
    });

    it('falls back to retail price when wholesale price not available', () => {
      const productWithoutWholesale = { ...mockProduct, opt1_price: undefined };
      render(
        <ProductCard product={productWithoutWholesale} userRole="wholesale_level1" layout="grid" />
      );

      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    });

    it('displays RRP for B2B users when showRRP is true', () => {
      const productWithRRP = {
        ...mockProduct,
        rrp: 1300,
      };
      render(
        <ProductCard
          product={productWithRRP}
          userRole="wholesale_level1"
          mode="b2b"
          showRRP={true}
          layout="grid"
        />
      );

      expect(screen.getByText(/РРЦ.*1 300/)).toBeInTheDocument();
    });
  });

  describe('Badge Logic', () => {
    it('displays SALE badge when product has discount', () => {
      const saleProduct = { ...mockProduct, is_sale: true, discount_percent: 20 };
      render(<ProductCard product={saleProduct} layout="grid" />);

      expect(screen.getByTestId('badge-sale')).toBeInTheDocument();
      expect(screen.getByText('20% скидка')).toBeInTheDocument();
    });

    it('displays NEW badge when product is new', () => {
      const newProduct = { ...mockProduct, is_new: true };
      render(<ProductCard product={newProduct} layout="grid" />);

      expect(screen.getByTestId('badge-new')).toBeInTheDocument();
    });

    it('displays HIT badge when product is hit', () => {
      const hitProduct = { ...mockProduct, is_hit: true };
      render(<ProductCard product={hitProduct} layout="grid" />);

      expect(screen.getByTestId('badge-hit')).toBeInTheDocument();
    });

    it('does not display badge when no flags are set', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.queryByTestId('badge-sale')).not.toBeInTheDocument();
      expect(screen.queryByTestId('badge-new')).not.toBeInTheDocument();
      expect(screen.queryByTestId('badge-hit')).not.toBeInTheDocument();
    });

    it('displays old price with line-through when discount exists', () => {
      const discountProduct = { ...mockProduct, discount_percent: 20 };
      const { container } = render(<ProductCard product={discountProduct} layout="grid" />);

      const oldPriceElement = container.querySelector('.line-through');
      expect(oldPriceElement).toBeInTheDocument();
      expect(oldPriceElement).toHaveTextContent('1 200 ₽');
    });
  });

  describe('Promo Pricing', () => {
    const layouts = ['grid', 'list', 'compact'] as const;
    const promoProduct: Product = {
      ...mockProduct,
      is_promo: true,
      promo_price: '800.00',
      current_price: '800.00',
      regular_price: '1000.00',
    };

    it.each(layouts)('показывает стикер «Акция» поверх распродажи в раскладке %s', layout => {
      render(
        <ProductCard
          product={{ ...promoProduct, is_sale: true, discount_percent: 20 }}
          layout={layout}
        />
      );

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.queryByText('20% скидка')).not.toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
    });

    it.each(layouts)(
      'флаг is_promo без акционной цены не даёт стикер «Акция» в раскладке %s',
      layout => {
        render(
          <ProductCard
            product={{ ...mockProduct, is_promo: true, is_sale: true, discount_percent: 20 }}
            layout={layout}
          />
        );

        // Стикер — по тому же правилу, что цена и подписи: нет применённой акции — нет стикера;
        // вместо него обычный стикер товара (распродажа)
        expect(screen.queryByText('Акция')).not.toBeInTheDocument();
        expect(screen.getByText('20% скидка')).toBeInTheDocument();
      }
    );

    it.each(layouts)('shows bold promo price and struck regular price in %s layout', layout => {
      render(<ProductCard product={promoProduct} layout={layout} userRole="wholesale_level2" />);

      const promoPrice = screen.getByTestId('promo-price');
      expect(promoPrice).toHaveTextContent('800 ₽');
      expect(promoPrice).toHaveClass('font-bold');
      const regularPrice = screen.getByTestId('regular-price');
      expect(regularPrice).toHaveTextContent('1 000 ₽');
      expect(regularPrice).toHaveClass('line-through');
    });

    it.each(layouts)(
      'подписывает назначение обеих цен для скринридера в раскладке %s',
      layout => {
        render(<ProductCard product={promoProduct} layout={layout} userRole="wholesale_level2" />);

        // Зачёркивание и жирность — только CSS: при чтении по порядку сумм без подписей
        // не понять, какую платит покупатель
        const promoLabel = within(screen.getByTestId('promo-price')).getByText(/Акционная цена/);
        expect(promoLabel).toHaveClass('sr-only');
        const regularLabel = within(screen.getByTestId('regular-price')).getByText(
          /Цена без акции/
        );
        expect(regularLabel).toHaveClass('sr-only');
      }
    );

    it.each(layouts)(
      'без зачёркнутой цены подписана только акционная в раскладке %s',
      layout => {
        const product = { ...promoProduct, regular_price: '800.00' };
        render(<ProductCard product={product} layout={layout} />);

        expect(
          within(screen.getByTestId('promo-price')).getByText(/Акционная цена/)
        ).toBeInTheDocument();
        expect(screen.queryByText(/Цена без акции/)).not.toBeInTheDocument();
      }
    );

    it.each(layouts)('обычная цена без акции остаётся без подписей в раскладке %s', layout => {
      render(<ProductCard product={mockProduct} layout={layout} />);

      expect(screen.queryByText(/Акционная цена/)).not.toBeInTheDocument();
      expect(screen.queryByText(/Цена без акции/)).not.toBeInTheDocument();
    });

    it.each(layouts)('hides struck price when regular equals promo in %s layout', layout => {
      const product = { ...promoProduct, regular_price: '800.00' };
      const { container } = render(<ProductCard product={product} layout={layout} />);

      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
      expect(container.querySelector('.line-through')).not.toBeInTheDocument();
    });

    // Клиент платит меньшую из цен: цена клиента 700 при акции 800 — акция ему не выгодна
    const unappliedPromo: Product = {
      ...promoProduct,
      promo_price: '800.00',
      current_price: '700.00',
      regular_price: '700.00',
    };

    it.each(layouts)('promo above client price looks like no promo in %s layout', layout => {
      const { container } = render(
        <ProductCard product={unappliedPromo} layout={layout} userRole="wholesale_level4" />
      );

      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
      expect(screen.queryByTestId('badge-promo')).not.toBeInTheDocument();
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
      expect(screen.queryByText(/Акционная цена/)).not.toBeInTheDocument();
      expect(container.querySelector('.line-through')).not.toBeInTheDocument();
      expect(screen.getByText('700 ₽')).toBeInTheDocument();
    });

    it.each(layouts)('promo above client price: all three marks come back at 900 in %s', layout => {
      // Та же акция 800 при цене клиента 900: стикер, зачёркнутая цена и подпись
      const product = { ...unappliedPromo, current_price: '800.00', regular_price: '900.00' };
      render(<ProductCard product={product} layout={layout} userRole="wholesale_level4" />);

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('900 ₽');
      expect(screen.getByText(/Акционная цена/)).toBeInTheDocument();
    });

    it.each(layouts)('promo equal to client price counts as applied in %s layout', layout => {
      const product = { ...promoProduct, current_price: '800.00', regular_price: '800.00' };
      const { container } = render(
        <ProductCard product={product} layout={layout} userRole="wholesale_level3" />
      );

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('800 ₽');
      expect(screen.queryByTestId('regular-price')).not.toBeInTheDocument();
      expect(container.querySelector('.line-through')).not.toBeInTheDocument();
    });

    // Неприменённая акция: сумму к оплате даёт current_price из API, а не цепочка цен карточки.
    // Список не отдаёт trainer_price / federation_price, а цепочка опт N → опт N-1 расходится
    // с backend, который без своей цены уровня берёт розницу
    it.each(['trainer', 'federation_rep'] as const)(
      'unapplied promo shows the API price of %s, not retail',
      role => {
        const product = {
          ...mockProduct,
          is_promo: true,
          promo_price: '800.00',
          current_price: '700.00',
          regular_price: '700.00',
        };
        render(<ProductCard product={product} layout="grid" userRole={role} />);

        expect(screen.getByText('700 ₽')).toBeInTheDocument();
        expect(screen.queryByText('1 200 ₽')).not.toBeInTheDocument();
        expect(screen.queryByText('Акция')).not.toBeInTheDocument();
      }
    );

    it('unapplied promo shows the API price of a level without its own price', () => {
      // opt3 пуст: backend берёт розницу 1200, а цепочка карточки дала бы opt2 = 900
      const product = {
        ...mockProduct,
        opt3_price: undefined,
        is_promo: true,
        promo_price: '1300.00',
        current_price: '1200.00',
        regular_price: '1200.00',
      };
      render(<ProductCard product={product} layout="grid" userRole="wholesale_level3" />);

      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
      expect(screen.queryByText('900 ₽')).not.toBeInTheDocument();
    });

    it('promo price wins over role price when it is lower', () => {
      const product = {
        ...promoProduct,
        promo_price: '600.00',
        current_price: '600.00',
        regular_price: '700.00',
      };
      render(<ProductCard product={product} layout="grid" userRole="wholesale_level4" />);

      expect(screen.getByTestId('promo-price')).toHaveTextContent('600 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('700 ₽');
    });

    it('discount strike-through is not shown during promo', () => {
      const product = { ...promoProduct, regular_price: '800.00', discount_percent: 20 };
      const { container } = render(<ProductCard product={product} layout="grid" />);

      expect(container.querySelector('.line-through')).not.toBeInTheDocument();
    });

    it('null promo_price keeps role pricing', () => {
      const product = { ...mockProduct, promo_price: null, current_price: '1200.00' };
      render(<ProductCard product={product} layout="grid" userRole="wholesale_level1" />);

      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.getByText('1 000 ₽')).toBeInTheDocument();
    });
  });

  describe('Роли VIP и «Спец цена»', () => {
    // API сырых vip_price / special_price не отдаёт: цена роли приходит в regular_price,
    // итог (с акцией) — в current_price
    const rolePriced: Product = {
      ...mockProduct,
      opt1_price: undefined,
      current_price: '900.00',
      regular_price: '900.00',
      promo_price: null,
    };
    const roles = ['vip', 'special_price'] as const;
    const layouts = ['grid', 'list', 'compact'] as const;

    it.each(roles)('shows the price of the role from regular_price for %s', role => {
      render(<ProductCard product={rolePriced} userRole={role} layout="grid" />);

      expect(screen.getByText('900 ₽')).toBeInTheDocument();
      expect(screen.queryByText('1 200 ₽')).not.toBeInTheDocument();
    });

    it.each(roles)('falls back to current_price, then retail for %s', role => {
      const onlyCurrent = { ...rolePriced, regular_price: undefined };
      const { unmount } = render(
        <ProductCard product={onlyCurrent} userRole={role} layout="grid" />
      );
      expect(screen.getByText('900 ₽')).toBeInTheDocument();
      unmount();

      const noApiPrices = { ...rolePriced, regular_price: undefined, current_price: undefined };
      render(<ProductCard product={noApiPrices} userRole={role} layout="grid" />);
      expect(screen.getByText('1 200 ₽')).toBeInTheDocument();
    });

    it.each(roles)('applied promo below the role price: promo, sticker, struck price for %s', role => {
      const product = {
        ...rolePriced,
        is_promo: true,
        promo_price: '700.00',
        current_price: '700.00',
        regular_price: '900.00',
      };
      render(<ProductCard product={product} userRole={role} layout="grid" />);

      expect(screen.getByText('Акция')).toBeInTheDocument();
      expect(screen.getByTestId('promo-price')).toHaveTextContent('700 ₽');
      expect(screen.getByTestId('regular-price')).toHaveTextContent('900 ₽');
    });

    it.each(roles)('promo above the role price looks like no promo for %s', role => {
      const product = {
        ...rolePriced,
        is_promo: true,
        promo_price: '1000.00',
        current_price: '900.00',
        regular_price: '900.00',
      };
      render(<ProductCard product={product} userRole={role} layout="grid" />);

      expect(screen.queryByText('Акция')).not.toBeInTheDocument();
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.getByText('900 ₽')).toBeInTheDocument();
    });

    it.each(roles)('shows RRP like for other B2B roles for %s', role => {
      render(
        <ProductCard
          product={{ ...rolePriced, rrp: 1300 }}
          userRole={role}
          mode="b2c"
          layout="grid"
        />
      );

      expect(screen.getByText(/РРЦ.*1 300/)).toBeInTheDocument();
    });

    it.each(layouts)('renders the role price in %s layout', layout => {
      render(<ProductCard product={rolePriced} userRole="vip" layout={layout} />);

      expect(screen.getByText('900 ₽')).toBeInTheDocument();
    });
  });

  describe('Favorite Button', () => {
    it('calls onToggleFavorite when favorite button is clicked', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      expect(mockOnToggleFavorite).toHaveBeenCalledWith(1);
      expect(mockOnToggleFavorite).toHaveBeenCalledTimes(1);
    });

    it('shows correct aria-label when product is favorite', () => {
      render(
        <ProductCard
          product={mockProduct}
          layout="grid"
          onToggleFavorite={mockOnToggleFavorite}
          isFavorite={true}
        />
      );

      expect(screen.getByLabelText('Удалить из избранного')).toBeInTheDocument();
    });

    it('shows correct aria-label when product is not favorite', () => {
      render(
        <ProductCard
          product={mockProduct}
          layout="grid"
          onToggleFavorite={mockOnToggleFavorite}
          isFavorite={false}
        />
      );

      expect(screen.getByLabelText('Добавить в избранное')).toBeInTheDocument();
    });

    it('renders filled heart icon when isFavorite is true', () => {
      render(<ProductCard product={mockProduct} layout="grid" isFavorite={true} />);

      const heartIcon = screen.getByTestId('heart-icon');
      expect(heartIcon).toHaveAttribute('data-fill', 'currentColor');
    });

    it('renders outline heart icon when isFavorite is false', () => {
      render(<ProductCard product={mockProduct} layout="grid" isFavorite={false} />);

      const heartIcon = screen.getByTestId('heart-icon');
      expect(heartIcon).toHaveAttribute('data-fill', 'none');
    });

    it('prevents event bubbling when favorite button is clicked', () => {
      const mockOnClick = vi.fn();
      render(
        <ProductCard
          product={mockProduct}
          layout="compact"
          onClick={mockOnClick}
          onToggleFavorite={mockOnToggleFavorite}
        />
      );

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      expect(mockOnToggleFavorite).toHaveBeenCalledTimes(1);
      expect(mockOnClick).not.toHaveBeenCalled();
    });
  });

  describe('Accessibility', () => {
    it('has correct role attribute', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const card = screen.getByRole('article');
      expect(card).toBeInTheDocument();
    });

    it('has correct aria-label on card', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.getByLabelText('Товар: Test Product')).toBeInTheDocument();
    });

    it('has correct aria-label on favorite button', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      expect(screen.getByLabelText('Добавить в избранное')).toBeInTheDocument();
    });

    it('favorite button has role="button"', () => {
      render(
        <ProductCard product={mockProduct} layout="grid" onToggleFavorite={mockOnToggleFavorite} />
      );

      const favoriteButton = screen.getByRole('button', { name: 'Добавить в избранное' });
      expect(favoriteButton).toBeInTheDocument();
    });

    it('product image has alt text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const image = screen.getByRole('img', { name: 'Test Product' });
      expect(image).toBeInTheDocument();
    });

    it('has title attribute on product name for truncated text', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const productName = screen.getByText('Test Product');
      expect(productName).toHaveAttribute('title', 'Test Product');
    });
  });

  describe('Edge Cases', () => {
    it('handles product without brand', () => {
      const productWithoutBrand = { ...mockProduct, brand: undefined };
      render(<ProductCard product={productWithoutBrand} layout="grid" />);

      expect(screen.queryByText('Nike')).not.toBeInTheDocument();
      expect(screen.getByText('Test Product')).toBeInTheDocument();
    });

    it('handles product without description in list layout', () => {
      const productWithoutDescription = { ...mockProduct, description: '' };
      render(<ProductCard product={productWithoutDescription} layout="list" />);

      expect(screen.queryByText('Test description')).not.toBeInTheDocument();
    });

    it('hides select button without showSelectButton', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      expect(screen.queryByText('Выбрать')).not.toBeInTheDocument();
    });

    it('handles missing onToggleFavorite callback', () => {
      render(<ProductCard product={mockProduct} layout="grid" />);

      const favoriteButton = screen.getByLabelText('Добавить в избранное');
      fireEvent.click(favoriteButton);

      // Should not throw error
      expect(favoriteButton).toBeInTheDocument();
    });

    it('applies custom className', () => {
      render(<ProductCard product={mockProduct} layout="grid" className="custom-class" />);

      const card = screen.getByRole('article');
      expect(card).toHaveClass('custom-class');
    });
  });
});
