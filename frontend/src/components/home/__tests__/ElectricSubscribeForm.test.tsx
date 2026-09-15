/**
 * Unit tests for ElectricSubscribeForm component
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import { ElectricSubscribeForm } from '../ElectricSubscribeForm';
import { toast } from 'react-hot-toast';

vi.mock('react-hot-toast', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/services/subscribeService', () => ({
  subscribeService: {
    subscribe: vi.fn(),
  },
}));

import { subscribeService } from '@/services/subscribeService';
import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';

// Дословные тексты AC1 стори 41.11 — общие для обеих форм подписки: согласие на ПДн
// и согласие на рассылку оформлены отдельными чекбоксами.
const PDP_CONSENT_NAME =
  'Я даю согласие на обработку моих персональных данных в соответствии с ' +
  '«Политикой обработки персональных данных»';
const MARKETING_CONSENT_NAME =
  'Я согласен(на) получать информационные и рекламные рассылки от OPTISPORT по электронной почте';
const PDP_CONSENT_POLICY_LINK_NAME = '«Политикой обработки персональных данных»';
const PDP_CONSENT_REQUIRED = 'Необходимо согласие на обработку персональных данных.';
const MARKETING_CONSENT_REQUIRED = 'Необходимо согласие на получение рассылок по электронной почте.';

const electricToastStyle = expect.objectContaining({
  style: expect.objectContaining({ borderRadius: '0' }),
});

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
  email = 'electric@example.com'
) => {
  await user.type(screen.getByLabelText(/email/i), email);
  await clickPdpCheckbox(user);
  await clickMarketingCheckbox(user);
};

describe('ElectricSubscribeForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders PDN checkbox with privacy policy link', () => {
    render(<ElectricSubscribeForm />);

    expect(getPdpCheckbox()).toBeInTheDocument();
    const link = screen.getByRole('link', { name: PDP_CONSENT_POLICY_LINK_NAME });
    expect(link).toHaveAttribute('href', '/privacy-policy');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link.closest('label')).toBeNull();
  });

  it('uses the approved consent wording verbatim in two unchecked checkboxes', () => {
    render(<ElectricSubscribeForm />);

    // Дословные тексты AC1: одни и те же формулировки в обеих формах подписки
    expect(screen.getAllByRole('checkbox')).toHaveLength(2);
    expect(getPdpCheckbox()).not.toBeChecked();
    expect(getMarketingCheckbox()).not.toBeChecked();
  });

  it('keeps PDN and newsletter wording in separate checkboxes (AC1)', () => {
    render(<ElectricSubscribeForm />);

    expect(screen.getAllByRole('checkbox', { name: /рассыл/i })).toEqual([getMarketingCheckbox()]);
    expect(screen.getAllByRole('checkbox', { name: /персональн/i })).toEqual([getPdpCheckbox()]);
    expect(screen.getAllByRole('checkbox', { name: /обработк/i })).toEqual([getPdpCheckbox()]);
  });

  it('keeps the checkmark glyph out of the accessible name of a checked checkbox', async () => {
    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    // Квадрат — тоже <label htmlFor>; после отметки в нём появляется «✓».
    await clickPdpCheckbox(user);
    await clickMarketingCheckbox(user);

    expect(getPdpCheckbox()).toBeChecked();
    expect(getMarketingCheckbox()).toBeChecked();
  });

  it('declares both consents required for assistive technologies via aria-required', () => {
    render(<ElectricSubscribeForm />);

    for (const checkbox of [getPdpCheckbox(), getMarketingCheckbox()]) {
      expect(checkbox).toHaveAttribute('aria-required', 'true');
      // Нативный `required` перехватил бы отправку до react-hook-form.
      expect(checkbox).not.toHaveAttribute('required');
    }
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<ElectricSubscribeForm />);

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('has no accessibility violations after a failed submit', async () => {
    const user = userEvent.setup();
    const { container } = render(<ElectricSubscribeForm />);

    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));
    await screen.findByText(MARKETING_CONSENT_REQUIRED);

    const results = await axe(container);
    expect(results.violations).toHaveLength(0);
  });

  it('keeps submit disabled until PDN consent is checked', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric@example.com');
    const button = screen.getByRole('button', { name: /подписаться/i });

    // Без согласия на обработку ПДн кнопка неактивна, submit невозможен
    expect(button).toBeDisabled();
    await user.click(button);
    expect(mockSubscribe).not.toHaveBeenCalled();

    // Галочка рассылки кнопку не активирует (решение Alex, 2026-09-12)
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
      email: 'electric@example.com',
    });
    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric@example.com');
    await clickPdpCheckbox(user);
    const button = screen.getByRole('button', { name: /подписаться/i });
    expect(button).toBeEnabled();

    await user.click(button);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(MARKETING_CONSENT_REQUIRED);
    expect(mockSubscribe).not.toHaveBeenCalled();
    const marketingCheckbox = getMarketingCheckbox();
    expect(marketingCheckbox).toHaveAttribute('aria-invalid', 'true');
    expect(marketingCheckbox).toHaveAttribute('aria-describedby', alert.id);
    expect(marketingCheckbox).toHaveFocus();
    expect(getPdpCheckbox()).not.toHaveAttribute('aria-invalid');

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
    render(<ElectricSubscribeForm />);

    // Email пуст, ПДн отмечен (кнопка активна), рассылка не отмечена — две ошибки.
    // Фокус — на первом ошибочном поле сверху по разметке, то есть на email.
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await screen.findByText(MARKETING_CONSENT_REQUIRED);
    expect(screen.getByText('Email обязателен')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toHaveFocus();
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
    render(<ElectricSubscribeForm />);

    // Согласия отмечены (кнопка активна), но backend возвращает ошибку pdp_consent
    await fillEmailAndAcceptConsent(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const alert = await screen.findByRole('alert');
    expect(getPdpCheckbox()).toHaveAttribute('aria-invalid', 'true');
    expect(getPdpCheckbox()).toHaveAttribute('aria-describedby', alert.id);
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
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-server-marketing@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(MARKETING_CONSENT_REQUIRED);
    expect(getMarketingCheckbox()).toHaveAttribute('aria-invalid', 'true');
    expect(getMarketingCheckbox()).toHaveAttribute('aria-describedby', alert.id);
    expect(getPdpCheckbox()).not.toHaveAttribute('aria-invalid');
    expect(toast.error).toHaveBeenCalledWith(MARKETING_CONSENT_REQUIRED, electricToastStyle);
  });

  it('generates unique consent ids for multiple form instances', () => {
    render(
      <>
        <ElectricSubscribeForm />
        <ElectricSubscribeForm />
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
      email: 'electric@example.com',
    });

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith({
        email: 'electric@example.com',
        pdp_consent: true,
        marketing_consent: true,
        // Версии показанных формулировок — по ним сервер отклоняет устаревшую вкладку.
        pdp_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterPdp,
        marketing_consent_text_version: CONSENT_TEXT_VERSIONS.newsletterMarketing,
      });
    });
  });

  it('resets email and both consent checkboxes after successful subscription', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'electric@example.com',
    });

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    const emailInput = screen.getByLabelText(/email/i);
    await fillEmailAndAcceptConsent(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(emailInput).toHaveValue('');
    expect(getPdpCheckbox()).not.toBeChecked();
    expect(getMarketingCheckbox()).not.toBeChecked();
  });

  it('shows backend PDN field error instead of generic subscription error', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: [PDP_CONSENT_REQUIRED],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-pdp@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(screen.getByText(PDP_CONSENT_REQUIRED)).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith(PDP_CONSENT_REQUIRED, electricToastStyle);
    });
  });

  it('shows unknown backend validation details instead of generic subscription fallback', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          non_field_errors: ['Не удалось сохранить согласие. Попробуйте позже.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-detail@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Не удалось сохранить согласие. Попробуйте позже.',
        electricToastStyle
      );
    });
  });

  it('показывает требование обновить страницу при устаревшей версии текста согласия', async () => {
    // Сервер разводит этот отказ машинным кодом `consent_text_outdated` на
    // верхнем уровне: человеку нужно обновить страницу, а не править ввод.
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        code: 'consent_text_outdated',
        details: {
          pdp_consent_text_version: [
            'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.',
          ],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-outdated@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'ТЕКСТ СОГЛАСИЯ ОБНОВИЛСЯ. ОБНОВИТЕ СТРАНИЦУ И ПОДТВЕРДИТЕ СОГЛАСИЕ ЗАНОВО.',
        electricToastStyle
      );
    });
  });

  it('при устаревшей версии показывает требование обновить страницу, а не попутную ошибку email', async () => {
    // В `details` рядом с полем версии может лежать обычная ошибка валидации.
    // Порядок ключей в JSON произволен, и «первое значение из details» показало
    // бы «введите корректный email» — совет, который ничего не чинит: пока
    // вкладка старая, запрос будет отклоняться при любом адресе.
    const emailMessage = 'Введите корректный адрес электронной почты.';
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        code: 'consent_text_outdated',
        details: {
          email: [emailMessage],
          marketing_consent_text_version: [
            'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.',
          ],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-mixed-details@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'ТЕКСТ СОГЛАСИЯ ОБНОВИЛСЯ. ОБНОВИТЕ СТРАНИЦУ И ПОДТВЕРДИТЕ СОГЛАСИЕ ЗАНОВО.',
        electricToastStyle
      );
    });
    expect(toast.error).not.toHaveBeenCalledWith(emailMessage.toUpperCase(), expect.anything());
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
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-server-error@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'НЕ УДАЛОСЬ СОХРАНИТЬ СОГЛАСИЕ. ПОПРОБУЙТЕ ПОЗЖЕ.',
        electricToastStyle
      );
    });
  });

  it('shows temporary server unavailable message on server error without backend details', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('server_error'));

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-server-unavailable@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'СЕРВЕР ВРЕМЕННО НЕДОСТУПЕН. ПОПРОБУЙТЕ ПОЗЖЕ',
        electricToastStyle
      );
    });
  });

  it('shows throttling message on 429 subscribe errors', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('throttled'));

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-throttled@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'СЛИШКОМ МНОГО ПОПЫТОК. ПОПРОБУЙТЕ ЧЕРЕЗ МИНУТУ.',
        electricToastStyle
      );
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
    render(<ElectricSubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'electric-retry@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await screen.findByText(PDP_CONSENT_REQUIRED);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledTimes(2);
      expect(screen.queryByText(PDP_CONSENT_REQUIRED)).not.toBeInTheDocument();
    });

    await act(async () => {
      resolveSecondSubmit!({ message: 'Success', email: 'electric-retry@example.com' });
    });
  });
});
