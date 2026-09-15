/**
 * Unit tests for SubscribeForm component
 * Story 11.3 - AC 6
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { SubscribeForm } from '../SubscribeForm';
import { toast } from 'react-hot-toast';

// Дословные тексты AC1 стори 41.11: согласие на ПДн и согласие на рассылку —
// два отдельных чекбокса с непересекающимися формулировками.
const PDP_CONSENT_NAME =
  'Я даю согласие на обработку моих персональных данных в соответствии с ' +
  '«Политикой обработки персональных данных»';
const MARKETING_CONSENT_NAME =
  'Я согласен(на) получать информационные и рекламные рассылки от OPTISPORT по электронной почте';
const PDP_CONSENT_POLICY_LINK_NAME = '«Политикой обработки персональных данных»';
const PDP_CONSENT_REQUIRED = 'Необходимо согласие на обработку персональных данных.';
const MARKETING_CONSENT_REQUIRED = 'Необходимо согласие на получение рассылок по электронной почте.';

// Mock react-hot-toast
vi.mock('react-hot-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock subscribeService
vi.mock('@/services/subscribeService', () => ({
  subscribeService: {
    subscribe: vi.fn(),
  },
}));

import { subscribeService } from '@/services/subscribeService';
import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';

const getPdpCheckbox = () => screen.getByRole('checkbox', { name: PDP_CONSENT_NAME });
const getMarketingCheckbox = () => screen.getByRole('checkbox', { name: MARKETING_CONSENT_NAME });

const clickPdpCheckbox = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(getPdpCheckbox());
};

const clickMarketingCheckbox = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(getMarketingCheckbox());
};

const fillEmailAndAcceptConsent = async (
  user: ReturnType<typeof userEvent.setup>,
  email = 'new@example.com'
) => {
  await user.type(screen.getByLabelText(/электронная почта/i), email);
  await clickPdpCheckbox(user);
  await clickMarketingCheckbox(user);
};

describe('SubscribeForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders subscribe form correctly', () => {
    render(<SubscribeForm />);

    expect(screen.getByText('Подписаться на рассылку')).toBeInTheDocument();
    expect(screen.getByLabelText(/электронная почта/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /подписаться/i })).toBeInTheDocument();
  });

  it('renders PDN checkbox with privacy policy link', () => {
    render(<SubscribeForm />);

    expect(getPdpCheckbox()).toBeInTheDocument();
    const link = screen.getByRole('link', {
      name: PDP_CONSENT_POLICY_LINK_NAME,
    });
    expect(link).toHaveAttribute('href', '/privacy-policy');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link.closest('label')).toBeNull();
  });

  it('renders two unchecked consent checkboxes', () => {
    render(<SubscribeForm />);

    expect(screen.getAllByRole('checkbox')).toHaveLength(2);
    expect(getPdpCheckbox()).not.toBeChecked();
    expect(getMarketingCheckbox()).not.toBeChecked();
  });

  it('keeps PDN and newsletter wording in separate checkboxes (AC1)', () => {
    render(<SubscribeForm />);

    // Поиск по регулярке идёт по вычисленному доступному имени: каждое слово
    // обязано найтись ровно в одном чекбоксе — в своём.
    expect(screen.getAllByRole('checkbox', { name: /рассыл/i })).toEqual([getMarketingCheckbox()]);
    expect(screen.getAllByRole('checkbox', { name: /персональн/i })).toEqual([getPdpCheckbox()]);
    expect(screen.getAllByRole('checkbox', { name: /обработк/i })).toEqual([getPdpCheckbox()]);
  });

  it('declares both consents required for assistive technologies via aria-required', () => {
    render(<SubscribeForm />);

    for (const checkbox of [getPdpCheckbox(), getMarketingCheckbox()]) {
      expect(checkbox).toHaveAttribute('aria-required', 'true');
      // Нативный `required` перехватил бы отправку до react-hook-form.
      expect(checkbox).not.toHaveAttribute('required');
    }
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<SubscribeForm />);

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('has no accessibility violations after a failed submit', async () => {
    const user = userEvent.setup();
    const { container } = render(<SubscribeForm />);

    // ПДн отмечен (кнопка активна), email и рассылка не заполнены — две ошибки.
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));
    await screen.findByText(MARKETING_CONSENT_REQUIRED);

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('shows validation error for invalid email pattern', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/электронная почта/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    // Email that passes HTML5 type=email validation but fails our regex pattern
    await user.type(input, 'test@x');
    await clickPdpCheckbox(user);
    await clickMarketingCheckbox(user);
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText('Введите корректный email')).toBeInTheDocument();
    });
  });

  it('shows validation error for empty email', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    const button = screen.getByRole('button', { name: /подписаться/i });
    await clickPdpCheckbox(user);
    await clickMarketingCheckbox(user);
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText('Email обязателен')).toBeInTheDocument();
    });
  });

  it('keeps submit disabled until PDN consent is checked', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    const user = userEvent.setup();
    render(<SubscribeForm />);

    await user.type(screen.getByLabelText(/электронная почта/i), 'new@example.com');
    const button = screen.getByRole('button', { name: /подписаться/i });

    // Без согласия на обработку ПДн кнопка неактивна, submit невозможен
    expect(button).toBeDisabled();
    await user.click(button);
    expect(mockSubscribe).not.toHaveBeenCalled();

    // Галочка рассылки кнопку не активирует: правило зависит только от ПДн
    // (решение Alex, 2026-09-12).
    await clickMarketingCheckbox(user);
    expect(getMarketingCheckbox()).toBeChecked();
    expect(button).toBeDisabled();
    await user.click(button);
    expect(mockSubscribe).not.toHaveBeenCalled();

    // После установки согласия кнопка становится активной
    await clickPdpCheckbox(user);
    expect(button).toBeEnabled();

    // Снятая галочка ПДн снова блокирует кнопку при отмеченной рассылке
    await clickPdpCheckbox(user);
    expect(button).toBeDisabled();
  });

  it('blocks submit without newsletter consent and puts the error on its checkbox', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'new@example.com',
    });
    const user = userEvent.setup();
    render(<SubscribeForm />);

    await user.type(screen.getByLabelText(/электронная почта/i), 'new@example.com');
    await clickPdpCheckbox(user);
    const button = screen.getByRole('button', { name: /подписаться/i });
    expect(button).toBeEnabled();

    await user.click(button);

    // Запрос не ушёл, ошибка — у чекбокса рассылки, фокус переведён на него
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(MARKETING_CONSENT_REQUIRED);
    expect(mockSubscribe).not.toHaveBeenCalled();
    const marketingCheckbox = getMarketingCheckbox();
    expect(marketingCheckbox).toHaveAttribute('aria-invalid', 'true');
    expect(marketingCheckbox).toHaveAttribute('aria-describedby', alert.id);
    expect(marketingCheckbox).toHaveFocus();
    expect(getPdpCheckbox()).not.toHaveAttribute('aria-invalid');

    // Галочка рассылки снимает ошибку, и отправка проходит
    await clickMarketingCheckbox(user);
    await waitFor(() => {
      expect(screen.queryByText(MARKETING_CONSENT_REQUIRED)).not.toBeInTheDocument();
    });
    expect(getMarketingCheckbox()).not.toHaveAttribute('aria-invalid');

    await user.click(button);
    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledTimes(1);
    });
  });

  it('focuses the email field, not the newsletter checkbox, when both are invalid', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    const user = userEvent.setup();
    render(<SubscribeForm />);

    // Email пуст, ПДн отмечен (кнопка активна), рассылка не отмечена — две ошибки.
    // Фокус — на первом ошибочном поле сверху по разметке, то есть на email.
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await screen.findByText(MARKETING_CONSENT_REQUIRED);
    expect(screen.getByText('Email обязателен')).toBeInTheDocument();
    expect(screen.getByLabelText(/электронная почта/i)).toHaveFocus();
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('marks PDN checkbox invalid and links error text through aria-describedby', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: [PDP_CONSENT_REQUIRED],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    // Согласия отмечены (кнопка активна), но backend возвращает ошибку pdp_consent
    await fillEmailAndAcceptConsent(user, 'new@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const checkbox = await screen.findByRole('checkbox', {
      name: PDP_CONSENT_NAME,
    });
    const alert = await screen.findByRole('alert');
    expect(checkbox).toHaveAttribute('aria-invalid', 'true');
    expect(checkbox).toHaveAttribute('aria-describedby', alert.id);
  });

  it('puts backend marketing_consent error on the newsletter checkbox', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          marketing_consent: [MARKETING_CONSENT_REQUIRED],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    // Клиентская проверка пройдена, отказ пришёл с сервера
    await fillEmailAndAcceptConsent(user, 'server-marketing@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(MARKETING_CONSENT_REQUIRED);
    expect(getMarketingCheckbox()).toHaveAttribute('aria-invalid', 'true');
    expect(getMarketingCheckbox()).toHaveAttribute('aria-describedby', alert.id);
    expect(getPdpCheckbox()).not.toHaveAttribute('aria-invalid');
    expect(toast.error).toHaveBeenCalledWith(MARKETING_CONSENT_REQUIRED);
  });

  it('показывает требование обновить страницу, когда сервер отклонил устаревшую версию текста', async () => {
    // Сервер отвечает 400 с машинным кодом `consent_text_outdated` на верхнем
    // уровне, если формулировку поправили после отрисовки этой вкладки. Человек
    // должен увидеть внятное требование обновить страницу, а не общий отказ.
    const outdatedMessage = 'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.';
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        code: 'consent_text_outdated',
        details: {
          pdp_consent_text_version: [outdatedMessage],
          marketing_consent_text_version: [outdatedMessage],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'outdated-version@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(outdatedMessage);
    });
  });

  it('при устаревшей версии показывает требование обновить страницу, а не попутную ошибку email', async () => {
    // В `details` рядом с полем версии может лежать обычная ошибка валидации.
    // Порядок ключей в JSON произволен, и «первое значение из details» показало
    // бы «введите корректный email» — совет, который ничего не чинит: пока
    // вкладка старая, запрос будет отклоняться при любом адресе.
    const outdatedMessage = 'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.';
    const emailMessage = 'Введите корректный адрес электронной почты.';
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        code: 'consent_text_outdated',
        details: {
          email: [emailMessage],
          pdp_consent_text_version: [outdatedMessage],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'mixed-details@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(outdatedMessage);
    });
    expect(toast.error).not.toHaveBeenCalledWith(emailMessage);
  });

  it('generates unique consent ids for multiple form instances', () => {
    render(
      <>
        <SubscribeForm />
        <SubscribeForm />
      </>
    );

    for (const name of [PDP_CONSENT_NAME, MARKETING_CONSENT_NAME]) {
      const checkboxes = screen.getAllByRole('checkbox', { name });
      expect(checkboxes).toHaveLength(2);
      const checkboxIds = checkboxes.map(checkbox => checkbox.getAttribute('id'));
      expect(new Set(checkboxIds).size).toBe(2);
    }
    const allIds = screen.getAllByRole('checkbox').map(checkbox => checkbox.getAttribute('id'));
    expect(new Set(allIds).size).toBe(4);
  });

  it('calls subscribe service with email, both consents and both text versions', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'new@example.com',
    });

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'new@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith({
        email: 'new@example.com',
        pdp_consent: true,
        marketing_consent: true,
        // Версии показанных формулировок — по ним сервер отклоняет устаревшую вкладку.
        pdp_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterPdp,
        marketing_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterMarketing,
      });
    });
  });

  it('shows success toast on successful subscription and resets form', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'new@example.com',
    });

    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/электронная почта/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    await fillEmailAndAcceptConsent(user, 'new@example.com');
    await user.click(button);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('Вы успешно подписались на рассылку');
    });

    expect(input).toHaveValue('');
    expect(getPdpCheckbox()).not.toBeChecked();
    expect(getMarketingCheckbox()).not.toBeChecked();
  });

  it('shows backend PDN field error instead of email validation fallback', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: [PDP_CONSENT_REQUIRED],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'server-pdp@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(screen.getByText(PDP_CONSENT_REQUIRED)).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith(PDP_CONSENT_REQUIRED);
    });
  });

  it('shows unknown backend validation details instead of generic email fallback', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          non_field_errors: ['Не удалось сохранить согласие. Попробуйте позже.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'server-detail@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Не удалось сохранить согласие. Попробуйте позже.');
    });
  });

  it('shows backend message on server error from subscribe service', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('server_error'), {
        details: {
          non_field_errors: ['Не удалось сохранить согласие. Попробуйте позже.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'server-error@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Не удалось сохранить согласие. Попробуйте позже.');
    });
  });

  it('shows temporary server unavailable message on server error without backend details', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('server_error'));

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'server-unavailable@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Сервер временно недоступен. Попробуйте позже');
    });
  });

  it('shows throttling message on 429 subscribe errors', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('throttled'));

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'throttled@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Слишком много попыток. Попробуйте через минуту.');
    });
  });

  it('clears stale PDN server error before retrying submit', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    let resolveSecondSubmit: (value: { message: string; email: string }) => void;
    mockSubscribe
      .mockRejectedValueOnce(
        Object.assign(new Error('validation_error'), {
          details: {
            pdp_consent: [PDP_CONSENT_REQUIRED],
          },
        })
      )
      .mockImplementationOnce(
        () =>
          new Promise(resolve => {
            resolveSecondSubmit = resolve;
          })
      );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'retry@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await screen.findByText(PDP_CONSENT_REQUIRED);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledTimes(2);
      expect(screen.queryByText(PDP_CONSENT_REQUIRED)).not.toBeInTheDocument();
    });

    await act(async () => {
      resolveSecondSubmit!({ message: 'Success', email: 'retry@example.com' });
    });
  });

  it('shows error toast on network error', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('network_error'));

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'test@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Не удалось подписаться. Попробуйте позже');
    });
  });

  it('disables button during submission', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    let resolvePromise: (value: { message: string; email: string }) => void;
    mockSubscribe.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolvePromise = resolve;
        })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    const button = screen.getByRole('button', { name: /подписаться/i });

    await fillEmailAndAcceptConsent(user, 'test@example.com');
    await user.click(button);

    // Button should be disabled and show loading text
    expect(button).toBeDisabled();
    expect(screen.getByText('Отправка...')).toBeInTheDocument();

    // Resolve the promise
    resolvePromise!({ message: 'Success', email: 'test@example.com' });

    // После успешной подписки форма сбрасывается: loading завершён,
    // но согласие снято (reset) — кнопка снова становится неактивной.
    await waitFor(() => {
      expect(screen.queryByText('Отправка...')).not.toBeInTheDocument();
    });
    expect(screen.getByRole('button', { name: /подписаться/i })).toBeDisabled();
  });
});
