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

/** Каноническая формулировка номера оператора (FR-41-17c, AC2). */
const REGISTRY_LINE =
  'Регистрационный номер в реестре операторов, осуществляющих обработку персональных данных: 26-22-003980';

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

  // Story 41.12 — AC2 (FR-41-17c): /coming-soon — живой подвал прода.
  it('содержит каноническую строку номера оператора обычным текстом (AC2)', () => {
    render(<ComingSoon />);

    const line = screen.getByText(REGISTRY_LINE);

    expect(line).toBeInTheDocument();
    expect(line.closest('a')).toBeNull();
    expect(screen.queryByText(/26-22-004188/)).not.toBeInTheDocument();
  });

  // Story 41.21 — AC4/AC6: карточка описывает только действующее предложение
  // (розница отключена), без превосходных степеней.
  it('описывает оптовое предложение без розницы и превосходных степеней (41.21)', () => {
    render(<ComingSoon />);

    expect(screen.getByText(/Оптовые продажи/)).toBeInTheDocument();
    expect(screen.getByText('Оптовые заказы')).toBeInTheDocument();
    expect(screen.getByText('Для организаций')).toBeInTheDocument();
    expect(screen.getByText('Скидки от объема закупок')).toBeInTheDocument();

    for (const text of [/B2C/, /B2B/, /Розничные/, /Лучшие цены/, /Платформа/]) {
      expect(screen.queryByText(text)).not.toBeInTheDocument();
    }
  });

  // Story 41.21 — AC4: подпись каждой карточки закреплена дословно и именно под
  // своим заголовком — перестановка или правка подписи должна ронять тест.
  it.each([
    ['Оптовые заказы', 'Каталог и условия для оптовых покупателей'],
    ['Для организаций', 'Магазины, спортивные клубы и федерации'],
    ['Скидки от объема закупок', 'Размер скидки зависит от объёма заказа'],
  ])('карточка «%s» подписана «%s» (41.21)', (title, caption) => {
    render(<ComingSoon />);

    const heading = screen.getByRole('heading', { level: 3, name: title });

    expect(heading.nextElementSibling?.tagName).toBe('P');
    expect(heading.nextElementSibling?.textContent?.trim()).toBe(caption);
  });

  it('содержит ровно три карточки преимуществ (41.21)', () => {
    render(<ComingSoon />);

    expect(screen.getAllByRole('heading', { level: 3 })).toHaveLength(3);
  });
});
