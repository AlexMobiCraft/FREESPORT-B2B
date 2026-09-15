/**
 * Регрессионные тесты одноразового черновика формы оформления заказа (Story 41.4).
 *
 * Черновик держит незавершённый ввод, пока пользователь читает условия возврата,
 * и обязан исчезать при смене владельца сессии: персональные данные одного
 * пользователя не должны попасть в форму другого.
 */

import { describe, it, expect, beforeEach } from 'vitest';
import {
  clearCheckoutDraft,
  readCheckoutDraft,
  saveCheckoutDraft,
  type CheckoutDraft,
} from '../checkoutDraft';
import { useAuthStore } from '@/stores/authStore';
import type { CheckoutFormInput } from '@/schemas/checkoutSchema';
import type { User } from '@/types/api';

function makeValues(overrides: Partial<CheckoutFormInput> = {}): CheckoutFormInput {
  return {
    email: 'pochta@mail.ru',
    phone: '+79001234567',
    firstName: 'Иван',
    lastName: 'Петров',
    city: 'Москва',
    street: 'Ленина',
    house: '10',
    buildingSection: '',
    apartment: '5',
    postalCode: '123456',
    deliveryMethod: 'pickup',
    paymentMethod: 'cash',
    comment: 'Позвонить заранее',
    ...overrides,
  } as CheckoutFormInput;
}

function makeDraft(overrides: Partial<CheckoutDraft> = {}): CheckoutDraft {
  return {
    userId: 1,
    values: makeValues(),
    selectedAddressId: 7,
    saveAddress: true,
    ...overrides,
  };
}

function makeUser(id: number): User {
  return {
    id,
    email: `user${id}@mail.ru`,
    first_name: 'Иван',
    last_name: 'Петров',
    phone: '+79001234567',
    role: 'retail',
  } as User;
}

describe('checkoutDraft', () => {
  beforeEach(() => {
    clearCheckoutDraft();
    useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });
    clearCheckoutDraft();
  });

  it('возвращает сохранённый черновик тому же пользователю целиком', () => {
    const draft = makeDraft();
    saveCheckoutDraft(draft);

    const restored = readCheckoutDraft(1);

    expect(restored).not.toBeNull();
    expect(restored?.values).toEqual(draft.values);
    expect(restored?.selectedAddressId).toBe(7);
    expect(restored?.saveAddress).toBe(true);
  });

  it('работает для анонимного посетителя (userId === null)', () => {
    saveCheckoutDraft(makeDraft({ userId: null, selectedAddressId: null, saveAddress: false }));

    expect(readCheckoutDraft(null)?.values.email).toBe('pochta@mail.ru');
  });

  it('не отдаёт черновик другому пользователю', () => {
    saveCheckoutDraft(makeDraft({ userId: 1 }));

    expect(readCheckoutDraft(2)).toBeNull();
    expect(readCheckoutDraft(null)).toBeNull();
  });

  it('не отдаёт черновик анонима авторизованному пользователю', () => {
    saveCheckoutDraft(makeDraft({ userId: null }));

    expect(readCheckoutDraft(1)).toBeNull();
  });

  it('копирует значения при сохранении: правка исходного объекта не меняет черновик', () => {
    const values = makeValues();
    saveCheckoutDraft(makeDraft({ values }));

    values.city = 'Санкт-Петербург';

    expect(readCheckoutDraft(1)?.values.city).toBe('Москва');
  });

  it('clearCheckoutDraft стирает черновик', () => {
    saveCheckoutDraft(makeDraft());

    clearCheckoutDraft();

    expect(readCheckoutDraft(1)).toBeNull();
  });

  it('перезапись черновика заменяет предыдущий, а не дополняет его', () => {
    saveCheckoutDraft(makeDraft({ values: makeValues({ city: 'Москва' }) }));
    saveCheckoutDraft(makeDraft({ values: makeValues({ city: 'Казань' }), saveAddress: false }));

    expect(readCheckoutDraft(1)?.values.city).toBe('Казань');
    expect(readCheckoutDraft(1)?.saveAddress).toBe(false);
  });

  it('вход другого пользователя стирает черновик предыдущего', () => {
    useAuthStore.setState({ user: makeUser(1), isAuthenticated: true });
    saveCheckoutDraft(makeDraft({ userId: 1 }));

    useAuthStore.setState({ user: makeUser(2), isAuthenticated: true });

    expect(readCheckoutDraft(1)).toBeNull();
    expect(readCheckoutDraft(2)).toBeNull();
  });

  it('выход из аккаунта стирает черновик', () => {
    useAuthStore.setState({ user: makeUser(1), isAuthenticated: true });
    saveCheckoutDraft(makeDraft({ userId: 1 }));

    useAuthStore.setState({ user: null, isAuthenticated: false, accessToken: null });

    expect(readCheckoutDraft(1)).toBeNull();
  });

  it('изменение постороннего поля стора черновик не трогает', () => {
    useAuthStore.setState({ user: makeUser(1), isAuthenticated: true });
    saveCheckoutDraft(makeDraft({ userId: 1 }));

    useAuthStore.setState({ accessToken: 'new-access-token' });

    expect(readCheckoutDraft(1)).not.toBeNull();
  });
});
