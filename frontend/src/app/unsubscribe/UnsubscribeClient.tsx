'use client';

import { useEffect, useRef, useState } from 'react';
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
      <p role="status" aria-live="polite" className="text-slate-600">
        Проверяем ссылку…
      </p>
    );
  }

  if (view.kind === 'confirm') {
    return (
      <div className="space-y-5">
        <p className="text-slate-700">
          После подтверждения адрес перестанет получать маркетинговые письма OPTISPORT.
        </p>
        <button
          type="button"
          onClick={submit}
          className="rounded-lg bg-slate-900 px-5 py-3 font-semibold text-white outline-none transition hover:bg-slate-700 focus-visible:ring-4 focus-visible:ring-orange-400"
        >
          Отписаться от рассылки
        </button>
      </div>
    );
  }

  if (view.kind === 'submitting') {
    return (
      <p role="status" aria-live="polite" aria-busy="true" className="text-slate-700">
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
        <h2 className="text-2xl font-bold text-slate-900">Запрос на отписку обработан</h2>
        <p className="text-slate-700">Изменение применено. Эту страницу можно закрыть.</p>
      </div>
    );
  }

  const retryable = view.error !== 'invalid_token';
  return (
    <div
      ref={resultRef}
      role="status"
      aria-live="assertive"
      tabIndex={-1}
      className="space-y-4 outline-none"
    >
      <h2 className="text-2xl font-bold text-slate-900">{ERROR_MESSAGES[view.error]}</h2>
      <p className="text-slate-700">
        {retryable
          ? 'Попробуйте ещё раз. Если ошибка повторится, вернитесь позже.'
          : 'Откройте актуальную ссылку из последнего письма.'}
      </p>
      {retryable && (
        <button
          type="button"
          onClick={submit}
          className="rounded-lg border-2 border-slate-900 px-5 py-3 font-semibold text-slate-900 outline-none transition hover:bg-slate-100 focus-visible:ring-4 focus-visible:ring-orange-400"
        >
          Повторить
        </button>
      )}
    </div>
  );
}
