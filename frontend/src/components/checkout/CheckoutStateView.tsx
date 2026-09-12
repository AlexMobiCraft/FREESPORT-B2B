'use client';

import Link from 'next/link';

import { Spinner } from '@/components/ui';
import { ReturnsAndSupportNotice } from '@/components/common';
import type { CheckoutView } from '@/utils/checkout/checkoutView';

// Тот же вид, что у middleware (`next=%2F...`): сканер считает разные написания
// одного адреса разными страницами (повторный аудит 10.09.2026).
const LOGIN_HREF = `/login?${new URLSearchParams({ next: '/checkout' })}`;

const CTA_CLASS =
  'h-12 px-8 inline-flex items-center justify-center bg-primary hover:bg-primary-hover text-text-inverse font-medium rounded-[var(--radius-sm)] transition-colors';

/**
 * Пропсы блока состояния (Story 41.10). Для `error` обработчик повтора обязателен:
 * кнопка «Повторить» без него ничего бы не делала. Остальным состояниям он не нужен,
 * но допускается — страница передаёт один и тот же `onRetry` при любом `view`.
 */
export type CheckoutStateViewProps =
  | {
      /** Ошибка загрузки корзины */
      view: 'error';
      /** Повторная попытка загрузки корзины */
      onRetry: () => void;
    }
  | {
      /** Текущее нефинальное состояние страницы оформления заказа */
      view: Exclude<CheckoutView, 'form' | 'error'>;
      /** Не используется: повтор есть только у состояния `error` */
      onRetry?: () => void;
    };

/**
 * Блоки состояний страницы `/checkout`, отличных от готовой формы (Story 41.10, FR-41-25).
 *
 * Заменяет форму на приглашение войти, индикатор загрузки, пустое состояние,
 * ошибку с повтором или индикатор редиректа после оформления заказа — во всех
 * случаях с заголовком h2 (иерархия h1 страницы → h2 блока, AC8) и блоком
 * условий возврата и поддержки (FR-41-15).
 */
export function CheckoutStateView(props: CheckoutStateViewProps) {
  return (
    <div className="rounded-lg bg-white p-6 shadow-sm" data-testid={testIdFor(props.view)}>
      {renderContent(props)}
      <ReturnsAndSupportNotice className="mt-6 text-center text-xs text-gray-500" />
    </div>
  );
}

function testIdFor(view: CheckoutStateViewProps['view']): string {
  switch (view) {
    case 'loading':
      return 'checkout-loading';
    case 'anonymous':
      return 'checkout-login-required';
    case 'empty':
      return 'checkout-empty-cart';
    case 'error':
      return 'checkout-cart-error';
    case 'redirecting':
      return 'checkout-redirecting';
  }
}

function renderContent(props: CheckoutStateViewProps) {
  switch (props.view) {
    // Видимый текст индикатора — заголовок блока: у каждого состояния есть h2 (AC8)
    case 'loading':
      return (
        <div className="flex flex-col items-center py-4 text-center">
          <Spinner size="large" label="Загрузка" className="mb-4" />
          <h2 className="text-sm font-normal text-gray-600">Загрузка…</h2>
        </div>
      );

    case 'redirecting':
      return (
        <div className="flex flex-col items-center py-4 text-center">
          <Spinner size="large" label="Переходим к подтверждению" className="mb-4" />
          <h2 className="text-sm font-normal text-gray-600">
            Заказ оформлен. Переходим к подтверждению…
          </h2>
        </div>
      );

    case 'anonymous':
      return (
        <div className="flex flex-col items-center py-4 text-center">
          <h2 className="mb-2 text-lg font-semibold text-gray-900">
            Войдите, чтобы оформить заказ
          </h2>
          <p className="mb-6 text-sm text-gray-600">
            Оформление заказа доступно после входа в личный кабинет.
          </p>
          <Link href={LOGIN_HREF} className={CTA_CLASS}>
            Войти
          </Link>
        </div>
      );

    case 'empty':
      return (
        <div className="flex flex-col items-center py-4 text-center">
          <h2 className="mb-2 text-lg font-semibold text-gray-900">Корзина пуста</h2>
          <p className="mb-6 text-sm text-gray-600">
            Добавьте товары из каталога, чтобы оформить заказ.
          </p>
          <Link href="/catalog" className={CTA_CLASS}>
            В каталог
          </Link>
        </div>
      );

    case 'error':
      return (
        <div className="flex flex-col items-center py-4 text-center" role="alert">
          <h2 className="mb-2 text-lg font-semibold text-gray-900">Не удалось загрузить корзину</h2>
          <p className="mb-6 text-sm text-gray-600">Проверьте подключение и попробуйте ещё раз.</p>
          <button type="button" onClick={props.onRetry} className={CTA_CLASS}>
            Повторить
          </button>
        </div>
      );
  }
}
