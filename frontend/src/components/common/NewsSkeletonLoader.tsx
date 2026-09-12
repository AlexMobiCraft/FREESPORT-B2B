/**
 * NewsSkeletonLoader Component
 * Skeleton loader для блока новостей
 *
 * @see Story 11.3 - AC 5
 */

import React from 'react';

export const NewsSkeletonLoader: React.FC = () => (
  <div className="space-y-4">
    {/* Заголовок секции skeleton */}
    <div className="h-6 w-32 bg-neutral-200 animate-pulse rounded" />

    {/* 3 карточки новостей skeleton */}
    {[1, 2, 3].map(i => (
      <div
        key={i}
        className="flex gap-4 p-4 bg-neutral-100 rounded-lg"
        aria-label="Загрузка новости"
      >
        {/* Изображение skeleton */}
        <div className="w-24 h-24 bg-neutral-200 animate-pulse rounded-lg shrink-0" />

        {/* Контент skeleton */}
        <div className="flex-1 space-y-2">
          {/* Заголовок */}
          <div className="h-5 bg-neutral-200 animate-pulse rounded w-3/4" />
          {/* Описание - 2 строки */}
          <div className="h-4 bg-neutral-200 animate-pulse rounded w-full" />
          <div className="h-4 bg-neutral-200 animate-pulse rounded w-5/6" />
          {/* Дата */}
          <div className="h-3 bg-neutral-200 animate-pulse rounded w-1/4" />
        </div>
      </div>
    ))}
  </div>
);
