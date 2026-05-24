/**
 * RegisterForm Component Tests
 * Story 28.1 - Task 4.3
 *
 * Component тесты для RegisterForm с использованием Vitest + RTL + MSW
 *
 * AC 9: Component Tests для RegisterForm
 */

import { describe, test, expect, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { RegisterForm } from '../RegisterForm';
import authService from '@/services/authService';

const PDP_CONSENT_NAME =
  'Я даю согласие на обработку моих персональных данных в соответствии с ' +
  '«Политикой обработки персональных данных ООО „Фриспорт“»';
const PDP_CONSENT_POLICY_LINK_NAME = '«Политикой обработки персональных данных ООО „Фриспорт“»';

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
    register: vi.fn(),
  },
}));

describe('RegisterForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPush.mockClear();
  });

  const acceptPdpConsent = async (user: ReturnType<typeof userEvent.setup>) => {
    await user.click(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME }));
  };

  const getMarketingConsent = () =>
    screen.getByRole('checkbox', {
      name: /получать рекламные и информационные рассылки от ооо/i,
    });

  describe('Rendering', () => {
    test('should render all form fields', () => {
      render(<RegisterForm />);

      expect(screen.getByLabelText(/имя/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/электронная почта/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^пароль$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/подтверждение пароля/i)).toBeInTheDocument();
      expect(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME })).toBeInTheDocument();
      expect(getMarketingConsent()).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /зарегистрироваться/i })).toBeInTheDocument();
    });

    test('should render native privacy policy link next to clickable pdp consent label text', async () => {
      const user = userEvent.setup();
      const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null);
      render(<RegisterForm />);

      const pdpCheckbox = screen.getByRole('checkbox', {
        name: PDP_CONSENT_NAME,
      });
      const link = screen.getByRole('link', {
        name: PDP_CONSENT_POLICY_LINK_NAME,
      });
      expect(link).toHaveAttribute('href', '/privacy-policy');
      expect(link).toHaveAttribute('target', '_blank');
      expect(link).toHaveAttribute('rel', 'noopener noreferrer');
      expect(link.closest('label')).toBeNull();
      const label = document.querySelector('label[for="register-pdp-consent"]');
      expect(label).not.toBeNull();

      await user.click(label!);
      expect(pdpCheckbox).toBeChecked();

      link.addEventListener('click', event => event.preventDefault(), { once: true });
      fireEvent.click(link, { ctrlKey: true });
      expect(pdpCheckbox).toBeChecked();
      expect(openSpy).not.toHaveBeenCalled();
      openSpy.mockRestore();
    });

    test('should render marketing consent unchecked by default', () => {
      render(<RegisterForm />);

      expect(getMarketingConsent()).not.toBeChecked();
    });

    test('should keep optional marketing checkbox without inline error state', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const marketingConsent = getMarketingConsent();
      expect(marketingConsent).not.toHaveAttribute('aria-invalid');
      expect(marketingConsent).not.toHaveAttribute('aria-describedby');

      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      expect(marketingConsent).not.toHaveAttribute('aria-invalid');
      expect(marketingConsent).not.toHaveAttribute('aria-describedby');
    });

    test('should have proper autocomplete attributes', () => {
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);

      expect(nameInput).toHaveAttribute('autocomplete', 'given-name');
      expect(emailInput).toHaveAttribute('autocomplete', 'email');
      expect(passwordInput).toHaveAttribute('autocomplete', 'new-password');
      expect(confirmInput).toHaveAttribute('autocomplete', 'new-password');
    });

    test('should show password helper text', () => {
      render(<RegisterForm />);

      expect(
        screen.getByText(/минимум 8 символов, 1 цифра и 1 заглавная буква/i)
      ).toBeInTheDocument();
    });
  });

  describe('Client-side Validation', () => {
    test('should show validation error for empty first name', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });
      await user.click(submitButton);

      expect(await screen.findByText(/имя обязательно/i)).toBeInTheDocument();
    });

    test('should show validation error for invalid email', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      // Browser type="email" blocks 'invalid-email' format from submitting
      // We verify the form doesn't submit (authService not called) when email is invalid
      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'invalid-email');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await user.click(submitButton);

      // With browser native validation blocking, authService should NOT be called
      await waitFor(() => {
        expect(mockRegister).not.toHaveBeenCalled();
      });
    });

    test('should show validation error when passwords do not match', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'ivan@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'DifferentPass456');
      await user.click(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME }));
      await user.click(submitButton);

      expect(await screen.findByText(/пароли не совпадают/i)).toBeInTheDocument();
    });

    test('should show validation error for password without digit', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'ivan@example.com');
      await user.type(passwordInput, 'NoDigitsHere');
      await user.type(confirmInput, 'NoDigitsHere');
      await user.click(submitButton);

      expect(await screen.findByText(/хотя бы 1 цифру/i)).toBeInTheDocument();
    });

    test('should show validation error for password without uppercase', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'ivan@example.com');
      await user.type(passwordInput, 'nouppercase123');
      await user.type(confirmInput, 'nouppercase123');
      await user.click(submitButton);

      expect(await screen.findByText(/хотя бы 1 заглавную букву/i)).toBeInTheDocument();
    });

    test('should block submit without pdp consent', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Иван');
      await user.type(screen.getByLabelText(/электронная почта/i), 'ivan@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      expect(
        (await screen.findAllByText(/необходимо согласие на обработку персональных данных/i))
          .length
      ).toBeGreaterThan(0);
      expect(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME })).toHaveAttribute(
        'aria-invalid',
        'true'
      );
      expect(mockRegister).not.toHaveBeenCalled();
    });
  });

  describe('Form Submission', () => {
    test('should submit form with valid data', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'newuser@example.com',
          first_name: 'Новый',
          last_name: '',
          phone: '',
          role: 'retail',
          is_verified: false,
        },
      });

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Новый');
      await user.type(emailInput, 'newuser@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith({
          email: 'newuser@example.com',
          password: 'SecurePass123',
          password_confirm: 'SecurePass123',
          first_name: 'Новый',
          last_name: '',
          phone: '',
          role: 'retail',
          company_name: undefined,
          tax_id: undefined,
          pdp_consent: true,
          marketing_consent: false,
        });
      });

      // Should redirect to root after successful registration
      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/');
      });
    });

    test('should call onSuccess callback after successful registration', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      const mockOnSuccess = vi.fn();

      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'newuser@example.com',
          first_name: 'Новый',
          last_name: '',
          phone: '',
          role: 'retail',
          is_verified: false,
        },
      });

      render(<RegisterForm onSuccess={mockOnSuccess} />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Новый');
      await user.type(emailInput, 'newuser@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockOnSuccess).toHaveBeenCalled();
      });
    });

    test('should redirect to redirectUrl when provided', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'user@example.com',
          first_name: 'Test',
          role: 'retail',
          is_verified: true,
          last_name: '',
          phone: '',
        },
      });

      render(<RegisterForm redirectUrl="/custom/path" />);

      await user.type(screen.getByLabelText(/имя/i), 'Test');
      await user.type(screen.getByLabelText(/электронная почта/i), 'test@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      await waitFor(() => {
        expect(mockPush).toHaveBeenCalledWith('/custom/path');
      });
    });

    test('should submit with marketing_consent false when unchecked', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'marketing-false@example.com',
          first_name: 'Marketing',
          last_name: '',
          phone: '',
          role: 'retail',
          is_verified: true,
        },
      });

      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Marketing');
      await user.type(screen.getByLabelText(/электронная почта/i), 'marketing-false@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          expect.objectContaining({
            pdp_consent: true,
            marketing_consent: false,
          })
        );
      });
    });

    test('should submit with marketing_consent true when checked', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'marketing-true@example.com',
          first_name: 'Marketing',
          last_name: '',
          phone: '',
          role: 'retail',
          is_verified: true,
        },
      });

      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Marketing');
      await user.type(screen.getByLabelText(/электронная почта/i), 'marketing-true@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(getMarketingConsent());
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          expect.objectContaining({
            pdp_consent: true,
            marketing_consent: true,
          })
        );
      });
    });
  });

  describe('Error Handling', () => {
    test('should display API error on 409 Conflict (existing email)', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      // Return empty email array so component uses Russian fallback message
      mockRegister.mockRejectedValue({
        response: {
          status: 409,
          data: { email: [] },
        },
      });

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Существующий');
      await user.type(emailInput, 'existing@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      // First verify the API was called
      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalled();
      });

      // Then wait for error message to appear with longer timeout
      expect(
        await screen.findByText(/пользователь с таким email уже существует/i, {}, { timeout: 3000 })
      ).toBeInTheDocument();
    });

    test('should display API error on 400 Bad Request (weak password)', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockRejectedValue({
        response: {
          status: 400,
          data: { password: ['Password is too weak'] },
        },
      });

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'ivan@example.com');
      await user.type(passwordInput, 'WeakPass1');
      await user.type(confirmInput, 'WeakPass1');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      expect((await screen.findAllByText(/password is too weak/i)).length).toBeGreaterThan(0);
    });

    test('should display backend pdp consent validation error inline', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockRejectedValue({
        response: {
          status: 400,
          data: { pdp_consent: ['Необходимо согласие на обработку персональных данных.'] },
        },
      });

      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Иван');
      await user.type(screen.getByLabelText(/электронная почта/i), 'ivan@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      expect(
        (await screen.findAllByText(/необходимо согласие на обработку персональных данных/i))
          .length
      ).toBeGreaterThan(0);
      expect(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME })).toHaveAccessibleDescription(
        /необходимо согласие на обработку персональных данных/i
      );
      expect(screen.getByRole('checkbox', { name: PDP_CONSENT_NAME })).toHaveAttribute(
        'aria-invalid',
        'true'
      );
    });

    test('should display backend email validation error inline', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockRejectedValue({
        response: {
          status: 400,
          data: { email: ['Пользователь с таким email уже существует.'] },
        },
      });

      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Иван');
      await user.type(screen.getByLabelText(/электронная почта/i), 'ivan@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      const emailInput = screen.getByLabelText(/электронная почта/i);
      expect(
        (await screen.findAllByText(/пользователь с таким email уже существует/i)).length
      ).toBeGreaterThan(0);
      expect(emailInput).toHaveAccessibleDescription(/пользователь с таким email уже существует/i);
      expect(emailInput).toHaveAttribute('aria-invalid', 'true');
    });

    test('should not hang on cyclic backend validation payloads', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      const cyclicPayload: Record<string, unknown> = {};
      cyclicPayload.self = cyclicPayload;
      mockRegister.mockRejectedValue({
        response: {
          status: 400,
          data: {
            nested: cyclicPayload,
            email: ['Email from backend'],
          },
        },
      });

      render(<RegisterForm />);

      await user.type(screen.getByLabelText(/имя/i), 'Иван');
      await user.type(screen.getByLabelText(/электронная почта/i), 'ivan@example.com');
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(screen.getByRole('button', { name: /зарегистрироваться/i }));

      expect((await screen.findAllByText(/email from backend/i)).length).toBeGreaterThan(0);
    });

    test('should display API error on 500 Internal Server Error', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockRejectedValue({
        response: {
          status: 500,
          data: { detail: 'Internal server error' },
        },
      });

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Иван');
      await user.type(emailInput, 'ivan@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      expect(await screen.findByText(/ошибка сервера/i)).toBeInTheDocument();
    });
  });

  describe('Loading State', () => {
    test('should show loading state during submission', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);

      mockRegister.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(
              () =>
                resolve({
                  access: 'token',
                  refresh: 'refresh',
                  user: {
                    id: 2,
                    email: 'test@example.com',
                    first_name: 'Test',
                    last_name: '',
                    phone: '',
                    role: 'retail',
                    is_verified: false,
                  },
                }),
              100
            )
          )
      );

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Test');
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      // Button should be disabled during submission
      expect(submitButton).toBeDisabled();

      await waitFor(() => {
        expect(submitButton).not.toBeDisabled();
      });
    });

    test('should disable form inputs during submission', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);

      mockRegister.mockImplementation(
        () =>
          new Promise(resolve =>
            setTimeout(
              () =>
                resolve({
                  access: 'token',
                  refresh: 'refresh',
                  user: {
                    id: 2,
                    email: 'test@example.com',
                    first_name: 'Test',
                    last_name: '',
                    phone: '',
                    role: 'retail',
                    is_verified: false,
                  },
                }),
              100
            )
          )
      );

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i) as HTMLInputElement;
      const emailInput = screen.getByLabelText(/электронная почта/i) as HTMLInputElement;
      const passwordInput = screen.getByLabelText(/^пароль$/i) as HTMLInputElement;
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i) as HTMLInputElement;
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Test');
      await user.type(emailInput, 'test@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      // All inputs should be disabled during submission
      expect(nameInput).toBeDisabled();
      expect(emailInput).toBeDisabled();
      expect(passwordInput).toBeDisabled();
      expect(confirmInput).toBeDisabled();

      await waitFor(() => {
        expect(nameInput).not.toBeDisabled();
      });
    });
  });

  describe('Accessibility', () => {
    test('should have proper labels for all inputs', () => {
      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);

      expect(nameInput).toHaveAccessibleName();
      expect(emailInput).toHaveAccessibleName();
      expect(passwordInput).toHaveAccessibleName();
      expect(confirmInput).toHaveAccessibleName();
    });

    test('should have role="alert" for error message container', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockRejectedValue({
        response: {
          status: 409,
          data: { email: ['User with this email already exists'] },
        },
      });

      render(<RegisterForm />);

      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.type(nameInput, 'Test');
      await user.type(emailInput, 'existing@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      const alert = await screen.findByRole('alert');
      expect(alert).toBeInTheDocument();
    });
  });

  // Story 29.1: Role Selection UI & Warnings Tests
  describe('Role Selection (Story 29.1)', () => {
    // AC 1, 2: Role field with 4 options and retail default
    test('should have role selector with retail selected by default', () => {
      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i) as HTMLSelectElement;
      expect(roleSelect).toBeInTheDocument();
      expect(roleSelect.value).toBe('retail');

      // AC 1: Should have all 4 role options
      const options = Array.from(roleSelect.options).map(opt => opt.value);
      expect(options).toContain('retail');
      expect(options).toContain('trainer');
      expect(options).toContain('wholesale_level1');
      expect(options).toContain('federation_rep');
    });

    // AC 3: InfoPanel appears when B2B role is selected
    test('should show InfoPanel when B2B role is selected', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i);

      // Initially retail, InfoPanel should not be visible
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();

      // Select trainer (B2B role)
      await user.selectOptions(roleSelect, 'trainer');

      // InfoPanel should now be visible
      const infoPanels = screen.getAllByRole('alert');
      const infoPanel = infoPanels.find(el =>
        el.textContent?.includes('заполнить дополнительные данные')
      );
      expect(infoPanel).toBeInTheDocument();
      expect(screen.getByText(/после проверки администратором/i)).toBeInTheDocument();
    });

    // AC 8: company_name field appears for B2B roles
    test('should show company_name field for B2B roles', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i);

      // Initially retail, company_name should not be visible
      expect(screen.queryByLabelText(/название компании/i)).not.toBeInTheDocument();

      // Select wholesale (B2B role)
      await user.selectOptions(roleSelect, 'wholesale_level1');

      // company_name should now be visible
      expect(screen.getByLabelText(/название компании/i)).toBeInTheDocument();
    });

    // AC 8: tax_id field appears for wholesale and federation_rep
    test('should show tax_id field for wholesale and federation roles', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i);

      // Initially retail, tax_id should not be visible
      expect(screen.queryByLabelText(/инн/i)).not.toBeInTheDocument();

      // Select wholesale_level1
      await user.selectOptions(roleSelect, 'wholesale_level1');
      expect(screen.getByLabelText(/инн/i)).toBeInTheDocument();

      // Select federation_rep
      await user.selectOptions(roleSelect, 'federation_rep');
      expect(screen.getByLabelText(/инн/i)).toBeInTheDocument();

      // Select trainer - tax_id should NOT be visible
      await user.selectOptions(roleSelect, 'trainer');
      expect(screen.queryByLabelText(/инн/i)).not.toBeInTheDocument();
    });

    // AC 4: Form submits with selected role
    test('should submit form with selected role', async () => {
      const user = userEvent.setup();
      const mockRegister = vi.mocked(authService.register);
      mockRegister.mockResolvedValue({
        access: 'mock-token',
        refresh: 'mock-refresh',
        user: {
          id: 2,
          email: 'trainer@example.com',
          first_name: 'Тренер',
          last_name: '',
          phone: '',
          role: 'trainer',
          company_name: 'Спортклуб',
          is_verified: false,
        },
      });

      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i);
      const nameInput = screen.getByLabelText(/имя/i);
      const emailInput = screen.getByLabelText(/электронная почта/i);
      const passwordInput = screen.getByLabelText(/^пароль$/i);
      const confirmInput = screen.getByLabelText(/подтверждение пароля/i);
      const submitButton = screen.getByRole('button', { name: /зарегистрироваться/i });

      await user.selectOptions(roleSelect, 'trainer');

      // Fill company_name (appears for B2B roles)
      const companyInput = await screen.findByLabelText(/название компании/i);
      await user.type(companyInput, 'Спортклуб');

      await user.type(nameInput, 'Тренер');
      await user.type(emailInput, 'trainer@example.com');
      await user.type(passwordInput, 'SecurePass123');
      await user.type(confirmInput, 'SecurePass123');
      await acceptPdpConsent(user);
      await user.click(submitButton);

      await waitFor(() => {
        expect(mockRegister).toHaveBeenCalledWith(
          expect.objectContaining({
            role: 'trainer',
            company_name: 'Спортклуб',
          })
        );
      });
    });

    // AC 8: Validation for required B2B fields (covered by submit test above + Zod schema tests)

    // AC 5: Role selector keyboard navigation
    test('should support keyboard navigation for role selector', async () => {
      const user = userEvent.setup();
      render(<RegisterForm />);

      const roleSelect = screen.getByLabelText(/тип аккаунта/i);

      // Focus on select
      await user.tab(); // Skip to first input (name)
      await user.tab(); // Skip to email
      await user.tab(); // Skip to role select
      expect(roleSelect).toHaveFocus();

      // Use arrow keys to change selection (browser default behavior)
      // This is natively supported by <select>, just verify it's focusable
      expect(roleSelect).toBeEnabled();
    });
  });
});
