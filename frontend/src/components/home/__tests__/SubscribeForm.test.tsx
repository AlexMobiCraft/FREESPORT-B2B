/**
 * Unit tests for SubscribeForm component
 * Story 11.3 - AC 6
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SubscribeForm } from '../SubscribeForm';
import { toast } from 'react-hot-toast';

const PDP_CONSENT_NAME =
  'Я даю согласие на обработку моих персональных данных в соответствии с ' +
  '«Политикой обработки персональных данных ООО „Фриспорт“»';
const PDP_CONSENT_POLICY_LINK_NAME = '«Политикой обработки персональных данных ООО „Фриспорт“»';

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

const getPdpCheckbox = () =>
  screen.getByRole('checkbox', { name: PDP_CONSENT_NAME });

const clickPdpCheckbox = async (user: ReturnType<typeof userEvent.setup>) => {
  await user.click(getPdpCheckbox());
};

const fillEmailAndAcceptConsent = async (
  user: ReturnType<typeof userEvent.setup>,
  email = 'new@example.com'
) => {
  await user.type(screen.getByLabelText(/электронная почта/i), email);
  await clickPdpCheckbox(user);
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

  it('shows validation error for invalid email pattern', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/электронная почта/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    // Email that passes HTML5 type=email validation but fails our regex pattern
    await user.type(input, 'test@x');
    await clickPdpCheckbox(user);
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
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText('Email обязателен')).toBeInTheDocument();
    });
  });

  it('blocks submit without PDN consent', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    const user = userEvent.setup();
    render(<SubscribeForm />);

    await user.type(screen.getByLabelText(/электронная почта/i), 'new@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(
        screen.getByText('Необходимо согласие на обработку персональных данных.')
      ).toBeInTheDocument();
    });
    expect(mockSubscribe).not.toHaveBeenCalled();
  });

  it('marks PDN checkbox invalid and links error text through aria-describedby', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    await user.type(screen.getByLabelText(/электронная почта/i), 'new@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    const checkbox = await screen.findByRole('checkbox', {
      name: PDP_CONSENT_NAME,
    });
    const alert = screen.getByRole('alert');
    expect(checkbox).toHaveAttribute('aria-invalid', 'true');
    expect(checkbox).toHaveAttribute('aria-describedby', alert.id);
  });

  it('generates unique PDN ids for multiple form instances', () => {
    render(
      <>
        <SubscribeForm />
        <SubscribeForm />
      </>
    );

    const checkboxes = screen.getAllByRole('checkbox', {
      name: PDP_CONSENT_NAME,
    });
    const checkboxIds = checkboxes.map(checkbox => checkbox.getAttribute('id'));
    expect(new Set(checkboxIds).size).toBe(2);
  });

  it('calls subscribe service with email and PDN consent payload', async () => {
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
  });

  it('shows backend PDN field error instead of email validation fallback', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(
      Object.assign(new Error('validation_error'), {
        details: {
          pdp_consent: ['Необходимо согласие на обработку персональных данных.'],
        },
      })
    );

    const user = userEvent.setup();
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'server-pdp@example.com');
    await user.click(screen.getByRole('button', { name: /подписаться/i }));

    await waitFor(() => {
      expect(screen.getByText('Необходимо согласие на обработку персональных данных.')).toBeInTheDocument();
      expect(toast.error).toHaveBeenCalledWith(
        'Необходимо согласие на обработку персональных данных.'
      );
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
    render(<SubscribeForm />);

    await fillEmailAndAcceptConsent(user, 'retry@example.com');
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

    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });
  });
});
