/**
 * Тест-страж инварианта AC3 стори 41.20 (решение E21): публичные формы не
 * показывают технических образцов на латинице.
 *
 * Зачем один тест на все пять форм. Плейсхолдер `name@example.ru` внёс не автор
 * исходной формы, а стори 41.16 — заменяя прежний образец, она сама породила
 * срабатывание редакторского аудита (регресс E10). Инвариант «в публичной форме
 * нет подстроки example» живёт выше отдельной формы, поэтому и проверяется одним
 * списком: новая публичная форма добавляется сюда одной строкой.
 *
 * Почему у поля почты нет плейсхолдера вовсе, а не «русский образец». Видимая
 * подпись «Электронная почта» есть у каждого поля, тип поля — `email`, поэтому
 * образец адреса избыточен; плейсхолдер, дублирующий видимую подпись, — ещё и
 * антипаттерн доступности.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';

import { SubscribeForm } from '@/components/home/SubscribeForm';
import { ElectricSubscribeForm } from '@/components/home/ElectricSubscribeForm';
import { RegisterForm } from '@/components/auth/RegisterForm';
import { B2BRegisterForm } from '@/components/auth/B2BRegisterForm';
import { PasswordResetRequestForm } from '@/components/auth/PasswordResetRequestForm';

// Моки, без которых формы не отрисуются. Взяты из consent-texts-registry.test.tsx
// и дополнены `requestPasswordReset` — его зовёт форма восстановления пароля.
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

vi.mock('@/services/authService', () => ({
  default: {
    register: vi.fn(),
    registerB2B: vi.fn(),
    refreshToken: vi.fn(),
    requestPasswordReset: vi.fn(),
  },
}));

vi.mock('@/services/subscribeService', () => ({
  subscribeService: {
    subscribe: vi.fn(),
  },
}));

vi.mock('react-hot-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

const PUBLIC_FORMS: Array<[string, () => React.ReactElement]> = [
  ['SubscribeForm (/home)', () => <SubscribeForm />],
  ['ElectricSubscribeForm (/electric)', () => <ElectricSubscribeForm />],
  ['RegisterForm (/register)', () => <RegisterForm />],
  ['B2BRegisterForm (/b2b-register)', () => <B2BRegisterForm />],
  ['PasswordResetRequestForm (/password-reset)', () => <PasswordResetRequestForm />],
];

describe('Публичные формы не содержат технических образцов example', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    cleanup();
  });

  it.each(PUBLIC_FORMS)('%s: у поля почты нет плейсхолдера', (_name, renderForm) => {
    const { container } = render(renderForm());

    const emailInput = container.querySelector('input[type="email"]');
    expect(emailInput).not.toBeNull();
    expect(emailInput).not.toHaveAttribute('placeholder');
  });

  it.each(PUBLIC_FORMS)('%s: поле почты сохранило видимую подпись', (_name, renderForm) => {
    render(renderForm());

    // Подпись — единственный носитель смысла поля после удаления плейсхолдера,
    // поэтому проверяется и доступное имя, и видимость самой подписи: скрытый
    // `sr-only`-label дал бы зелёное доступное имя, но AC3 требует подпись,
    // которую видно глазами, — иначе поле визуально останется без пояснения.
    const emailInput = screen.getByLabelText(/электронная почта/i);
    expect(emailInput).toHaveAccessibleName(/электронная почта/i);

    const labelId = emailInput.getAttribute('aria-labelledby');
    const label = labelId
      ? document.getElementById(labelId)
      : document.querySelector(`label[for="${emailInput.id}"]`);
    expect(label).not.toBeNull();
    expect(label).toBeVisible();
    expect(label).toHaveTextContent(/электронная почта/i);
  });

  it.each(PUBLIC_FORMS)('%s: разметка не содержит подстроки example', (_name, renderForm) => {
    const { container } = render(renderForm());

    // Проверяется вся разметка, а не только плейсхолдер: так страж ловит и
    // видимый текст, и любой другой атрибут — в том числе будущий регресс.
    expect(container.innerHTML.toLowerCase()).not.toContain('example');
  });
});
