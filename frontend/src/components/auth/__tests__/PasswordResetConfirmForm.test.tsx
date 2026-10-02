/**
 * PasswordResetConfirmForm Component Tests
 * Story 28.3 - Task 6.3
 *
 * Component тесты для PasswordResetConfirmForm с использованием Vitest + RTL
 *
 * AC 9: Component Tests для PasswordResetConfirmForm
 */

import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PasswordResetConfirmForm } from '../PasswordResetConfirmForm';
import authService from '@/services/authService';

// Mock next/navigation
const mockReplace = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: mockReplace,
  }),
}));

// Mock authService
vi.mock('@/services/authService', () => ({
  default: {
    validateResetToken: vi.fn(),
    confirmPasswordReset: vi.fn(),
  },
}));

describe('PasswordResetConfirmForm', () => {
  const defaultProps = {
    uid: 'MQ',
    token: 'valid-token-123',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockReplace.mockClear();
  });

  describe('Token Validation on Mount', () => {
    test('should show loading state while validating token', () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      // Mock a promise that never resolves to keep loading state
      mockValidateResetToken.mockImplementation(() => new Promise(() => {}));

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(screen.getByText(/проверка ссылки.../i)).toBeInTheDocument();
    });

    test('should validate token on component mount', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      await waitFor(() => {
        expect(mockValidateResetToken).toHaveBeenCalledWith('MQ', 'valid-token-123');
      });
    });

    test('should show form after successful token validation', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(await screen.findByLabelText(/новый пароль/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/подтверждение пароля/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /сбросить пароль/i })).toBeInTheDocument();
    });

    test('should show error for expired token (410)', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockRejectedValue({
        response: { status: 410 },
      });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(await screen.findByText(/срок действия ссылки истёк/i)).toBeInTheDocument();
      expect(screen.getByText(/запросить новую ссылку/i)).toBeInTheDocument();
    });

    test('should show error for invalid token (404)', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockRejectedValue({
        response: { status: 404 },
      });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(await screen.findByText(/недействительная ссылка/i)).toBeInTheDocument();
    });

    test('should show generic error for other validation errors', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockRejectedValue({
        response: { status: 500 },
      });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(await screen.findByText(/произошла ошибка при проверке ссылки/i)).toBeInTheDocument();
    });

    test('should show link to request new reset when token is invalid', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockRejectedValue({
        response: { status: 410 },
      });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      const link = await screen.findByRole('link', {
        name: /запросить новую ссылку/i,
      });
      expect(link).toHaveAttribute('href', '/password-reset');
    });
  });

  describe('Rendering', () => {
    test('should render password fields after valid token', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      expect(await screen.findByLabelText(/новый пароль/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/подтверждение пароля/i)).toBeInTheDocument();
    });

    test('should have password strength hint', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      await waitFor(() => {
        expect(screen.getByText(/пароль должен содержать минимум 8 символов/i)).toBeInTheDocument();
      });
    });

    test('should have proper autocomplete attributes', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);

      expect(passwordInput).toHaveAttribute('autocomplete', 'new-password');
      expect(confirmPasswordInput).toHaveAttribute('autocomplete', 'new-password');
    });
  });

  describe('Client-side Validation', () => {
    beforeEach(async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });
    });

    test('should show error for short password', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'short');
      await user.type(confirmPasswordInput, 'short');
      await user.click(submitButton);

      // Wait for error to appear - use getAllByText and check first alert role element
      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const passwordError = alerts.find(el => el.textContent?.includes('минимум 8 символов'));
        expect(passwordError).toBeTruthy();
      });
    });

    test('should show error for password without digit', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NoDigitsHere');
      await user.type(confirmPasswordInput, 'NoDigitsHere');
      await user.click(submitButton);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const passwordError = alerts.find(el => el.textContent?.includes('хотя бы 1 цифру'));
        expect(passwordError).toBeTruthy();
      });
    });

    test('should show error for password without uppercase', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'nouppercase123');
      await user.type(confirmPasswordInput, 'nouppercase123');
      await user.click(submitButton);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const passwordError = alerts.find(el =>
          el.textContent?.includes('хотя бы 1 заглавную букву')
        );
        expect(passwordError).toBeTruthy();
      });
    });

    test('should show error when passwords do not match', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmPasswordInput, 'DifferentPass123');
      await user.click(submitButton);

      await waitFor(() => {
        const alerts = screen.getAllByRole('alert');
        const passwordError = alerts.find(el => el.textContent?.includes('Пароли не совпадают'));
        expect(passwordError).toBeTruthy();
      });
    });
  });

  describe('Form Submission', () => {
    beforeEach(() => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });
    });

    test('should submit form with valid password', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockResolvedValue({
        detail: 'Password has been reset successfully.',
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockConfirmPasswordReset).toHaveBeenCalledWith(
          'MQ',
          'valid-token-123',
          'NewSecurePass123'
        );
      });
    });

    test('should redirect to login page with success query on successful reset', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockResolvedValue({
        detail: 'Password has been reset successfully.',
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalledWith('/login?reset=success');
      });
    });

    test('should use router.replace() instead of router.push() for security', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockResolvedValue({
        detail: 'Password has been reset successfully.',
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      // Verify replace was called (not push)
      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalled();
      });
    });
  });

  describe('Error Handling', () => {
    beforeEach(() => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });
    });

    test('should show error for expired token during confirmation (410)', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockRejectedValue({
        response: { status: 410 },
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      expect(await screen.findByText(/срок действия ссылки истёк/i)).toBeInTheDocument();
    });

    test('should show error for invalid token during confirmation (404)', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockRejectedValue({
        response: { status: 404 },
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      expect(await screen.findByText(/недействительная ссылка/i)).toBeInTheDocument();
    });

    test('should show validation error for weak password from backend (400)', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockRejectedValue({
        response: {
          status: 400,
          data: { new_password: ['Password is too weak'] },
        },
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'ValidPass1'); // Passes client validation
      await user.type(confirmPasswordInput, 'ValidPass1');
      await user.click(submitButton);

      expect(await screen.findByText(/password is too weak/i)).toBeInTheDocument();
    });

    test('should show generic error for other API errors', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockRejectedValue({
        response: { status: 500 },
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      expect(await screen.findByText(/произошла ошибка. попробуйте позже./i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    beforeEach(() => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });
    });

    test('should show loading state during password reset submission', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(() => resolve({ detail: 'Password has been reset successfully.' }), 100)
          )
      );

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      // Button should be disabled and show loading text
      expect(submitButton).toBeDisabled();
      expect(submitButton).toHaveTextContent(/сброс пароля.../i);

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalled();
      });
    });

    test('should disable form inputs during submission', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(() => resolve({ detail: 'Password has been reset successfully.' }), 100)
          )
      );

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = (await screen.findByLabelText(/новый пароль/i)) as HTMLInputElement;
      const confirmPasswordInput = screen.getByLabelText(
        /подтверждение пароля/i
      ) as HTMLInputElement;
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      // Both inputs should be disabled during submission
      expect(passwordInput).toBeDisabled();
      expect(confirmPasswordInput).toBeDisabled();

      await waitFor(() => {
        expect(mockReplace).toHaveBeenCalled();
      });
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });
    });

    test('should have proper labels for password inputs', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);

      expect(passwordInput).toHaveAccessibleName();
      expect(confirmPasswordInput).toHaveAccessibleName();
    });

    test('should have aria-required on password fields', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);

      expect(passwordInput).toHaveAttribute('aria-required', 'true');
      expect(confirmPasswordInput).toHaveAttribute('aria-required', 'true');
    });

    test('should have aria-describedby for error messages', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'short');
      await user.click(submitButton);

      // Password field should have aria-describedby when error appears
      await waitFor(() => {
        expect(passwordInput).toHaveAttribute('aria-describedby');
      });
    });

    test('should have role="alert" for error messages', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      const mockConfirmPasswordReset = vi.mocked(authService.confirmPasswordReset);
      mockValidateResetToken.mockResolvedValue({ valid: true });
      mockConfirmPasswordReset.mockRejectedValue({
        response: { status: 500 },
      });

      const user = userEvent.setup();
      render(<PasswordResetConfirmForm {...defaultProps} />);

      const passwordInput = await screen.findByLabelText(/новый пароль/i);
      const confirmPasswordInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', {
        name: /сбросить пароль/i,
      });

      await user.type(passwordInput, 'NewSecurePass123');
      await user.type(confirmPasswordInput, 'NewSecurePass123');
      await user.click(submitButton);

      const errorElement = await screen.findByRole('alert');
      expect(errorElement).toBeInTheDocument();
    });

    test('should have aria-label on submit button', async () => {
      const mockValidateResetToken = vi.mocked(authService.validateResetToken);
      mockValidateResetToken.mockResolvedValue({ valid: true });

      render(<PasswordResetConfirmForm {...defaultProps} />);

      const submitButton = await screen.findByRole('button', {
        name: /сбросить пароль/i,
      });
      expect(submitButton).toHaveAttribute('aria-label');
    });
  });
});
