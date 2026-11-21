'use client';

/**
 * AuthGate — показывает спиннер, пока AuthProvider восстанавливает сессию.
 *
 * AuthProvider рендерит страницы сразу, не дожидаясь инициализации. Разделам,
 * которым для отрисовки нужен заполненный authStore (личный кабинет), этот
 * компонент возвращает прежнее поведение: содержимое появляется после неё.
 */

import React from 'react';
import { useAuth } from '@/providers/AuthProvider';

interface AuthGateProps {
  children: React.ReactNode;
}

export function AuthGate({ children }: AuthGateProps) {
  const { isInitialized } = useAuth();

  if (!isInitialized) {
    return (
      <div role="status" className="flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-4">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-primary"></div>
          <p className="text-body-m text-[var(--color-text-muted)]">Загрузка...</p>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
