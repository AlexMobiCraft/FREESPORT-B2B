'use client';

/**
 * RequisitesForm Component
 * Форма редактирования реквизитов компании для B2B пользователей
 */

import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Loader2 } from 'lucide-react';
import apiClient from '@/services/api-client';
import { useToast } from '@/components/ui/Toast/ToastProvider';
import { authSelectors } from '@/stores/authStore';

/**
 * Данные формы реквизитов
 */
interface RequisitesFormData {
  legal_name: string;
  tax_id: string;
  kpp: string;
  legal_address: string;
  bank_name: string;
  bank_bik: string;
  account_number: string;
}

/**
 * Ответ API для Company
 */
interface CompanyResponse {
  id: number;
  legal_name: string;
  tax_id: string;
  kpp: string;
  legal_address: string;
  bank_name: string;
  bank_bik: string;
  account_number: string;
  created_at: string;
  updated_at: string;
}

const defaultValues: RequisitesFormData = {
  legal_name: '',
  tax_id: '',
  kpp: '',
  legal_address: '',
  bank_name: '',
  bank_bik: '',
  account_number: '',
};

/**
 * RequisitesForm - форма редактирования реквизитов компании
 */
const RequisitesForm: React.FC = () => {
  const isB2B = authSelectors.useIsB2BUser();
  const { success, error } = useToast();

  const [isLoading, setIsLoading] = useState(false);
  const [isFetching, setIsFetching] = useState(true);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isDirty },
  } = useForm<RequisitesFormData>({
    defaultValues,
  });

  /**
   * Загрузка данных реквизитов при монтировании
   */
  useEffect(() => {
    const fetchCompany = async () => {
      try {
        setIsFetching(true);
        const response = await apiClient.get<CompanyResponse>('/users/company/');
        const data = response.data;

        reset({
          legal_name: data.legal_name || '',
          tax_id: data.tax_id || '',
          kpp: data.kpp || '',
          legal_address: data.legal_address || '',
          bank_name: data.bank_name || '',
          bank_bik: data.bank_bik || '',
          account_number: data.account_number || '',
        });
      } catch (err) {
        console.error('Failed to fetch company:', err);
        error('Не удалось загрузить реквизиты компании');
      } finally {
        setIsFetching(false);
      }
    };

    if (isB2B) {
      fetchCompany();
    } else {
      setIsFetching(false);
    }
  }, [reset, isB2B, error]);

  /**
   * Обработчик отправки формы
   */
  const onSubmit = async (data: RequisitesFormData) => {
    try {
      setIsLoading(true);

      await apiClient.put<CompanyResponse>('/users/company/', data);

      // Сбрасываем форму с новыми данными (isDirty станет false)
      reset(data);

      success('Реквизиты компании успешно обновлены');
    } catch (err) {
      console.error('Failed to update company:', err);
      error('Ошибка при сохранении реквизитов');
    } finally {
      setIsLoading(false);
    }
  };

  // Если не B2B пользователь
  if (!isB2B) {
    return (
      <div className="text-center py-12">
        <p className="text-body-m text-neutral-600">Раздел доступен только для B2B пользователей</p>
      </div>
    );
  }

  // Loader пока загружаются данные
  if (isFetching) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <span className="ml-3 text-body-m text-neutral-600">Загрузка реквизитов...</span>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
      {/* Юридическая информация */}
      <div className="space-y-4">
        <h2 className="text-title-m text-neutral-900">Юридическая информация</h2>

        {/* Юридическое название */}
        <div>
          <label htmlFor="legal_name" className="block text-body-s text-neutral-700 mb-1">
            Юридическое название
          </label>
          <input
            id="legal_name"
            type="text"
            {...register('legal_name')}
            className={`
              w-full h-10 px-4 rounded-sm border text-body-m
              bg-neutral-100 transition-colors
              focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
              ${errors.legal_name ? 'border-danger' : 'border-neutral-400'}
            `}
            placeholder="ООО «Спортмастер»"
          />
        </div>

        {/* ИНН и КПП */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="tax_id" className="block text-body-s text-neutral-700 mb-1">
              ИНН
            </label>
            <input
              id="tax_id"
              type="text"
              {...register('tax_id')}
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.tax_id ? 'border-danger' : 'border-neutral-400'}
              `}
              placeholder="1234567890"
              maxLength={12}
            />
          </div>
          <div>
            <label htmlFor="kpp" className="block text-body-s text-neutral-700 mb-1">
              КПП
            </label>
            <input
              id="kpp"
              type="text"
              {...register('kpp')}
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.kpp ? 'border-danger' : 'border-neutral-400'}
              `}
              placeholder="123456789"
              maxLength={9}
            />
          </div>
        </div>

        {/* Юридический адрес */}
        <div>
          <label htmlFor="legal_address" className="block text-body-s text-neutral-700 mb-1">
            Юридический адрес
          </label>
          <textarea
            id="legal_address"
            {...register('legal_address')}
            rows={3}
            className={`
              w-full px-4 py-2 rounded-sm border text-body-m
              bg-neutral-100 transition-colors resize-none
              focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
              ${errors.legal_address ? 'border-danger' : 'border-neutral-400'}
            `}
            placeholder="123456, г. Москва, ул. Примерная, д. 1, офис 100"
          />
        </div>
      </div>

      {/* Банковские реквизиты */}
      <div className="space-y-4 pt-4 border-t border-neutral-300">
        <h2 className="text-title-m text-neutral-900">Банковские реквизиты</h2>

        {/* Название банка */}
        <div>
          <label htmlFor="bank_name" className="block text-body-s text-neutral-700 mb-1">
            Название банка
          </label>
          <input
            id="bank_name"
            type="text"
            {...register('bank_name')}
            className={`
              w-full h-10 px-4 rounded-sm border text-body-m
              bg-neutral-100 transition-colors
              focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
              ${errors.bank_name ? 'border-danger' : 'border-neutral-400'}
            `}
            placeholder="ПАО Сбербанк"
          />
        </div>

        {/* БИК и Расчётный счёт */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label htmlFor="bank_bik" className="block text-body-s text-neutral-700 mb-1">
              БИК
            </label>
            <input
              id="bank_bik"
              type="text"
              {...register('bank_bik')}
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.bank_bik ? 'border-danger' : 'border-neutral-400'}
              `}
              placeholder="044525225"
              maxLength={9}
            />
          </div>
          <div>
            <label htmlFor="account_number" className="block text-body-s text-neutral-700 mb-1">
              Расчётный счёт
            </label>
            <input
              id="account_number"
              type="text"
              {...register('account_number')}
              className={`
                w-full h-10 px-4 rounded-sm border text-body-m
                bg-neutral-100 transition-colors
                focus:outline-none focus:ring-2 focus:ring-primary focus:border-primary
                ${errors.account_number ? 'border-danger' : 'border-neutral-400'}
              `}
              placeholder="40702810000000000000"
              maxLength={20}
            />
          </div>
        </div>
      </div>

      {/* Submit Button */}
      <div className="pt-4">
        <button
          type="submit"
          disabled={isLoading || !isDirty}
          className={`
            w-full sm:w-auto h-10 px-6 rounded-sm text-body-m font-medium
            transition-colors duration-150
            ${
              isLoading || !isDirty
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
            'Сохранить реквизиты'
          )}
        </button>
      </div>
    </form>
  );
};

export default RequisitesForm;
