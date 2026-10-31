import { describe, it, expect, vi, beforeEach } from 'vitest';
import { subscribeService, SubscribeServiceError } from '../subscribeService';
import apiClient from '../api-client';
import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';

vi.mock('../api-client');

// Согласия формы подписки: со стори 41.11 два чекбокса, у каждого своя версия.
const CONSENTS = {
  pdp_consent: true,
  marketing_consent: true,
  pdp_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterPdp,
  marketing_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterMarketing,
} as const;

describe('subscribeService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // URL — с конечным слэшем: маршрут Django `subscribe/`, на POST без слэша
  // `APPEND_SLASH` отвечает редиректом, и подписка не проходит (стори 41.11).
  it('posts the full subscribe payload to /subscribe/ with a trailing slash', async () => {
    vi.mocked(apiClient.post).mockResolvedValueOnce({
      data: {
        message: 'Вы успешно подписались на рассылку',
        email: 'new@example.com',
      },
    });

    await subscribeService.subscribe({ email: 'new@example.com', ...CONSENTS });

    expect(apiClient.post).toHaveBeenCalledWith('/subscribe/', {
      email: 'new@example.com',
      pdp_consent: true,
      marketing_consent: true,
      pdp_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterPdp,
      marketing_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterMarketing,
    });
  });

  it('preserves backend field errors for 400 validation responses', async () => {
    const details = {
      pdp_consent: ['Необходимо согласие на обработку персональных данных.'],
      marketing_consent: ['Необходимо согласие на получение рассылок по электронной почте.'],
    };
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 400,
        data: details,
      },
    });

    await expect(
      subscribeService.subscribe({ email: 'new@example.com', ...CONSENTS })
    ).rejects.toMatchObject({
      message: 'validation_error',
      details,
    });
  });

  it('прокидывает машинный код consent_text_outdated с верхнего уровня ответа', async () => {
    // Сервер разводит устаревшую версию формулировки и обычную валидацию кодом,
    // а не текстом сообщения: сообщение правят, статус у всей валидации общий.
    const details = {
      pdp_consent_text_version: [
        'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.',
      ],
    };
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 400,
        data: { error: 'consent_text_outdated', details },
      },
    });

    await expect(
      subscribeService.subscribe({
        email: 'stale-tab@example.com',
        ...CONSENTS,
        pdp_consent_text_version: 'старая-версия',
      })
    ).rejects.toMatchObject({
      message: 'validation_error',
      code: 'consent_text_outdated',
      details,
    });
  });

  it('maps 429 responses to throttled errors with backend details', async () => {
    const details = {
      non_field_errors: ['Слишком много попыток. Попробуйте через минуту.'],
    };
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 429,
        data: details,
      },
    });

    await expect(
      subscribeService.subscribe({ email: 'new@example.com', ...CONSENTS })
    ).rejects.toMatchObject({
      message: 'throttled',
      details,
    });
  });

  it('does not expose the removed already_subscribed contract for unexpected 409 responses', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 409,
        data: {
          email: ['Этот email уже подписан на рассылку'],
        },
      },
    });

    try {
      await subscribeService.subscribe({ email: 'existing@example.com', ...CONSENTS });
      throw new Error('Expected subscribeService to reject');
    } catch (error) {
      expect(error).toBeInstanceOf(SubscribeServiceError);
      expect((error as SubscribeServiceError).message).toBe('network_error');
      expect((error as SubscribeServiceError).details).toBeUndefined();
    }
  });

  it('maps 503 responses to server errors when details match the OpenAPI contract', async () => {
    const details = {
      non_field_errors: ['Не удалось сохранить согласие. Попробуйте позже.'],
    };
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 503,
        data: {
          error: 'consent_persistence_failed',
          details,
        },
      },
    });

    await expect(
      subscribeService.subscribe({ email: 'new@example.com', ...CONSENTS })
    ).rejects.toMatchObject({
      message: 'server_error',
      details,
    });
  });

  it('maps 5xx responses without contract details to server errors', async () => {
    vi.mocked(apiClient.post).mockRejectedValueOnce({
      response: {
        status: 502,
        data: '<html>Bad Gateway</html>',
      },
    });

    await expect(
      subscribeService.subscribe({ email: 'new@example.com', ...CONSENTS })
    ).rejects.toMatchObject({
      message: 'server_error',
      details: undefined,
    });
  });
});
