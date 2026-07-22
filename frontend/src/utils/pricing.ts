/**
 * Утилиты для работы с ценообразованием (Story 12.1)
 */

import type { ProductPrice } from '@/types/api';

export type UserRole =
  | 'retail'
  | 'wholesale_level1'
  | 'wholesale_level2'
  | 'wholesale_level3'
  | 'trainer'
  | 'federation_rep'
  | 'admin'
  | 'guest';

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
