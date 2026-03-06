/**
 * CartSummary Component - Блок итогов заказа и кнопка оформления
 *
 * Функции:
 * - Отображение итоговой суммы заказа (totalPrice из cartStore)
 * - Отображение скидки по промокоду (Story 26.4)
 * - Кнопка "Оформить заказ" с условным рендерингом Link/button
 * - Sticky позиционирование на desktop
 * - Hydration паттерн с mounted state
 * - Accessibility: aria-live для динамических сумм
 *
 * @see Story 26.3: Cart Summary & Checkout CTA
 * @see Story 26.4: Promo Code Integration
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useCartStore } from '@/stores/cartStore';
import { formatPrice } from '@/utils/pricing';
import { cn } from '@/utils/cn';
import PromoCodeInput from './PromoCodeInput';

/**
 * Компонент итогов корзины с кнопкой оформления заказа
 */
export const CartSummary = () => {
  // Hydration паттерн - предотвращаем mismatch между server/client
  const [mounted, setMounted] = useState(false);
  const { items, totalPrice, getPromoDiscount } = useCartStore();

  useEffect(() => {
    setMounted(true);
  }, []);

  // До монтирования или при пустой корзине - кнопка неактивна
  const isEmpty = !mounted || items.length === 0;

  // Story 26.4: скидка по промокоду (динамический расчёт)
  const promoDiscount = mounted ? getPromoDiscount() : 0;
  const finalTotal = Math.max(0, totalPrice - promoDiscount);

  return (
    <div
      className="bg-[var(--bg-panel)] rounded-[var(--radius-lg)] p-6
                 shadow-[0_18px_40px_rgba(0,55,166,0.12)] lg:sticky lg:top-24"
      data-testid="cart-summary"
    >
      {/* Заголовок */}
      <h2 className="text-title-m font-semibold text-[var(--color-text-primary)] mb-6">
        Итоги заказа
      </h2>

      {/* Price Breakdown - с aria-live для динамических обновлений */}
      <div className="space-y-3 mb-6" aria-live="polite">
        {/* Сумма товаров */}
        <div className="flex justify-between text-body-m">
          <span className="text-[var(--color-text-secondary)]">Товары на сумму</span>
          <span
            className="text-[var(--color-text-primary)] font-medium"
            data-testid="subtotal-amount"
          >
            {mounted ? formatPrice(totalPrice) : '—'}
          </span>
        </div>

        {/* Скидка по промокоду (Story 26.4) */}
        {promoDiscount > 0 && (
          <div className="flex justify-between text-body-m">
            <span className="text-[var(--color-accent-success)]">Скидка по промокоду</span>
            <span
              className="text-[var(--color-accent-success)] font-medium"
              data-testid="promo-discount-amount"
            >
              -{formatPrice(promoDiscount)}
            </span>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="border-t border-[var(--color-neutral-300)] my-4" />

      {/* Total - итоговая сумма */}
      <div className="flex justify-between items-center mb-6">
        <span className="text-title-m font-semibold text-[var(--color-text-primary)]">
          Итого к оплате
        </span>
        <span
          className="text-headline-m font-bold text-[var(--color-text-primary)]"
          data-testid="total-amount"
        >
          {mounted ? formatPrice(finalTotal) : '—'}
        </span>
      </div>

      {/* Promo Code (Story 26.4) */}
      <PromoCodeInput />

      {/* Checkout Button - условный рендеринг Link/button */}
      {isEmpty ? (
        <button
          disabled
          className={cn(
            'w-full h-14 flex items-center justify-center',
            'bg-[var(--color-primary)]',
            'rounded-[var(--radius-md)] text-body-l font-medium text-[var(--color-text-inverse)]',
            'opacity-50 cursor-not-allowed'
          )}
          data-testid="checkout-button"
          aria-disabled="true"
        >
          Перейти к оформлению
        </button>
      ) : (
        <Link
          href="/checkout"
          className={cn(
            'w-full h-14 flex items-center justify-center',
            'bg-[var(--color-primary)]',
            'rounded-[var(--radius-md)] text-body-l font-medium text-[var(--color-text-inverse)]',
            'hover:bg-[var(--color-primary-hover)] transition-colors'
          )}
          data-testid="checkout-button"
        >
          Перейти к оформлению
        </Link>
      )}
    </div>
  );
};

export default CartSummary;
