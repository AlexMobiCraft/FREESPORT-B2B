/**
 * NewsletterSettings — блок «Рассылка» в личном кабинете.
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import NewsletterSettings from './NewsletterSettings';
import { newsletterSettingsService } from '@/services/newsletterSettingsService';

const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
};

vi.mock('@/components/ui/Toast/ToastProvider', () => ({
  useToast: () => mockToast,
}));

vi.mock('@/services/newsletterSettingsService', () => ({
  newsletterSettingsService: {
    getStatus: vi.fn(),
    unsubscribe: vi.fn(),
  },
}));

const getStatus = vi.mocked(newsletterSettingsService.getStatus);
const unsubscribe = vi.mocked(newsletterSettingsService.unsubscribe);

const SUBSCRIBED_TEXT =
  'Вы подписаны на информационные и рекламные рассылки OPTISPORT по электронной почте.';
const NOT_SUBSCRIBED_TEXT = 'Вы не подписаны на рассылку.';

describe('NewsletterSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state until status arrives', async () => {
    getStatus.mockReturnValue(new Promise(() => {}));

    render(<NewsletterSettings />);

    expect(screen.getByRole('heading', { name: 'Рассылка' })).toBeInTheDocument();
    expect(screen.getByText('Загрузка...')).toBeInTheDocument();
  });

  it('shows subscribed status with unsubscribe button', async () => {
    getStatus.mockResolvedValue({ subscribed: true });

    render(<NewsletterSettings />);

    expect(await screen.findByText(SUBSCRIBED_TEXT)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Отписаться' })).toBeEnabled();
  });

  it('shows not subscribed status without button', async () => {
    getStatus.mockResolvedValue({ subscribed: false });

    render(<NewsletterSettings />);

    expect(await screen.findByText(NOT_SUBSCRIBED_TEXT)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отписаться' })).not.toBeInTheDocument();
  });

  it('unsubscribes and switches to not subscribed status', async () => {
    const user = userEvent.setup();
    getStatus.mockResolvedValue({ subscribed: true });
    unsubscribe.mockResolvedValue({ subscribed: false });

    render(<NewsletterSettings />);
    await user.click(await screen.findByRole('button', { name: 'Отписаться' }));

    expect(await screen.findByText(NOT_SUBSCRIBED_TEXT)).toBeInTheDocument();
    expect(unsubscribe).toHaveBeenCalledTimes(1);
    expect(mockToast.error).not.toHaveBeenCalled();
  });

  it('keeps subscribed status and shows toast when unsubscribe fails', async () => {
    const user = userEvent.setup();
    getStatus.mockResolvedValue({ subscribed: true });
    unsubscribe.mockRejectedValue(new Error('network'));

    render(<NewsletterSettings />);
    await user.click(await screen.findByRole('button', { name: 'Отписаться' }));

    expect(mockToast.error).toHaveBeenCalledWith('Не удалось отписаться. Попробуйте позже.');
    expect(screen.getByText(SUBSCRIBED_TEXT)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Отписаться' })).toBeEnabled();
  });

  it('shows load error when status request fails', async () => {
    getStatus.mockRejectedValue(new Error('network'));

    render(<NewsletterSettings />);

    expect(
      await screen.findByText('Не удалось загрузить статус подписки. Обновите страницу.')
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Отписаться' })).not.toBeInTheDocument();
  });

  it('treats unexpected status body as load error, not as unsubscribed', async () => {
    getStatus.mockResolvedValue({} as never);

    render(<NewsletterSettings />);

    expect(
      await screen.findByText('Не удалось загрузить статус подписки. Обновите страницу.')
    ).toBeInTheDocument();
    expect(screen.queryByText(NOT_SUBSCRIBED_TEXT)).not.toBeInTheDocument();
  });
});
