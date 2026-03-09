/**
 * PasswordResetRequestForm Component Tests
 * Story 28.3 - Task 6.2
 *
 * Component тесты для PasswordResetRequestForm с использованием Vitest + RTL
 *
 * AC 9: Component Tests для PasswordResetRequestForm
 */

import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PasswordResetRequestForm } from '../PasswordResetRequestForm';
import authService from '@/services/authService';

// Mock authService
vi.mock('@/services/authService', () => ({
  default: {
    requestPasswordReset: vi.fn(),
  },
}));

describe('PasswordResetRequestForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    test('should render email field and submit button', () => {
      render(<PasswordResetRequestForm />);

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(
        screen.getByRole('button', { name: /отправить ссылку для сброса/i })
      ).toBeInTheDocument();
    });

    test('should have proper autocomplete attribute', () => {
      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveAttribute('autocomplete', 'email');
    });

    test('should have email placeholder', () => {
      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveAttribute('placeholder', 'example@email.com');
    });
  });

  describe('Client-side Validation', () => {
    test('should not submit with empty email', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      render(<PasswordResetRequestForm />);

      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.click(submitButton);

      // Browser native validation should prevent form submission
      await waitFor(() => {
        expect(mockRequestPasswordReset).not.toHaveBeenCalled();
      });
    });

    test('should show validation error for invalid email format', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      // Type invalid email (browser type="email" will block this)
      await user.type(emailInput, 'invalid-email');
      await user.click(submitButton);

      // Browser validation should prevent API call
      await waitFor(() => {
        expect(mockRequestPasswordReset).not.toHaveBeenCalled();
      });
    });
  });

  describe('Form Submission', () => {
    test('should submit form with valid email', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      mockRequestPasswordReset.mockResolvedValue({
        detail: 'Password reset email sent.',
      });

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockRequestPasswordReset).toHaveBeenCalledWith('user@example.com');
      });
    });

    test('should show success message after successful submission', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      mockRequestPasswordReset.mockResolvedValue({
        detail: 'Password reset email sent.',
      });

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Success message should appear
      expect(await screen.findByText(/проверьте вашу почту/i)).toBeInTheDocument();
      expect(screen.getByText(/если аккаунт с указанным email существует/i)).toBeInTheDocument();
    });

    test('should hide form after successful submission', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      mockRequestPasswordReset.mockResolvedValue({
        detail: 'Password reset email sent.',
      });

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Wait for success state
      await waitFor(() => {
        expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument();
        expect(screen.queryByRole('button', { name: /отправить/i })).not.toBeInTheDocument();
      });
    });
  });

  describe('Error Handling', () => {
    test('should display error message on API failure', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      mockRequestPasswordReset.mockRejectedValue(new Error('Network error'));

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      expect(await screen.findByText(/произошла ошибка. попробуйте позже./i)).toBeInTheDocument();
    });

    test('should clear previous error on new submission', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);

      // First request fails
      mockRequestPasswordReset.mockRejectedValueOnce(new Error('Network error'));
      // Second request succeeds
      mockRequestPasswordReset.mockResolvedValueOnce({
        detail: 'Password reset email sent.',
      });

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      // First submission - should fail
      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      expect(await screen.findByText(/произошла ошибка/i)).toBeInTheDocument();

      // Clear input and retry
      await user.clear(emailInput);
      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Error should be cleared and success message shown
      await waitFor(() => {
        expect(screen.queryByText(/произошла ошибка/i)).not.toBeInTheDocument();
        expect(screen.getByText(/проверьте вашу почту/i)).toBeInTheDocument();
      });
    });
  });

  describe('Loading State', () => {
    test('should show loading state during submission', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);

      // Delayed promise to capture loading state
      mockRequestPasswordReset.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(() => resolve({ detail: 'Password reset email sent.' }), 100)
          )
      );

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Button should be disabled during submission
      expect(submitButton).toBeDisabled();
      expect(submitButton).toHaveTextContent(/отправка.../i);

      // Wait for submission to complete
      await waitFor(() => {
        expect(screen.queryByRole('button', { name: /отправка/i })).not.toBeInTheDocument();
      });
    });

    test('should disable email input during submission', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);

      mockRequestPasswordReset.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(() => resolve({ detail: 'Password reset email sent.' }), 100)
          )
      );

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i) as HTMLInputElement;
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Email input should be disabled during submission
      expect(emailInput).toBeDisabled();

      await waitFor(() => {
        expect(screen.queryByLabelText(/email/i)).not.toBeInTheDocument(); // Form is replaced with success message
      });
    });
  });

  describe('Accessibility', () => {
    test('should have proper label for email input', () => {
      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveAccessibleName();
    });

    test('should have aria-required on email field', () => {
      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      expect(emailInput).toHaveAttribute('aria-required', 'true');
    });

    test('should have aria-describedby for error messages', async () => {
      const user = userEvent.setup();
      const mockRequestPasswordReset = vi.mocked(authService.requestPasswordReset);
      mockRequestPasswordReset.mockRejectedValue(new Error('Network error'));

      render(<PasswordResetRequestForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса/i,
      });

      await user.type(emailInput, 'user@example.com');
      await user.click(submitButton);

      // Error should have role="alert"
      const errorElement = await screen.findByRole('alert');
      expect(errorElement).toBeInTheDocument();
    });

    test('should have aria-label on submit button', () => {
      render(<PasswordResetRequestForm />);

      const submitButton = screen.getByRole('button', {
        name: /отправить ссылку для сброса пароля/i,
      });
      expect(submitButton).toHaveAttribute('aria-label');
    });
  });
});
