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

// Дословная формулировка согласия из AC1 стори 41.3 — общая для обеих форм подписки
const PDP_CONSENT_NAME =
  'Я даю согласие на обработку моих персональных данных в соответствии с ' +
  '«Политикой обработки персональных данных» и согласен(на) получать ' +
  'информационные и рекламные рассылки от OPTISPORT по электронной почте';
const PDP_CONSENT_POLICY_LINK_NAME = '«Политикой обработки персональных данных»';

const getPdpCheckbox = () => screen.getByRole('checkbox', { name: PDP_CONSENT_NAME });

const clickPdpCheckbox = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(getPdpCheckbox());
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

  it('uses the approved consent wording verbatim', () => {
    render(<ElectricSubscribeForm />);

    // Дословный текст AC1: одна формулировка на обе формы подписки
    expect(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME })).toBeInTheDocument();
  });

  it('mentions email newsletter in the consent checkbox accessible name', () => {
    render(<ElectricSubscribeForm />);

    // Согласие получено одним чекбоксом на оба смысла: обработка ПДн и рассылка
    expect(
      screen.getByRole('checkbox', {
        name: /рассылки от OPTISPORT по электронной почте/i,
      })
    ).toBeInTheDocument();
  });

  it('has no accessibility violations', async () => {
    const { container } = render(<ElectricSubscribeForm />);

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

    // После установки согласия кнопка становится активной
    await clickPdpCheckbox(user);
    expect(button).toBeEnabled();
  });

  it('marks PDN checkbox invalid and links error text through aria-describedby', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: ['Необходимо согласие на обработку персональных данных.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    // Согласие отмечено (кнопка активна), но backend возвращает ошибку pdp_consent
    await user.type(screen.getByLabelText(/email/i), 'electric@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const checkbox = await screen.findByRole('checkbox', {
      name: /обработку моих персональных данных/i,
    });
    const alert = await screen.findByRole('alert');
    expect(checkbox).toHaveAttribute('aria-invalid', 'true');
    expect(checkbox).toHaveAttribute('aria-describedby', alert.id);
  });

  it('generates unique PDN ids for multiple form instances', () => {
    render(
      <>
        <ElectricSubscribeForm />
        <ElectricSubscribeForm />
      </>
    );

    const checkboxes = screen.getAllByRole('checkbox', {
      name: /обработку моих персональных данных/i,
    });
    const checkboxIds = checkboxes.map(checkbox => checkbox.getAttribute('id'));
    expect(new Set(checkboxIds).size).toBe(2);
  });

  it('calls subscribe service with email and PDN consent payload', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'electric@example.com',
    });

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledWith({
        email: 'electric@example.com',
        pdp_consent: true,
        // Версия показанной формулировки — по ней сервер отклоняет устаревшую вкладку.
        consent_text_version: CONSENT_TEXT_VERSIONS.newsletter,
      });
    });
  });

  it('resets email and PDN checkbox after successful subscription', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'electric@example.com',
    });

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    const emailInput = screen.getByLabelText(/email/i);
    await user.type(emailInput, 'electric@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalled();
    });
    expect(emailInput).toHaveValue('');
    expect(getPdpCheckbox()).not.toBeChecked();
  });

  it('shows backend PDN field error instead of generic subscription error', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: ['Необходимо согласие на обработку персональных данных.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric-pdp@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(screen.getByText('Необходимо согласие на обработку персональных данных.')).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith(
        'Необходимо согласие на обработку персональных данных.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
      );
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

    await user.type(screen.getByLabelText(/email/i), 'electric-detail@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Не удалось сохранить согласие. Попробуйте позже.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
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
          consent_text_version: [
            'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.',
          ],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric-outdated@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'ТЕКСТ СОГЛАСИЯ ОБНОВИЛСЯ. ОБНОВИТЕ СТРАНИЦУ И ПОДТВЕРДИТЕ СОГЛАСИЕ ЗАНОВО.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
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
          consent_text_version: [
            'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.',
          ],
        },
      })
    );

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric-mixed-details@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'ТЕКСТ СОГЛАСИЯ ОБНОВИЛСЯ. ОБНОВИТЕ СТРАНИЦУ И ПОДТВЕРДИТЕ СОГЛАСИЕ ЗАНОВО.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
      );
    });
    expect(toast.error).not.toHaveBeenCalledWith(
      emailMessage.toUpperCase(),
      expect.anything()
    );
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

    await user.type(screen.getByLabelText(/email/i), 'electric-server-error@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'НЕ УДАЛОСЬ СОХРАНИТЬ СОГЛАСИЕ. ПОПРОБУЙТЕ ПОЗЖЕ.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
      );
    });
  });

  it('shows temporary server unavailable message on server error without backend details', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('server_error'));

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric-server-unavailable@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'СЕРВЕР ВРЕМЕННО НЕДОСТУПЕН. ПОПРОБУЙТЕ ПОЗЖЕ',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
      );
    });
  });

  it('shows throttling message on 429 subscribe errors', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('throttled'));

    const user = userEvent.setup();
    render(<ElectricSubscribeForm />);

    await user.type(screen.getByLabelText(/email/i), 'electric-throttled@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'СЛИШКОМ МНОГО ПОПЫТОК. ПОПРОБУЙТЕ ЧЕРЕЗ МИНУТУ.',
        expect.objectContaining({
          style: expect.objectContaining({ borderRadius: '0' }),
        })
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
            pdp_consent: ['Необходимо согласие на обработку персональных данных.'],
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

    await user.type(screen.getByLabelText(/email/i), 'electric-retry@example.com');
    await clickPdpCheckbox(user);
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await screen.findByText('Необходимо согласие на обработку персональных данных.');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(mockSubscribe).toHaveBeenCalledTimes(2);
      expect(
        screen.queryByText('Необходимо согласие на обработку персональных данных.')
      ).not.toBeInTheDocument();
    });

    await act(async () => {
      resolveSecondSubmit!({ message: 'Success', email: 'electric-retry@example.com' });
    });
  });
});
