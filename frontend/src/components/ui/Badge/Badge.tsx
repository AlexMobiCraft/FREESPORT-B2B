/**
 * Badge Component
 * Бейдж для карточек товаров с различными статусами
 *
 * @see frontend/docs/design-system.json#components.Badge
 */

import React from 'react';
import { CheckCircle2, Truck, X, Sparkles } from 'lucide-react';
import { cn } from '@/utils/cn';

export type BadgeVariant =
  | 'delivered'
  | 'transit'
  | 'cancelled'
  | 'promo'
  | 'sale'
  | 'discount'
  | 'premium'
  | 'new'
  | 'hit';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  /** Вариант бейджа */
  variant: BadgeVariant;
  /** Текст */
  children: React.ReactNode;
}

const variantConfig: Record<BadgeVariant, { bg: string; text: string; icon?: React.ReactNode }> = {
  delivered: {
    bg: 'bg-[#E0F5E0]',
    text: 'text-[#1F7A1F]',
    icon: <CheckCircle2 className="w-3 h-3" aria-hidden="true" />,
  },
  transit: {
    bg: 'bg-[#FFF1CC]',
    text: 'text-[#8C5A00]',
    icon: <Truck className="w-3 h-3" aria-hidden="true" />,
  },
  cancelled: {
    bg: 'bg-[#FFE1E1]',
    text: 'text-[#A62828]',
    icon: <X className="w-3 h-3" aria-hidden="true" />,
  },
  promo: { bg: 'bg-[#FFF0F5]', text: 'text-accent-promo' },
  sale: { bg: 'bg-[#FFE1E8]', text: 'text-accent-danger' },
  discount: { bg: 'bg-[#F0E7FF]', text: 'text-[#7C3AED]' },
  premium: {
    bg: 'bg-[#F6F0E4]',
    text: 'text-[#6D4C1F]',
    icon: <Sparkles className="w-3 h-3" aria-hidden="true" />,
  },
  new: { bg: 'bg-[#E7F3FF]', text: 'text-primary' },
  hit: { bg: 'bg-[#E0F5E8]', text: 'text-accent-success' },
};

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ variant, children, className, ...props }, ref) => {
    const config = variantConfig[variant];

    return (
      <span
        ref={ref}
        className={cn(
          // Базовые стили
          'inline-flex items-center gap-1',
          'px-2 py-0.5 rounded-full',
          'text-[11px] leading-[14px] font-medium',
          // Edge Case: Переполнение текста - max 200px
          'max-w-[200px] truncate',

          // Вариант
          config.bg,
          config.text,

          className
        )}
        {...props}
      >
        {/* Edge Case: Иконка может не загрузиться - показываем только текст */}
        {config.icon}
        {children}
      </span>
    );
  }
);

Badge.displayName = 'Badge';
