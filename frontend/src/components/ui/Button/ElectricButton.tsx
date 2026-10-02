'use client';

import React, { forwardRef } from 'react';
import { cn } from '@/utils/cn';

export interface ElectricButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'ghost';
  size?: 'sm' | 'md' | 'lg';
  children: React.ReactNode;
}

export const ElectricButton = forwardRef<HTMLButtonElement, ElectricButtonProps>(
  ({ variant = 'primary', size = 'md', className, children, style, ...props }, ref) => {
    const sizeClasses = {
      sm: 'h-8 px-2 text-xs md:h-9 md:px-2.5 md:text-sm',
      md: 'h-10 px-4 text-sm md:h-11 md:px-6 md:text-base',
      lg: 'h-12 px-6 text-base md:h-14 md:px-8 md:text-lg',
    };

    const variantClasses = {
      primary:
        'bg-[var(--color-primary)] text-black hover:bg-[var(--color-text-primary)] hover:text-[var(--color-primary-active)] hover:shadow-[var(--shadow-hover)] border-transparent',
      outline:
        'bg-transparent border-2 border-[var(--foreground)] text-[var(--foreground)] hover:border-[var(--color-primary)] hover:text-[var(--color-primary)]',
      ghost:
        'bg-transparent text-[var(--foreground)] hover:text-[var(--color-primary)] hover:bg-[var(--color-primary-subtle)] border-transparent',
    };

    return (
      <button
        ref={ref}
        className={cn(
          'font-roboto-condensed font-semibold uppercase transition-all duration-300 flex items-center justify-center',
          sizeClasses[size],
          variantClasses[variant],
          className
        )}
        style={{
          transform: 'skewX(-12deg)',
          ...style,
        }}
        {...props}
      >
        <span style={{ transform: 'skewX(12deg)', display: 'inline-block' }}>{children}</span>
      </button>
    );
  }
);

ElectricButton.displayName = 'ElectricButton';
