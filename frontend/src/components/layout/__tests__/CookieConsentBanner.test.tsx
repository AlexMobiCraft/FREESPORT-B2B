/**
 * Тесты cookie-баннера.
 * Story 41.1 — AC1, AC2, AC6, AC7.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import CookieConsentBanner from '../CookieConsentBanner';
import { __resetCookieConsentStoreForTests } from '@/hooks/useCookieConsent';

const STORAGE_KEY = 'cookie_consent_accepted';
const STORAGE_VALUE = '1';
const CONSENT_KEY = 'cookie_consent';

/** Дословный текст баннера из AC1. */
const BANNER_TEXT =
  'Мы используем файлы cookie. Технически необходимые нужны для работы сайта, ' +
  'остальные — только с вашего согласия. Подробнее — в «Политике обработки персональных данных».';

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    // Стор хука — модульный синглтон: без сброса тесты зависят от порядка.
    __resetCookieConsentStoreForTests();
    window.localStorage.removeItem(CONSENT_KEY);
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('показывает текст, ссылку и кнопку при первом визите', async () => {
    render(<CookieConsentBanner />);

    const banner = await screen.findByRole('region', { name: 'Уведомление об использовании cookie' });

    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/Мы используем файлы cookie/)).toBeInTheDocument();
    expect(
      screen.getByRole('link', { name: 'Политике обработки персональных данных' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /принять/i })).toBeInTheDocument();
  });

  it('содержит дословный текст AC1 и не содержит модель подразумеваемого согласия', async () => {
    render(<CookieConsentBanner />);

    const banner = await screen.findByRole('region', { name: 'Уведомление об использовании cookie' });

    expect(banner.textContent?.replace(/\s+/g, ' ').trim()).toContain(BANNER_TEXT);
    expect(screen.queryByText(/Продолжая пользоваться сайтом/)).not.toBeInTheDocument();
  });

  it('не показывает баннер, если согласие уже принято', async () => {
    window.localStorage.setItem(STORAGE_KEY, STORAGE_VALUE);

    render(<CookieConsentBanner />);

    await waitFor(() => {
      expect(
        screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
      ).not.toBeInTheDocument();
    });
  });

  it('показывает две равнозначные кнопки одинакового размера', async () => {
    render(<CookieConsentBanner />);

    const acceptButton = await screen.findByRole('button', { name: 'Принять' });
    const declineButton = screen.getByRole('button', { name: 'Отклонить' });

    expect(acceptButton).toBeInTheDocument();
    expect(declineButton).toBeInTheDocument();
    // size="medium" у обеих — общий класс высоты из Button.
    expect(acceptButton).toHaveClass('h-11');
    expect(declineButton).toHaveClass('h-11');
    // «Отклонить» — полноценная кнопка, а не ссылка и не приглушённый вариант (NFR-41-07).
    expect(declineButton.tagName).toBe('BUTTON');
    expect(declineButton).toHaveClass('border-primary');
  });

  it('скрывает баннер после нажатия Принять и сохраняет localStorage', async () => {
    const user = userEvent.setup();
    render(<CookieConsentBanner />);

    await user.click(await screen.findByRole('button', { name: 'Принять' }));

    await waitFor(() => {
      expect(
        screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
      ).not.toBeInTheDocument();
    });
    expect(window.localStorage.getItem(CONSENT_KEY)).toBe('accepted');
  });

  it('скрывает баннер после нажатия Отклонить и сохраняет отказ', async () => {
    const user = userEvent.setup();
    render(<CookieConsentBanner />);

    await user.click(await screen.findByRole('button', { name: 'Отклонить' }));

    await waitFor(() => {
      expect(
        screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
      ).not.toBeInTheDocument();
    });
    expect(window.localStorage.getItem(CONSENT_KEY)).toBe('declined');
  });

  it('ведёт на страницу политики в новой вкладке', async () => {
    render(<CookieConsentBanner />);

    const link = await screen.findByRole('link', {
      name: 'Политике обработки персональных данных',
    });

    expect(link).toHaveAttribute('href', '/privacy-policy');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('имеет доступный region и обе доступные кнопки', async () => {
    render(<CookieConsentBanner />);

    expect(
      await screen.findByRole('region', { name: 'Уведомление об использовании cookie' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Принять' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Отклонить' })).toBeEnabled();
  });

  it('не имеет нарушений доступности по axe', async () => {
    const { container } = render(<CookieConsentBanner />);

    await screen.findByRole('region', { name: 'Уведомление об использовании cookie' });

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });
});
