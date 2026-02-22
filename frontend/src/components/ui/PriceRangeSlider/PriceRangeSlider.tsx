/**
 * PriceRangeSlider Component
 * Dual-thumb range slider для выбора диапазона цен
 * Style: Electric Orange (Skewed -12deg)
 */

'use client';

import React, { useState, useRef, useCallback, useEffect } from 'react';
import { cn } from '@/utils/cn';

export interface PriceRangeSliderProps {
  /** Минимальное значение */
  min: number;
  /** Максимальное значение */
  max: number;
  /** Текущее значение [от, до] */
  value: [number, number];
  /** Callback при изменении */
  onChange: (value: [number, number]) => void;
  /** Шаг изменения */
  step?: number;
  /** Функция форматирования цены */
  formatPrice?: (price: number) => string;
  /** Дополнительные классы */
  className?: string;
  /** Disable skew explicitly if needed */
  noSkew?: boolean;
}

export const PriceRangeSlider = React.forwardRef<HTMLDivElement, PriceRangeSliderProps>(
  ({ min, max, value, onChange, step = 1, formatPrice, className, noSkew = false }, ref) => {
    const [minValue, maxValue] = value;
    const [isDragging, setIsDragging] = useState<'min' | 'max' | null>(null);
    const trackRef = useRef<HTMLDivElement>(null);

    const clampValue = useCallback(
      (val: number) => {
        return Math.min(Math.max(val, min), max);
      },
      [min, max]
    );

    const getPercent = useCallback(
      (val: number) => {
        return ((val - min) / (max - min)) * 100;
      },
      [min, max]
    );

    const handleMinInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      // Allow empty string for better UX while typing
      const val = e.target.value.replace(/\D/g, '');
      if (val === '') {
        // handle empty? for now just don't update or set to min?
        // Setting to min might be annoying. Let's parse as number.
        return;
      }
      const newMin = Number(val);
      // We don't clamp strictly here to allow typing, but we should eventually validity it.
      // For instant feedback, clamping is safer.
      const clampedMin = clampValue(newMin);

      if (clampedMin <= maxValue) {
        onChange([clampedMin, maxValue]);
      }
    };

    const handleMaxInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const val = e.target.value.replace(/\D/g, '');
      if (val === '') return;
      const newMax = Number(val);
      const clampedMax = clampValue(newMax);

      if (clampedMax >= minValue) {
        onChange([minValue, clampedMax]);
      }
    };

    const handleMouseDown = (thumb: 'min' | 'max') => (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation(); // Stop propagation to prevent conflict with other interactions
      setIsDragging(thumb);
    };

    const calculateValue = useCallback(
      (clientX: number) => {
        if (!trackRef.current) return null;

        const rect = trackRef.current.getBoundingClientRect();
        const percent = Math.max(0, Math.min(100, ((clientX - rect.left) / rect.width) * 100));
        const rawValue = (percent / 100) * (max - min) + min;
        const steppedValue = Math.round(rawValue / step) * step;

        return clampValue(steppedValue);
      },
      [min, max, step, clampValue]
    );

    useEffect(() => {
      if (!isDragging) return;

      const handleMouseMove = (e: MouseEvent) => {
        const newValue = calculateValue(e.clientX);
        if (newValue === null) return;

        if (isDragging === 'min') {
          const safeMax = Math.max(newValue, min); // Ensure min is respected
          if (safeMax <= maxValue) onChange([safeMax, maxValue]);
        } else if (isDragging === 'max') {
          const safeMin = Math.min(newValue, max); // Ensure max is respected
          if (safeMin >= minValue) onChange([minValue, safeMin]);
        }
      };

      const handleMouseUp = () => {
        setIsDragging(null);
      };

      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);

      return () => {
        document.removeEventListener('mousemove', handleMouseMove);
        document.removeEventListener('mouseup', handleMouseUp);
      };
    }, [isDragging, minValue, maxValue, onChange, calculateValue, min, max]);

    const minPercent = getPercent(minValue);
    const maxPercent = getPercent(maxValue);

    return (
      <div ref={ref} className={cn('w-full', className)}>
        {/* Input Fields - Rectangular (0deg) */}
        <div className="flex items-center gap-3 mb-6">
          <div className="flex-1">
            <input
              type="text"
              value={formatPrice ? formatPrice(minValue) : minValue.toLocaleString('ru-RU')}
              onChange={handleMinInputChange}
              className={cn(
                'w-full h-10 px-3',
                'bg-transparent border border-[var(--border-default)]',
                'text-[var(--foreground)] text-right font-inter text-sm',
                'focus:outline-none focus:border-[var(--color-primary)] transition-colors'
              )}
              aria-label="Минимальная цена"
            />
          </div>

          <span className="text-[var(--color-text-muted)]">—</span>

          <div className="flex-1">
            <input
              type="text"
              value={formatPrice ? formatPrice(maxValue) : maxValue.toLocaleString('ru-RU')}
              onChange={handleMaxInputChange}
              className={cn(
                'w-full h-10 px-3',
                'bg-transparent border border-[var(--border-default)]',
                'text-[var(--foreground)] text-right font-inter text-sm',
                'focus:outline-none focus:border-[var(--color-primary)] transition-colors'
              )}
              aria-label="Максимальная цена"
            />
          </div>
        </div>

        {/* Slider Track - Skewed (-12deg) */}
        <div className="relative h-6 flex items-center">
          <div
            ref={trackRef}
            className="relative w-full h-1.5 bg-[var(--border-default)] cursor-pointer"
            style={{ transform: noSkew ? 'none' : 'skewX(-12deg)' }}
            role="presentation"
            onMouseDown={e => {
              // Click on track logic to jump to position
              const newValue = calculateValue(e.clientX);
              if (newValue !== null) {
                const distMin = Math.abs(newValue - minValue);
                const distMax = Math.abs(newValue - maxValue);
                if (distMin < distMax) {
                  if (newValue <= maxValue) onChange([newValue, maxValue]);
                } else {
                  if (newValue >= minValue) onChange([minValue, newValue]);
                }
              }
            }}
          >
            {/* Active Range */}
            <div
              className="absolute h-full bg-[var(--color-primary)]"
              style={{
                left: `${minPercent}%`,
                right: `${100 - maxPercent}%`,
              }}
            />

            {/* Min Thumb */}
            <div
              className={cn(
                'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
                'w-5 h-5 bg-[var(--color-primary)]',
                'border-2 border-black', // High contrast border
                'cursor-grab active:cursor-grabbing',
                'transition-transform hover:scale-110'
              )}
              style={{ left: `${minPercent}%` }}
              onMouseDown={handleMouseDown('min')}
              role="slider"
              tabIndex={0}
              aria-label="Минимальная цена"
              aria-valuenow={minValue}
              aria-valuemin={min}
              aria-valuemax={max}
              onKeyDown={e => {
                if (e.key === 'ArrowRight') {
                  const nextVal = Math.min(minValue + step, maxValue);
                  onChange([nextVal, maxValue]);
                } else if (e.key === 'ArrowLeft') {
                  const nextVal = Math.max(minValue - step, min);
                  onChange([nextVal, maxValue]);
                }
              }}
            />

            {/* Max Thumb */}
            <div
              className={cn(
                'absolute top-1/2 -translate-y-1/2 -translate-x-1/2',
                'w-5 h-5 bg-[var(--color-primary)]',
                'border-2 border-black',
                'cursor-grab active:cursor-grabbing',
                'transition-transform hover:scale-110'
              )}
              style={{ left: `${maxPercent}%` }}
              onMouseDown={handleMouseDown('max')}
              role="slider"
              tabIndex={0}
              aria-label="Максимальная цена"
              aria-valuenow={maxValue}
              aria-valuemin={min}
              aria-valuemax={max}
              onKeyDown={e => {
                if (e.key === 'ArrowRight') {
                  const nextVal = Math.min(maxValue + step, max);
                  onChange([minValue, nextVal]);
                } else if (e.key === 'ArrowLeft') {
                  const nextVal = Math.max(maxValue - step, minValue);
                  onChange([minValue, nextVal]);
                }
              }}
            />
          </div>
        </div>
      </div>
    );
  }
);

PriceRangeSlider.displayName = 'PriceRangeSlider';
