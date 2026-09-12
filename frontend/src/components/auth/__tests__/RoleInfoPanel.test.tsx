/**
 * RoleInfoPanel Component Tests
 * Story 29.1 - Role Selection UI & Warnings
 *
 * Тесты для информационной панели B2B ролей
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RoleInfoPanel } from '../RoleInfoPanel';

describe('RoleInfoPanel', () => {
  // AC 3: Панель не отображается когда visible=false
  it('should not render when visible is false', () => {
    const { container } = render(<RoleInfoPanel visible={false} />);
    expect(container.firstChild).toBeNull();
  });

  // AC 3: Панель отображается когда visible=true
  it('should render when visible is true', () => {
    render(<RoleInfoPanel visible={true} />);
    const alert = screen.getByRole('alert');
    expect(alert).toBeInTheDocument();
  });

  // AC 3: Проверяем все три информационных сообщения
  it('should display all three information messages', () => {
    render(<RoleInfoPanel visible={true} />);

    expect(screen.getByText(/заполнить дополнительные данные/i)).toBeInTheDocument();
    expect(screen.getByText(/после проверки администратором/i)).toBeInTheDocument();
    expect(screen.getByText(/получите уведомление на email/i)).toBeInTheDocument();
  });

  // AC 6: Проверяем accessibility атрибуты
  it('should have correct accessibility attributes', () => {
    render(<RoleInfoPanel visible={true} />);
    const alert = screen.getByRole('alert');

    expect(alert).toHaveAttribute('role', 'alert');
    expect(alert).toHaveAttribute('aria-live', 'polite');
  });

  // AC 7: Проверяем стилизацию согласно Design System (warning colors)
  it('should have warning color styles from design system', () => {
    render(<RoleInfoPanel visible={true} />);
    const alert = screen.getByRole('alert');

    // Проверяем наличие классов для warning цветов
    expect(alert).toHaveClass('bg-[var(--color-warning-50)]');
    expect(alert).toHaveClass('border-[var(--color-warning-300)]');
  });
});
