'use client';

import Link from 'next/link';
import { Button } from '@/components/ui';
import { useCookieConsent } from '@/hooks/useCookieConsent';

export default function CookieConsentBanner() {
  const { isAccepted, isLoaded, accept } = useCookieConsent();

  if (!isLoaded || isAccepted) {
    return null;
  }

  return (
    <div
      role="region"
      aria-label="Уведомление об использовании cookie"
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-200 bg-white shadow-lg"
    >
      <div className="container mx-auto flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:py-4">
        <p className="text-sm text-text-secondary">
          Мы используем файлы cookie, чтобы сайт работал корректно. Продолжая пользоваться сайтом,
          вы соглашаетесь с обработкой файлов cookie и пользовательских данных согласно{' '}
          <Link
            href="/privacy-policy"
            target="_blank"
            rel="noopener noreferrer"
            className="text-primary underline transition-colors hover:text-primary-hover hover:no-underline"
          >
            Политике обработки персональных данных
          </Link>
          .
        </p>
        <Button variant="primary" size="medium" onClick={accept} className="shrink-0">
          Принять
        </Button>
      </div>
    </div>
  );
}
