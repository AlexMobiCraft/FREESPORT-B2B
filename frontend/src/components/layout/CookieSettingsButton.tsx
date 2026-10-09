'use client';

import { useRef } from 'react';
import { useCookieConsent } from '@/hooks/useCookieConsent';

export interface CookieSettingsButtonProps {
  /** Классы подвала: палитру задаёт вызывающая сторона, а не сама кнопка. */
  className?: string;
}

/**
 * Кнопка «Настройки cookie» для подвала (Story 41.1, FR-41-02).
 *
 * Один компонент на все три подвала (`Footer`, `ElectricFooter` и собственный
 * подвал `/coming-soon`). Рендерится ВСЕГДА, независимо от сохранённого
 * выбора: условный рендер по состоянию согласия даёт расхождение серверной и
 * клиентской разметки.
 */
export default function CookieSettingsButton({ className }: CookieSettingsButtonProps) {
  const { reopen } = useCookieConsent();
  const buttonRef = useRef<HTMLButtonElement>(null);

  return (
    <button
      ref={buttonRef}
      type="button"
      // Кнопка передаёт себя, чтобы баннер вернул ей фокус при закрытии (AC6).
      onClick={() => reopen(buttonRef.current)}
      className={className}
    >
      Настройки cookie
    </button>
  );
}
