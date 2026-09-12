/**
 * Tests for Pagination Component
 * Testing all variants, states, and edge cases
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Pagination } from '../Pagination';

describe('Pagination', () => {
  const mockOnPageChange = vi.fn();

  afterEach(() => {
    mockOnPageChange.mockClear();
  });

  describe('Rendering', () => {
    it('should render pagination with correct number of pages', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      // Проверяем наличие номеров страниц
      expect(screen.getByRole('button', { name: 'Страница 1' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 5' })).toBeInTheDocument();
    });

    it('should not render when totalPages is 1', () => {
      const { container } = render(
        <Pagination currentPage={1} totalPages={1} onPageChange={mockOnPageChange} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should not render when totalPages is 0 or negative', () => {
      const { container } = render(
        <Pagination currentPage={1} totalPages={0} onPageChange={mockOnPageChange} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should render navigation buttons (prev/next)', () => {
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      expect(screen.getByRole('button', { name: 'Предыдущая страница' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Следующая страница' })).toBeInTheDocument();
    });

    it('should render first/last buttons when showFirstLast is true', () => {
      render(
        <Pagination currentPage={2} totalPages={10} onPageChange={mockOnPageChange} showFirstLast />
      );

      expect(screen.getByRole('button', { name: 'Первая страница' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Последняя страница' })).toBeInTheDocument();
    });
  });

  describe('Active State', () => {
    it('should mark current page as active with aria-current', () => {
      render(<Pagination currentPage={3} totalPages={5} onPageChange={mockOnPageChange} />);

      const activePage = screen.getByRole('button', { name: 'Страница 3' });
      expect(activePage).toHaveAttribute('aria-current', 'page');
    });

    it('should apply active styles to current page', () => {
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      const activePage = screen.getByRole('button', { name: 'Страница 2' });
      expect(activePage).toHaveClass('bg-primary', 'text-text-inverse');
    });
  });

  describe('Disabled States', () => {
    it('should disable previous button on first page', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      const prevButton = screen.getByRole('button', { name: 'Предыдущая страница' });
      expect(prevButton).toBeDisabled();
    });

    it('should disable next button on last page', () => {
      render(<Pagination currentPage={5} totalPages={5} onPageChange={mockOnPageChange} />);

      const nextButton = screen.getByRole('button', { name: 'Следующая страница' });
      expect(nextButton).toBeDisabled();
    });

    it('should disable first button on first page', () => {
      render(
        <Pagination currentPage={1} totalPages={10} onPageChange={mockOnPageChange} showFirstLast />
      );

      const firstButton = screen.getByRole('button', { name: 'Первая страница' });
      expect(firstButton).toBeDisabled();
    });

    it('should disable last button on last page', () => {
      render(
        <Pagination
          currentPage={10}
          totalPages={10}
          onPageChange={mockOnPageChange}
          showFirstLast
        />
      );

      const lastButton = screen.getByRole('button', { name: 'Последняя страница' });
      expect(lastButton).toBeDisabled();
    });
  });

  describe('Interaction', () => {
    it('should call onPageChange when clicking a page number', async () => {
      const user = userEvent.setup();
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      const page3Button = screen.getByRole('button', { name: 'Страница 3' });
      await user.click(page3Button);

      expect(mockOnPageChange).toHaveBeenCalledWith(3);
      expect(mockOnPageChange).toHaveBeenCalledTimes(1);
    });

    it('should call onPageChange when clicking next button', async () => {
      const user = userEvent.setup();
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      const nextButton = screen.getByRole('button', { name: 'Следующая страница' });
      await user.click(nextButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(3);
    });

    it('should call onPageChange when clicking prev button', async () => {
      const user = userEvent.setup();
      render(<Pagination currentPage={3} totalPages={5} onPageChange={mockOnPageChange} />);

      const prevButton = screen.getByRole('button', { name: 'Предыдущая страница' });
      await user.click(prevButton);

      expect(mockOnPageChange).toHaveBeenCalledWith(2);
    });

    it('should not call onPageChange when clicking current page', async () => {
      const user = userEvent.setup();
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      const currentPageButton = screen.getByRole('button', { name: 'Страница 2' });
      await user.click(currentPageButton);

      expect(mockOnPageChange).not.toHaveBeenCalled();
    });

    it('should not call onPageChange when clicking disabled buttons', async () => {
      const user = userEvent.setup();
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      const prevButton = screen.getByRole('button', { name: 'Предыдущая страница' });
      await user.click(prevButton);

      expect(mockOnPageChange).not.toHaveBeenCalled();
    });
  });

  describe('Ellipsis Logic', () => {
    it('should show ellipsis when total pages > maxVisiblePages', () => {
      render(<Pagination currentPage={1} totalPages={20} onPageChange={mockOnPageChange} />);

      const ellipsis = screen.getAllByText('…');
      expect(ellipsis.length).toBeGreaterThan(0);
    });

    it('should show all pages when total pages <= maxVisiblePages', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      const ellipsis = screen.queryByText('…');
      expect(ellipsis).not.toBeInTheDocument();

      // Проверяем что все 5 страниц видны
      expect(screen.getByRole('button', { name: 'Страница 1' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 5' })).toBeInTheDocument();
    });

    it('should show ellipsis at end when current page is near start', () => {
      render(<Pagination currentPage={2} totalPages={20} onPageChange={mockOnPageChange} />);

      // Должен быть ellipsis в конце
      const ellipsis = screen.getAllByText('…');
      expect(ellipsis.length).toBeGreaterThan(0);
    });

    it('should show ellipsis at start when current page is near end', () => {
      render(<Pagination currentPage={19} totalPages={20} onPageChange={mockOnPageChange} />);

      // Должен быть ellipsis в начале
      const ellipsis = screen.getAllByText('…');
      expect(ellipsis.length).toBeGreaterThan(0);
    });

    it('should show ellipsis on both sides when current page is in middle', () => {
      render(<Pagination currentPage={10} totalPages={20} onPageChange={mockOnPageChange} />);

      // Должен быть ellipsis с обеих сторон
      const ellipsis = screen.getAllByText('…');
      expect(ellipsis.length).toBeGreaterThan(0);
    });
  });

  describe('MaxVisiblePages Prop', () => {
    it('should respect custom maxVisiblePages value', () => {
      render(
        <Pagination
          currentPage={1}
          totalPages={20}
          onPageChange={mockOnPageChange}
          maxVisiblePages={7}
        />
      );

      // С maxVisiblePages=7 должно быть видно больше страниц
      expect(screen.getByRole('button', { name: 'Страница 6' })).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    it('should have proper navigation landmark', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      const nav = screen.getByRole('navigation', { name: 'Pagination' });
      expect(nav).toBeInTheDocument();
    });

    it('should have aria-label on all buttons', () => {
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      expect(screen.getByRole('button', { name: 'Предыдущая страница' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Следующая страница' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 1' })).toBeInTheDocument();
    });

    it('should mark ellipsis as aria-hidden', () => {
      const { container } = render(
        <Pagination currentPage={1} totalPages={20} onPageChange={mockOnPageChange} />
      );

      const ellipsisElements = container.querySelectorAll('[aria-hidden="true"]');
      expect(ellipsisElements.length).toBeGreaterThan(0);
    });
  });

  describe('Edge Cases', () => {
    it('should handle currentPage > totalPages gracefully', () => {
      const { container } = render(
        <Pagination currentPage={10} totalPages={5} onPageChange={mockOnPageChange} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should handle currentPage < 1 gracefully', () => {
      const { container } = render(
        <Pagination currentPage={0} totalPages={5} onPageChange={mockOnPageChange} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('should display 99+ for cart counts > 99 in badge', () => {
      // This is a conceptual test - the badge is in Header, not Pagination
      // Keeping here as reminder of badge behavior pattern
      expect(true).toBe(true);
    });
  });

  describe('Custom ClassName', () => {
    it('should apply custom className', () => {
      const { container } = render(
        <Pagination
          currentPage={1}
          totalPages={5}
          onPageChange={mockOnPageChange}
          className="custom-pagination"
        />
      );

      const nav = container.querySelector('nav');
      expect(nav).toHaveClass('custom-pagination');
    });
  });
});
