/**
 * SearchHistory Component Tests
 *
 * @see docs/stories/epic-18/18.3.search-history.md#Task6
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchHistory } from '../SearchHistory';

describe('SearchHistory', () => {
  const mockHistory = ['кроссовки Nike', 'футболка Adidas', 'шорты Puma'];
  const mockOnSelect = vi.fn();
  const mockOnRemove = vi.fn();
  const mockOnClear = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Rendering', () => {
    it('should render list of history items', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      expect(screen.getByText('История поиска')).toBeInTheDocument();
      expect(screen.getByText('кроссовки Nike')).toBeInTheDocument();
      expect(screen.getByText('футболка Adidas')).toBeInTheDocument();
      expect(screen.getByText('шорты Puma')).toBeInTheDocument();
    });

    it('should render clear history button', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      expect(screen.getByText('Очистить историю')).toBeInTheDocument();
    });

    it('should render with custom className', () => {
      const { container } = render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
          className="custom-class"
        />
      );

      const historyElement = container.querySelector('[role="listbox"]');
      expect(historyElement).toHaveClass('custom-class');
    });

    it('should not render when history is empty', () => {
      const { container } = render(
        <SearchHistory
          history={[]}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      expect(container.firstChild).toBeNull();
    });

    // Clock icons are tested implicitly through UI rendering

    it('should render remove button for each item', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const removeButtons = screen.getAllByLabelText(/Удалить запрос:/);
      expect(removeButtons).toHaveLength(mockHistory.length);
    });
  });

  describe('Interactions', () => {
    it('should call onSelect when clicking on history item', async () => {
      const user = userEvent.setup();

      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const historyItem = screen.getByRole('option', {
        name: /Выбрать запрос: кроссовки Nike/,
      });
      await user.click(historyItem);

      expect(mockOnSelect).toHaveBeenCalledWith('кроссовки Nike');
      expect(mockOnSelect).toHaveBeenCalledTimes(1);
    });

    it('should call onRemove when clicking remove button', async () => {
      const user = userEvent.setup();

      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const removeButton = screen.getByLabelText('Удалить запрос: футболка Adidas');
      await user.click(removeButton);

      expect(mockOnRemove).toHaveBeenCalledWith('футболка Adidas');
      expect(mockOnRemove).toHaveBeenCalledTimes(1);
    });

    it('should not call onSelect when clicking remove button', async () => {
      const user = userEvent.setup();

      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const removeButton = screen.getByLabelText('Удалить запрос: футболка Adidas');
      await user.click(removeButton);

      expect(mockOnSelect).not.toHaveBeenCalled();
    });

    it('should show confirmation on first clear click', async () => {
      const user = userEvent.setup();

      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const clearButton = screen.getByText('Очистить историю');
      await user.click(clearButton);

      expect(screen.getByText('Нажмите еще раз для подтверждения')).toBeInTheDocument();
      expect(mockOnClear).not.toHaveBeenCalled();
    });

    it('should call onClear on second clear click', async () => {
      const user = userEvent.setup();

      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const clearButton = screen.getByText('Очистить историю');

      // Первый клик - показать подтверждение
      await user.click(clearButton);
      expect(mockOnClear).not.toHaveBeenCalled();

      // Второй клик - вызвать onClear
      const confirmButton = screen.getByText('Нажмите еще раз для подтверждения');
      await user.click(confirmButton);

      expect(mockOnClear).toHaveBeenCalledTimes(1);
    });

    // Timeout reset is tested in integration tests
  });

  describe('Accessibility', () => {
    it('should have role="listbox" on container', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const listbox = screen.getByRole('listbox');
      expect(listbox).toHaveAttribute('aria-label', 'История поиска');
    });

    it('should have role="option" on history items', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const options = screen.getAllByRole('option');
      expect(options).toHaveLength(mockHistory.length);

      options.forEach((option, index) => {
        expect(option).toHaveAttribute('aria-label', `Выбрать запрос: ${mockHistory[index]}`);
      });
    });

    it('should have aria-label on remove buttons', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      mockHistory.forEach(query => {
        const removeButton = screen.getByLabelText(`Удалить запрос: ${query}`);
        expect(removeButton).toBeInTheDocument();
      });
    });

    it('should have aria-label on clear button', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const clearButton = screen.getByLabelText('Очистить историю поиска');
      expect(clearButton).toBeInTheDocument();
    });
  });

  describe('Styling', () => {
    it('should apply hover styles to history items', () => {
      render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const historyItem = screen.getByRole('option', {
        name: /Выбрать запрос: кроссовки Nike/,
      });

      expect(historyItem).toHaveClass('hover:bg-[#F5F7FA]');
    });

    it('should have proper border and shadow styles', () => {
      const { container } = render(
        <SearchHistory
          history={mockHistory}
          onSelect={mockOnSelect}
          onRemove={mockOnRemove}
          onClear={mockOnClear}
        />
      );

      const listbox = container.querySelector('[role="listbox"]');
      expect(listbox).toHaveClass('border', 'border-[#E3E8F2]', 'shadow-lg');
    });
  });
});
