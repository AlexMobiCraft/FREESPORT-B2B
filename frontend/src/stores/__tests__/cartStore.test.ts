/**
 * Cart Store Tests
 * Обновлено для async API с variant_id (Story 12.3)
 */
import { useCartStore } from '../cartStore';
import cartService from '@/services/cartService';
import type { CartItem } from '@/types/cart';

// Mock cartService
vi.mock('@/services/cartService');

const mockCartItem: CartItem = {
  id: 1,
  variant_id: 101,
  product: {
    id: 1,
    name: 'Test Product',
    slug: 'test-product',
    image: '/test.jpg',
  },
  variant: {
    sku: 'TEST-SKU-001',
    color_name: 'Красный',
    size_value: 'L',
  },
  quantity: 2,
  unit_price: '100.00',
  total_price: '200.00',
  added_at: new Date().toISOString(),
};

describe('cartStore', () => {
  beforeEach(() => {
    // Очищаем store перед каждым тестом
    useCartStore.setState({
      items: [],
      totalItems: 0,
      totalPrice: 0,
      isLoading: false,
      error: null,
    });

    // Сбрасываем моки
    vi.clearAllMocks();
  });

  describe('addItem (async)', () => {
    test('successfully adds new variant to cart', async () => {
      // Arrange
      vi.mocked(cartService.add).mockResolvedValue(mockCartItem);

      // Act
      const store = useCartStore.getState();
      const result = await store.addItem(101, 2);

      // Assert
      expect(result.success).toBe(true);
      expect(cartService.add).toHaveBeenCalledWith(101, 2);

      const state = useCartStore.getState();
      expect(state.items).toHaveLength(1);
      expect(state.items[0].variant_id).toBe(101);
      expect(state.items[0].quantity).toBe(2);
      expect(state.totalItems).toBe(2);
      expect(state.totalPrice).toBe(200);
    });

    test('handles API error with rollback', async () => {
      // Arrange
      const errorMsg = 'Product out of stock';
      vi.mocked(cartService.add).mockRejectedValue(new Error(errorMsg));

      // Act
      const store = useCartStore.getState();
      const result = await store.addItem(101, 1);

      // Assert
      expect(result.success).toBe(false);
      expect(result.error).toBe(errorMsg);

      const state = useCartStore.getState();
      expect(state.items).toHaveLength(0); // Rollback successful
      expect(state.totalItems).toBe(0);
      expect(state.error).toBe(errorMsg);
    });

    test('performs optimistic update before API call', async () => {
      // Arrange
      vi.mocked(cartService.add).mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve(mockCartItem), 100))
      );

      // Act
      const store = useCartStore.getState();
      const promise = store.addItem(101, 2);

      // Assert - optimistic update должен произойти мгновенно
      const stateBeforeResolve = useCartStore.getState();
      expect(stateBeforeResolve.items.length).toBeGreaterThan(0); // Temporary item added
      expect(stateBeforeResolve.isLoading).toBe(true);

      await promise;

      // После resolve - реальные данные
      const stateFinal = useCartStore.getState();
      expect(stateFinal.items[0].variant_id).toBe(101);
      expect(stateFinal.isLoading).toBe(false);
    });
  });

  describe('removeItem (async)', () => {
    test('successfully removes item from cart', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });
      vi.mocked(cartService.remove).mockResolvedValue();

      // Act
      const store = useCartStore.getState();
      const result = await store.removeItem(1);

      // Assert
      expect(result.success).toBe(true);
      expect(cartService.remove).toHaveBeenCalledWith(1);

      const state = useCartStore.getState();
      expect(state.items).toHaveLength(0);
      expect(state.totalItems).toBe(0);
      expect(state.totalPrice).toBe(0);
    });

    test('handles API error with rollback', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });
      vi.mocked(cartService.remove).mockRejectedValue(new Error('Network error'));

      // Act
      const store = useCartStore.getState();
      const result = await store.removeItem(1);

      // Assert
      expect(result.success).toBe(false);

      const state = useCartStore.getState();
      expect(state.items).toHaveLength(1); // Rollback - item still present
      expect(state.items[0].id).toBe(1);
    });
  });

  describe('updateQuantity (async)', () => {
    test('successfully updates item quantity', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });

      const updatedItem = { ...mockCartItem, quantity: 5, total_price: '500.00' };
      vi.mocked(cartService.update).mockResolvedValue(updatedItem);

      // Act
      const store = useCartStore.getState();
      const result = await store.updateQuantity(1, 5);

      // Assert
      expect(result.success).toBe(true);
      expect(cartService.update).toHaveBeenCalledWith(1, 5);

      const state = useCartStore.getState();
      expect(state.items[0].quantity).toBe(5);
      expect(state.totalItems).toBe(5);
      expect(state.totalPrice).toBe(500);
    });

    test('handles API error with rollback', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });
      vi.mocked(cartService.update).mockRejectedValue(new Error('Invalid quantity'));

      // Act
      const store = useCartStore.getState();
      const result = await store.updateQuantity(1, 10);

      // Assert
      expect(result.success).toBe(false);

      const state = useCartStore.getState();
      expect(state.items[0].quantity).toBe(2); // Rollback - original quantity
      expect(state.totalItems).toBe(2);
    });
  });

  describe('clearCart (async)', () => {
    test('successfully clears all items', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });
      vi.mocked(cartService.clear).mockResolvedValue();

      // Act
      const store = useCartStore.getState();
      await store.clearCart();

      // Assert
      expect(cartService.clear).toHaveBeenCalled();

      const state = useCartStore.getState();
      expect(state.items).toHaveLength(0);
      expect(state.totalItems).toBe(0);
      expect(state.totalPrice).toBe(0);
    });

    test('handles API error with rollback', async () => {
      // Arrange
      useCartStore.setState({
        items: [mockCartItem],
        totalItems: 2,
        totalPrice: 200,
      });
      vi.mocked(cartService.clear).mockRejectedValue(new Error('Server error'));

      // Act
      const store = useCartStore.getState();
      await store.clearCart();

      // Assert
      const state = useCartStore.getState();
      expect(state.items).toHaveLength(1); // Rollback - items restored
      expect(state.error).toBeTruthy();
    });
  });

  describe('getTotalItems', () => {
    test('returns correct total items count', () => {
      // Arrange
      useCartStore.setState({
        items: [
          { ...mockCartItem, id: 1, quantity: 2 },
          { ...mockCartItem, id: 2, quantity: 3 },
        ],
        totalItems: 5,
        totalPrice: 500,
      });

      // Act
      const store = useCartStore.getState();
      const total = store.getTotalItems();

      // Assert
      expect(total).toBe(5);
    });
  });
});
