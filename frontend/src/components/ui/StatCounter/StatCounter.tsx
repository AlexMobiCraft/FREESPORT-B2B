/**
 * StatCounter - Анимированный счётчик с Intersection Observer
 * Story 19.1 - AC 2, 5, 7
 */

'use client';

import React, { useEffect, useRef, useState } from 'react';
import styles from './StatCounter.module.css';

export interface StatCounterProps {
  /** Числовое значение для анимации (например, 1000) */
  value: number;
  /** Суффикс после числа (например, "+", "%", " лет") */
  suffix?: string;
  /** Подпись под числом (например, "товаров") */
  label: string;
  /** Длительность анимации в ms (по умолчанию 2000) */
  duration?: number;
  /** Дополнительные CSS классы */
  className?: string;
}

export const StatCounter: React.FC<StatCounterProps> = ({
  value,
  suffix = '',
  label,
  duration = 2000,
  className = '',
}) => {
  const [currentValue, setCurrentValue] = useState(0);
  const [hasAnimated, setHasAnimated] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);

  // Проверяем prefers-reduced-motion
  const prefersReducedMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  useEffect(() => {
    const element = elementRef.current;
    if (!element || hasAnimated) return;

    // Если пользователь предпочитает уменьшенную анимацию, показываем финальное значение сразу
    if (prefersReducedMotion) {
      setCurrentValue(value);
      setHasAnimated(true);
      return;
    }

    // Создаём Intersection Observer
    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting && !hasAnimated) {
            animateValue();
            setHasAnimated(true);
          }
        });
      },
      {
        threshold: 0.2, // Запускаем когда 20% элемента видимо
      }
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hasAnimated, value, prefersReducedMotion]);

  const animateValue = () => {
    const startTime = performance.now();

    const updateValue = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);

      // Easing function (ease-out)
      const easeOut = 1 - Math.pow(1 - progress, 3);

      setCurrentValue(Math.floor(value * easeOut));

      if (progress < 1) {
        requestAnimationFrame(updateValue);
      } else {
        setCurrentValue(value); // Устанавливаем финальное значение
      }
    };

    requestAnimationFrame(updateValue);
  };

  const formattedValue = currentValue.toLocaleString('ru-RU');

  return (
    <div
      ref={elementRef}
      className={`${styles.statCounter} ${className}`}
      role="status"
      aria-live="polite"
      aria-label={`${value}${suffix} ${label}`}
    >
      <div className={styles.value} aria-hidden="true">
        {formattedValue}
        {suffix && <span className={styles.suffix}>{suffix}</span>}
      </div>
      <div className={styles.label}>{label}</div>
    </div>
  );
};
