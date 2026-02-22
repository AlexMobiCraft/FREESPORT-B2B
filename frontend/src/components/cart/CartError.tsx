/**
 * CartError Component
 *
 * Отображает ошибку при загрузке корзины:
 * - Сообщение об ошибке
 * - Кнопка "Повторить" для retry
 */

'use client';

import { AlertCircle, RefreshCw } from 'lucide-react';
import { Breadcrumb } from '@/components/ui';

const breadcrumbItems = [{ label: 'Главная', href: '/' }, { label: 'Корзина' }];

interface CartErrorProps {
  /** Текст ошибки */
  error: string;
  /** Callback для повторной попытки загрузки */
  onRetry: () => void;
}

export const CartError = ({ error, onRetry }: CartErrorProps) => {
  return (
    <main className="max-w-[1280px] mx-auto px-4 lg:px-6 py-6" data-testid="cart-error" role="main">
      <Breadcrumb items={breadcrumbItems} className="mb-6" />

      <h1 className="text-display-m font-bold text-text-primary mb-8">Ваша корзина</h1>

      <div className="flex flex-col items-center justify-center py-16 bg-white rounded-[var(--radius-md)] shadow-[var(--shadow-default)]">
        <AlertCircle className="w-16 h-16 text-red-500 mb-6" aria-hidden="true" />

        <h2 className="text-title-l font-semibold text-text-primary mb-2">Ошибка загрузки</h2>

        <p className="text-body-m text-text-secondary mb-2 text-center max-w-md">
          Не удалось загрузить корзину. Пожалуйста, попробуйте ещё раз.
        </p>

        <p className="text-body-s text-red-500 mb-8 text-center max-w-md">{error}</p>

        <button
          onClick={onRetry}
          className="h-12 px-8 inline-flex items-center justify-center gap-2 bg-primary hover:bg-primary-hover text-text-inverse font-medium rounded-[var(--radius-sm)] transition-colors"
          data-testid="cart-retry-button"
        >
          <RefreshCw className="w-5 h-5" aria-hidden="true" />
          Повторить
        </button>
      </div>
    </main>
  );
};

CartError.displayName = 'CartError';
