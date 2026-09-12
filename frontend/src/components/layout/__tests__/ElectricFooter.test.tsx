/**
 * Тесты подвала темы electric.
 * Story 41.1 — AC3 (FR-41-02): кнопка «Настройки cookie» обязана быть во всех
 * трёх подвалах. Прецедент 41.3: правка в одной теме и пропуск другой вернулись
 * находкой код-ревью.
 */

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';
import ElectricFooter from '../ElectricFooter';
import { __resetCookieConsentStoreForTests } from '@/hooks/useCookieConsent';

describe('ElectricFooter', () => {
  beforeEach(() => {
    __resetCookieConsentStoreForTests();
    window.localStorage.removeItem('cookie_consent');
    window.localStorage.removeItem('cookie_consent_accepted');
  });

  it('содержит кнопку «Настройки cookie» в нижней панели', () => {
    render(<ElectricFooter />);

    const button = screen.getByRole('button', { name: 'Настройки cookie' });

    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute('type', 'button');
  });

  it('кнопка использует токен с достаточным контрастом (AC6)', () => {
    // Регрессия код-ревью: --color-text-muted (#666666) на --bg-card (#1a1a1a)
    // даёт 3.03:1 при требуемых для кегля 10-12 px 4.5:1.
    // --color-text-secondary (#a0a0a0) — 6.66:1.
    render(<ElectricFooter />);

    const button = screen.getByRole('button', { name: 'Настройки cookie' });

    expect(button.className).toContain('text-[var(--color-text-secondary)]');
    expect(button.className).not.toContain('text-[var(--color-text-muted)]');
  });

  it('сохраняет ссылки нижней панели', () => {
    render(<ElectricFooter />);

    expect(screen.getByRole('link', { name: 'Политика конфиденциальности' })).toHaveAttribute(
      'href',
      '/privacy-policy'
    );
    expect(screen.getByRole('link', { name: 'Пользовательское соглашение' })).toHaveAttribute(
      'href',
      '/oferta'
    );
  });

  it('ряд ссылок нижней панели переносится по строкам', () => {
    // Регрессия код-ревью: кнопка стала третьим элементом ряда. Без переноса
    // на 320 px flex ужимает каждую ссылку до узкого столбца и рвёт подпись
    // посреди слова (замер в браузере: 30 px высоты против 15 px). JSDOM не
    // считает раскладку, поэтому проверяется контракт классов контейнера.
    render(<ElectricFooter />);

    const row = screen.getByRole('button', { name: 'Настройки cookie' })
      .parentElement as HTMLElement;

    expect(row.className).toContain('flex-wrap');
    expect(row.className).toContain('justify-center');
    expect(row.className).not.toMatch(/(?<!-)gap-6/);
  });

  it('нижняя панель с кнопкой не имеет нарушений доступности по axe', async () => {
    render(<ElectricFooter />);

    // Проверяется нижняя панель — та часть подвала, куда добавлена кнопка (AC6).
    // Подвал целиком axe не проходит из-за ПРЕДСУЩЕСТВУЮЩЕГО дефекта темы
    // electric: соцсети-иконки — <Link href="#"> без доступного имени
    // (нарушение link-name). В теме blue у них есть aria-label. Дефект внесён
    // не этой стори, своей стори не имеет и здесь намеренно не чинится (AC8).
    const bottomBar = screen.getByRole('button', { name: 'Настройки cookie' })
      .parentElement as HTMLElement;

    const results = await axe(bottomBar);
    expect(results.violations).toHaveLength(0);
  });
});
