/**
 * ReturnsAndSupportNotice Component
 *
 * Блок обязательной торговой информации рядом с оплатой (Story 41.4, FR-41-15):
 * ссылка на условия возврата и рекламаций + канал связи с поддержкой.
 *
 * Используется одним и тем же компонентом в двух местах — в сводке корзины
 * (`CartSummary`) и в сводке заказа (`OrderSummary`), поэтому собственный цвет
 * текста и типографику не задаёт: темы у этих страниц разные, оформление
 * передаётся вызывающим через `className`.
 *
 * Директива `'use client'` не нужна: компонент без состояния и обработчиков.
 *
 * @example
 * ```tsx
 * <ReturnsAndSupportNotice className="text-body-s text-[var(--color-text-secondary)]" />
 * ```
 */

import React from 'react';
import Link from 'next/link';
import { SUPPORT_EMAIL, SUPPORT_PHONE_DISPLAY, SUPPORT_PHONE_HREF } from '@/config/contacts';
import { cn } from '@/utils/cn';

export interface ReturnsAndSupportNoticeProps {
  /** Дополнительные CSS классы (типографика и цвет задаются вызывающим) */
  className?: string;
}

export function ReturnsAndSupportNotice({ className }: ReturnsAndSupportNoticeProps) {
  return (
    <section
      aria-label="Условия возврата и поддержка"
      data-testid="returns-support-notice"
      className={cn('mt-4 space-y-1', className)}
    >
      <p>
        {/* Условия возврата живут в разделе «Рекламации и возвраты» на /partners.
            Маршрута /returns в проекте нет — ссылаться на него нельзя (AC7). */}
        <Link href="/partners#returns" className="underline hover:no-underline">
          Условия возврата и рекламаций
        </Link>
      </p>
      <p>
        Поддержка:{' '}
        <a href={SUPPORT_PHONE_HREF} className="underline hover:no-underline">
          {SUPPORT_PHONE_DISPLAY}
        </a>
        ,{' '}
        <a href={`mailto:${SUPPORT_EMAIL}`} className="underline hover:no-underline">
          {SUPPORT_EMAIL}
        </a>
      </p>
    </section>
  );
}

export default ReturnsAndSupportNotice;
