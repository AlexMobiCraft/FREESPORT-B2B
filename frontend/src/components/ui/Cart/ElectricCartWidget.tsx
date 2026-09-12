/**
 * Electric Orange Cart Widget Component
 *
 * Мини-корзина в стиле Electric Orange (для header)
 * Features:
 * - Skewed badge with item count
 * - Dropdown on hover/click
 * - Product rows with prices
 * - Checkout button
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import { ShoppingBag, X, Trash2 } from 'lucide-react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface CartItem {
  id: string;
  title: string;
  price: number;
  quantity: number;
  image?: string;
}

export interface ElectricCartWidgetProps {
  /** Cart items */
  items: CartItem[];
  /** Remove item callback */
  onRemoveItem?: (id: string) => void;
  /** Checkout callback */
  onCheckout?: () => void;
  /** View cart callback */
  onViewCart?: () => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricCartWidget({
  items,
  onRemoveItem,
  onCheckout,
  onViewCart,
  className,
}: ElectricCartWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);

  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  const totalPrice = items.reduce((sum, item) => sum + item.price * item.quantity, 0);

  const formatPrice = (price: number) => {
    return new Intl.NumberFormat('ru-RU').format(price) + ' ₽';
  };

  return (
    <div className={cn('relative', className)}>
      {/* Trigger Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className={cn(
          'relative flex items-center justify-center',
          'w-11 h-11',
          'border border-[var(--border-default)]',
          'transform -skew-x-12',
          'transition-all duration-200',
          'hover:border-[var(--color-primary)]',
          isOpen && 'border-[var(--color-primary)] bg-[var(--color-primary-subtle)]'
        )}
      >
        <ShoppingBag className="w-5 h-5 text-[var(--foreground)] transform skew-x-12" />

        {/* Badge */}
        {totalItems > 0 && (
          <span
            className={cn(
              'absolute -top-2 -right-1',
              'w-5 h-5',
              'flex items-center justify-center',
              'bg-[var(--color-primary)] text-black',
              'text-xs font-bold',
              'transform -skew-x-12'
            )}
          >
            <span className="transform skew-x-12">{totalItems}</span>
          </span>
        )}
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          className={cn(
            'absolute top-full right-0 z-50 mt-2',
            'w-80',
            'bg-[var(--bg-card)] border border-[var(--border-default)]',
            'animate-fadeIn'
          )}
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-[var(--border-default)]">
            <span className="font-roboto-condensed font-bold text-sm uppercase text-[var(--foreground)] transform -skew-x-12">
              <span className="transform skew-x-12 inline-block">Корзина</span>
            </span>
            <button
              onClick={() => setIsOpen(false)}
              className="text-[var(--color-text-muted)] hover:text-[var(--foreground)] transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          {/* Items */}
          {items.length === 0 ? (
            <div className="p-6 text-center text-[var(--color-text-muted)]">Корзина пуста</div>
          ) : (
            <>
              <div className="max-h-60 overflow-y-auto">
                {items.map(item => (
                  <div
                    key={item.id}
                    className="flex gap-3 p-3 border-b border-[var(--border-default)] last:border-b-0"
                  >
                    {/* Image */}
                    {item.image && (
                      <div className="w-12 h-12 bg-[var(--bg-card-hover)] flex-shrink-0 overflow-hidden relative">
                        <Image src={item.image} alt={item.title} fill className="object-cover" />
                      </div>
                    )}

                    {/* Info */}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-[var(--foreground)] truncate">{item.title}</p>
                      <p className="text-xs text-[var(--color-text-muted)]">
                        {item.quantity} × {formatPrice(item.price)}
                      </p>
                    </div>

                    {/* Remove */}
                    <button
                      onClick={() => onRemoveItem?.(item.id)}
                      className="text-[var(--color-text-muted)] hover:text-[var(--color-danger)] transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>

              {/* Footer */}
              <div className="p-4 border-t border-[var(--border-default)]">
                <div className="flex justify-between mb-4">
                  <span className="text-[var(--color-text-secondary)] text-sm">Итого:</span>
                  <span className="font-roboto-condensed font-bold text-[var(--color-primary)] transform -skew-x-12">
                    <span className="transform skew-x-12 inline-block">
                      {formatPrice(totalPrice)}
                    </span>
                  </span>
                </div>

                <div className="flex gap-2">
                  <button
                    onClick={onViewCart}
                    className={cn(
                      'flex-1 py-2 text-sm font-bold uppercase',
                      'border border-[var(--border-default)] text-[var(--foreground)]',
                      'transform -skew-x-12',
                      'hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]',
                      'transition-all'
                    )}
                  >
                    <span className="transform skew-x-12 inline-block">В корзину</span>
                  </button>
                  <button
                    onClick={onCheckout}
                    className={cn(
                      'flex-1 py-2 text-sm font-bold uppercase',
                      'bg-[var(--color-primary)] text-black',
                      'transform -skew-x-12',
                      'hover:bg-[var(--foreground)] hover:text-[var(--color-primary)]',
                      'transition-all'
                    )}
                  >
                    <span className="transform skew-x-12 inline-block">Оформить</span>
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}

ElectricCartWidget.displayName = 'ElectricCartWidget';

export default ElectricCartWidget;
