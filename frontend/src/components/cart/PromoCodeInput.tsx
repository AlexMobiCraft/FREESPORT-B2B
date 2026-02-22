/**
 * PromoCodeInput Component - Ввод и применение промокода
 *
 * Функции:
 * - Input поле для ввода промокода с валидацией
 * - Кнопка "Применить" с loading state
 * - Applied state: показывает код и кнопку удаления
 * - Toast уведомления (success/error)
 * - Feature flag: скрывается если NEXT_PUBLIC_PROMO_ENABLED !== 'true'
 * - Accessibility: aria-labels, focus management
 *
 * @see Story 26.4: Promo Code Integration
 */
'use client';

import { useState, useRef, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useCartStore } from '@/stores/cartStore';
import promoService from '@/services/promoService';

/**
 * Проверка feature flag для promo функционала
 */
const isPromoEnabled = () => process.env.NEXT_PUBLIC_PROMO_ENABLED === 'true';

/**
 * Компонент ввода промокода с полной логикой
 */
const PromoCodeInput = () => {
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Состояние из store
  const { promoCode, totalPrice, applyPromo, clearPromo } = useCartStore();

  // Если feature flag отключен - не рендерим компонент
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;
  if (!isPromoEnabled()) return null;

  /**
   * Валидация формата промокода
   * Минимум 4 символа, только буквы и цифры
   */
  const validateCode = (value: string): boolean => {
    if (value.length < 4) {
      setValidationError('Минимум 4 символа');
      return false;
    }
    if (!/^[A-Z0-9]+$/i.test(value)) {
      setValidationError('Только буквы и цифры');
      return false;
    }
    setValidationError(null);
    return true;
  };

  /**
   * Обработчик изменения input
   */
  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.toUpperCase();
    setCode(value);
    if (value.length >= 4) {
      validateCode(value);
    } else {
      setValidationError(null);
    }
  };

  /**
   * Обработчик применения промокода
   */
  const handleApply = async () => {
    if (!code.trim() || !validateCode(code)) {
      inputRef.current?.focus();
      return;
    }

    setIsLoading(true);
    setValidationError(null);

    try {
      const response = await promoService.applyPromo(code, totalPrice);

      if (response.success && response.code && response.discount_type && response.discount_value) {
        // Успешно применён промокод
        applyPromo(response.code, response.discount_type, response.discount_value);
        toast.success('Промокод применён');
        setCode('');
      } else {
        // Ошибка применения
        const errorMsg = response.error || 'Промокод недействителен';
        toast.error(errorMsg);
        inputRef.current?.focus();
      }
    } catch {
      toast.error('Не удалось применить промокод');
      inputRef.current?.focus();
    } finally {
      setIsLoading(false);
    }
  };

  /**
   * Обработчик удаления промокода
   */
  const handleClearPromo = () => {
    clearPromo();
    toast.success('Промокод удалён');
  };

  /**
   * Обработчик нажатия Enter
   */
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && code.trim() && !isLoading) {
      handleApply();
    }
  };

  // Если промокод уже применён - показываем applied state
  if (promoCode) {
    return (
      <div
        className="flex items-center justify-between p-3 bg-[var(--color-accent-success-bg)] 
                    rounded-[var(--radius-sm)] mb-4"
        data-testid="promo-code-section"
      >
        <span
          className="text-body-m font-medium text-[var(--color-accent-success)]"
          data-testid="applied-promo-code"
        >
          ✓ Промокод {promoCode} применён
        </span>
        <button
          onClick={handleClearPromo}
          className="text-body-s text-[var(--color-accent-success)] hover:underline"
          aria-label="Удалить промокод"
          data-testid="clear-promo-button"
        >
          Удалить
        </button>
      </div>
    );
  }

  // Форма ввода промокода
  const isButtonDisabled = !code.trim() || code.length < 4 || isLoading;

  return (
    <div className="mb-4" data-testid="promo-code-section">
      <div className="flex gap-2">
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={code}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            placeholder="Введите промокод"
            disabled={isLoading}
            className="w-full h-10 px-3 border border-[var(--color-neutral-400)] rounded-[var(--radius-sm)]
                       text-body-m focus:outline-none focus:ring-[var(--focus-ring)] 
                       focus:border-[var(--color-primary)] bg-[var(--bg-panel)]
                       disabled:opacity-50 disabled:cursor-not-allowed
                       uppercase"
            data-testid="promo-code-input"
            aria-label="Промокод"
            aria-describedby={validationError ? 'promo-error' : undefined}
            aria-invalid={!!validationError}
          />
        </div>
        <button
          onClick={handleApply}
          disabled={isButtonDisabled}
          className="px-4 h-10 bg-[var(--color-primary-subtle)] text-[var(--color-primary)] 
                     rounded-[var(--radius-sm)] text-body-m font-medium 
                     hover:bg-[var(--color-primary)] hover:text-[var(--color-text-inverse)]
                     disabled:opacity-50 disabled:cursor-not-allowed transition-colors
                     flex items-center justify-center min-w-[100px]"
          data-testid="apply-promo-button"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Проверка
            </span>
          ) : (
            'Применить'
          )}
        </button>
      </div>
      {validationError && (
        <p
          id="promo-error"
          className="text-body-s text-[var(--color-accent-danger)] mt-1"
          role="alert"
        >
          {validationError}
        </p>
      )}
    </div>
  );
};

export default PromoCodeInput;
