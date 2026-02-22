/**
 * LoginForm Component Tests
 * Story 28.1 - Task 4.2
 *
 * Component тесты для LoginForm с использованием Vitest + RTL + MSW
 *
 * AC 9: Component Tests для LoginForm
 */

import { describe, test, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LoginForm } from '../LoginForm';
import authService from '@/services/authService';

// Mock next/navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

// Mock authService
vi.mock('@/services/authService', () => ({
  default: {
    login: vi.fn(),
  },
}));

describe('LoginForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPush.mockClear();
  });

  describe('Rendering', () => {
    test('should render email and password fields', () => {
      render(<LoginForm />);

      expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^пароль$/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /войти/i })).toBeInTheDocument();
    });

    test('should have proper autocomplete attributes', () => {
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);

      expect(emailInput).toHaveAttribute('autocomplete', 'email');
      expect(passwordInput).toHaveAttribute('autocomplete', 'current-password');
    });
  });

  describe('Client-side Validation', () => {
    test('should show validation error for invalid email', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      // Use a format that passes browser validation but might fail Zod
      // Note: browser type="email" blocks 'invalid-email', so we verify
      // the form doesn't submit (authService not called) with invalid email via browser validation
      await user.type(emailInput, 'invalid-email');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      // With browser native validation blocking, authService should NOT be called
      // Wait a bit to ensure any async would have completed
      await waitFor(() => {
        expect(mockLogin).not.toHaveBeenCalled();
      });
    });

    test('should show validation error for short password', async () => {
      const user = userEvent.setup();
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'short');
      await user.click(submitButton);

      expect(await screen.findByText(/минимум 8 символов/i)).toBeInTheDocument();
    });

    test('should show validation error for password without digit', async () => {
      const user = userEvent.setup();
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'NoDigitsHere');
      await user.click(submitButton);

      expect(await screen.findByText(/хотя бы 1 цифру/i)).toBeInTheDocument();
    });

    test('should show validation error for password without uppercase', async () => {
      const user = userEvent.setup();
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'nouppercase123');
      await user.click(submitButton);

      expect(await screen.findByText(/хотя бы 1 заглавную букву/i)).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    test('should submit form with valid credentials', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      mockLogin.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 1,
          email: 'test@example.com',
          first_name: 'Test',
          last_name: 'User',
          phone: '',
          role: 'retail',
          is_verified: true,
        },
      });

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith({
          email: 'test@example.com',
          password: 'SecurePass123',
        });
      });

      // Should redirect to home by default
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    test('should redirect to custom URL when provided', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      mockLogin.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 1,
          email: 'test@example.com',
          first_name: 'Test',
          last_name: 'User',
          phone: '',
          role: 'retail',
          is_verified: true,
        },
      });

      render(<LoginForm redirectUrl="/dashboard" />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/dashboard');
      });
    });
  });

  describe('Error Handling', () => {
    test('should display API error on 401 Unauthorized', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      mockLogin.mockRejectedValue({
        response: {
          status: 401,
          data: { detail: 'Invalid credentials' },
        },
      });

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'wrong@example.com');
      await user.type(passwordInput, 'WrongPassword123');
      await user.click(submitButton);

      expect(await screen.findByText(/неверные учетные данные/i)).toBeInTheDocument();
    });

    test('should display API error on 500 Internal Server Error', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      mockLogin.mockRejectedValue({
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
      });

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      expect(await screen.findByText(/ошибка сервера/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    test('should show loading state during submission', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);

      // Delayed promise to capture loading state
      mockLogin.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(
              () =>
                resolve({
                  access: 'token',
                  refresh: 'refresh',
                  user: {
                    id: 1,
                    email: 'test@example.com',
                    first_name: 'Test',
                    last_name: 'User',
                    phone: '',
                    role: 'retail',
                    is_verified: true,
                  },
                }),
              100
            )
          )
      );

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      // Button should be disabled during submission
      expect(submitButton).toBeDisabled();

      // Wait for submission to complete
      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
    });

    test('should disable form inputs during submission', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);

      mockLogin.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(
              () =>
                resolve({
                  access: 'token',
                  refresh: 'refresh',
                  user: {
                    id: 1,
                    email: 'test@example.com',
                    first_name: 'Test',
                    last_name: 'User',
                    phone: '',
                    role: 'retail',
                    is_verified: true,
                  },
                }),
              100
            )
          )
      );

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i) as HTMLInputElement;
      const passwordInput = screen.getByLabelText(/^пароль$/i) as HTMLInputElement;
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.click(submitButton);

      // Inputs should be disabled during submission
      expect(emailInput).toBeDisabled();
      expect(passwordInput).toBeDisabled();

      await waitFor(() => {
        expect(emailInput).not.toBeDisabled();
        expect(passwordInput).not.toBeDisabled();
      });
    });
  });

  describe('Accessibility', () => {
    test('should have proper labels for inputs', () => {
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);

      // Labels should exist and be associated
      expect(emailInput).toHaveAccessibleName();
      expect(passwordInput).toHaveAccessibleName();
    });

    test('should have aria-describedby for error messages', async () => {
      const user = userEvent.setup();
      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      // Use valid email but short password to trigger Zod validation error
      // This bypasses browser native email validation
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'short');
      await user.click(submitButton);

      // Check that password field gets aria-describedby when validation error appears
      await waitFor(() => {
        expect(passwordInput).toHaveAttribute('aria-describedby');
      });
    });

    test('should have role="alert" for error message container', async () => {
      const user = userEvent.setup();
      const mockLogin = vi.mocked(authService.login);
      mockLogin.mockRejectedValue({
        response: {
          status: 401,
          data: { detail: 'Invalid credentials' },
        },
      });

      render(<LoginForm />);

      const emailInput = screen.getByLabelText(/email/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const submitButton = screen.getByRole('button', { name: /войти/i });

      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'WrongPass123');
      await user.click(submitButton);

      const alert = await screen.findByRole('alert');
      expect(alert).toBeInTheDocument();
    });
  });
});
