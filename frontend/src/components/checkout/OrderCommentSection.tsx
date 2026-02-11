'use client';

import { UseFormReturn } from 'react-hook-form';
import { CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';

export interface OrderCommentSectionProps {
  form: UseFormReturn<CheckoutFormInput, unknown, CheckoutFormData>;
}

/**
 * Секция комментариев к заказу для формы checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * Поле:
 * - Комментарий (опционально, максимум 500 символов)
 *
 * Особенности:
 * - Отображает счётчик символов (например, "250/500")
 * - Styled textarea вместо UI Kit Input (для многострочного текста)
 */
export function OrderCommentSection({ form }: OrderCommentSectionProps) {
  const {
    register,
    watch,
    formState: { errors },
  } = form;

  const comment = watch('comment') || '';
  const maxLength = 500;
  const currentLength = comment.length;

  return (
    <section className="rounded-lg bg-white p-6 shadow-sm" aria-labelledby="comment-section">
      <h2 id="comment-section" className="mb-4 text-lg font-semibold text-gray-900">
        Комментарий к заказу
      </h2>

      <div>
        <label htmlFor="comment" className="mb-1 block text-sm font-medium text-gray-700">
          Комментарий (необязательно)
        </label>
        <textarea
          {...register('comment')}
          id="comment"
          rows={4}
          maxLength={maxLength}
          placeholder="Укажите дополнительную информацию для доставки или пожелания к заказу..."
          className={`
            block w-full rounded-sm border px-3 py-2 text-sm shadow-sm
            transition-colors duration-200
            placeholder:text-gray-400
            focus:outline-none focus:ring-2 focus:ring-offset-1
            disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-500
            ${errors.comment
              ? 'border-red-300 focus:border-red-500 focus:ring-red-500'
              : 'border-gray-300 focus:border-primary focus:ring-primary'
            }
          `}
          aria-invalid={!!errors.comment}
          aria-describedby={errors.comment ? 'comment-error' : 'comment-helper'}
        />

        {/* Счётчик символов и ошибка */}
        <div className="mt-1 flex items-center justify-between">
          <div>
            {errors.comment ? (
              <p id="comment-error" className="text-sm text-red-600">
                {errors.comment.message}
              </p>
            ) : (
              <p id="comment-helper" className="text-xs text-gray-500">
                Необязательное поле
              </p>
            )}
          </div>
          <p
            className={`text-xs ${currentLength > maxLength * 0.9 ? 'text-orange-600' : 'text-gray-500'
              }`}
            aria-live="polite"
          >
            {currentLength}/{maxLength}
          </p>
        </div>
      </div>
    </section>
  );
}
