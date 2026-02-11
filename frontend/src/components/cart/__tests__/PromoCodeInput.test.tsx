/**
 * PromoCodeInput Component Tests
 *
 * Покрытие:
 * - Feature flag (компонент скрывается если disabled)
 * - Рендеринг input и кнопки
 * - Валидация формата (минимум 4 символа, буквы и цифры)
 * - Успешное применение промокода
 * - Ошибка (невалидный код)
 * - Удаление примененного промокода
 * - Loading state
 * - Accessibility
 *
 * @see Story 26.4: Promo Code Integration
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import PromoCodeInput from '../PromoCodeInput';
import { useCartStore } from '@/stores/cartStore';
import promoService from '@/services/promoService';

// Mock promoService
vi.mock('@/services/promoService', () => ({
  default: {
    applyPromo: vi.fn(),
    clearPromo: vi.fn(),
    validateFormat: vi.fn((code: string) => /^[A-Z0-9]{4,}$/i.test(code)),
  },
}));

// Mock react-hot-toast
vi.mock('react-hot-toast', () => ({
  default: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Helper для сброса store
const resetStore = () => {
  useCartStore.setState({
    items: [],
    totalItems: 0,
    totalPrice: 5000,
    isLoading: false,
    error: null,
    promoCode: null,
    discountType: null,
    discountValue: 0,
  });
};

// Helper для установки env
const setPromoEnabled = (enabled: boolean) => {
  vi.stubEnv('NEXT_PUBLIC_PROMO_ENABLED', enabled ? 'true' : 'false');
};

describe('PromoCodeInput', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
    setPromoEnabled(true);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // ================== Feature Flag ==================
  describe('Feature Flag', () => {
    it('renders nothing when NEXT_PUBLIC_PROMO_ENABLED is false', async () => {
      setPromoEnabled(false);
      const { container } = render(<PromoCodeInput />);

      // Ждём mount
      await waitFor(() => {
        expect(container.firstChild).toBeNull();
      });
    });

    it('renders component when NEXT_PUBLIC_PROMO_ENABLED is true', async () => {
      setPromoEnabled(true);
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-section')).toBeInTheDocument();
      });
    });
  });

  // ================== Базовый рендеринг ==================
  describe('Rendering', () => {
    it('renders promo code section container', async () => {
      render(<PromoCodeInput />);
      await waitFor(() => {
        expect(screen.getByTestId('promo-code-section')).toBeInTheDocument();
      });
    });

    it('renders promo code input field', async () => {
      render(<PromoCodeInput />);
      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });
    });

    it('renders apply button', async () => {
      render(<PromoCodeInput />);
      await waitFor(() => {
        expect(screen.getByTestId('apply-promo-button')).toBeInTheDocument();
      });
    });

    it('displays placeholder text', async () => {
      render(<PromoCodeInput />);
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Введите промокод')).toBeInTheDocument();
      });
    });
  });

  // ================== Валидация формата ==================
  describe('Validation', () => {
    it('button is disabled when code is less than 4 characters', async () => {
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'ABC' } });

      expect(button).toBeDisabled();
    });

    it('button is enabled when code is 4+ characters', async () => {
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE10' } });

      expect(button).not.toBeDisabled();
    });

    it('converts input to uppercase', async () => {
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input') as HTMLInputElement;

      fireEvent.change(input, { target: { value: 'save10' } });

      expect(input.value).toBe('SAVE10');
    });
  });

  // ================== Успешное применение ==================
  describe('Apply Success', () => {
    it('applies promo code successfully and shows toast', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({
        success: true,
        code: 'SAVE10',
        discount_type: 'percent',
        discount_value: 10,
      });

      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.click(button);

      await waitFor(() => {
        expect(mockApplyPromo).toHaveBeenCalledWith('SAVE10', 5000);
      });

      await waitFor(() => {
        expect(toast.default.success).toHaveBeenCalledWith('Промокод применён');
      });
    });

    it('updates store with promo data on success', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({
        success: true,
        code: 'SAVE10',
        discount_type: 'percent',
        discount_value: 10,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.click(button);

      await waitFor(() => {
        const state = useCartStore.getState();
        expect(state.promoCode).toBe('SAVE10');
        expect(state.discountType).toBe('percent');
        expect(state.discountValue).toBe(10);
      });
    });
  });

  // ================== Ошибка применения ==================
  describe('Apply Error', () => {
    it('shows error toast when promo code is invalid', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({
        success: false,
        error: 'Промокод недействителен',
      });

      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'INVALID' } });
      fireEvent.click(button);

      await waitFor(() => {
        expect(toast.default.error).toHaveBeenCalledWith('Промокод недействителен');
      });
    });

    it('shows error toast when promo code is expired', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({
        success: false,
        error: 'Срок действия промокода истёк',
      });

      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'EXPIRED' } });
      fireEvent.click(button);

      await waitFor(() => {
        expect(toast.default.error).toHaveBeenCalledWith('Срок действия промокода истёк');
      });
    });
  });

  // ================== Удаление промокода ==================
  describe('Clear Promo', () => {
    it('shows applied state when promo is active', async () => {
      // Устанавливаем примененный промокод в store
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 10,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('applied-promo-code')).toBeInTheDocument();
        expect(screen.getByText(/SAVE10 применён/)).toBeInTheDocument();
      });
    });

    it('shows clear button when promo is applied', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 10,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('clear-promo-button')).toBeInTheDocument();
      });
    });

    it('clears promo when clear button is clicked', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 10,
      });

      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('clear-promo-button')).toBeInTheDocument();
      });

      const clearButton = screen.getByTestId('clear-promo-button');
      fireEvent.click(clearButton);

      await waitFor(() => {
        const state = useCartStore.getState();
        expect(state.promoCode).toBeNull();
        expect(toast.default.success).toHaveBeenCalledWith('Промокод удалён');
      });
    });
  });

  // ================== Loading State ==================
  describe('Loading State', () => {
    it('shows loading spinner when applying promo', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ success: false }), 100))
      );

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.click(button);

      expect(screen.getByText('Проверка')).toBeInTheDocument();
      expect(button).toBeDisabled();
    });

    it('disables input during loading', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockImplementation(
        () => new Promise(resolve => setTimeout(() => resolve({ success: false }), 100))
      );

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.click(button);

      expect(input).toBeDisabled();
    });
  });

  // ================== Keyboard Interaction ==================
  describe('Keyboard Interaction', () => {
    it('triggers apply on Enter key press', async () => {
      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({ success: false });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      await waitFor(() => {
        expect(mockApplyPromo).toHaveBeenCalled();
      });
    });
  });

  // ================== Accessibility ==================
  describe('Accessibility', () => {
    it('input has aria-label', async () => {
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      expect(input).toHaveAttribute('aria-label', 'Промокод');
    });

    it('clear button has aria-label', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 10,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('clear-promo-button')).toBeInTheDocument();
      });

      const clearButton = screen.getByTestId('clear-promo-button');
      expect(clearButton).toHaveAttribute('aria-label', 'Удалить промокод');
    });
  });

  // ================== Min Order Amount ==================
  describe('Min Order Amount', () => {
    it('shows error for SAVE20 when cart total is below minimum', async () => {
      useCartStore.setState({ totalPrice: 3000 }); // Меньше 5000

      const mockApplyPromo = vi.mocked(promoService.applyPromo);
      mockApplyPromo.mockResolvedValueOnce({
        success: false,
        error: 'Минимальная сумма заказа для этого промокода: 5000₽',
      });

      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      fireEvent.change(input, { target: { value: 'SAVE20' } });
      fireEvent.click(button);

      await waitFor(() => {
        expect(toast.default.error).toHaveBeenCalledWith(
          'Минимальная сумма заказа для этого промокода: 5000₽'
        );
      });
    });
  });
});
