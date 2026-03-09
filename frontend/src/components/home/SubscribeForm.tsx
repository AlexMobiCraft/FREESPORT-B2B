/**
 * SubscribeForm Component
 * Форма подписки на email-рассылку
 *
 * @see Story 11.3 - AC 1, 2, 5
 */

'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'react-hot-toast';
import { subscribeService } from '@/services/subscribeService';
import { Input } from '@/components/ui/Input/Input';
import { Button } from '@/components/ui/Button/Button';

interface SubscribeFormData {
  email: string;
}

export const SubscribeForm: React.FC = () => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<SubscribeFormData>();

  const onSubmit = async (data: SubscribeFormData) => {
    try {
      await subscribeService.subscribe(data.email);
      toast.success('Вы успешно подписались на рассылку');
      reset();
    } catch (error: unknown) {
      if (error instanceof Error) {
        if (error.message === 'already_subscribed') {
          toast.error('Этот email уже подписан на рассылку');
        } else if (error.message === 'validation_error') {
          toast.error('Введите корректный email');
        } else {
          toast.error('Не удалось подписаться. Попробуйте позже');
        }
      } else {
        toast.error('Не удалось подписаться. Попробуйте позже');
      }
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <h3 className="text-xl font-semibold text-text-primary">Подписаться на рассылку</h3>
      <p className="text-sm text-text-secondary">
        Получайте первыми информацию о новинках и акциях
      </p>
      <Input
        label="Email"
        type="email"
        placeholder="your@email.com"
        error={errors.email?.message}
        aria-required="true"
        aria-invalid={!!errors.email}
        {...register('email', {
          required: 'Email обязателен',
          pattern: {
            value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
            message: 'Введите корректный email',
          },
        })}
      />
      <Button
        type="submit"
        variant="primary"
        disabled={isSubmitting}
        loading={isSubmitting}
        className="w-full"
      >
        {isSubmitting ? 'Отправка...' : 'Подписаться'}
      </Button>
    </form>
  );
};
