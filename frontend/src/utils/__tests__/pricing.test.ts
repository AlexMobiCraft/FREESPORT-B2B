/**
 * Unit тесты для утилит ценообразования (Story 12.1)
 */

import { describe, it, expect } from 'vitest';
import {
  getPriceForRole,
  getProductDisplayPrice,
  formatPrice,
  isApiPricedRole,
  isB2BRole,
  isPromoApplied,
} from '../pricing';
import type { ProductPrice } from '@/types/api';

describe('getPriceForRole', () => {
  const mockPrice: ProductPrice = {
    retail: 12990,
    wholesale: {
      level1: 11890,
      level2: 11290,
      level3: 10790,
      level4: 10490,
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

  it('возвращает wholesale level4 для роли wholesale_level4', () => {
    expect(getPriceForRole(mockPrice, 'wholesale_level4')).toBe(10490);
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
    expect(getPriceForRole(priceWithoutWholesale, 'wholesale_level4')).toBe(12990);
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
        // level2, level3 и level4 отсутствуют
      },
      currency: 'RUB',
    };
    expect(getPriceForRole(partialWholesale, 'wholesale_level1')).toBe(11890);
    expect(getPriceForRole(partialWholesale, 'wholesale_level2')).toBe(12990); // fallback
    expect(getPriceForRole(partialWholesale, 'wholesale_level3')).toBe(12990); // fallback
    expect(getPriceForRole(partialWholesale, 'wholesale_level4')).toBe(12990); // fallback
  });
});

describe('isB2BRole', () => {
  it('относит wholesale_level4 к B2B', () => {
    expect(isB2BRole('wholesale_level4')).toBe(true);
  });

  it('не относит unregistered к B2B', () => {
    expect(isB2BRole('unregistered')).toBe(false);
  });

  it.each(['vip', 'special_price'] as const)('относит %s к B2B (РРЦ/МРЦ, оптовые условия)', role => {
    expect(isB2BRole(role)).toBe(true);
  });

  it.each(['retail', 'guest', 'admin', undefined] as const)('не относит %s к B2B', role => {
    expect(isB2BRole(role)).toBe(false);
  });
});

describe('isApiPricedRole', () => {
  it.each(['vip', 'special_price'] as const)('%s берёт цену из API итогом', role => {
    expect(isApiPricedRole(role)).toBe(true);
  });

  it.each(['retail', 'wholesale_level1', 'trainer', 'federation_rep', 'guest', undefined] as const)(
    '%s считается по полям товара',
    role => {
      expect(isApiPricedRole(role)).toBe(false);
    }
  );
});

