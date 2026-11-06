/**
 * Integration тесты для ProductOptions (Story 13.5b)
 * Тестирование интеграции ProductOptions с ProductGallery и ProductSummary
 *
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { renderToStaticMarkup } from 'react-dom/server';
import ProductPageClient from '../ProductPageClient';
import ProductSummary, { validateOptions } from '../ProductSummary';
import ProductImageGallery from '../ProductImageGallery';
import type { ProductVariant } from '@/types/api';
import type { ProductDetailWithVariants } from '../ProductSummary';
// Mock useToast using vi.hoisted to avoid reference errors
const { mockToast } = vi.hoisted(() => {
  return {
    mockToast: {
      success: vi.fn(),
      error: vi.fn(),
    },
  };
});

vi.mock('@/components/ui/Toast', () => ({
  useToast: () => mockToast,
}));

/**
 * Mock данные для интеграционных тестов
 */
const mockVariants: ProductVariant[] = [
  {
    id: 1,
    sku: 'NIKE-AM-RED-42',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 15,
    is_in_stock: true,
    available_quantity: 15,
    stock_range: '15 шт.',
    main_image: '/media/products/variants/nike-red.jpg',
    gallery_images: ['/media/nike-red-side.jpg', '/media/nike-red-back.jpg'],
  },
  {
    id: 2,
    sku: 'NIKE-AM-BLUE-42',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '42',
    current_price: '6490.00',
    stock_quantity: 10,
    is_in_stock: true,
    available_quantity: 10,
    stock_range: '10 шт.',
    main_image: '/media/products/variants/nike-blue.jpg',
    gallery_images: ['/media/nike-blue-side.jpg'],
  },
  {
    id: 3,
    sku: 'NIKE-AM-RED-43',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '43',
    current_price: '5990.00',
    stock_quantity: 0,
    is_in_stock: false,
    available_quantity: 0,
    stock_range: 'Нет в наличии',
    main_image: '/media/products/variants/nike-red.jpg',
  },
  {
    id: 4,
    sku: 'NIKE-AM-BLUE-43',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '43',
    current_price: '6490.00',
    stock_quantity: 5,
    is_in_stock: true,
    available_quantity: 5,
    stock_range: '5 шт.',
    main_image: '/media/products/variants/nike-blue.jpg',
  },
];

const mockProduct: ProductDetailWithVariants = {
  id: 1,
  slug: 'nike-air-max',
  name: 'Nike Air Max',
  sku: 'NIKE-AM',
  article: 'AM-90-RED',
  brand: 'Nike',
  description: 'Классические кроссовки Nike Air Max',
  price: {
    retail: 5990,
    currency: 'RUB',
  },
  stock_quantity: 30,
  images: [
    { image: '/media/nike-default.jpg', alt_text: 'Nike Air Max', is_primary: true },
    {
      image: '/media/nike-default-side.jpg',
      alt_text: 'Nike Air Max вид сбоку',
      is_primary: false,
    },
    { image: '/media/products/base/nike-red.jpg', alt_text: 'Nike Air Max Красный', is_primary: false },
    { image: '/media/products/base/nike-blue.jpg', alt_text: 'Nike Air Max Синий', is_primary: false },
  ],
  category: {
    id: 1,
    name: 'Кроссовки',
    slug: 'sneakers',
    breadcrumbs: [
      { id: 100, name: 'Обувь', slug: 'shoes' },
      { id: 101, name: 'Кроссовки', slug: 'sneakers' },
    ],
  },
  is_in_stock: true,
  can_be_ordered: true,
  variants: mockVariants,
};

