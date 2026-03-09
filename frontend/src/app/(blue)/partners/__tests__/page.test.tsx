/**
 * Unit тесты для страницы "Партнёрам" (/partners)
 * Story 19.4 - Task 10
 */

import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import PartnersPage from '../page';

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('PartnersPage', () => {
  it('renders breadcrumb navigation', () => {
    render(<PartnersPage />);

    expect(screen.getByText('Главная')).toBeInTheDocument();
    expect(screen.getByText('Партнёрам')).toBeInTheDocument();
  });

  it('renders hero section with title and description', () => {
    render(<PartnersPage />);

    expect(
      screen.getByRole('heading', { level: 1, name: /условия сотрудничества/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/выстраиваем долгосрочные партнёрские отношения/i)).toBeInTheDocument();
  });

  it('renders 6 client type cards', () => {
    render(<PartnersPage />);

    // Проверяем наличие всех типов клиентов
    expect(screen.getByText('Спортивные магазины')).toBeInTheDocument();
    expect(screen.getByText('Интернет-магазины')).toBeInTheDocument();
    expect(screen.getByText('Тренеры')).toBeInTheDocument();
    expect(screen.getByText('Фитнес-клубы')).toBeInTheDocument();
    expect(screen.getByText('Федерации')).toBeInTheDocument();
    expect(screen.getByText('Школы и ДЮСШ')).toBeInTheDocument();
  });

  it('renders process steps section', () => {
    render(<PartnersPage />);

    expect(
      screen.getByRole('heading', { level: 2, name: /как начать сотрудничество/i })
    ).toBeInTheDocument();
    expect(screen.getByText('Подайте заявку')).toBeInTheDocument();
    expect(screen.getByText('Получите доступ')).toBeInTheDocument();
    expect(screen.getByText('Работайте с менеджером')).toBeInTheDocument();
  });

  it('renders info panel about personal manager', () => {
    render(<PartnersPage />);

    expect(screen.getByText('Персональный менеджер')).toBeInTheDocument();
    expect(
      screen.getByText(/на всех этапах сотрудничества с вами работает персональный менеджер/i)
    ).toBeInTheDocument();
  });

  it('renders complaints and returns section', () => {
    render(<PartnersPage />);

    expect(
      screen.getByRole('heading', { level: 2, name: /рекламации и возвраты/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/при недовложении или пересортице необходимо/i)).toBeInTheDocument();
  });

  it('renders accordion with FAQ items', () => {
    render(<PartnersPage />);

    expect(
      screen.getByRole('heading', { level: 2, name: /часто задаваемые вопросы/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/какие документы нужны для сотрудничества/i)).toBeInTheDocument();
    expect(screen.getByText(/как происходит оплата/i)).toBeInTheDocument();
    expect(screen.getByText(/есть ли минимальная сумма заказа/i)).toBeInTheDocument();
    expect(screen.getByText(/работаете ли вы с эдо/i)).toBeInTheDocument();
  });

  it('renders CTA button with correct link', () => {
    render(<PartnersPage />);

    const registerButton = screen.getByRole('link', { name: /зарегистрироваться/i });
    expect(registerButton).toBeInTheDocument();
    expect(registerButton).toHaveAttribute('href', '/register?from=partners');
  });

  it('renders login link in CTA section', () => {
    render(<PartnersPage />);

    expect(screen.getByText(/уже есть аккаунт/i)).toBeInTheDocument();
    const loginLink = screen.getByRole('link', { name: /войти/i });
    expect(loginLink).toBeInTheDocument();
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  it('has all sections with proper structure', () => {
    render(<PartnersPage />);

    // Проверяем что все основные секции присутствуют
    const sections = screen.getAllByRole('region', { hidden: true });
    expect(sections.length).toBeGreaterThan(0);

    // Проверяем что заголовки h2 присутствуют для всех секций
    const headings = screen.getAllByRole('heading', { level: 2 });
    expect(headings.length).toBeGreaterThanOrEqual(5);
  });
});
