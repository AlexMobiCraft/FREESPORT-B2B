import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import CookieConsentBanner from '../CookieConsentBanner';

const STORAGE_KEY = 'cookie_consent_accepted';
const STORAGE_VALUE = '1';

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('показывает текст, ссылку и кнопку при первом визите', async () => {
    render(<CookieConsentBanner />);

    const banner = await screen.findByRole('region', { name: 'Уведомление об использовании cookie' });

    expect(banner).toBeInTheDocument();
    expect(screen.getByText(/Мы используем файлы cookie/)).toBeInTheDocument();
    expect(screen.getByText(/Продолжая пользоваться сайтом/)).toBeInTheDocument();
    expect(banner).toHaveTextContent(
      /пользовательских данных согласно Политике обработки персональных данных\./
    );
    expect(
      screen.getByRole('link', { name: 'Политике обработки персональных данных' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /принять/i })).toBeInTheDocument();
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

  it('скрывает баннер после нажатия Принять и сохраняет localStorage', async () => {
    const user = userEvent.setup();
    render(<CookieConsentBanner />);

    await user.click(await screen.findByRole('button', { name: /принять/i }));

    await waitFor(() => {
      expect(
        screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
      ).not.toBeInTheDocument();
    });
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(STORAGE_VALUE);
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

  it('имеет доступный region и доступную кнопку', async () => {
    render(<CookieConsentBanner />);

    expect(
      await screen.findByRole('region', { name: 'Уведомление об использовании cookie' })
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /принять/i })).toBeEnabled();
  });
});
