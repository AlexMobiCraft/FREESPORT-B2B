/**
 * FilterGroup Component Tests
 * Тесты для collapsible группы фильтров
 */

import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { FilterGroup } from '../FilterGroup';

describe('FilterGroup', () => {
  it('renders with title and children', () => {
    render(
      <FilterGroup title="Категории">
        <div>Filter content</div>
      </FilterGroup>
    );

    expect(screen.getByText('Категории')).toBeInTheDocument();
    expect(screen.getByText('Filter content')).toBeInTheDocument();
  });

  it('is expanded by default', () => {
    render(
      <FilterGroup title="Test">
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('can be collapsed by default', () => {
    render(
      <FilterGroup title="Test" defaultExpanded={false}>
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'false');
  });

  it('toggles expanded state on click', () => {
    render(
      <FilterGroup title="Test">
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('does not toggle when collapsible is false', () => {
    render(
      <FilterGroup title="Test" collapsible={false}>
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-expanded', 'true');

    fireEvent.click(button);
    expect(button).toHaveAttribute('aria-expanded', 'true');
  });

  it('shows chevron icon when collapsible', () => {
    render(
      <FilterGroup title="Test" collapsible={true}>
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    const svg = button.querySelector('svg');
    expect(svg).toBeInTheDocument();
  });

  it('does not show chevron when not collapsible', () => {
    render(
      <FilterGroup title="Test" collapsible={false}>
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    const svg = button.querySelector('svg');
    expect(svg).not.toBeInTheDocument();
  });

  it('has correct accessibility attributes', () => {
    render(
      <FilterGroup title="Категории">
        <div>Content</div>
      </FilterGroup>
    );

    const button = screen.getByRole('button');
    expect(button).toHaveAttribute('aria-controls', 'filter-group-категории');
  });
});
