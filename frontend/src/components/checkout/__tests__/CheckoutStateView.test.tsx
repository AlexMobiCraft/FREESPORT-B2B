import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi } from 'vitest';
import * as axeMatchers from 'vitest-axe';
import { axe } from 'vitest-axe';
import { CheckoutStateView } from '../CheckoutStateView';
import type { CheckoutView } from '@/utils/checkout/checkoutView';

// @ts-expect-error vitest-axe types mismatch with vitest
expect.extend(axeMatchers);

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

const ALL_VIEWS: Exclude<CheckoutView, 'form'>[] = [
  'loading',
  'anonymous',
  'error',
  'redirecting',
  'empty',
];

/** Видимый заголовок h2 каждого блока состояния (AC8: h1 страницы → h2 блока). */
const HEADING_BY_VIEW: Record<Exclude<CheckoutView, 'form'>, string> = {
  loading: 'Загрузка…',
  anonymous: 'Войдите, чтобы оформить заказ',
  error: 'Не удалось загрузить корзину',
  redirecting: 'Заказ оформлен. Переходим к подтверждению…',
  empty: 'Корзина пуста',
};

describe('CheckoutStateView', () => {
  it('loading: показывает индикатор с видимым текстом "Загрузка…"', () => {
    render(<CheckoutStateView view="loading" />);
    expect(screen.getByTestId('checkout-loading')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText('Загрузка…')).toBeInTheDocument();
  });

  it('redirecting: показывает индикатор с текстом про переход к подтверждению', () => {
    render(<CheckoutStateView view="redirecting" />);
    expect(screen.getByTestId('checkout-redirecting')).toBeInTheDocument();
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(
      screen.getByText('Заказ оформлен. Переходим к подтверждению…')
    ).toBeInTheDocument();
  });

  it.each(ALL_VIEWS)('%s: ровно один h2 с видимым текстом блока (AC8)', view => {
    render(<CheckoutStateView view={view} onRetry={() => {}} />);
    const headings = screen.getAllByRole('heading');
    expect(headings).toHaveLength(1);
    expect(headings[0].tagName).toBe('H2');
    expect(headings[0]).toHaveTextContent(HEADING_BY_VIEW[view]);
  });

  it('error: обработчик повтора обязателен на уровне типов', () => {
    // @ts-expect-error — кнопка «Повторить» без onRetry ничего бы не делала
    const element = <CheckoutStateView view="error" />;
    expect(element).toBeTruthy();
  });

  it('anonymous: показывает приглашение войти со ссылкой next=%2Fcheckout', () => {
    render(<CheckoutStateView view="anonymous" />);
    expect(screen.getByTestId('checkout-login-required')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Войдите, чтобы оформить заказ' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Оформление заказа доступно после входа в личный кабинет.')
    ).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Войти' });
    expect(link).toHaveAttribute('href', '/login?next=%2Fcheckout');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('empty: показывает пустое состояние со ссылкой в каталог', () => {
    render(<CheckoutStateView view="empty" />);
    expect(screen.getByTestId('checkout-empty-cart')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Корзина пуста' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Добавьте товары из каталога, чтобы оформить заказ.')
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'В каталог' })).toHaveAttribute('href', '/catalog');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('error: показывает role="alert" с кнопкой повтора и вызывает onRetry по клику', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(<CheckoutStateView view="error" onRetry={onRetry} />);
    expect(screen.getByTestId('checkout-cart-error')).toBeInTheDocument();
    expect(screen.getByRole('alert')).toBeInTheDocument();
    expect(
      screen.getByRole('heading', { level: 2, name: 'Не удалось загрузить корзину' })
    ).toBeInTheDocument();
    expect(
      screen.getByText('Проверьте подключение и попробуйте ещё раз.')
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Повторить' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it.each(ALL_VIEWS)('%s: рендерит ровно один returns-support-notice и без полей формы', view => {
    const { container } = render(<CheckoutStateView view={view} onRetry={() => {}} />);
    expect(screen.getAllByTestId('returns-support-notice')).toHaveLength(1);
    expect(container.querySelector('form')).toBeNull();
    expect(container.querySelector('input')).toBeNull();
    expect(container.querySelector('textarea')).toBeNull();
    expect(container.querySelector('select')).toBeNull();
  });

  it.each(ALL_VIEWS)('%s: не нарушает доступность (axe)', async view => {
    const { container } = render(<CheckoutStateView view={view} onRetry={() => {}} />);
    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