describe('ProductOptions Integration (Story 13.5b)', () => {
  describe('validateOptions function (AC: 6)', () => {
    it('возвращает ошибку если размер не выбран', () => {
      const result = validateOptions({ color: 'Красный' }, mockVariants);
      expect(result.valid).toBe(false);
      expect(result.message).toBe('Пожалуйста, выберите размер');
    });

    it('возвращает ошибку если цвет не выбран', () => {
      const result = validateOptions({ size: '42' }, mockVariants);
      expect(result.valid).toBe(false);
      expect(result.message).toBe('Пожалуйста, выберите цвет');
    });

    it('возвращает valid: true если все опции выбраны', () => {
      const result = validateOptions({ size: '42', color: 'Красный' }, mockVariants);
      expect(result.valid).toBe(true);
      expect(result.message).toBeUndefined();
    });

    it('возвращает valid: true если нет размеров в вариантах', () => {
      const variantsWithoutSizes: ProductVariant[] = [
        {
          id: 1,
          sku: 'TEST',
          color_name: 'Красный',
          current_price: '100',
          stock_quantity: 1,
          is_in_stock: true,
          available_quantity: 1,
        },
      ];
      const result = validateOptions({ color: 'Красный' }, variantsWithoutSizes);
      expect(result.valid).toBe(true);
    });

    it('возвращает valid: true если нет цветов в вариантах', () => {
      const variantsWithoutColors: ProductVariant[] = [
        {
          id: 1,
          sku: 'TEST',
          size_value: '42',
          current_price: '100',
          stock_quantity: 1,
          is_in_stock: true,
          available_quantity: 1,
        },
      ];
      const result = validateOptions({ size: '42' }, variantsWithoutColors);
      expect(result.valid).toBe(true);
    });
  });

  describe('ProductSummary Integration (AC: 4, 5, IV3)', () => {
    it('автоматически выбирает вариант по умолчанию', () => {
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      // Должен автоматически выбрать первый вариант
      expect(screen.getByTestId('add-to-cart-button')).toHaveTextContent('Добавить в корзину');
      expect(screen.getByTestId('add-to-cart-button')).not.toBeDisabled();
      expect(screen.getByTestId('selected-variant-info')).toBeInTheDocument();
    });

    it('показывает артикул товара, а не технический sku варианта', () => {
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      const info = screen.getByTestId('selected-variant-info');
      expect(info).toHaveTextContent('AM-90-RED');
      expect(info).not.toHaveTextContent('NIKE-AM-RED-42');
    });

    it('показывает прочерк, когда артикул в 1С не заполнен', () => {
      render(<ProductSummary product={{ ...mockProduct, article: '' }} userRole="retail" />);

      expect(screen.getByTestId('selected-variant-info')).toHaveTextContent('Артикул:—');
    });

    it('обновляет цену при выборе варианта', async () => {
      const user = userEvent.setup();
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      // Выбираем размер 42
      const size42 = screen.getByRole('radio', { name: /Размер: 42/i });
      await user.click(size42);

      // Выбираем цвет Красный
      const redColor = screen.getByRole('radio', { name: /Цвет: Красный/i });
      await user.click(redColor);

      // Проверяем что отображается информация о варианте
      await waitFor(() => {
        expect(screen.getByTestId('selected-variant-info')).toBeInTheDocument();
      });

      // Проверяем цену (она может быть в ProductInfo или в selected-variant-info)
      expect(screen.getByText(/5\s*990/)).toBeInTheDocument();
    });

    it('отображает наличие выбранного варианта', async () => {
      const user = userEvent.setup();
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      // Выбираем доступный вариант
      await user.click(screen.getByRole('radio', { name: /Размер: 42/i }));
      await user.click(screen.getByRole('radio', { name: /Цвет: Красный/i }));

      await waitFor(() => {
        expect(screen.getByText(/15 шт\./)).toBeInTheDocument();
      });
    });

    // Тест удален так как авто-выбор предотвращает состояние "ничего не выбрано" при загрузке
    // для товаров с валидными вариантами.
    // it('показывает ошибку валидации при попытке добавить в корзину без выбора опций', ...

    it('кнопка "Добавить в корзину" активна сразу (из-за авто-выбора)', async () => {
      const user = userEvent.setup();
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      // Изначально кнопка enabled из-за авто-выбора
      expect(screen.getByTestId('add-to-cart-button')).not.toBeDisabled();
      expect(screen.getByTestId('add-to-cart-button')).toHaveTextContent('Добавить в корзину');

      // Можем изменить выбор
      await user.click(screen.getByRole('radio', { name: /Цвет: Синий/i }));

      // Кнопка все еще enabled
      await waitFor(() => {
        expect(screen.getByTestId('add-to-cart-button')).not.toBeDisabled();
      });
    });

    it('вызывает onVariantChange при изменении выбора', async () => {
      const user = userEvent.setup();
      const onVariantChange = vi.fn();

      render(
        <ProductSummary product={mockProduct} userRole="retail" onVariantChange={onVariantChange} />
      );

      // Выбираем размер
      await user.click(screen.getByRole('radio', { name: /Размер: 42/i }));

      expect(onVariantChange).toHaveBeenCalled();
    });

    it('вызывает onAddToCart с variantId при добавлении в корзину', async () => {
      const user = userEvent.setup();
      const onAddToCart = vi.fn();

      render(<ProductSummary product={mockProduct} userRole="retail" onAddToCart={onAddToCart} />);

      // Выбираем опции
      await user.click(screen.getByRole('radio', { name: /Размер: 42/i }));
      await user.click(screen.getByRole('radio', { name: /Цвет: Красный/i }));

      // Добавляем в корзину
      await user.click(screen.getByTestId('add-to-cart-button'));

      expect(onAddToCart).toHaveBeenCalledWith(1); // ID первого варианта
    });
  });

  describe('ProductImageGallery Integration (AC: 3, IV2)', () => {
    it('выбирает кадр товара, совпадающий с фото варианта', () => {
      const { rerender } = render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={null}
        />
      );

      // Изначально показывается default изображение (первый img - main image)
      const images = screen.getAllByRole('img');
      const mainImage = images[0];
      expect(mainImage).toHaveAttribute('src', expect.stringContaining('nike-default'));

      // Обновляем с выбранным вариантом
      rerender(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={mockVariants[0]} // Красный вариант
        />
      );

      // Основным становится кадр товара с тем же именем файла
      const updatedMainImage = screen.getAllByRole('img')[0];
      expect(updatedMainImage).toHaveAttribute(
        'src',
        expect.stringContaining('/media/products/base/nike-red.jpg')
      );
    });

    it('не подменяет галерею товара фото варианта', () => {
      const { rerender } = render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={null}
        />
      );

      expect(screen.getByTestId('image-thumbnails').children.length).toBe(4);

      rerender(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={mockVariants[0]} // Красный с 2 gallery_images
        />
      );

      // gallery_images варианта в галерею не попадают
      expect(screen.getByTestId('image-thumbnails').children.length).toBe(4);
    });

    it('показывает фото товара, если фото варианта среди них нет', () => {
      // Устаревшее фото варианта: 1С обновила фото товара, а вариант остался со старым
      const staleVariant: ProductVariant = {
        ...mockVariants[0],
        main_image: '/media/products/variants/nike-old.jpg',
        gallery_images: ['/media/products/variants/nike-old-side.jpg'],
      };

      render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={staleVariant}
        />
      );

      const srcs = screen.getAllByRole('img').map(img => img.getAttribute('src'));
      expect(srcs[0]).toEqual(expect.stringContaining('nike-default'));
      expect(srcs.some(src => src?.includes('nike-old'))).toBe(false);
      expect(screen.getByTestId('image-thumbnails').children.length).toBe(4);
    });

    it('сбрасывает изображения при сбросе selectedVariant', () => {
      const { rerender } = render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={mockVariants[0]}
        />
      );

      // Сбрасываем вариант
      rerender(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={null}
        />
      );

      // Должны вернуться к исходным изображениям (первый img - main image)
      const images = screen.getAllByRole('img');
      const mainImage = images[0];
      expect(mainImage).toHaveAttribute('src', expect.stringContaining('nike-default'));
    });
  });

  describe('ProductPageClient Full Integration', () => {
    it('синхронизирует ProductGallery с ProductOptions через selectedVariant', async () => {
      const user = userEvent.setup();

      render(<ProductPageClient product={mockProduct} userRole="retail" />);

      // Выбираем синий цвет
      await user.click(screen.getByRole('radio', { name: /Цвет: Синий/i }));

      // Проверяем что изображение обновилось
      await waitFor(() => {
        const images = screen.getAllByRole('img');
        const mainImage = images.find(img => img.getAttribute('alt')?.includes('Синий'));
        expect(mainImage).toBeTruthy();
      });
    });

    it('отображает цену выбранного варианта в ProductSummary', async () => {
      const user = userEvent.setup();

      render(<ProductPageClient product={mockProduct} userRole="retail" />);

      // Выбираем синий вариант (цена 6490)
      await user.click(screen.getByRole('radio', { name: /Размер: 42/i }));
      await user.click(screen.getByRole('radio', { name: /Цвет: Синий/i }));

      // Проверяем цену
      await waitFor(() => {
        expect(screen.getByText(/6\s*490/)).toBeInTheDocument();
      });
    });
  });

  describe('Edge Cases', () => {
    it('корректно работает с товаром без вариантов', () => {
      const productWithoutVariants: ProductDetailWithVariants = {
        ...mockProduct,
        variants: [],
      };

      render(<ProductSummary product={productWithoutVariants} userRole="retail" />);

      // Кнопка должна быть enabled (товар в наличии)
      expect(screen.getByTestId('add-to-cart-button')).not.toBeDisabled();
      expect(screen.getByTestId('add-to-cart-button')).toHaveTextContent('Добавить в корзину');
    });

    it('блокирует кнопку для недоступного варианта', async () => {
      const user = userEvent.setup();
      render(<ProductSummary product={mockProduct} userRole="retail" />);

      // Выбираем недоступный вариант (Красный 43 - is_in_stock: false)
      await user.click(screen.getByRole('radio', { name: /Размер: 43/i }));
      await user.click(screen.getByRole('radio', { name: /Цвет: Красный/i }));

      // Кнопка должна показывать "Нет в наличии"
      await waitFor(() => {
        expect(screen.getByTestId('add-to-cart-button')).toHaveTextContent('Нет в наличии');
      });
    });

    it('обрабатывает вариант без gallery_images', () => {
      const variantWithoutGallery = mockVariants[2]; // Красный 43 без gallery_images

      render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={variantWithoutGallery}
        />
      );

      // Галерея товара целиком, основным выбран кадр варианта
      expect(screen.getByTestId('image-thumbnails').children.length).toBe(4);
      expect(screen.getAllByRole('img')[0]).toHaveAttribute(
        'src',
        expect.stringContaining('/media/products/base/nike-red.jpg')
      );
    });

    it('автоматически выбирает вариант если у вариантов нет опций (размер/цвет)', () => {
      const variantsWithoutOptions: ProductVariant[] = [
        {
          id: 1,
          sku: 'SIMPLE-VARIANT',
          current_price: '1000.00',
          stock_quantity: 10,
          is_in_stock: true,
          available_quantity: 10,
          // size_value and color_name are undefined/null
        },
      ];
      const productWithSimpleVariant = {
        ...mockProduct,
        variants: variantsWithoutOptions,
      };

      render(<ProductSummary product={productWithSimpleVariant} userRole="retail" />);

      // Кнопка должна быть enabled и "Добавить в корзину"
      const button = screen.getByTestId('add-to-cart-button');
      expect(button).not.toBeDisabled();
      expect(button).toHaveTextContent('Добавить в корзину');

      // Вариант выбран — блок с артикулом и наличием отрисован
      expect(screen.getByTestId('selected-variant-info')).toBeInTheDocument();
    });
  });
});