describe('isPromoApplied', () => {
  it('акции нет — не применена', () => {
    expect(isPromoApplied({ promo_price: null, current_price: '700.00' })).toBe(false);
    expect(isPromoApplied({ promo_price: '', current_price: '700.00' })).toBe(false);
    expect(isPromoApplied({ current_price: '700.00' })).toBe(false);
    expect(isPromoApplied(null)).toBe(false);
    expect(isPromoApplied(undefined)).toBe(false);
  });

  it('нулевая и мусорная акционная цена — не применена', () => {
    expect(isPromoApplied({ promo_price: '0.00', current_price: '700.00' })).toBe(false);
    expect(isPromoApplied({ promo_price: 'abc', current_price: '700.00' })).toBe(false);
  });

  it('клиент платит акционную цену (ниже своей) — применена', () => {
    expect(isPromoApplied({ promo_price: '700.00', current_price: '700.00' })).toBe(true);
  });

  it('акция равна цене клиента — применена', () => {
    expect(isPromoApplied({ promo_price: '800.00', current_price: '800.00' })).toBe(true);
  });

  it('клиент платит свою цену, она ниже акционной — не применена', () => {
    expect(isPromoApplied({ promo_price: '800.00', current_price: '700.00' })).toBe(false);
    expect(isPromoApplied({ promo_price: '900.00', current_price: '800.00' })).toBe(false);
  });

  it('копейки различаются: 800,40 против 800,49', () => {
    expect(isPromoApplied({ promo_price: '800.49', current_price: '800.40' })).toBe(false);
    expect(isPromoApplied({ promo_price: '800.40', current_price: '800.40' })).toBe(true);
  });

  it('нет current_price — акция считается применённой, как до правила «меньшая из цен»', () => {
    expect(isPromoApplied({ promo_price: '800.00' })).toBe(true);
    expect(isPromoApplied({ promo_price: '800.00', current_price: '' })).toBe(true);
    expect(isPromoApplied({ promo_price: '800.00', current_price: null })).toBe(true);
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

describe('getProductDisplayPrice', () => {
  // Розница 1200, оптовая первого уровня 700, акции нет
  const product = {
    price: { retail: 1200, wholesale: { level1: 700 }, currency: 'RUB' },
    current_price: '700.00',
    promo_price: null,
  };

  it('без варианта и акции отдаёт цену по роли, а не розницу (D14-2)', () => {
    expect(getProductDisplayPrice(product, 'wholesale_level1', null)).toBe(700);
  });

  it('гостю без варианта и акции — розница', () => {
    expect(getProductDisplayPrice(product, 'guest', null)).toBe(1200);
  });

  it('при акции без варианта — current_price товара для любой роли', () => {
    const promo = { ...product, current_price: '800.00', promo_price: '800.00' };
    expect(getProductDisplayPrice(promo, 'guest')).toBe(800);
    expect(getProductDisplayPrice(promo, 'wholesale_level1')).toBe(800);
  });

  it('при акции и пустом current_price — акционная цена', () => {
    const promo = { ...product, current_price: '', promo_price: '800.00' };
    expect(getProductDisplayPrice(promo, 'guest')).toBe(800);
  });

  it('выбранный вариант задаёт цену', () => {
    const variant = { current_price: '650.00', promo_price: null };
    expect(getProductDisplayPrice(product, 'guest', variant)).toBe(650);
  });

  it('у варианта с пустым current_price — цена по роли, а не NaN', () => {
    const variant = { current_price: '', promo_price: null };
    expect(getProductDisplayPrice(product, 'wholesale_level1', variant)).toBe(700);
  });

  describe('VIP и «Спец цена»: цену отдаёт API итогом', () => {
    const roleProduct = {
      price: { retail: 1200, currency: 'RUB' },
      current_price: '900.00',
      regular_price: '900.00',
      promo_price: null,
    };

    it.each(['vip', 'special_price'] as const)('без варианта — current_price для %s', role => {
      expect(getProductDisplayPrice(roleProduct, role, null)).toBe(900);
    });

    it.each(['vip', 'special_price'] as const)('current_price с акцией для %s', role => {
      const promo = { ...roleProduct, current_price: '700.00', promo_price: '700.00' };
      expect(getProductDisplayPrice(promo, role)).toBe(700);
    });

    it.each(['vip', 'special_price'] as const)(
      'без current_price — regular_price, затем розница для %s',
      role => {
        const onlyRegular = { ...roleProduct, current_price: '' };
        expect(getProductDisplayPrice(onlyRegular, role)).toBe(900);

        const nothing = { ...roleProduct, current_price: '', regular_price: '' };
        expect(getProductDisplayPrice(nothing, role)).toBe(1200);
      }
    );

    it.each(['vip', 'special_price'] as const)('выбранный вариант задаёт цену для %s', role => {
      const variant = { current_price: '850.00', promo_price: null };
      expect(getProductDisplayPrice(roleProduct, role, variant)).toBe(850);
    });

    it('розница и другие роли по-прежнему считаются по полям товара', () => {
      expect(getProductDisplayPrice(roleProduct, 'guest')).toBe(1200);
      expect(getPriceForRole(roleProduct.price, 'vip')).toBe(1200);
      expect(getPriceForRole(roleProduct.price, 'special_price')).toBe(1200);
    });
  });

  it('без price у товара — 0', () => {
    const noPrice = { ...product, price: undefined as unknown as typeof product.price };
    expect(getProductDisplayPrice(noPrice, 'guest', null)).toBe(0);
  });
});
