'use client';

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { MailX } from 'lucide-react';
import { Button } from '@/components/ui';
import {
  UnsubscribeServiceError,
  type UnsubscribeErrorKind,
  unsubscribeService,
} from '@/services/unsubscribeService';

type ViewState =
  | { kind: 'checking' }
  | { kind: 'confirm' }
  | { kind: 'submitting' }
  | { kind: 'success' }
  | { kind: 'error'; error: UnsubscribeErrorKind };

const TOKEN_PATTERN = /^[A-Za-z0-9_-]{43}$/;

const ERROR_MESSAGES: Record<UnsubscribeErrorKind, string> = {
  invalid_token: 'Ссылка недействительна',
  throttled: 'Слишком много попыток',
  network_error: 'Не удалось обработать запрос',
  server_error: 'Не удалось обработать запрос',
};

export default function UnsubscribeClient() {
  const [token, setToken] = useState<string | null>(null);
  const [view, setView] = useState<ViewState>({ kind: 'checking' });
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const value = window.location.hash.slice(1);
    window.history.replaceState(null, '', `${window.location.pathname}${window.location.search}`);
    if (!TOKEN_PATTERN.test(value)) {
      setView({ kind: 'error', error: 'invalid_token' });
      return;
    }
    setToken(value);
    setView({ kind: 'confirm' });
  }, []);

  useEffect(() => {
    if (view.kind === 'success' || view.kind === 'error') {
      resultRef.current?.focus();
    }
  }, [view]);

  const submit = async () => {
    if (!token) return;
    setView({ kind: 'submitting' });
    try {
      await unsubscribeService.unsubscribe(token);
      setView({ kind: 'success' });
    } catch (error) {
      const kind =
        error instanceof UnsubscribeServiceError
          ? (error.message as UnsubscribeErrorKind)
          : 'network_error';
      setView({ kind: 'error', error: kind });
    }
  };

  if (view.kind === 'checking') {
    return (
      <p role="status" aria-live="polite" className="text-body-m text-text-secondary">
        Проверяем ссылку…
      </p>
    );
  }

  if (view.kind === 'confirm') {
    return (
      <div className="space-y-5">
        <p className="text-body-m text-text-secondary">
          После подтверждения адрес перестанет получать маркетинговые письма OPTISPORT.
        </p>
        <Button type="button" variant="primary" size="large" onClick={submit}>
          Отписаться от рассылки
        </Button>
      </div>
    );
  }

  if (view.kind === 'submitting') {
    return (
      <p
        role="status"
        aria-live="polite"
        aria-busy="true"
        className="text-body-m text-text-secondary"
      >
        Обрабатываем запрос…
      </p>
    );
  }

  if (view.kind === 'success') {
    return (
      <div
        ref={resultRef}
        role="status"
        aria-live="polite"
        tabIndex={-1}
        className="space-y-2 outline-none"
      >
        <h2 className="text-title-l font-semibold text-text-primary">
          Запрос на отписку обработан
        </h2>
        <p className="text-body-m text-text-secondary">
          Изменение применено. Эту страницу можно закрыть.
        </p>
      </div>
    );
  }

  if (view.kind === 'error' && view.error === 'invalid_token') {
    // Тупиковое состояние — по образцу EmptyCart: иконка, заголовок, пояснение, CTA
    return (
      <div
        ref={resultRef}
        role="status"
        aria-live="assertive"
        tabIndex={-1}
        className="flex flex-col items-center justify-center py-8 text-center outline-none"
        data-testid="unsubscribe-invalid-token"
      >
        <MailX className="w-16 h-16 text-neutral-500 mb-6" aria-hidden="true" />

        <h2 className="text-title-l font-semibold text-text-primary mb-2">
          {ERROR_MESSAGES.invalid_token}
        </h2>

        <p className="text-body-m text-text-secondary mb-8">
          Откройте актуальную ссылку из последнего письма.
        </p>

        <Link
          href="/"
          className="h-12 px-8 inline-flex items-center justify-center bg-primary hover:bg-primary-hover text-text-inverse font-medium rounded-[var(--radius-sm)] transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2"
          data-testid="go-home-button"
        >
          На главную
        </Link>
      </div>
    );
  }

  return (
    <div
      ref={resultRef}
      role="status"
      aria-live="assertive"
      tabIndex={-1}
      className="space-y-4 outline-none"
    >
      <h2 className="text-title-l font-semibold text-text-primary">{ERROR_MESSAGES[view.error]}</h2>
      <p className="text-body-m text-text-secondary">
        Попробуйте ещё раз. Если ошибка повторится, вернитесь позже.
      </p>
      <Button type="button" variant="secondary" size="large" onClick={submit}>
        Повторить
      </Button>
    </div>
  );
}
