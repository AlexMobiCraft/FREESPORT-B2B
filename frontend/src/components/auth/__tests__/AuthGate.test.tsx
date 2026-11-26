import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { AuthGate } from '../AuthGate';

const mockUseAuth = vi.fn();
vi.mock('@/providers/AuthProvider', () => ({
  useAuth: () => mockUseAuth(),
}));

describe('AuthGate', () => {
  it('до восстановления сессии показывает спиннер вместо содержимого', () => {
    mockUseAuth.mockReturnValue({ isInitialized: false, isLoading: true });
    render(
      <AuthGate>
        <div data-testid="cabinet">Кабинет</div>
      </AuthGate>
    );

    expect(screen.getByRole('status')).toHaveTextContent('Загрузка...');
    expect(screen.queryByTestId('cabinet')).not.toBeInTheDocument();
  });

  it('после восстановления сессии показывает содержимое', () => {
    mockUseAuth.mockReturnValue({ isInitialized: true, isLoading: false });
    render(
      <AuthGate>
        <div data-testid="cabinet">Кабинет</div>
      </AuthGate>
    );

    expect(screen.getByTestId('cabinet')).toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });
});
