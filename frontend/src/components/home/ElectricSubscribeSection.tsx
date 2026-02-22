/**
 * Electric Subscribe Section
 * Секция подписки для Electric Orange Theme (без дублирования блога)
 */

import React from 'react';
import { ElectricSubscribeForm } from './ElectricSubscribeForm';

export const ElectricSubscribeSection: React.FC = () => {
  return (
    <section className="py-16 bg-[var(--bg-card)] border-t border-b border-[var(--border-default)]">
      <div className="max-w-[1280px] mx-auto px-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-end">
          {/* Left: Form */}
          <div>
            <ElectricSubscribeForm />
          </div>

          {/* Right: Decor / Promo Text instead of duplicates */}
          <div className="hidden md:block">
            <div className="border border-[var(--color-primary)] p-8 transform -skew-x-12 bg-[var(--bg-body)]">
              <div className="transform skew-x-12 text-center">
                <h4 className="text-xl font-bold text-[var(--color-primary)] uppercase mb-4">
                  Бонус за подписку
                </h4>
                <p className="text-[var(--foreground)] text-lg font-bold mb-2 uppercase">
                  Скидка 5% на первый заказ
                </p>
                <p className="text-[var(--color-text-secondary)] text-sm">
                  Подпишитесь на наши новости и получите промокод на скидку для первой покупки.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
