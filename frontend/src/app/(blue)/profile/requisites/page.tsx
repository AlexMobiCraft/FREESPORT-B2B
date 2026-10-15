/**
 * Страница реквизитов компании
 * Доступна только для B2B пользователей
 */

import React from 'react';
import RequisitesForm from '@/components/business/RequisitesForm';

export default function RequisitesPage() {
  return (
    <div>
      <h1 className="text-title-l text-neutral-900 mb-6">Реквизиты компании</h1>
      <RequisitesForm />
    </div>
  );
}
