/**
 * Electric Orange Table Component
 *
 * Таблица в стиле Electric Orange
 * Features:
 * - Skewed header (-12deg)
 * - Alternating row colors
 * - Orange left border on hover
 * - Dark theme
 *
 * @see docs/4-ux-design/00-design-system-migration/02-component-specs.md
 */

'use client';

import React from 'react';
import { cn } from '@/utils/cn';

// ============================================
// Types
// ============================================

export interface ElectricTableColumn<T> {
  key: keyof T | string;
  header: string;
  width?: string;
  align?: 'left' | 'center' | 'right';
  render?: (row: T) => React.ReactNode;
}

export interface ElectricTableProps<T> {
  /** Table columns configuration */
  columns: ElectricTableColumn<T>[];
  /** Table data */
  data: T[];
  /** Row key extractor */
  getRowKey: (row: T) => string | number;
  /** Row click handler */
  onRowClick?: (row: T) => void;
  /** Additional class names */
  className?: string;
}

// ============================================
// Component
// ============================================

export function ElectricTable<T extends Record<string, unknown>>({
  columns,
  data,
  getRowKey,
  onRowClick,
  className,
}: ElectricTableProps<T>) {
  const alignClasses = {
    left: 'text-left',
    center: 'text-center',
    right: 'text-right',
  };

  return (
    <div className={cn('w-full overflow-x-auto', className)}>
      <table className="w-full border-collapse">
        {/* Header */}
        <thead>
          <tr className="border-b border-[var(--border-default)]">
            {columns.map(column => (
              <th
                key={String(column.key)}
                className={cn('p-4 bg-[var(--bg-card)]', alignClasses[column.align || 'left'])}
                style={{ width: column.width }}
              >
                {/* Skewed header text */}
                <span className="font-roboto-condensed font-bold text-sm uppercase text-[var(--foreground)] transform -skew-x-12 inline-block">
                  <span className="transform skew-x-12 inline-block">{column.header}</span>
                </span>
              </th>
            ))}
          </tr>
        </thead>

        {/* Body */}
        <tbody>
          {data.map((row, rowIndex) => (
            <tr
              key={getRowKey(row)}
              onClick={() => onRowClick?.(row)}
              className={cn(
                'border-b border-[var(--border-default)]',
                'transition-all duration-200',
                rowIndex % 2 === 0 ? 'bg-[var(--bg-body)]' : 'bg-[var(--bg-card)]',
                onRowClick &&
                  'cursor-pointer hover:bg-[var(--bg-card-hover)] hover:border-l-4 hover:border-l-[var(--color-primary)]'
              )}
            >
              {columns.map(column => {
                const cellValue = column.render
                  ? column.render(row)
                  : (row[column.key as keyof T] as React.ReactNode);

                return (
                  <td
                    key={String(column.key)}
                    className={cn(
                      'p-4 text-sm text-[var(--color-text-secondary)]',
                      alignClasses[column.align || 'left']
                    )}
                  >
                    {cellValue}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Empty state */}
      {data.length === 0 && (
        <div className="p-8 text-center text-[var(--color-text-muted)]">
          Нет данных для отображения
        </div>
      )}
    </div>
  );
}

ElectricTable.displayName = 'ElectricTable';

export default ElectricTable;
