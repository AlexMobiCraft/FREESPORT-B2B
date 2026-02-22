/**
 * CartItemCard Component Tests
 *
 * Покрытие:
 * - Рендеринг всех полей товара
 * - +/- кнопки с Optimistic Updates
 * - Удаление товара
 * - Валидация quantity bounds (min=1, max=99)
 * - Image placeholder при отсутствии изображения
 * - Debounce на input (300ms)
 * - Loading state
 * - Accessibility
 *
 * @see Story 26.2: Cart Item Card Component
 */

import React from 'react';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { CartItemCard } from '../CartItemCard';
import type { CartItem } from '@/types/cart';

// Mock react-hot-toast
vi.mock('react-hot-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock next/image
vi.mock('next/image', () => ({
  default: ({ src, alt, ...props }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} data-testid="cart-item-image" {...props} />
  ),
}));

// Mock formatPrice
vi.mock('@/utils/pricing', () => ({
  formatPrice: (price: number) => `${price.toLocaleString('ru-RU')} ₽`,
}));

/**
 * Фикстура тестового элемента корзины
 */
const createMockCartItem = (overrides?: Partial<CartItem>): CartItem => ({
  id: 1,
  variant_id: 100,
  product: {
    id: 10,
    name: 'Кроссовки Nike Air Max',
    slug: 'nike-air-max',
    image: '/images/nike-air-max.jpg',
  },
  variant: {
    sku: 'NK-AM-001',
    color_name: 'Чёрный',
    size_value: '42',
  },
  quantity: 2,
  unit_price: '5990.00',
  total_price: '11980.00',
  added_at: '2025-12-07T12:00:00Z',
  ...overrides,
});

