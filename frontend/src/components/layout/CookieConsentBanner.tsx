'use client';

import { useEffect, useRef } from 'react';
import Link from 'next/link';
import { Button } from '@/components/ui';
import { consumeCookieConsentTrigger, useCookieConsent } from '@/hooks/useCookieConsent';

export default function CookieConsentBanner() {
  const { isBannerVisible, isForced, accept, decline } = useCookieConsent();
  const bannerRef = useRef<HTMLDivElement>(null);
  // Баннер был открыт кнопкой подвала — значит, при закрытии фокус нужно вернуть.
  const openedFromTriggerRef = useRef(false);

  // Баннер перекрывает подвал, откуда его открыли. Без перевода фокуса
  // клавиатурный пользователь не заметит, что что-то произошло (AC6).
  // При первом показе фокус не крадём — открытие не было действием пользователя.
  useEffect(() => {
    if (isBannerVisible && isForced) {
      openedFromTriggerRef.current = true;
      bannerRef.current?.focus();
      return;
    }

    // Баннер закрылся: фокус со скрытой области ушёл бы на body, поэтому
    // возвращаем его кнопке «Настройки cookie», которая баннер и открыла.
    if (!isBannerVisible && openedFromTriggerRef.current) {
      openedFromTriggerRef.current = false;
      consumeCookieConsentTrigger()?.focus();
    }
  }, [isBannerVisible, isForced]);

  if (!isBannerVisible) {
    return null;
  }

  return (
    <div
      ref={bannerRef}
      role="region"
      tabIndex={-1}
      aria-label="Уведомление об использовании cookie"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-200 bg-white shadow-lg"
    >
      <div className="container mx-auto flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-4">
        <p className="text-sm text-text-secondary">
          Мы используем файлы cookie. Технически необходимые нужны для работы сайта, остальные —
          только с вашего согласия. Подробнее — в{' '}
          <>
            «
            <Link
              href="/privacy-policy"
              target="_blank"
              rel="noopener noreferrer"
              className="text-primary underline transition-colors hover:text-primary-hover hover:no-underline"
            >
              Политике обработки персональных данных
            </Link>
            ».
          </>
        </p>
        <div className="flex shrink-0 gap-3">
          <Button variant="primary" size="medium" onClick={accept}>
            Принять
          </Button>
          <Button variant="secondary" size="medium" onClick={decline}>
            Отклонить
          </Button>
        </div>
      </div>
    </div>
  );
}
