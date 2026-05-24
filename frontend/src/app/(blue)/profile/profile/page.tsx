'use client';

/**
 * Profile Page
 * Страница профиля пользователя с формой редактирования
 * Story 16.1 - AC: 2, 3, 4
 */

import React from 'react';
import ProfileForm from '@/components/business/ProfileForm/ProfileForm';

/**
 * Страница /profile
 * Отображает форму редактирования профиля пользователя
 */
export default function ProfilePage() {
  return (
    <div>
      <h1 className="text-title-l text-neutral-900 mb-6">Профиль</h1>
      <ProfileForm />
    </div>
  );
}
