/**
 * Product Detail Error Boundary (Story 12.1)
 * Обработка ошибок при загрузке товара
 */

'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Button from '@/components/ui/Button';

interface ErrorProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ProductError({ error, reset }: ErrorProps) {
  const router = useRouter();

  useEffect(() => {
    // Логируем ошибку на клиенте
    console.error('Product page error:', error);
  }, [error]);

  return (
    <div className="container mx-auto px-4 py-16">
      <div className="max-w-md mx-auto text-center">
        <div className="mb-6">
          <svg
            className="w-24 h-24 mx-auto text-red-500"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>

        <h1 className="text-3xl font-bold text-neutral-900 mb-4">Произошла ошибка</h1>

        <p className="text-neutral-600 mb-8">
          К сожалению, не удалось загрузить информацию о товаре. Попробуйте обновить страницу или
          вернуться к каталогу.
        </p>

        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Button onClick={reset} variant="primary">
            Попробовать снова
          </Button>

          <Button onClick={() => router.push('/catalog')} variant="secondary">
            Вернуться в каталог
          </Button>
        </div>

        {process.env.NODE_ENV === 'development' && error.message && (
          <div className="mt-8 p-4 bg-red-50 border border-red-200 rounded-lg text-left">
            <p className="text-sm font-mono text-red-800 break-all">
              <strong>Error:</strong> {error.message}
            </p>
            {error.digest && (
              <p className="text-sm font-mono text-red-600 mt-2">
                <strong>Digest:</strong> {error.digest}
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
