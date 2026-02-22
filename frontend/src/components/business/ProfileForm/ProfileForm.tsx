'use client';

/**
 * ProfileForm Component
 * Форма редактирования профиля пользователя с React Hook Form + Zod валидацией
 * Story 16.1 - AC: 2, 3, 4
 */

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';

import apiClient from '@/services/api-client';

import { useAuthStore, authSelectors } from '@/stores/authStore';
import { useToast } from '@/components/ui/Toast/ToastProvider';
import { PhoneInput } from '@/components/ui';
import { profileSchema, ProfileFormData, defaultProfileValues } from './schema';
import type { User } from '@/types/api';

/**
 * Маппинг статусов верификации на человекочитаемые названия и стили
 */
const VERIFICATION_STATUS_MAP: Record<string, { label: string; className: string }> = {
  verified: {
    label: 'Верифицирован',
    className: 'bg-success-bg text-success',
  },
  pending: {
    label: 'На проверке',
    className: 'bg-warning-bg text-warning',
  },
  unverified: {
    label: 'Не верифицирован',
    className: 'bg-neutral-200 text-neutral-700',
  },
};

/**
 * Компонент Badge для отображения статуса верификации
 */
const VerificationBadge: React.FC<{ status?: string }> = ({ status }) => {
  const statusConfig = VERIFICATION_STATUS_MAP[status || 'unverified'];

  return (
    <span
      className={`
        inline-flex items-center px-3 py-1 rounded-full text-body-s font-medium
        ${statusConfig.className}
      `}
    >
      {statusConfig.label}
    </span>
  );
};

/**
 * ProfileForm - форма редактирования профиля
 */
