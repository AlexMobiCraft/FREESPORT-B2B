/**
 * RoleInfoPanel Component
 * Story 29.1 - Role Selection UI & Warnings
 *
 * Информационная панель, отображаемая при выборе B2B роли (не-retail)
 *
 * AC 3: Показывает информацию о необходимости дополнительных данных и проверки
 * AC 6: Accessibility с role="alert" и aria-live="polite"
 */

'use client';

import React from 'react';

export interface RoleInfoPanelProps {
  /** Видимость панели - true когда выбрана B2B роль */
  visible: boolean;
}

/**
 * RoleInfoPanel - предупреждающая панель для B2B регистрации
 *
 * @param visible - отображать ли панель (true для B2B ролей)
 */
export const RoleInfoPanel: React.FC<RoleInfoPanelProps> = ({ visible }) => {
  // AC 3: Условное отображение
  if (!visible) return null;

  return (
    <div
      // AC 6: Accessibility attributes для screen readers
      role="alert"
      aria-live="polite"
      // AC 7: Стилизация согласно Design System (warning colors)
      className="p-4 rounded-lg bg-[var(--color-warning-50)] border border-[var(--color-warning-300)]"
    >
      <ul className="space-y-2 text-body-s text-[var(--color-warning-700)]">
        {/* AC 3: Три информационных пункта */}
        <li>• Вам потребуется заполнить дополнительные данные</li>
        <li>• Доступ к порталу будет открыт после проверки администратором</li>
        <li>• Вы получите уведомление на email</li>
      </ul>
    </div>
  );
};