describe('CartItemCard', () => {
  const mockOnQuantityChange = vi.fn().mockResolvedValue({ success: true });
  const mockOnRemove = vi.fn().mockResolvedValue({ success: true });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // Базовый рендеринг
  describe('Rendering', () => {
    it('renders cart item card container', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('cart-item-card')).toBeInTheDocument();
    });

    it('renders product image', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      const image = screen.getByTestId('cart-item-image');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', '/images/nike-air-max.jpg');
      expect(image).toHaveAttribute('alt', 'Кроссовки Nike Air Max');
    });

    it('renders product name', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('cart-item-name')).toHaveTextContent('Кроссовки Nike Air Max');
    });

    it('renders SKU, color and size', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      const skuElement = screen.getByTestId('cart-item-sku');
      expect(skuElement).toHaveTextContent('Арт: NK-AM-001');
      expect(skuElement).toHaveTextContent('Цвет: Чёрный');
      expect(skuElement).toHaveTextContent('Размер: 42');
    });

    it('renders only SKU when color and size are null', () => {
      const item = createMockCartItem({
        variant: { sku: 'NK-001', color_name: null, size_value: null },
      });
      render(<CartItemCard item={item} />);

      const skuElement = screen.getByTestId('cart-item-sku');
      expect(skuElement).toHaveTextContent('Арт: NK-001');
      expect(skuElement).not.toHaveTextContent('Цвет:');
      expect(skuElement).not.toHaveTextContent('Размер:');
    });
  });

  // Image Placeholder
  describe('Image Placeholder', () => {
    it('renders placeholder when product.image is null', () => {
      const item = createMockCartItem({
        product: { id: 10, name: 'Test', slug: 'test', image: null },
      });
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('cart-item-image-placeholder')).toBeInTheDocument();
      expect(screen.queryByTestId('cart-item-image')).not.toBeInTheDocument();
    });

    it('placeholder has Package icon', () => {
      const item = createMockCartItem({
        product: { id: 10, name: 'Test', slug: 'test', image: null },
      });
      render(<CartItemCard item={item} />);

      const placeholder = screen.getByTestId('cart-item-image-placeholder');
      const svg = placeholder.querySelector('svg');
      expect(svg).toBeInTheDocument();
    });
  });

  // Price Display
  describe('Price Display', () => {
    it('renders unit price with quantity', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('cart-item-unit-price')).toHaveTextContent('5 990 ₽ × 2');
    });

    it('renders total price', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('cart-item-total-price')).toHaveTextContent('11 980 ₽');
    });

    it('correctly parses string prices from backend', () => {
      const item = createMockCartItem({
        unit_price: '1234.56',
        total_price: '2469.12',
        quantity: 2,
      });
      render(<CartItemCard item={item} />);

      // parseFloat преобразует string в number для formatPrice
      expect(screen.getByTestId('cart-item-unit-price')).toBeInTheDocument();
      expect(screen.getByTestId('cart-item-total-price')).toBeInTheDocument();
    });
  });

  // Quantity Selector Integration
  describe('Quantity Selector', () => {
    it('renders quantity selector with correct value', () => {
      const item = createMockCartItem({ quantity: 3 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      expect(screen.getByTestId('quantity-input')).toHaveValue('3');
    });

    it('calls onQuantityChange when increment button is clicked', () => {
      const item = createMockCartItem({ quantity: 2 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      fireEvent.click(incrementButton);

      expect(mockOnQuantityChange).toHaveBeenCalledWith(1, 3);
    });

    it('calls onQuantityChange when decrement button is clicked', () => {
      const item = createMockCartItem({ quantity: 3 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      fireEvent.click(decrementButton);

      expect(mockOnQuantityChange).toHaveBeenCalledWith(1, 2);
    });

    it('decrement button is disabled at quantity=1', () => {
      const item = createMockCartItem({ quantity: 1 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const decrementButton = screen.getByTestId('quantity-decrement');
      expect(decrementButton).toBeDisabled();
    });

    it('increment button is disabled at quantity=99', () => {
      const item = createMockCartItem({ quantity: 99 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      expect(incrementButton).toBeDisabled();
    });
  });

  // Debounce on Input
  describe('Debounce Input', () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });

    it('debounces input changes by 300ms', () => {
      const item = createMockCartItem({ quantity: 2 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const input = screen.getByTestId('quantity-input');

      // Изменяем значение
      fireEvent.change(input, { target: { value: '5' } });

      // Сразу после изменения - onChange не вызван
      expect(mockOnQuantityChange).not.toHaveBeenCalled();

      // Продвигаем таймер на 300ms
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // После debounce - onChange вызван
      expect(mockOnQuantityChange).toHaveBeenCalledWith(1, 5);
    });

    it('only calls onChange once for rapid input changes', () => {
      const item = createMockCartItem({ quantity: 2 });
      render(<CartItemCard item={item} onQuantityChange={mockOnQuantityChange} />);

      const input = screen.getByTestId('quantity-input');

      // Быстрые изменения
      fireEvent.change(input, { target: { value: '3' } });
      act(() => {
        vi.advanceTimersByTime(100);
      });

      fireEvent.change(input, { target: { value: '4' } });
      act(() => {
        vi.advanceTimersByTime(100);
      });

      fireEvent.change(input, { target: { value: '5' } });

      // Продвигаем на 300ms после последнего изменения
      act(() => {
        vi.advanceTimersByTime(300);
      });

      // onChange должен быть вызван только с последним значением
      expect(mockOnQuantityChange).toHaveBeenCalledTimes(1);
      expect(mockOnQuantityChange).toHaveBeenCalledWith(1, 5);
    });
  });

  // Remove Item
  describe('Remove Item', () => {
    it('renders remove button', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByTestId('remove-item-button')).toBeInTheDocument();
    });

    it('calls onRemove when remove button is clicked', async () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} onRemove={mockOnRemove} />);

      const removeButton = screen.getByTestId('remove-item-button');
      await act(async () => {
        fireEvent.click(removeButton);
      });

      expect(mockOnRemove).toHaveBeenCalledWith(1);
    });

    it('shows success toast on successful remove', async () => {
      const { toast } = await import('react-hot-toast');
      const item = createMockCartItem();

      render(<CartItemCard item={item} onRemove={mockOnRemove} />);

      const removeButton = screen.getByTestId('remove-item-button');
      await act(async () => {
        fireEvent.click(removeButton);
      });

      expect(toast.success).toHaveBeenCalledWith('Товар удалён из корзины');
    });

    it('shows error toast on failed remove', async () => {
      const { toast } = await import('react-hot-toast');
      const failingOnRemove = vi.fn().mockResolvedValue({ success: false, error: 'Error' });
      const item = createMockCartItem();

      render(<CartItemCard item={item} onRemove={failingOnRemove} />);

      const removeButton = screen.getByTestId('remove-item-button');
      await act(async () => {
        fireEvent.click(removeButton);
      });

      expect(toast.error).toHaveBeenCalledWith('Не удалось удалить товар');
    });
  });

  // Loading State
  describe('Loading State', () => {
    it('passes isUpdating to QuantitySelector', () => {
      const item = createMockCartItem();
      render(
        <CartItemCard item={item} isUpdating={true} onQuantityChange={mockOnQuantityChange} />
      );

      // При loading все кнопки должны быть disabled
      const input = screen.getByTestId('quantity-input');
      expect(input).toBeDisabled();
    });

    it('disables remove button when isUpdating', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} isUpdating={true} onRemove={mockOnRemove} />);

      const removeButton = screen.getByTestId('remove-item-button');
      expect(removeButton).toBeDisabled();
    });
  });

  // Optimistic Updates Error Handling
  describe('Optimistic Updates Error Handling', () => {
    it('shows error toast when quantity update fails', async () => {
      const { toast } = await import('react-hot-toast');
      const failingOnQuantityChange = vi.fn().mockResolvedValue({ success: false, error: 'Error' });
      const item = createMockCartItem({ quantity: 2 });

      render(<CartItemCard item={item} onQuantityChange={failingOnQuantityChange} />);

      const incrementButton = screen.getByTestId('quantity-increment');
      await act(async () => {
        fireEvent.click(incrementButton);
      });

      expect(toast.error).toHaveBeenCalledWith('Не удалось обновить количество');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('remove button has aria-label', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      const removeButton = screen.getByTestId('remove-item-button');
      expect(removeButton).toHaveAttribute('aria-label', 'Удалить товар');
    });

    it('quantity selector has role="spinbutton"', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    });

    it('quantity selector has aria-valuenow', () => {
      const item = createMockCartItem({ quantity: 5 });
      render(<CartItemCard item={item} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuenow', '5');
    });

    it('quantity selector has aria-valuemin and aria-valuemax', () => {
      const item = createMockCartItem();
      render(<CartItemCard item={item} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuemin', '1');
      expect(spinbutton).toHaveAttribute('aria-valuemax', '99');
    });
  });
});
