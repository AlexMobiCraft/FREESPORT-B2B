/**
 * Регрессионные тесты страницы /coming-soon.
 * Story 41.3 — AC5 (FR-41-04): формы подписки на странице быть не должно.
 *
 * Форма собирала email без правового основания, без согласия и без ссылки
 * на политику, а адрес никуда не сохранялся. Она удалена; этот файл
 * существует, чтобы её возврат падал в CI, а не проходил незамеченным.
 */

import { beforeEach, describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import ComingSoon from '../ComingSoonClient';
import { __resetCookieConsentStoreForTests } from '@/hooks/useCookieConsent';

// Мок motion/react: анимации в тестах не нужны, важна только разметка
vi.mock('motion/react', () => ({
  motion: {
    div: ({ children, ...props }: { children?: React.ReactNode; [key: string]: unknown }) => (
      <div {...filterMotionProps(props)}>{children}</div>
    ),
  },
}));

// Отбрасывает специфичные для motion пропсы, невалидные как HTML-атрибуты
function filterMotionProps(props: Record<string, unknown>) {
  const htmlProps: Record<string, unknown> = {};
  const motionKeys = ['initial', 'animate', 'exit', 'transition', 'variants', 'whileHover'];
  for (const [key, value] of Object.entries(props)) {
    if (!motionKeys.includes(key)) {
      htmlProps[key] = value;
    }
  }
  return htmlProps;
}

describe('ComingSoonClient — AC5: формы подписки нет', () => {
  // Подвал страницы содержит CookieSettingsButton с модульным стором.
  beforeEach(() => {
    __resetCookieConsentStoreForTests();
    window.localStorage.removeItem('cookie_consent');
    window.localStorage.removeItem('cookie_consent_accepted');
  });

  it('не содержит поля ввода email', () => {
    const { container } = render(<ComingSoon />);

    // AC5: поля email быть не должно — это маркер формы подписки.
    // Другие поля ввода (если появятся) не должны ронять этот тест.
    expect(container.querySelectorAll('input[type="email"]')).toHaveLength(0);
    expect(screen.queryByRole('textbox', { name: /email|электронная почта/i })).not.toBeInTheDocument();
  });

  it('не содержит формы подписки и кнопки «Подписаться»', () => {
    const { container } = render(<ComingSoon />);

    // Кнопка «Подписаться» — однозначный маркер формы подписки.
    expect(screen.queryByRole('button', { name: /подписаться/i })).not.toBeInTheDocument();

    // Форма подписки определяется по наличию в ней email-поля или кнопки
    // «Подписаться»; независимая форма (например, контакты) не должна
    // ронять тест — проверяются только признаки подписки.
    const forms = container.querySelectorAll('form');
    forms.forEach(form => {
      const hasEmailInput = form.querySelector('input[type="email"]') !== null;
      const hasSubscribeButton =
        Array.from(form.querySelectorAll('button')).some(btn =>
          /подписаться/i.test(btn.textContent ?? '')
        );
      expect(hasEmailInput || hasSubscribeButton).toBe(false);
    });
  });

  it('не обещает уведомление о запуске', () => {
    render(<ComingSoon />);

    expect(screen.queryByText(/узнайте первым о нашем запуске/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/уведомим вас о запуске/i)).not.toBeInTheDocument();
  });

  it('сохраняет канал связи в подвале', () => {
    render(<ComingSoon />);

    expect(screen.getByText(/info@optisport\.ru/)).toBeInTheDocument();
  });

  it('оставляет содержательную часть страницы нетронутой', () => {
    render(<ComingSoon />);

    expect(screen.getByRole('heading', { name: /мы скоро вернемся/i })).toBeInTheDocument();
    expect(screen.getByText(/разработка идет по плану/i)).toBeInTheDocument();
  });
  // Story 41.1 — AC3 (FR-41-02): /coming-soon — боевая тема прода, а Footer
  // здесь не используется. Без своей кнопки отказавшийся посетитель прода
  // не смог бы передумать.
  it('содержит кнопку «Настройки cookie» в подвале страницы', () => {
    render(<ComingSoon />);

    const button = screen.getByRole('button', { name: 'Настройки cookie' });

    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('type', 'button');
  });
});