/**
 * R72, R73: видимая цена и `offers.price` в JSON-LD относятся к одному варианту.
 *
 * Тесты идут через настоящие `ProductPageClient`, `ProductSummary`, `ProductInfo` и `ProductOptions`:
 * прямой `rerender(ProductInfo)` разметку не создаёт и расхождения не покажет.
 */
describe('Видимая цена и JSON-LD при акции (R72, R73)', () => {
  function promoVariant(
    id: number,
    currentPrice: string,
    promoPrice: string | null,
    options: Pick<ProductVariant, 'size_value'> = {}
  ): ProductVariant {
    return {
      id,
      sku: `PROMO-JSONLD-${id}`,
      color_name: null,
      size_value: null,
      current_price: currentPrice,
      regular_price: '1200.00',
      promo_price: promoPrice,
      stock_quantity: 10,
      is_in_stock: true,
      available_quantity: 10,
      ...options,
    };
  }

  function promoProduct(variants: ProductVariant[]): ProductDetailWithVariants {
    return {
      ...mockProduct,
      price: { retail: 1200, currency: 'RUB' },
      // Верхнеуровневые поля API выбраны по варианту с акцией
      current_price: '800.00',
      regular_price: '1200.00',
      promo_price: '800.00',
      variants,
    };
  }

  function offerPrice(container: HTMLElement): number {
    const script = container.querySelector('script[type="application/ld+json"]')!;
    return JSON.parse(script.textContent ?? '').offers.price;
  }

  function offerPriceOfHtml(html: string): number {
    const open = '<script type="application/ld+json">';
    const bodyStart = html.indexOf(open) + open.length;
    return JSON.parse(html.slice(bodyStart, html.indexOf('</script>', bodyStart))).offers.price;
  }

  describe('товар без опций с двумя вариантами (R72)', () => {
    // Первый вариант обычный (1200), второй акционный (800): сводка выбирает первый
    const variants = [promoVariant(1, '1200.00', null), promoVariant(2, '800.00', '800.00')];

    it('после монтирования в разметке цена выбранного варианта, а не верхнеуровневая акционная', () => {
      const { container } = render(
        <ProductPageClient product={promoProduct(variants)} userRole="retail" />
      );

      expect(screen.getByText(/1\s*200\s*₽/)).toBeInTheDocument();
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(offerPrice(container)).toBe(1200);
    });

    it('SSR-разметка отдаёт ту же сумму, что видит покупатель', () => {
      // Поисковики читают HTML до гидрации: начальный выбор не должен ждать эффекта
      const html = renderToStaticMarkup(
        <ProductPageClient product={promoProduct(variants)} userRole="retail" />
      );

      expect(html).toMatch(/1\s*200\s*₽/);
      expect(offerPriceOfHtml(html)).toBe(1200);
    });

    it('оптовик без акции: в разметке ролевая цена варианта, а не розница', () => {
      // Часть D11-1 для товара без опций: интерфейс показывает 700, а JSON-LD сообщал розничные 1200
      const wholesaleProduct: ProductDetailWithVariants = {
        ...promoProduct([promoVariant(1, '700.00', null)]),
        price: { retail: 1200, wholesale: { level1: 700 }, currency: 'RUB' },
        current_price: '700.00',
        regular_price: '700.00',
        promo_price: null,
      };

      const { container } = render(
        <ProductPageClient product={wholesaleProduct} userRole="wholesale_level1" />
      );

      expect(screen.getByText(/700\s*₽/)).toBeInTheDocument();
      expect(offerPrice(container)).toBe(700);
    });

    it('единственный акционный вариант без опций: и сумма, и разметка акционные', () => {
      const { container } = render(
        <ProductPageClient
          product={promoProduct([promoVariant(2, '800.00', '800.00')])}
          userRole="retail"
        />
      );

      expect(screen.getByTestId('promo-price')).toHaveTextContent(/800/);
      expect(offerPrice(container)).toBe(800);
    });
  });

  describe('товар с опциями до автовыбора (D14-2)', () => {
    it('оптовик без акции: SSR показывает и называет в разметке ролевую цену, а не розницу', () => {
      // Автовыбор — эффект, в SSR его нет: вариант не выбран, цена берётся с товара.
      // Цены вариантов отличаются от цены товара, чтобы SSR не мог взять цену варианта
      const wholesaleProduct: ProductDetailWithVariants = {
        ...promoProduct([
          promoVariant(1, '650.00', null, { size_value: 'S' }),
          promoVariant(2, '650.00', null, { size_value: 'M' }),
        ]),
        price: { retail: 1200, wholesale: { level1: 700 }, currency: 'RUB' },
        current_price: '700.00',
        regular_price: '700.00',
        promo_price: null,
      };

      const html = renderToStaticMarkup(
        <ProductPageClient product={wholesaleProduct} userRole="wholesale_level1" />
      );

      expect(html).toMatch(/700\s*₽/);
      expect(offerPriceOfHtml(html)).toBe(700);
    });
  });

  describe('переключение размера между акционным и обычным вариантом (R73)', () => {
    const variants = [
      promoVariant(1, '800.00', '800.00', { size_value: 'S' }),
      promoVariant(2, '1200.00', null, { size_value: 'M' }),
    ];

    it('сумма в интерфейсе и offers.price меняются вместе в обе стороны', async () => {
      const user = userEvent.setup();
      const { container } = render(
        <ProductPageClient product={promoProduct(variants)} userRole="retail" />
      );

      // Автовыбор берёт первый вариант — акционный S
      await waitFor(() => expect(offerPrice(container)).toBe(800));
      expect(screen.getByTestId('promo-price')).toHaveTextContent(/800/);
      expect(screen.getByTestId('regular-price')).toHaveTextContent(/1\s*200/);

      await user.click(screen.getByRole('radio', { name: /Размер: M/i }));
      await waitFor(() => expect(offerPrice(container)).toBe(1200));
      expect(screen.queryByTestId('promo-price')).not.toBeInTheDocument();
      expect(screen.getByText(/1\s*200\s*₽/)).toBeInTheDocument();

      await user.click(screen.getByRole('radio', { name: /Размер: S/i }));
      await waitFor(() => expect(offerPrice(container)).toBe(800));
      expect(screen.getByTestId('promo-price')).toHaveTextContent(/800/);
    });
  });
});
