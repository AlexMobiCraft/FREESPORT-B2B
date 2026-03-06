/**
 * Tabs Component Tests
 * Покрытие keyboard navigation, overflow, disabled состояния
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Tabs, Tab } from '../Tabs';

// Mock scrollIntoView (не поддерживается в jsdom)
Element.prototype.scrollIntoView = vi.fn();

describe('Tabs', () => {
  const mockTabs: Tab[] = [
    { id: 'tab1', label: 'Tab 1', content: <div>Content 1</div> },
    { id: 'tab2', label: 'Tab 2', content: <div>Content 2</div> },
    { id: 'tab3', label: 'Tab 3', content: <div>Content 3</div> },
  ];

  // Базовый рендеринг
  it('renders all tabs', () => {
    render(<Tabs tabs={mockTabs} />);

    expect(screen.getByRole('tab', { name: 'Tab 1' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Tab 2' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Tab 3' })).toBeInTheDocument();
  });

  it('renders first tab as active by default', () => {
    render(<Tabs tabs={mockTabs} />);

    const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
    expect(tab1).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Content 1')).toBeVisible();
  });

  it('uses defaultTab when provided', () => {
    render(<Tabs tabs={mockTabs} defaultTab="tab2" />);

    const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
    expect(tab2).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByText('Content 2')).toBeVisible();
  });

  // Tab switching
  describe('Tab Switching', () => {
    it('switches active tab on click', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.click(tab2);

      expect(tab2).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByText('Content 2')).toBeVisible();
      expect(screen.getByText('Content 1')).not.toBeVisible();
    });

    it('calls onChange callback when tab changes', () => {
      const handleChange = vi.fn();
      render(<Tabs tabs={mockTabs} onChange={handleChange} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.click(tab2);

      expect(handleChange).toHaveBeenCalledWith('tab2');
    });

    it('shows only active tab content', () => {
      render(<Tabs tabs={mockTabs} />);

      expect(screen.getByText('Content 1')).toBeVisible();
      expect(screen.getByText('Content 2')).not.toBeVisible();
      expect(screen.getByText('Content 3')).not.toBeVisible();
    });
  });

  // Edge Case: Keyboard navigation
  describe('Keyboard Navigation', () => {
    it('navigates to next tab with ArrowRight', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      fireEvent.keyDown(tab1, { key: 'ArrowRight' });

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      expect(tab2).toHaveAttribute('aria-selected', 'true');
    });

    it('navigates to previous tab with ArrowLeft', () => {
      render(<Tabs tabs={mockTabs} defaultTab="tab2" />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.keyDown(tab2, { key: 'ArrowLeft' });

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      expect(tab1).toHaveAttribute('aria-selected', 'true');
    });

    it('wraps to last tab when ArrowLeft on first tab', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      fireEvent.keyDown(tab1, { key: 'ArrowLeft' });

      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      expect(tab3).toHaveAttribute('aria-selected', 'true');
    });

    it('wraps to first tab when ArrowRight on last tab', () => {
      render(<Tabs tabs={mockTabs} defaultTab="tab3" />);

      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      fireEvent.keyDown(tab3, { key: 'ArrowRight' });

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      expect(tab1).toHaveAttribute('aria-selected', 'true');
    });

    it('navigates to first tab with Home key', () => {
      render(<Tabs tabs={mockTabs} defaultTab="tab3" />);

      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      fireEvent.keyDown(tab3, { key: 'Home' });

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      expect(tab1).toHaveAttribute('aria-selected', 'true');
    });

    it('navigates to last tab with End key', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      fireEvent.keyDown(tab1, { key: 'End' });

      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      expect(tab3).toHaveAttribute('aria-selected', 'true');
    });

    it('activates tab with Enter key', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.keyDown(tab2, { key: 'Enter' });

      expect(tab2).toHaveAttribute('aria-selected', 'true');
    });

    it('activates tab with Space key', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.keyDown(tab2, { key: ' ' });

      expect(tab2).toHaveAttribute('aria-selected', 'true');
    });
  });

  // Edge Case: Disabled состояние
  describe('Disabled State', () => {
    const tabsWithDisabled: Tab[] = [
      { id: 'tab1', label: 'Tab 1', content: <div>Content 1</div> },
      { id: 'tab2', label: 'Tab 2', content: <div>Content 2</div>, disabled: true },
      { id: 'tab3', label: 'Tab 3', content: <div>Content 3</div> },
    ];

    it('renders disabled tab with proper styles', () => {
      render(<Tabs tabs={tabsWithDisabled} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      expect(tab2).toHaveClass('opacity-50', 'cursor-not-allowed');
      expect(tab2).toBeDisabled();
    });

    it('does not switch to disabled tab on click', () => {
      render(<Tabs tabs={tabsWithDisabled} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.click(tab2);

      expect(tab2).toHaveAttribute('aria-selected', 'false');
      expect(screen.getByText('Content 1')).toBeVisible();
    });

    it('skips disabled tabs in keyboard navigation', () => {
      render(<Tabs tabs={tabsWithDisabled} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      fireEvent.keyDown(tab1, { key: 'ArrowRight' });

      // Should skip tab2 (disabled) and go to tab3
      const tab3 = screen.getByRole('tab', { name: 'Tab 3' });
      expect(tab3).toHaveAttribute('aria-selected', 'true');
    });

    it('has aria-disabled attribute', () => {
      render(<Tabs tabs={tabsWithDisabled} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      expect(tab2).toHaveAttribute('aria-disabled', 'true');
    });
  });

  // Underline indicator
  describe('Underline Indicator', () => {
    it('shows underline on active tab', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      const underline = tab1.querySelector('span[aria-hidden="true"]');

      expect(underline).toBeInTheDocument();
      expect(underline).toHaveClass('bg-primary', 'h-[3px]');
    });

    it('moves underline when tab changes', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });
      fireEvent.click(tab2);

      const underline = tab2.querySelector('span[aria-hidden="true"]');
      expect(underline).toBeInTheDocument();
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has role="tablist" on container', () => {
      const { container } = render(<Tabs tabs={mockTabs} />);

      const tablist = container.querySelector('[role="tablist"]');
      expect(tablist).toBeInTheDocument();
    });

    it('tabs have role="tab"', () => {
      render(<Tabs tabs={mockTabs} />);

      const tabs = screen.getAllByRole('tab');
      expect(tabs).toHaveLength(3);
    });

    it('tab panels have role="tabpanel"', () => {
      const { container } = render(<Tabs tabs={mockTabs} />);

      const panels = container.querySelectorAll('[role="tabpanel"]');
      expect(panels).toHaveLength(3);
    });

    it('active tab has tabIndex 0, others have -1', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      const tab2 = screen.getByRole('tab', { name: 'Tab 2' });

      expect(tab1).toHaveAttribute('tabIndex', '0');
      expect(tab2).toHaveAttribute('tabIndex', '-1');
    });

    it('tabs have aria-controls pointing to panel', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      expect(tab1).toHaveAttribute('aria-controls', 'tabpanel-tab1');
    });

    it('has focus ring on tabs', () => {
      render(<Tabs tabs={mockTabs} />);

      const tab1 = screen.getByRole('tab', { name: 'Tab 1' });
      expect(tab1).toHaveClass('focus:ring-2', 'focus:ring-primary');
    });
  });

  // Edge Case: Overflow - горизонтальный скролл
  it('has horizontal scroll for overflow', () => {
    const { container } = render(<Tabs tabs={mockTabs} />);

    const tablist = container.querySelector('[role="tablist"]');
    expect(tablist).toHaveClass('overflow-x-auto');
  });

  // Custom className
  it('accepts custom className', () => {
    const { container } = render(<Tabs tabs={mockTabs} className="custom-class" />);

    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper).toHaveClass('custom-class');
  });
});
