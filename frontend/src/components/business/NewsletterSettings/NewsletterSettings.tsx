'use client';

/**
 * Блок «Рассылка» в личном кабинете: статус подписки и отписка.
 * Выполняет п. 7 «Согласия на получение рекламы» — отзыв согласия в кабинете.
 * Повторная подписка — только через форму на главной (решение 2026-09-21).
 */

import React, { useEffect, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { useToast } from '@/components/ui/Toast/ToastProvider';
import { newsletterSettingsService } from '@/services/newsletterSettingsService';

type LoadState = 'loading' | 'ready' | 'failed';

/**
 * Ответ пришёл по сети: подписанным считаем только явное `true`. Для загрузки
 * статуса любое другое тело — сбой, а не «не подписан»: иначе подписанный
 * человек потерял бы кнопку отписки из-за странного ответа прокси.
 */
const readSubscribed = (value: unknown): boolean => {
  if (!value || typeof value !== 'object') {
    throw new Error('Unexpected newsletter status response');
  }
  const subscribed = (value as { subscribed?: unknown }).subscribed;
  if (typeof subscribed !== 'boolean') {
    throw new Error('Unexpected newsletter status response');
  }
  return subscribed;
};

const NewsletterSettings: React.FC = () => {
  const { error } = useToast();
  const [loadState, setLoadState] = useState<LoadState>('loading');
  const [subscribed, setSubscribed] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;

    newsletterSettingsService
      .getStatus()
      .then(status => {
        if (cancelled) return;
        setSubscribed(readSubscribed(status));
        setLoadState('ready');
      })
      .catch(() => {
        if (!cancelled) setLoadState('failed');
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const handleUnsubscribe = async () => {
    setIsSubmitting(true);
    try {
      const status = await newsletterSettingsService.unsubscribe();
      setSubscribed(readSubscribed(status));
    } catch {
      error('Не удалось отписаться. Попробуйте позже.');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section aria-labelledby="newsletter-settings-title" className="mt-10 space-y-3">
      <h2 id="newsletter-settings-title" className="text-title-m text-neutral-900">
        Рассылка
      </h2>

      {/* Смену статуса после отписки озвучивает скринридер. */}
      <div aria-live="polite" className="space-y-3">
        {loadState === 'loading' && (
          <p className="flex items-center gap-2 text-body-m text-neutral-600">
            <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
            Загрузка...
          </p>
        )}

        {loadState === 'failed' && (
          <p className="text-body-m text-neutral-600">
            Не удалось загрузить статус подписки. Обновите страницу.
          </p>
        )}

        {loadState === 'ready' && subscribed && (
          <>
            <p className="text-body-m text-neutral-700">
              Вы подписаны на информационные и рекламные рассылки OPTISPORT по электронной почте.
            </p>
            <button
              type="button"
              onClick={handleUnsubscribe}
              disabled={isSubmitting}
              className={`
              h-10 px-6 rounded-sm text-body-m font-medium border transition-colors duration-150
              ${
                isSubmitting
                  ? 'border-neutral-300 text-neutral-400 cursor-not-allowed'
                  : 'border-neutral-400 text-neutral-900 hover:bg-neutral-100'
              }
            `}
            >
              {isSubmitting ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin" aria-hidden="true" />
                  Отписка...
                </span>
              ) : (
                'Отписаться'
              )}
            </button>
          </>
        )}

        {loadState === 'ready' && !subscribed && (
          <p className="text-body-m text-neutral-700">Вы не подписаны на рассылку.</p>
        )}
      </div>
    </section>
  );
};

export default NewsletterSettings;
