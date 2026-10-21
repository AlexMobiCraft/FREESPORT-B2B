/**
 * Card Component
 * Базовый контейнер с shadow и hover эффектами
 *
 * @see frontend/docs/design-system.json#components.Card
 */

import React from 'react';
import { cn } from '@/utils/cn';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Включить hover эффект */
  hover?: boolean;
  /** Дочерние элементы */
  children: React.ReactNode;
}

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ hover = false, children, className, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          // Базовые стили
          'bg-neutral-100 rounded-md p-6',
          'shadow-default',
          'transition-all duration-medium',

          // Hover эффект
          hover && 'hover:shadow-hover hover:-translate-y-0.5 cursor-pointer',

          className
        )}
        {...props}
      >
        {children}
      </div>
    );
  }
);

Card.displayName = 'Card';
