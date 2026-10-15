/** Состояние страницы оформления заказа (Story 41.10, FR-41-25). */
export type CheckoutView = 'loading' | 'anonymous' | 'error' | 'redirecting' | 'empty' | 'form';

export type CartLoadStatus = 'pending' | 'ready' | 'error';

export interface CheckoutViewInput {
  isAuthInitialized: boolean;
  isAuthenticated: boolean;
  cartLoad: CartLoadStatus;
  hasItems: boolean;
  isRedirecting: boolean;
}

export function resolveCheckoutView(input: CheckoutViewInput): CheckoutView {
  // Порядок проверок — часть требования, см. Dev Notes «Приоритет состояний».
  if (!input.isAuthInitialized) return 'loading';
  if (!input.isAuthenticated) return 'anonymous';
  if (input.cartLoad === 'pending') return 'loading';
  if (input.cartLoad === 'error') return 'error';
  if (input.isRedirecting) return 'redirecting';
  if (!input.hasItems) return 'empty';
  return 'form';
}
