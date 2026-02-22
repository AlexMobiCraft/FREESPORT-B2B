/**
 * Unit тесты для утилит ценообразования (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import { getPriceForRole, formatPrice } from '../pricing';
import type { ProductPrice } from '@/types/api';

describe('getPriceForRole', () => {
  const mockPrice: ProductPrice = {
    retail: 12990,
    wholesale: {
      level1: 11890,
      level2: 11290,
      level3: 10790,
    },
    trainer: 10990,
    federation: 9990,
    currency: 'RUB',
  };

  it('возвращает retail цену для роли retail', () => {
    expect(getPriceForRole(mockPrice, 'retail')).toBe(12990);
  });

  it('возвращает wholesale level1 для роли wholesale_level1', () => {
    expect(getPriceForRole(mockPrice, 'wholesale_level1')).toBe(11890);
  });

  it('возвращает wholesale level2 для роли wholesale_level2', () => {
    expect(getPriceForRole(mockPrice, 'wholesale_level2')).toBe(11290);
  });

  it('возвращает wholesale level3 для роли wholesale_level3', () => {
    expect(getPriceForRole(mockPrice, 'wholesale_level3')).toBe(10790);
  });

  it('возвращает trainer цену для роли trainer', () => {
    expect(getPriceForRole(mockPrice, 'trainer')).toBe(10990);
  });

  it('возвращает federation цену для роли federation_rep', () => {
    expect(getPriceForRole(mockPrice, 'federation_rep')).toBe(9990);
  });

  it('возвращает retail цену для роли admin', () => {
    expect(getPriceForRole(mockPrice, 'admin')).toBe(12990);
  });

  it('возвращает retail цену для роли guest', () => {
    expect(getPriceForRole(mockPrice, 'guest')).toBe(12990);
  });

  it('fallback на retail если wholesale цена отсутствует', () => {
    const priceWithoutWholesale: ProductPrice = {
      retail: 12990,
      currency: 'RUB',
    };
    expect(getPriceForRole(priceWithoutWholesale, 'wholesale_level1')).toBe(12990);
    expect(getPriceForRole(priceWithoutWholesale, 'wholesale_level2')).toBe(12990);
    expect(getPriceForRole(priceWithoutWholesale, 'wholesale_level3')).toBe(12990);
  });

  it('fallback на retail если trainer цена отсутствует', () => {
    const priceWithoutTrainer: ProductPrice = {
      retail: 12990,
      currency: 'RUB',
    };
    expect(getPriceForRole(priceWithoutTrainer, 'trainer')).toBe(12990);
  });

  it('fallback на retail если federation цена отсутствует', () => {
    const priceWithoutFederation: ProductPrice = {
      retail: 12990,
      currency: 'RUB',
    };
    expect(getPriceForRole(priceWithoutFederation, 'federation_rep')).toBe(12990);
  });

  it('обрабатывает частично заполненные wholesale цены', () => {
    const partialWholesale: ProductPrice = {
      retail: 12990,
      wholesale: {
        level1: 11890,
        // level2 и level3 отсутствуют
      },
      currency: 'RUB',
    };
    expect(getPriceForRole(partialWholesale, 'wholesale_level1')).toBe(11890);
    expect(getPriceForRole(partialWholesale, 'wholesale_level2')).toBe(12990); // fallback
    expect(getPriceForRole(partialWholesale, 'wholesale_level3')).toBe(12990); // fallback
  });
});

describe('formatPrice', () => {
  it('форматирует цену в рублях без копеек', () => {
    expect(formatPrice(12990, 'RUB')).toBe('12\u00A0990\u00A0₽');
  });

  it('форматирует цену с дефолтной валютой RUB', () => {
    expect(formatPrice(5500)).toBe('5\u00A0500\u00A0₽');
  });

  it('форматирует большие числа с пробелами', () => {
    expect(formatPrice(1234567, 'RUB')).toBe('1\u00A0234\u00A0567\u00A0₽');
  });

  it('форматирует маленькие числа', () => {
    expect(formatPrice(99, 'RUB')).toBe('99\u00A0₽');
  });

  it('форматирует ноль корректно', () => {
    expect(formatPrice(0, 'RUB')).toBe('0\u00A0₽');
  });
});
