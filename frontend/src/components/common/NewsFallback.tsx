/**
 * NewsFallback Component
 * Fallback контент при ошибке загрузки новостей
 *
 * @see Story 11.3 - AC 5
 */

import React from 'react';

export const NewsFallback: React.FC = () => (
  <div className="text-center py-8 px-4" role="alert" aria-live="polite">
    <p className="text-base text-text-secondary">
      Новости временно недоступны. Попробуйте обновить страницу позже.
    </p>
  </div>
);
