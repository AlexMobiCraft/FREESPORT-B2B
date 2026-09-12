/**
 * Тесты кнопки «Настройки cookie» и её связки с баннером.
 * Story 41.1 — AC3, AC4, AC6, AC7.
 */

import { render, screen, waitFor } from '@testing-library/react';
import { renderToStaticMarkup } from 'react-dom/server';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { axe } from 'vitest-axe';
import CookieSettingsButton from '../CookieSettingsButton';
import CookieConsentBanner from '../CookieConsentBanner';
import { __resetCookieConsentStoreForTests } from '@/hooks/useCookieConsent';

const CONSENT_KEY = 'cookie_consent';
const LEGACY_KEY = 'cookie_consent_accepted';

describe('CookieSettingsButton', () => {
  beforeEach(() => {
    __resetCookieConsentStoreForTests();
    window.localStorage.removeItem(CONSENT_KEY);
    window.localStorage.removeItem(LEGACY_KEY);
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it('рендерит семантическую кнопку с доступным именем «Настройки cookie»', () => {
    render(<CookieSettingsButton />);

    const button = screen.getByRole('button', { name: 'Настройки cookie' });

    expect(button).toBeInTheDocument();
    expect(button.tagName).toBe('BUTTON');
    expect(button).toHaveAttribute('type', 'button');
  });

  it('применяет переданный className, чтобы каждый подвал задал свою палитру', () => {
    render(<CookieSettingsButton className="text-white/80 hover:text-white" />);

    const button = screen.getByRole('button', { name: 'Настройки cookie' });

    expect(button).toHaveClass('text-white/80');
    expect(button).toHaveClass('hover:text-white');
  });

  it.each(['accepted', 'declined', null])(
    'рендерится при сохранённом выборе %s',
    async storedValue => {
      // Стор сбрасывается только между отрисовками, когда предыдущий
      // потребитель уже размонтирован: сброс при живой подписке снял бы её
      // слушатель и сделал результат теста зависящим от порядка.
      if (storedValue === null) {
        window.localStorage.removeItem(CONSENT_KEY);
      } else {
        window.localStorage.setItem(CONSENT_KEY, storedValue);
      }
      __resetCookieConsentStoreForTests();

      const { unmount } = render(<CookieSettingsButton />);

      await waitFor(() => {
        expect(screen.getByRole('button', { name: 'Настройки cookie' })).toBeInTheDocument();
      });

      unmount();
    }
  );

  it('серверная разметка совпадает с клиентской (SSR-разметка стабильна)', () => {
    window.localStorage.setItem(CONSENT_KEY, 'accepted');

    // На сервере хранилища нет: кнопка обязана присутствовать в SSR-выводе,
    // иначе гидрация даст расхождение разметки.
    const serverHtml = renderToStaticMarkup(<CookieSettingsButton className="footer-link" />);
    expect(serverHtml).toContain('Настройки cookie');
    expect(serverHtml).toContain('type="button"');

    const { container } = render(<CookieSettingsButton className="footer-link" />);

    expect(container.innerHTML).toBe(serverHtml);
  });

  it('не имеет нарушений доступности по axe', async () => {
    const { container } = render(
      <footer>
        <p>© 2026 OPTISPORT</p>
        <CookieSettingsButton className="text-xs text-neutral-500" />
      </footer>
    );

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  describe('связка с баннером через общий стор (AC4)', () => {
    it('открывает баннер без перезагрузки, не стирая сохранённый выбор', async () => {
      const user = userEvent.setup();
      window.localStorage.setItem(CONSENT_KEY, 'declined');

      render(
        <>
          <CookieConsentBanner />
          <footer>
            <CookieSettingsButton />
          </footer>
        </>
      );

      // Выбор сделан — баннера нет.
      await waitFor(() => {
        expect(
          screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
        ).not.toBeInTheDocument();
      });

      await user.click(screen.getByRole('button', { name: 'Настройки cookie' }));

      expect(
        await screen.findByRole('region', { name: 'Уведомление об использовании cookie' })
      ).toBeInTheDocument();
      // Сохранённый выбор кнопка не трогает.
      expect(window.localStorage.getItem(CONSENT_KEY)).toBe('declined');
    });

    it('переводит фокус на баннер после открытия из подвала (AC6)', async () => {
      const user = userEvent.setup();
      window.localStorage.setItem(CONSENT_KEY, 'accepted');

      render(
        <>
          <CookieConsentBanner />
          <footer>
            <CookieSettingsButton />
          </footer>
        </>
      );

      await user.click(screen.getByRole('button', { name: 'Настройки cookie' }));

      const banner = await screen.findByRole('region', {
        name: 'Уведомление об использовании cookie',
      });

      await waitFor(() => {
        expect(document.activeElement).toBe(banner);
      });
    });

    it('возвращает фокус на кнопку подвала после закрытия баннера (AC6)', async () => {
      // Иначе после «Принять»/«Отклонить» фокус остаётся на body и
      // клавиатурный пользователь теряет позицию в подвале.
      const user = userEvent.setup();
      window.localStorage.setItem(CONSENT_KEY, 'accepted');

      render(
        <>
          <CookieConsentBanner />
          <footer>
            <CookieSettingsButton />
          </footer>
        </>
      );

      const settingsButton = screen.getByRole('button', { name: 'Настройки cookie' });
      await user.click(settingsButton);
      await user.click(await screen.findByRole('button', { name: 'Отклонить' }));

      await waitFor(() => {
        expect(document.activeElement).toBe(settingsButton);
      });
    });

    it('не крадёт фокус, когда баннер закрылся без принудительного открытия', async () => {
      const user = userEvent.setup();

      render(
        <>
          <CookieConsentBanner />
          <footer>
            <CookieSettingsButton />
          </footer>
        </>
      );

      const settingsButton = screen.getByRole('button', { name: 'Настройки cookie' });
      await user.click(await screen.findByRole('button', { name: 'Принять' }));

      await waitFor(() => {
        expect(
          screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
        ).not.toBeInTheDocument();
      });
      expect(document.activeElement).not.toBe(settingsButton);
    });

    it('повторный выбор в открытом баннере перезаписывает сохранённый', async () => {
      const user = userEvent.setup();
      window.localStorage.setItem(CONSENT_KEY, 'declined');

      render(
        <>
          <CookieConsentBanner />
          <footer>
            <CookieSettingsButton />
          </footer>
        </>
      );

      await user.click(screen.getByRole('button', { name: 'Настройки cookie' }));
      await user.click(await screen.findByRole('button', { name: 'Принять' }));

      await waitFor(() => {
        expect(
          screen.queryByRole('region', { name: 'Уведомление об использовании cookie' })
        ).not.toBeInTheDocument();
      });
      expect(window.localStorage.getItem(CONSENT_KEY)).toBe('accepted');
    });
  });
});
