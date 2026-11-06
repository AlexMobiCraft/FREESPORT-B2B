import { describe, expect, it } from 'vitest';
import {
  resolveCheckoutView,
  type CartLoadStatus,
  type CheckoutView,
  type CheckoutViewInput,
} from '../checkoutView';

function makeInput(overrides: Partial<CheckoutViewInput> = {}): CheckoutViewInput {
  return {
    isAuthInitialized: true,
    isAuthenticated: true,
    cartLoad: 'ready',
    hasItems: true,
    isRedirecting: false,
    ...overrides,
  };
}

const BOOLS = [false, true] as const;
const CART_LOADS: CartLoadStatus[] = ['pending', 'ready', 'error'];

/** Все 48 комбинаций входа — для проверки, что старшее условие перекрывает любые младшие. */
const ALL_INPUTS: CheckoutViewInput[] = BOOLS.flatMap(isAuthInitialized =>
  BOOLS.flatMap(isAuthenticated =>
    CART_LOADS.flatMap(cartLoad =>
      BOOLS.flatMap(hasItems =>
        BOOLS.map(isRedirecting => ({
          isAuthInitialized,
          isAuthenticated,
          cartLoad,
          hasItems,
          isRedirecting,
        }))
      )
    )
  )
);

/**
 * Слои приоритета из Dev Notes «Приоритет состояний»: каждый слой забирает все входы,
 * которые не забрали слои выше, и обязан дать одно и то же состояние при любых
 * значениях младших полей. Перестановка проверок в resolveCheckoutView ломает хотя бы
 * один слой.
 */
const PRIORITY_LAYERS: Array<{
  name: string;
  matches: (input: CheckoutViewInput) => boolean;
  expected: (input: CheckoutViewInput) => CheckoutView;
}> = [
  {
    name: 'сессия не восстановлена → loading',
    matches: i => !i.isAuthInitialized,
    expected: () => 'loading',
  },
  {
    name: 'аноним → anonymous',
    matches: i => !i.isAuthenticated,
    expected: () => 'anonymous',
  },
  {
    name: 'корзина загружается → loading',
    matches: i => i.cartLoad === 'pending',
    expected: () => 'loading',
  },
  {
    name: 'ошибка корзины → error',
    matches: i => i.cartLoad === 'error',
    expected: () => 'error',
  },
  {
    name: 'заказ создан → redirecting',
    matches: i => i.isRedirecting,
    expected: () => 'redirecting',
  },
  {
    name: 'готовая корзина → empty / form по наличию товаров',
    matches: () => true,
    expected: i => (i.hasItems ? 'form' : 'empty'),
  },
];

describe('resolveCheckoutView — матрица приоритетов', () => {
  it('перебирает все 48 комбинаций входа', () => {
    expect(ALL_INPUTS).toHaveLength(48);
  });

  // Раскладываем входы по слоям: вход достаётся первому слою, чьё условие выполнено.
  const remaining = [...ALL_INPUTS];
  const layerCases = PRIORITY_LAYERS.map(layer => {
    const taken = remaining.filter(layer.matches);
    for (const input of taken) remaining.splice(remaining.indexOf(input), 1);
    return { ...layer, inputs: taken };
  });

  it('каждая комбинация попадает ровно в один слой', () => {
    expect(remaining).toHaveLength(0);
    expect(layerCases.map(layer => layer.inputs.length)).toEqual([24, 12, 4, 4, 2, 2]);
  });

  it.each(layerCases)('$name — при любых значениях младших полей', layer => {
    for (const input of layer.inputs) {
      expect(resolveCheckoutView(input), JSON.stringify(input)).toBe(layer.expected(input));
    }
  });
});

describe('resolveCheckoutView', () => {
  it('возвращает loading, пока сессия не восстановлена, при любых остальных значениях', () => {
    expect(
      resolveCheckoutView(
        makeInput({
          isAuthInitialized: false,
          isAuthenticated: true,
          cartLoad: 'ready',
          hasItems: true,
          isRedirecting: true,
        })
      )
    ).toBe('loading');
    expect(
      resolveCheckoutView(
        makeInput({
          isAuthInitialized: false,
          isAuthenticated: false,
          cartLoad: 'error',
          hasItems: false,
        })
      )
    ).toBe('loading');
  });

  it('возвращает anonymous для не вошедшего пользователя, даже если в корзине есть товары', () => {
    expect(
      resolveCheckoutView(
        makeInput({ isAuthenticated: false, cartLoad: 'ready', hasItems: true })
      )
    ).toBe('anonymous');
  });

  it('возвращает loading, пока корзина авторизованного пользователя загружается', () => {
    expect(resolveCheckoutView(makeInput({ cartLoad: 'pending' }))).toBe('loading');
  });

  it('возвращает error при ошибке загрузки корзины, даже если есть товары', () => {
    expect(
      resolveCheckoutView(makeInput({ cartLoad: 'error', hasItems: true }))
    ).toBe('error');
  });

  it('возвращает redirecting при пустой корзине после оформления заказа', () => {
    expect(
      resolveCheckoutView(
        makeInput({ cartLoad: 'ready', hasItems: false, isRedirecting: true })
      )
    ).toBe('redirecting');
  });

  it('возвращает empty для готовой пустой корзины без редиректа', () => {
    expect(
      resolveCheckoutView(
        makeInput({ cartLoad: 'ready', hasItems: false, isRedirecting: false })
      )
    ).toBe('empty');
  });

  it('возвращает form для готовой корзины с товарами', () => {
    expect(
      resolveCheckoutView(
        makeInput({ cartLoad: 'ready', hasItems: true, isRedirecting: false })
      )
    ).toBe('form');
  });
});
