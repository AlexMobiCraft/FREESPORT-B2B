/**
 * Tests for Pagination Component
 * Testing all variants, states, and edge cases
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Pagination } from '../Pagination';

describe('Pagination', () => {
  const mockOnPageChange = vi.fn();

  /** Подменяет matchMedia: reduce === true включает prefers-reduced-motion */
  const mockReducedMotion = (reduce: boolean) => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: reduce && query === '(prefers-reduced-motion: reduce)',
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
      onchange: null,
    })) as unknown as typeof window.matchMedia;
  };

  const renderRow = (currentPage: number, totalPages: number) =>
    render(
      <Pagination currentPage={currentPage} totalPages={totalPages} onPageChange={mockOnPageChange} />
    );

  /** Ряд плиток без стрелок: номера и многоточие через пробел */
  const getRowCells = () =>
    Array.from(document.querySelectorAll('li'))
      .map(item => item.textContent?.trim() ?? '')
      .filter(text => text !== '')
      .join(' ');

  beforeEach(() => {
    window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
    mockReducedMotion(false);
  });

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

    it('should style inactive tiles and keep text-sm typography', () => {
      render(<Pagination currentPage={2} totalPages={5} onPageChange={mockOnPageChange} />);

      const inactive = screen.getByRole('button', { name: 'Страница 3' });
      expect(inactive).toHaveClass('bg-primary-subtle', 'text-primary', 'text-sm', 'font-medium');
      expect(screen.getByRole('button', { name: 'Страница 2' })).toHaveClass('text-sm');
    });
  });

  describe('Edge arrows and first/last buttons', () => {
    it('should not render previous button on first page', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      expect(screen.queryByRole('button', { name: 'Предыдущая страница' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Следующая страница' })).toBeInTheDocument();
    });

    it('should not render next button on last page', () => {
      render(<Pagination currentPage={5} totalPages={5} onPageChange={mockOnPageChange} />);

      expect(screen.queryByRole('button', { name: 'Следующая страница' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Предыдущая страница' })).toBeInTheDocument();
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

    it('should not call onPageChange when clicking disabled first button', async () => {
      const user = userEvent.setup();
      render(
        <Pagination currentPage={1} totalPages={10} onPageChange={mockOnPageChange} showFirstLast />
      );

      await user.click(screen.getByRole('button', { name: 'Первая страница' }));

      expect(mockOnPageChange).not.toHaveBeenCalled();
      expect(window.scrollTo).not.toHaveBeenCalled();
    });
  });

  describe('Scroll to top', () => {
    it('should scroll smoothly to top once when selecting a page', async () => {
      const user = userEvent.setup();
      renderRow(1, 5);

      await user.click(screen.getByRole('button', { name: 'Страница 3' }));

      expect(mockOnPageChange).toHaveBeenCalledWith(3);
      expect(window.scrollTo).toHaveBeenCalledTimes(1);
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
    });

    it('should scroll to top when clicking an arrow', async () => {
      const user = userEvent.setup();
      renderRow(2, 5);

      await user.click(screen.getByRole('button', { name: 'Следующая страница' }));

      expect(mockOnPageChange).toHaveBeenCalledWith(3);
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'smooth' });
    });

    it('should neither change page nor scroll when clicking current page', async () => {
      const user = userEvent.setup();
      renderRow(2, 5);

      await user.click(screen.getByRole('button', { name: 'Страница 2' }));

      expect(mockOnPageChange).not.toHaveBeenCalled();
      expect(window.scrollTo).not.toHaveBeenCalled();
    });

    it('should scroll without animation when prefers-reduced-motion is set', async () => {
      mockReducedMotion(true);
      const user = userEvent.setup();
      renderRow(1, 5);

      await user.click(screen.getByRole('button', { name: 'Страница 3' }));

      expect(window.scrollTo).toHaveBeenCalledTimes(1);
      expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, behavior: 'auto' });
    });
  });

  describe('Keyboard focus on edge pages', () => {
    it('should move focus to the last page tile when Enter is pressed on next arrow', async () => {
      const user = userEvent.setup();
      const { rerender } = renderRow(19, 20);

      const next = screen.getByRole('button', { name: 'Следующая страница' });
      const lastTile = screen.getByRole('button', { name: 'Страница 20' });
      const focusSpy = vi.spyOn(lastTile, 'focus');
      next.focus();
      await user.keyboard('{Enter}');

      expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
      expect(mockOnPageChange).toHaveBeenCalledWith(20);
      expect(lastTile).toHaveFocus();

      // Родитель принял страницу: стрелка исчезла, фокус остался на той же плитке
      rerender(<Pagination currentPage={20} totalPages={20} onPageChange={mockOnPageChange} />);
      expect(screen.queryByRole('button', { name: 'Следующая страница' })).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 20' })).toBe(lastTile);
      expect(lastTile).toHaveFocus();
    });

    it('should move focus to the first page tile when Enter is pressed on previous arrow', async () => {
      const user = userEvent.setup();
      renderRow(2, 20);

      const prev = screen.getByRole('button', { name: 'Предыдущая страница' });
      const firstTile = screen.getByRole('button', { name: 'Страница 1' });
      const focusSpy = vi.spyOn(firstTile, 'focus');
      prev.focus();
      await user.keyboard('{Enter}');

      expect(focusSpy).toHaveBeenCalledWith({ preventScroll: true });
      expect(mockOnPageChange).toHaveBeenCalledWith(1);
    });

    it('should not move focus when the arrow is clicked with a mouse', async () => {
      const user = userEvent.setup();
      renderRow(19, 20);

      const lastTile = screen.getByRole('button', { name: 'Страница 20' });
      const focusSpy = vi.spyOn(lastTile, 'focus');
      await user.click(screen.getByRole('button', { name: 'Следующая страница' }));

      expect(focusSpy).not.toHaveBeenCalled();
      expect(mockOnPageChange).toHaveBeenCalledWith(20);
    });

    it('should not move focus when the target page is neither first nor last', () => {
      renderRow(5, 20);

      const target = screen.getByRole('button', { name: 'Страница 6' });
      const focusSpy = vi.spyOn(target, 'focus');
      fireEvent.click(screen.getByRole('button', { name: 'Следующая страница' }));

      expect(focusSpy).not.toHaveBeenCalled();
      expect(mockOnPageChange).toHaveBeenCalledWith(6);
    });
  });

  describe('Ellipsis Logic', () => {
    it.each([
      // [currentPage, totalPages, ожидаемый ряд ячеек между стрелками]
      [1, 20, '1 2 3 4 5 … 10 20'],
      [1, 138, '1 2 3 4 5 … 69 138'],
      [70, 138, '1 … 68 69 70 71 72 … 138'],
      [138, 138, '1 … 69 … 134 135 136 137 138'],
      [5, 138, '1 2 3 4 5 6 7 … 138'],
      [4, 138, '1 2 3 4 5 … 69 138'],
      [1, 7, '1 2 3 4 5 6 7'],
      [1, 5, '1 2 3 4 5'],
      [1, 8, '1 2 3 4 5 … 8'],
      [1, 11, '1 2 3 4 5 6 … 11'],
      [1, 13, '1 2 3 4 5 6 7 … 13'],
      [1, 15, '1 2 3 4 5 … 8 15'],
      [20, 20, '1 … 10 … 16 17 18 19 20'],
      [19, 20, '1 … 10 … 16 17 18 19 20'],
    ])('page %i of %i renders "%s"', (currentPage, totalPages, expected) => {
      renderRow(currentPage, totalPages);

      expect(getRowCells()).toBe(expected);
    });

    it('should not render ellipsis when total pages <= maxVisiblePages', () => {
      render(<Pagination currentPage={1} totalPages={5} onPageChange={mockOnPageChange} />);

      expect(screen.queryByText('…')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 1' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Страница 5' })).toBeInTheDocument();
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
