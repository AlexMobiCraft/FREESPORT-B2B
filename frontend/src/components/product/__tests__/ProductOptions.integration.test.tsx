/**
 * Integration тесты для ProductOptions (Story 13.5b)
 * Тестирование интеграции ProductOptions с ProductGallery и ProductSummary
 *
 * @see docs/stories/epic-13/13.5b.productoptions-api-integration.md
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
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
    main_image: '/media/nike-red.jpg',
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
    main_image: '/media/nike-blue.jpg',
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
    main_image: '/media/nike-red.jpg',
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
    main_image: '/media/nike-blue.jpg',
  },
];

const mockProduct: ProductDetailWithVariants = {
  id: 1,
  slug: 'nike-air-max',
  name: 'Nike Air Max',
  sku: 'NIKE-AM',
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
    it('обновляет изображение при изменении selectedVariant', () => {
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

      // Изображение должно обновиться на изображение варианта
      const updatedImages = screen.getAllByRole('img');
      const updatedMainImage = updatedImages[0];
      expect(updatedMainImage).toHaveAttribute('src', expect.stringContaining('nike-red'));
    });

    it('обновляет галерею при изменении selectedVariant', () => {
      const { rerender } = render(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={null}
        />
      );

      // Изначально 2 изображения в галерее
      expect(screen.getByTestId('image-thumbnails').children.length).toBe(2);

      // Обновляем с вариантом у которого есть gallery_images
      rerender(
        <ProductImageGallery
          images={mockProduct.images}
          productName={mockProduct.name}
          selectedVariant={mockVariants[0]} // Красный с 2 gallery_images
        />
      );

      // Галерея должна обновиться: main_image + 2 gallery_images = 3
      expect(screen.getByTestId('image-thumbnails').children.length).toBe(3);
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

      // Должен показать только main_image
      // Thumbnails не должны отображаться если только 1 изображение
      expect(screen.queryByTestId('image-thumbnails')).not.toBeInTheDocument();
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

      // Должен отображаться артикул выбранного варианта
      expect(screen.getAllByText('SIMPLE-VARIANT').length).toBeGreaterThan(0);


    });
  });
});
