/**
 * PromoCodeInput Component - Ввод промокода
 *
 * Функции:
 * - Input поле для ввода промокода с клиентской валидацией формата
 * - Pending state: показывает код как «будет проверен при оформлении» (stub)
 * - Кнопка удаления pending-кода
 * - Feature flag: скрывается если NEXT_PUBLIC_PROMO_ENABLED !== 'true'
 * - Accessibility: aria-labels, focus management
 *
 * NOTE (Story 34-2): Promo-система не реализована на сервере. Код сохраняется
 * в cartStore и передаётся в `promo_code` при POST /orders/, но скидка всегда = 0.
 * UI показывает pending-state, не обещает скидку до оформления.
 *
 * @see Story 26.4: Promo Code Integration
 * @see Story 34-2: server-authoritative discount contract
 */
'use client';

import { useState, useRef, useEffect } from 'react';
import toast from 'react-hot-toast';
import { useCartStore } from '@/stores/cartStore';

/**
 * Проверка feature flag для promo функционала
 */
const isPromoEnabled = () => process.env.NEXT_PUBLIC_PROMO_ENABLED === 'true';

/**
 * Компонент ввода промокода с полной логикой
 */
const PromoCodeInput = () => {
  const [code, setCode] = useState('');
  const [validationError, setValidationError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Состояние из store
  const { promoCode, applyPromo, clearPromo } = useCartStore();

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
   * Обработчик применения промокода (stub: сохраняет код, сервер проверит при оформлении)
   */
  const handleApply = () => {
    const trimmedCode = code.trim();
    if (!trimmedCode || !validateCode(trimmedCode)) {
      inputRef.current?.focus();
      return;
    }

    // Stub: сохраняем код в store; реальная проверка — на сервере при POST /orders/
    applyPromo(trimmedCode, 'percent', 0);
    toast.success('Промокод принят — скидка будет рассчитана при оформлении');
    setCode('');
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
    if (e.key === 'Enter' && code.trim()) {
      handleApply();
    }
  };

  // Если промокод сохранён — показываем pending state (не «применён», а «будет проверен»)
  if (promoCode) {
    return (
      <div
        className="flex items-center justify-between p-3 bg-[var(--color-neutral-100)]
                    rounded-[var(--radius-sm)] mb-4"
        data-testid="promo-code-section"
      >
        <span
          className="text-body-m text-[var(--color-text-secondary)]"
          data-testid="applied-promo-code"
        >
          Промокод {promoCode} — будет проверен при оформлении
        </span>
        <button
          onClick={handleClearPromo}
          className="text-body-s text-[var(--color-text-secondary)] hover:underline"
          aria-label="Удалить промокод"
          data-testid="clear-promo-button"
        >
          Удалить
        </button>
      </div>
    );
  }

  // Форма ввода промокода
  const isButtonDisabled = !code.trim() || code.trim().length < 4;

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
            className="w-full h-10 px-3 border border-[var(--color-neutral-400)] rounded-[var(--radius-sm)]
                       text-body-m focus:outline-none focus:ring-[var(--focus-ring)]
                       focus:border-[var(--color-primary)] bg-[var(--bg-panel)]
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
          Применить
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
