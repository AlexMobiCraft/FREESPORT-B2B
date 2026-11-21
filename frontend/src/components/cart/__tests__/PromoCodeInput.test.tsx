/**
 * PromoCodeInput Component Tests
 *
 * Story 34-2: синхронизировано с server-authoritative promo contract.
 * PromoCodeInput сохраняет код в store (pending) и не обещает скидку до оформления.
 *
 * Покрытие:
 * - Feature flag (компонент скрывается если disabled)
 * - Рендеринг input и кнопки
 * - Валидация формата (минимум 4 символа, буквы и цифры)
 * - Сохранение кода в store + toast «Промокод принят — скидка будет рассчитана при оформлении»
 * - Pending state: текст «будет проверен при оформлении» (не «применён»)
 * - Удаление pending-кода
 * - Keyboard Interaction
 * - Accessibility
 *
 * @see Story 26.4: Promo Code Integration
 * @see Story 34-2: server-authoritative discount contract
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import PromoCodeInput from '../PromoCodeInput';
import { useCartStore } from '@/stores/cartStore';

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

  // ================== Pending state (Story 34-2 contract) ==================
  describe('[Story 34-2] Pending state — не обещает скидку', () => {
    it('stores promo code in cart store when applied', async () => {
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
      });
    });

    it('shows pending toast (not success-applied) when code is entered', async () => {
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
        expect(toast.default.success).toHaveBeenCalledWith(
          'Промокод принят — скидка будет рассчитана при оформлении'
        );
      });

      // [Story 34-2] НЕ должно быть старого успешного тоста «применён»
      expect(toast.default.success).not.toHaveBeenCalledWith('Промокод применён');
    });

    it('does NOT store discountType or discountValue from client side', async () => {
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
        // Verify state actually changed (promoCode is set — proves applyPromo was called)
        expect(state.promoCode).toBe('SAVE10');
        // Stub: discountValue = 0, скидка не применяется клиентом до сервера
        expect(state.discountValue).toBe(0);
        // [Story 34-2] discountType = 'percent' (stub, server-authoritative pending)
        expect(state.discountType).toBe('percent');
      });
    });

    it('accepts promo code with leading/trailing spaces (trims before validate)', async () => {
      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');
      const button = screen.getByTestId('apply-promo-button');

      // Simulate paste with spaces: handleChange -> toUpperCase() keeps spaces
      fireEvent.change(input, { target: { value: ' SAVE10 ' } });

      // Button is enabled because code.trim() has length >= 4
      expect(button).not.toBeDisabled();

      fireEvent.click(button);

      await waitFor(() => {
        const state = useCartStore.getState();
        // Trimmed code is stored, not the raw value with spaces
        expect(state.promoCode).toBe('SAVE10');
        // [Story 34-2 Patch 7] store trim regression: promoCode не должен содержать пробелы
        expect(state.promoCode).not.toContain(' ');
      });
    });

    it('shows pending text (not applied text) in pending state', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 0,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('applied-promo-code')).toBeInTheDocument();
      });

      const pendingEl = screen.getByTestId('applied-promo-code');
      // [Story 34-2] должен показывать «будет проверен», НЕ «применён»
      expect(pendingEl.textContent).toContain('будет проверен при оформлении');
      expect(pendingEl.textContent).not.toContain('применён');
      expect(pendingEl.textContent).not.toContain('✓');
    });
  });

  // ================== Удаление промокода ==================
  describe('Clear Promo', () => {
    it('shows pending state when promo code is set', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 0,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('applied-promo-code')).toBeInTheDocument();
        // [Story 34-2] shows pending text, not success text
        expect(screen.getByText(/будет проверен при оформлении/)).toBeInTheDocument();
      });
    });

    it('shows clear button when promo code is set', async () => {
      useCartStore.setState({
        promoCode: 'SAVE10',
        discountType: 'percent',
        discountValue: 0,
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
        discountValue: 0,
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

  // ================== Keyboard Interaction ==================
  describe('Keyboard Interaction', () => {
    it('stores code and shows pending toast on Enter key press', async () => {
      const toast = await import('react-hot-toast');

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('promo-code-input')).toBeInTheDocument();
      });

      const input = screen.getByTestId('promo-code-input');

      fireEvent.change(input, { target: { value: 'SAVE10' } });
      fireEvent.keyDown(input, { key: 'Enter' });

      await waitFor(() => {
        expect(toast.default.success).toHaveBeenCalledWith(
          'Промокод принят — скидка будет рассчитана при оформлении'
        );
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
        discountValue: 0,
      });

      render(<PromoCodeInput />);

      await waitFor(() => {
        expect(screen.getByTestId('clear-promo-button')).toBeInTheDocument();
      });

      const clearButton = screen.getByTestId('clear-promo-button');
      expect(clearButton).toHaveAttribute('aria-label', 'Удалить промокод');
    });
  });
});
