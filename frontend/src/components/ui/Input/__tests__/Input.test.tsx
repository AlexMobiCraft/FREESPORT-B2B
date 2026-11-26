/**
 * Input Component Tests
 * Полное покрытие включая edge cases из спецификации
 */

import React from 'react';
import { render, screen } from '@testing-library/react';
import { Input, REQUIRED_MARK_CLASS_NAME } from '../Input';
import { Search } from 'lucide-react';

describe('Input', () => {
  // Базовый рендеринг
  it('renders input with label', () => {
    render(<Input label="Email" value="" onChange={() => {}} />);
    expect(screen.getByLabelText('Email')).toBeInTheDocument();
  });

  // Helper text
  it('displays helper text', () => {
    render(<Input label="Email" helper="Enter your email" value="" onChange={() => {}} />);
    expect(screen.getByText('Enter your email')).toBeInTheDocument();
  });

  // Edge Case: Конфликтующие состояния (error + success) - обновлено для v2.0
  describe('Edge Case: Conflicting States', () => {
    it('prioritizes error over success when both provided', () => {
      render(
        <Input
          label="Test"
          value=""
          onChange={() => {}}
          error="Invalid input"
          success="Valid input"
        />
      );

      // Должен отображаться error, а не success
      expect(screen.getByText('Invalid input')).toBeInTheDocument();
      expect(screen.queryByText('Valid input')).not.toBeInTheDocument();

      const input = screen.getByLabelText('Test');
      // Проверяем использование CSS переменных v2.0
      expect(input.className).toContain('border-[var(--color-accent-danger)]');
      expect(input.className).not.toContain('border-[var(--color-accent-success)]');
    });
  });

  // Edge Case: Длинный текст label
  describe('Edge Case: Long Label Text', () => {
    it('wraps long label text (>50 chars)', () => {
      const longLabel = 'A'.repeat(60); // 60 символов
      render(<Input label={longLabel} value="" onChange={() => {}} />);

      const label = screen.getByText(longLabel);
      expect(label).toHaveClass('whitespace-normal', 'break-words');
    });
  });

  // Edge Case: Длинный helper/error текст
  describe('Edge Case: Long Helper/Error Text', () => {
    it('wraps long error text (>100 chars)', () => {
      const longError = 'Error: ' + 'x'.repeat(110);
      render(<Input label="Test" value="" onChange={() => {}} error={longError} />);

      const errorText = screen.getByText(longError);
      expect(errorText).toHaveClass('whitespace-normal', 'break-words');
    });
  });

  // Edge Case: Icon + error
  describe('Edge Case: Icon and Error Icons', () => {
    it('displays both icon and error icon', () => {
      render(
        <Input
          label="Search"
          value=""
          onChange={() => {}}
          icon={<Search />}
          error="Invalid search"
        />
      );

      const input = screen.getByLabelText('Search');
      // Input должен иметь padding для обоих иконок
      expect(input).toHaveClass('pl-10'); // Для left icon
    });
  });

  // Disabled состояние
  describe('Disabled State', () => {
    it('applies disabled styles to error/success states', () => {
      render(<Input label="Test" value="" onChange={() => {}} error="Error" disabled />);

      const input = screen.getByLabelText('Test');
      expect(input).toBeDisabled();
      expect(input).toHaveClass('opacity-50', 'cursor-not-allowed');
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('links label to input with id', () => {
      render(<Input label="Email" value="" onChange={() => {}} />);
      const input = screen.getByLabelText('Email');
      expect(input).toHaveAttribute('id');
    });

    it('sets aria-invalid when error is present', () => {
      render(<Input label="Email" value="" onChange={() => {}} error="Invalid email" />);
      const input = screen.getByLabelText('Email');
      expect(input).toHaveAttribute('aria-invalid', 'true');
    });

    it('sets aria-describedby for helper/error text', () => {
      render(<Input label="Email" value="" onChange={() => {}} error="Invalid" />);
      const input = screen.getByLabelText('Email');
      expect(input).toHaveAttribute('aria-describedby');
    });
  });

  // Placeholder truncation
  it('truncates long placeholder', () => {
    render(
      <Input
        label="Test"
        value=""
        onChange={() => {}}
        placeholder="A very long placeholder that should be truncated"
      />
    );

    const input = screen.getByLabelText('Test');
    expect(input).toHaveClass('placeholder:truncate');
  });

  describe('requiredMark', () => {
    const REQUIRED_MARK_CLASSES = REQUIRED_MARK_CLASS_NAME.split(' ');

    it('adds neither the mark nor aria-required by default', () => {
      render(<Input label="Имя" value="" onChange={() => {}} />);

      const input = screen.getByLabelText('Имя');
      expect(input).not.toHaveAttribute('aria-required');
      expect(input).not.toHaveAttribute('required');
      const label = screen.getByText('Имя');
      for (const className of REQUIRED_MARK_CLASSES) {
        expect(label).not.toHaveClass(className);
      }
    });

    it('marks the label and sets aria-required without changing the label text', () => {
      render(<Input label="Имя" value="" onChange={() => {}} requiredMark />);

      const input = screen.getByLabelText('Имя');
      expect(input).toHaveAttribute('aria-required', 'true');
      // Нативный required заменил бы сообщения Zod браузерной подсказкой
      expect(input).not.toHaveAttribute('required');
      expect(input).toHaveAccessibleName('Имя');
      expect(input).toHaveAttribute('id', 'input-имя');
      const label = screen.getByText('Имя');
      expect(label).toHaveClass(...REQUIRED_MARK_CLASSES);
      expect(label.textContent).toBe('Имя');
    });

    it('lets an explicit aria-required from the caller win', () => {
      render(
        <Input label="Имя" value="" onChange={() => {}} requiredMark aria-required={false} />
      );

      expect(screen.getByLabelText('Имя')).toHaveAttribute('aria-required', 'false');
    });
  });
});
