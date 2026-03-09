'use client';

/**
 * Providers Component
 * Клиентская обёртка для всех провайдеров приложения
 *
 * Story 28.4: AuthProvider для session initialization
 */

import React from 'react';
import { ToastProvider } from '@/components/ui/Toast/ToastProvider';
import { AuthProvider } from '@/providers/AuthProvider';

interface ProvidersProps {
  children: React.ReactNode;
}

export default function Providers({ children }: ProvidersProps) {
  return (
    <AuthProvider>
      <ToastProvider>{children}</ToastProvider>
    </AuthProvider>
  );
}
