import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { axe } from 'vitest-axe';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import UnsubscribeClient from '../UnsubscribeClient';
import { UnsubscribeServiceError, unsubscribeService } from '@/services/unsubscribeService';

vi.mock('@/services/unsubscribeService', async importOriginal => {
  const actual = await importOriginal<typeof import('@/services/unsubscribeService')>();
  return { ...actual, unsubscribeService: { unsubscribe: vi.fn() } };
});

const TOKEN = 'a'.repeat(43);

describe('UnsubscribeClient', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.history.replaceState(null, '', `/unsubscribe#${TOKEN}`);
  });

  afterEach(() => {
    window.history.replaceState(null, '', '/');
  });

  it('сразу очищает fragment и ждёт явного подтверждения', async () => {
    render(<UnsubscribeClient />);

    await screen.findByRole('button', { name: 'Отписаться от рассылки' });
    expect(window.location.pathname).toBe('/unsubscribe');
    expect(window.location.hash).toBe('');
    expect(unsubscribeService.unsubscribe).not.toHaveBeenCalled();
  });

  it('отправляет токен только после подтверждения и показывает нейтральный успех', async () => {
    vi.mocked(unsubscribeService.unsubscribe).mockResolvedValueOnce({ status: 'processed' });
    render(<UnsubscribeClient />);
    const button = await screen.findByRole('button', { name: 'Отписаться от рассылки' });

    fireEvent.click(button);

    expect(await screen.findByText('Запрос на отписку обработан')).toBeTruthy();
    expect(unsubscribeService.unsubscribe).toHaveBeenCalledWith(TOKEN);
    expect(screen.queryByText(/@/)).toBeNull();
  });

  it('показывает нейтральную недействительную ссылку без API-запроса', async () => {
    window.history.replaceState(null, '', '/unsubscribe');

    render(<UnsubscribeClient />);

    expect(await screen.findByText('Ссылка недействительна')).toBeTruthy();
    expect(unsubscribeService.unsubscribe).not.toHaveBeenCalled();
  });

  it('в состоянии invalid_token показывает CTA «На главную» вместо «Повторить»', async () => {
    window.history.replaceState(null, '', '/unsubscribe');

    render(<UnsubscribeClient />);

    const block = await screen.findByTestId('unsubscribe-invalid-token');
    const cta = screen.getByTestId('go-home-button');
    expect(block).toContainElement(cta);
    expect(cta).toHaveAttribute('href', '/');
    expect(screen.queryByRole('button', { name: 'Повторить' })).toBeNull();
  });

  it.each([
    ['invalid_token', 'Ссылка недействительна', false],
    ['throttled', 'Слишком много попыток', true],
    ['network_error', 'Не удалось обработать запрос', true],
    ['server_error', 'Не удалось обработать запрос', true],
  ] as const)('обрабатывает %s и возможность повтора', async (kind, text, retryable) => {
    vi.mocked(unsubscribeService.unsubscribe).mockRejectedValueOnce(
      new UnsubscribeServiceError(kind)
    );
    render(<UnsubscribeClient />);
    fireEvent.click(await screen.findByRole('button', { name: 'Отписаться от рассылки' }));

    expect(await screen.findByText(text)).toBeTruthy();
    expect(screen.queryByRole('button', { name: 'Повторить' }) !== null).toBe(retryable);
  });

  it('объявляет результат и переводит на него фокус', async () => {
    vi.mocked(unsubscribeService.unsubscribe).mockResolvedValueOnce({ status: 'processed' });
    render(<UnsubscribeClient />);
    fireEvent.click(await screen.findByRole('button', { name: 'Отписаться от рассылки' }));

    const heading = await screen.findByText('Запрос на отписку обработан');
    const result = heading.closest('[role="status"]');
    await waitFor(() => expect(result).toHaveFocus());
  });

  it('не имеет автоматических axe-нарушений', async () => {
    const { container } = render(<UnsubscribeClient />);
    await screen.findByRole('button', { name: 'Отписаться от рассылки' });

    const results = await axe(container);
    expect(results.violations).toEqual([]);
  });
});