const ProfileForm: React.FC = () => {
  const user = authSelectors.useUser();
  const isB2B = authSelectors.useIsB2BUser();
  const setUser = useAuthStore(state => state.setUser);
  const { success, error } = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<ProfileFormData>({
    resolver: zodResolver(profileSchema),
    defaultValues: defaultProfileValues,
  });

  /**
   * Загрузка данных профиля при монтировании
   */
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        setIsFetching(true);
        const response = await apiClient.get<User>('/users/profile/');
        const profileData = response.data;

        // Обновляем форму данными с сервера
        reset({
          email: profileData.email || '',
          first_name: profileData.first_name || '',
          last_name: profileData.last_name || '',
          phone: profileData.phone || '',
          company_name: profileData.company_name || '',
          tax_id: profileData.tax_id || '',
        });

        // Обновляем user в authStore
        setUser(profileData);
      } catch {
        error('Не удалось загрузить данные профиля');
      } finally {
        setIsFetching(false);
      }
    };

    fetchProfile();
  }, [reset, setUser, error]);

  /**
   * Обработчик отправки формы
   */
  const onSubmit = async (data: ProfileFormData) => {
    try {
      setIsLoading(true);

      // Подготавливаем данные для отправки (исключаем email - он readonly)
      const updateData: Partial<ProfileFormData> = {
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone,
      };

      // Добавляем B2B поля только для B2B пользователей
      if (isB2B) {
        updateData.company_name = data.company_name;
        updateData.tax_id = data.tax_id;
      }

      const response = await apiClient.put<User>('/users/profile/', updateData);

      // Обновляем user в authStore
      setUser(response.data);

      // Сбрасываем форму с новыми данными (isDirty станет false)
      reset({
        email: response.data.email || '',
        first_name: response.data.first_name || '',
        last_name: response.data.last_name || '',
        phone: response.data.phone || '',
        company_name: response.data.company_name || '',
        tax_id: response.data.tax_id || '',
      });

      success('Профиль успешно обновлён');
    } catch {
      error('Ошибка при сохранении профиля');
    } finally {
      setIsLoading(false);
    }
  };

  // Показываем loader пока загружаются данные
  if (isFetching) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="ml-3 text-body-m text-neutral-600">Загрузка профиля...</span>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Основные поля */}
      <div className="space-y-4">
        <h2 className="text-title-m text-neutral-900">Личные данные</h2>

        {/* Email (readonly) */}
        <div>
          <label htmlFor="email" className="block text-body-s text-neutral-700 mb-1">
            Email
          </label>
          <input
            id="email"
            type="email"
            {...register('email')}
            readOnly
            disabled
            className="
              w-full h-10 px-4 rounded-sm border border-neutral-400
              bg-neutral-200 text-neutral-600 cursor-not-allowed
              text-body-m
            "
          />
          <p className="mt-1 text-caption text-neutral-500">Email нельзя изменить</p>
        </div>

        {/* Имя */}
        <div>
          <label htmlFor="first_name" className="block text-body-s text-neutral-700 mb-1">
            Имя *
          </label>
          <input
            id="first_name"
            type="text"
            {...register('first_name')}
            className={`
              w-full h-10 px-4 rounded-sm border text-body-m
              bg-neutral-100 transition-colors
              focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
              ${errors.first_name ? 'border-danger' : 'border-neutral-400'}
            `}
          />
          {errors.first_name && (
            <p className="mt-1 text-caption text-danger">{errors.first_name.message}</p>
          )}
        </div>

        {/* Фамилия */}
        <div>
          <label htmlFor="last_name" className="block text-body-s text-neutral-700 mb-1">
            Фамилия *
          </label>
          <input
            id="last_name"
            type="text"
            {...register('last_name')}
            className={`
              w-full h-10 px-4 rounded-sm border text-body-m
              bg-neutral-100 transition-colors
              focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
              ${errors.last_name ? 'border-danger' : 'border-neutral-400'}
            `}
          />
          {errors.last_name && (
            <p className="mt-1 text-caption text-danger">{errors.last_name.message}</p>
          )}
        </div>

        {/* Телефон */}
        <PhoneInput
          id="phone"
          {...register('phone')}
          label="Телефон *"
          error={errors.phone?.message}
        />
      </div>

      {/* B2B поля - только для B2B пользователей */}
      {isB2B && (
        <div className="space-y-4 pt-4 border-t border-neutral-300">
          <div className="flex items-center justify-between">
            <h2 className="text-title-m text-neutral-900">Данные компании</h2>
            <VerificationBadge status={user?.is_verified ? 'verified' : 'unverified'} />
          </div>

          {/* Название компании */}
          <div>
            <label htmlFor="company_name" className="block text-body-s text-neutral-700 mb-1">
              Название компании
            </label>
            <input
              id="company_name"
              type="text"
              {...register('company_name')}
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.company_name ? 'border-danger' : 'border-neutral-400'}
              `}
            />
            {errors.company_name && (
              <p className="mt-1 text-caption text-danger">{errors.company_name.message}</p>
            )}
          </div>

          {/* ИНН */}
          <div>
            <label htmlFor="tax_id" className="block text-body-s text-neutral-700 mb-1">
              ИНН
            </label>
            <input
              id="tax_id"
              type="text"
              {...register('tax_id')}
              placeholder="10 или 12 цифр"
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.tax_id ? 'border-danger' : 'border-neutral-400'}
              `}
            />
            {errors.tax_id && (
              <p className="mt-1 text-caption text-danger">{errors.tax_id.message}</p>
            )}
          </div>
        </div>
      )}

      {/* Submit Button */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={isLoading || !isDirty}
          className={`
            w-full sm:w-auto h-10 px-6 rounded-sm text-body-m font-medium
            transition-colors duration-150
            ${isLoading || !isDirty
              ? 'bg-neutral-400 text-neutral-100 cursor-not-allowed'
              : 'bg-primary text-white hover:bg-primary-hover active:bg-primary-active'
            }
          `}
        >
          {isLoading ? (
            <span className="flex items-center justify-center gap-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              Сохранение...
            </span>
          ) : (
            'Сохранить изменения'
          )}
        </button>
      </div>
    </form>
  );
};

export default ProfileForm;
