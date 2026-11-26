import type { CheckoutFormInput } from '@/schemas/checkoutSchema';
import { useAuthStore } from '@/stores/authStore';

export interface CheckoutDraft {
  userId: number | null;
  values: CheckoutFormInput;
  selectedAddressId: number | null;
  saveAddress: boolean;
}

// Только память вкладки: черновик нужен для возврата из условий, а не для
// долговременного хранения персональных данных или восстановления после reload.
let draft: CheckoutDraft | null = null;

export function readCheckoutDraft(userId: number | null): CheckoutDraft | null {
  return draft?.userId === userId ? draft : null;
}

export function saveCheckoutDraft(value: CheckoutDraft): void {
  draft = { ...value, values: { ...value.values } };
}

export function clearCheckoutDraft(): void {
  draft = null;
}

// Подписка живёт дольше формы: выход на странице условий тоже удаляет черновик.
useAuthStore.subscribe((state, previous) => {
  if (state.user?.id !== previous.user?.id || state.isAuthenticated !== previous.isAuthenticated) {
    clearCheckoutDraft();
  }
});
