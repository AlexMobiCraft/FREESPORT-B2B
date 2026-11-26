/**
 * ProductSpecs Component (Story 12.1)
 * Таблица характеристик товара
 */

import React from 'react';

interface ProductSpecsProps {
  specifications?: Record<string, string>;
}

/**
 * Форматирует значение характеристики
 * Заменяет placeholder-значения из 1С на прочерк
 *
 * @param value - значение характеристики
 * @returns отформатированное значение или прочерк
 */
function formatSpecValue(value: string): string {
  if (!value) return '—';

  // Паттерны для placeholder-значений из 1С (отсутствие данных)
  const placeholderPatterns = [
    '-999 999 999,9',
    '-999999999,9',
    '-999999999.9',
    '-999 999 999.9',
    '-999999999',
    '-999 999 999',
  ];

  const trimmedValue = value.trim();

  // Проверяем на placeholder-значения
  if (placeholderPatterns.includes(trimmedValue)) {
    return '—';
  }

  // Проверяем числовое значение близкое к -999999999
  const numValue = parseFloat(trimmedValue.replace(/\s/g, '').replace(',', '.'));
  if (!isNaN(numValue) && numValue <= -999999999) {
    return '—';
  }

  return value;
}

export default function ProductSpecs({ specifications }: ProductSpecsProps) {
  // Если спецификации пустые или отсутствуют - не отображаем блок
  if (!specifications || Object.keys(specifications).length === 0) {
    return null;
  }

  return (
    <div className="bg-white rounded-lg border border-neutral-200 overflow-hidden">
      <div className="px-6 py-4 bg-neutral-50 border-b border-neutral-200">
        <h2 className="text-xl font-semibold text-neutral-900">Характеристики</h2>
      </div>
      <dl className="divide-y divide-neutral-200">
        {Object.entries(specifications).map(([key, value]) => (
          <div
            key={key}
            className="px-6 py-4 grid grid-cols-3 gap-4 hover:bg-neutral-50 transition-colors"
          >
            <dt className="text-sm font-medium text-neutral-600 col-span-1">{key}</dt>
            <dd className="text-sm text-neutral-900 col-span-2">{formatSpecValue(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
