/**
 * Утилиты для работы с ценообразованием (Story 12.1)
 */

import type { ProductPrice } from '@/types/api';

export type UserRole =
  | 'retail'
  | 'wholesale_level1'
  | 'wholesale_level2'
  | 'wholesale_level3'
  | 'wholesale_level4'
  | 'trainer'
  | 'federation_rep'
  | 'admin'
  // Контрагент 1С без портального аккаунта: цены розничные (ветка default)
  | 'unregistered'
  | 'guest';

/**
 * Видит ли роль B2B-информацию (РРЦ, МРЦ, оптовые условия).
 *
 * Не «всё, кроме retail»: гость, а также контрагент 1С без портального
 * аккаунта (`unregistered`) к B2B-ценам доступа не имеют.
 */
export function isB2BRole(role: UserRole | undefined): boolean {
  return (
    role === 'wholesale_level1' ||
    role === 'wholesale_level2' ||
    role === 'wholesale_level3' ||
    role === 'wholesale_level4' ||
    role === 'trainer' ||
    role === 'federation_rep'
  );
}

/**
 * Получает цену для конкретной роли пользователя
 * @param price - Объект цен товара
 * @param userRole - Роль пользователя
 * @returns Цена для данной роли (fallback на retail)
 */
export function getPriceForRole(price: ProductPrice, userRole: UserRole): number {
  switch (userRole) {
    case 'retail':
      return price.retail;
    case 'wholesale_level1':
      return price.wholesale?.level1 || price.retail;
    case 'wholesale_level2':
      return price.wholesale?.level2 || price.retail;
    case 'wholesale_level3':
      return price.wholesale?.level3 || price.retail;
    case 'wholesale_level4':
      return price.wholesale?.level4 || price.retail;
    case 'trainer':
      return price.trainer || price.retail;
    case 'federation_rep':
      return price.federation || price.retail;
    case 'admin':
      return price.retail;
    case 'guest':
    default:
      return price.retail;
  }
}

/**
 * Форматирует цену в рублях с валютой
 * @param price - Цена в числовом формате
 * @param currency - Код валюты (по умолчанию RUB)
 * @returns Отформатированная строка цены
 */
export function formatPrice(price: number, currency: string = 'RUB'): string {
  const formatter = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
  return formatter.format(price);
}
