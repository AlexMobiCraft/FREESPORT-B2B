/**
 * B2BRegisterForm Component Tests
 * Story 28.2 - Поток регистрации B2B
 *
 * Tests для компонента формы B2B регистрации
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { B2BRegisterForm } from '@/components/auth/B2BRegisterForm';

// Mock authService
vi.mock('@/services/authService', () => ({
  default: {
    registerB2B: vi.fn(),
    refreshToken: vi.fn().mockResolvedValue({}),
  },
}));

// Mock useRouter
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: mockPush,
  }),
}));

describe('B2BRegisterForm', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render all required fields', () => {
      render(<B2BRegisterForm />);

      expect(screen.getByLabelText(/^имя$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/фамилия/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/телефон/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/название компании/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^инн$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^огрн$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/юридический адрес/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^пароль$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/подтверждение пароля/i)).toBeInTheDocument();
    });

    it('should show B2B information panel', () => {
      render(<B2BRegisterForm />);

      expect(screen.getByText(/регистрация для бизнес-партнеров/i)).toBeInTheDocument();
    });

    it('should render submit button', () => {
      render(<B2BRegisterForm />);

      const submitButton = screen.getByRole('button', { name: /отправить заявку/i });
      expect(submitButton).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper labels for inputs', () => {
      render(<B2BRegisterForm />);

      // Check specific important inputs have labels
      expect(screen.getByLabelText(/^имя$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^email$/i)).toBeInTheDocument();
      expect(screen.getByLabelText(/^инн$/i)).toBeInTheDocument();
    });
  });

  describe('Form Submission', () => {
    it('should submit form and redirect to root on success', async () => {
      const { userEvent } = await import('@testing-library/user-event');
      const authService = (await import('@/services/authService')).default;
      const user = userEvent.setup();

      vi.mocked(authService.registerB2B).mockResolvedValue({
        access: 'token',
        refresh: 'refresh',
        user: {
          id: 1,
          email: 'b2b@example.com',
          first_name: 'B2B',
          role: 'wholesale_level1',
          is_verified: true, // Auto-verified for immediate redirect test
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
        } as any,
      });

      render(<B2BRegisterForm />);

      await user.type(screen.getByLabelText(/^имя$/i), 'Иван');
      await user.type(screen.getByLabelText(/фамилия/i), 'Петров');
      await user.type(screen.getByLabelText(/^email$/i), 'b2b@example.com');
      await user.type(screen.getByLabelText(/телефон/i), '+79991234567');
      await user.type(screen.getByLabelText(/название компании/i), 'ООО Тест');
      await user.type(screen.getByLabelText(/^инн$/i), '1234567890');
      await user.type(screen.getByLabelText(/^огрн$/i), '1234567890123');
      await user.type(
        screen.getByLabelText(/юридический адрес/i),
        'г. Москва, ул. Примерная, д. 1'
      );
      await user.type(screen.getByLabelText(/^пароль$/i), 'SecurePass123');
      await user.type(screen.getByLabelText(/подтверждение пароля/i), 'SecurePass123');

      const submitButton = screen.getByRole('button', { name: /отправить заявку/i });
      await user.click(submitButton);

      await waitFor(
        () => {
          expect(mockPush).toHaveBeenCalledWith('/');
        },
        { timeout: 2000 }
      );
    });
  });
});
