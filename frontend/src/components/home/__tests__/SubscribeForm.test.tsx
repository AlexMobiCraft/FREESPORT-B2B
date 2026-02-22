/**
 * Unit tests for SubscribeForm component
 * Story 11.3 - AC 6
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SubscribeForm } from '../SubscribeForm';
import { toast } from 'react-hot-toast';

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

describe('SubscribeForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders subscribe form correctly', () => {
    render(<SubscribeForm />);

    expect(screen.getByText('Подписаться на рассылку')).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /подписаться/i })).toBeInTheDocument();
  });

  it('shows validation error for invalid email pattern', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/email/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    // Email that passes HTML5 type=email validation but fails our regex pattern
    await user.type(input, 'test@x');
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText('Введите корректный email')).toBeInTheDocument();
    });
  });

  it('shows validation error for empty email', async () => {
    const user = userEvent.setup();
    render(<SubscribeForm />);

    const button = screen.getByRole('button', { name: /подписаться/i });
    await user.click(button);

    await waitFor(() => {
      expect(screen.getByText('Email обязателен')).toBeInTheDocument();
    });
  });

  it('shows success toast on successful subscription', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockResolvedValueOnce({
      message: 'Successfully subscribed',
      email: 'new@example.com',
    });

    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/email/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    await user.type(input, 'new@example.com');
    await user.click(button);

    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('Вы успешно подписались на рассылку');
    });

    // Form should be reset
    expect(input).toHaveValue('');
  });

  it('shows error toast when email already subscribed', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('already_subscribed'));

    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/email/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    await user.type(input, 'existing@example.com');
    await user.click(button);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Этот email уже подписан на рассылку');
    });
  });

  it('shows error toast on network error', async () => {
    const mockSubscribe = vi.mocked(subscribeService.subscribe);
    mockSubscribe.mockRejectedValueOnce(new Error('network_error'));

    const user = userEvent.setup();
    render(<SubscribeForm />);

    const input = screen.getByLabelText(/email/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    await user.type(input, 'test@example.com');
    await user.click(button);

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

    const input = screen.getByLabelText(/email/i);
    const button = screen.getByRole('button', { name: /подписаться/i });

    await user.type(input, 'test@example.com');
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
