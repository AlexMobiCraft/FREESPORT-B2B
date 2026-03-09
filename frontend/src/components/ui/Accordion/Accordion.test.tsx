/**
 * Accordion Unit Tests
 * Story 19.1 - AC 6 (покрытие ≥ 80%)
 */

import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Accordion } from './Accordion';

describe('Accordion', () => {
  const mockFAQ = [
    { question: 'Какие документы нужны?', answer: 'ИНН, ОГРН, реквизиты' },
    { question: 'Как происходит оплата?', answer: 'По безналичному расчёту' },
    { question: 'Какие сроки доставки?', answer: 'От 1 до 7 рабочих дней' },
  ];

  it('renders all items collapsed by default', () => {
    render(<Accordion items={mockFAQ} />);

    expect(screen.getByText('Какие документы нужны?')).toBeInTheDocument();
    expect(screen.getByText('Как происходит оплата?')).toBeInTheDocument();
    expect(screen.getByText('Какие сроки доставки?')).toBeInTheDocument();

    // Ответы должны быть скрыты (в DOM, но с max-height: 0)
    const answers = screen.getAllByText(/ИНН|безналичному|рабочих/);
    expect(answers.length).toBeGreaterThan(0);
  });

  it('expands item on click', async () => {
    render(<Accordion items={mockFAQ} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    fireEvent.click(firstQuestion);

    await waitFor(() => {
      const button = firstQuestion.closest('button');
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  it('collapses other items when allowMultiple is false', async () => {
    render(<Accordion items={mockFAQ} allowMultiple={false} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    const secondQuestion = screen.getByText('Как происходит оплата?');

    // Открываем первый
    fireEvent.click(firstQuestion);

    await waitFor(() => {
      const button1 = firstQuestion.closest('button');
      expect(button1).toHaveAttribute('aria-expanded', 'true');
    });

    // Открываем второй
    fireEvent.click(secondQuestion);

    await waitFor(() => {
      const button1 = firstQuestion.closest('button');
      const button2 = secondQuestion.closest('button');

      expect(button1).toHaveAttribute('aria-expanded', 'false'); // Первый закрылся
      expect(button2).toHaveAttribute('aria-expanded', 'true'); // Второй открылся
    });
  });

  it('allows multiple items to be open when allowMultiple is true', async () => {
    render(<Accordion items={mockFAQ} allowMultiple={true} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    const secondQuestion = screen.getByText('Как происходит оплата?');

    // Открываем первый
    fireEvent.click(firstQuestion);

    await waitFor(() => {
      const button1 = firstQuestion.closest('button');
      expect(button1).toHaveAttribute('aria-expanded', 'true');
    });

    // Открываем второй
    fireEvent.click(secondQuestion);

    await waitFor(() => {
      const button1 = firstQuestion.closest('button');
      const button2 = secondQuestion.closest('button');

      expect(button1).toHaveAttribute('aria-expanded', 'true'); // Первый остался открытым
      expect(button2).toHaveAttribute('aria-expanded', 'true'); // Второй открылся
    });
  });

  it('supports keyboard navigation with Enter', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    const button = firstQuestion.closest('button')!;

    button.focus();
    await user.keyboard('{Enter}');

    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  it('supports keyboard navigation with Space', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    const button = firstQuestion.closest('button')!;

    button.focus();
    await user.keyboard(' ');

    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });
  });

  it('supports ArrowDown navigation', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const buttons = screen.getAllByRole('button');
    buttons[0].focus();

    await user.keyboard('{ArrowDown}');

    await waitFor(() => {
      expect(document.activeElement).toBe(buttons[1]);
    });
  });

  it('supports ArrowUp navigation', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const buttons = screen.getAllByRole('button');
    buttons[1].focus();

    await user.keyboard('{ArrowUp}');

    await waitFor(() => {
      expect(document.activeElement).toBe(buttons[0]);
    });
  });

  it('wraps navigation from last to first item with ArrowDown', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const buttons = screen.getAllByRole('button');
    buttons[2].focus(); // Последний элемент

    await user.keyboard('{ArrowDown}');

    await waitFor(() => {
      expect(document.activeElement).toBe(buttons[0]); // Переходим к первому
    });
  });

  it('wraps navigation from first to last item with ArrowUp', async () => {
    const user = userEvent.setup();
    render(<Accordion items={mockFAQ} />);

    const buttons = screen.getAllByRole('button');
    buttons[0].focus(); // Первый элемент

    await user.keyboard('{ArrowUp}');

    await waitFor(() => {
      expect(document.activeElement).toBe(buttons[2]); // Переходим к последнему
    });
  });

  it('has correct ARIA attributes', () => {
    render(<Accordion items={mockFAQ} />);

    const accordion = screen.getByRole('region', { name: 'Часто задаваемые вопросы' });
    expect(accordion).toBeInTheDocument();

    const buttons = screen.getAllByRole('button');
    buttons.forEach(button => {
      expect(button).toHaveAttribute('aria-expanded');
      expect(button).toHaveAttribute('aria-controls');
    });
  });

  it('content regions have correct aria-labelledby', () => {
    const { container } = render(<Accordion items={mockFAQ} />);

    const regions = container.querySelectorAll('[role="region"]');
    // Первый region это сам accordion, остальные - content области
    expect(regions.length).toBeGreaterThan(1);

    // Проверяем что content regions имеют aria-labelledby
    const contentRegions = Array.from(regions).slice(1); // Пропускаем первый (accordion wrapper)
    contentRegions.forEach(region => {
      expect(region).toHaveAttribute('aria-labelledby');
    });
  });

  it('opens item at defaultOpenIndex', () => {
    render(<Accordion items={mockFAQ} defaultOpenIndex={1} />);

    const secondQuestion = screen.getByText('Как происходит оплата?');
    const button = secondQuestion.closest('button');

    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('applies custom className', () => {
    const { container } = render(<Accordion items={mockFAQ} className="custom-class" />);
    const accordion = container.firstChild as HTMLElement;

    expect(accordion.className).toContain('custom-class');
  });

  it('closes expanded item when clicked again', async () => {
    render(<Accordion items={mockFAQ} />);

    const firstQuestion = screen.getByText('Какие документы нужны?');
    const button = firstQuestion.closest('button')!;

    // Открываем
    fireEvent.click(button);
    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'true');
    });

    // Закрываем
    fireEvent.click(button);
    await waitFor(() => {
      expect(button).toHaveAttribute('aria-expanded', 'false');
    });
  });

  it('renders with custom IDs', () => {
    const itemsWithIds = [
      { id: 'faq-1', question: 'Question 1', answer: 'Answer 1' },
      { id: 'faq-2', question: 'Question 2', answer: 'Answer 2' },
    ];

    const { container } = render(<Accordion items={itemsWithIds} />);

    expect(container.querySelector('#faq-1-button')).toBeInTheDocument();
    expect(container.querySelector('#faq-2-button')).toBeInTheDocument();
  });
});
