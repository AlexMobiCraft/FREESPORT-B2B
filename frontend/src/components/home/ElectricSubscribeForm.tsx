/**
 * Electric Subscribe Form Component
 * Форма подписки на email-рассылку в стиле Electric Orange
 */

'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'react-hot-toast';
import { subscribeService } from '@/services/subscribeService';
import { ElectricButton } from '@/components/ui/Button/ElectricButton';

interface SubscribeFormData {
  email: string;
}

export const ElectricSubscribeForm: React.FC = () => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SubscribeFormData>();

  const onSubmit = async (data: SubscribeFormData) => {
    try {
      await subscribeService.subscribe(data.email);
      toast.success('ВЫ УСПЕШНО ПОДПИСАЛИСЬ НА РАССЫЛКУ!', {
        style: {
          borderRadius: '0',
          background: '#000',
          color: '#fff',
          border: '1px solid #FF6600',
        },
      });
      reset();
    } catch (error: unknown) {
      // Error handling similar to original but with toast styles if we want
      if (error instanceof Error && error.message === 'already_subscribed') {
        toast.error('ЭТОТ EMAIL УЖЕ ПОДПИСАН', {
          style: { borderRadius: '0', background: '#000', color: '#fff', border: '1px solid red' },
        });
      } else {
        toast.error('ОШИБКА ПОДПИСКИ', {
          style: { borderRadius: '0', background: '#000', color: '#fff', border: '1px solid red' },
        });
      }
    }
  };

  return (
    <form
      onSubmit={handleSubmit(onSubmit)}
      className="space-y-6 max-w-xl mx-auto md:max-w-none md:mx-0"
    >
      <div>
        <h3 className="text-2xl md:text-3xl font-bold text-[var(--foreground)] uppercase mb-2 transform -skew-x-12">
          <span className="inline-block transform skew-x-12">Подписаться на рассылку</span>
        </h3>
        <p className="text-[var(--color-text-secondary)] font-inter text-sm md:text-base">
          Получайте первыми информацию о новинках и акциях
        </p>
      </div>

      <div className="space-y-2">
        <label
          htmlFor="email-subscribe"
          className="block text-sm font-bold text-[var(--foreground)] uppercase transform -skew-x-12"
        >
          <span className="inline-block transform skew-x-12">Email</span>
        </label>
        <div className="relative transform -skew-x-12">
          <input
            id="email-subscribe"
            type="email"
            placeholder="your@email.com"
            className={`
                   w-full bg-[var(--bg-card)] border-2 px-4 py-3 outline-none transition-all duration-300 transform skew-x-12
                   placeholder:text-[var(--color-text-muted)]
                   ${errors.email
                ? 'border-red-500 focus:border-red-500'
                : 'border-[var(--border-default)] focus:border-[var(--color-primary)]'
              }
                `}
            {...register('email', {
              required: 'Email обязателен',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Введите корректный email',
              },
            })}
          />
        </div>
        {errors.email && (
          <p className="text-red-500 text-xs font-bold uppercase mt-1">{errors.email.message}</p>
        )}
      </div>

      <ElectricButton
        type="submit"
        variant="primary"
        size="lg"
        disabled={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'ОТПРАВКА...' : 'ПОДПИСАТЬСЯ'}
      </ElectricButton>
    </form>
  );
};
