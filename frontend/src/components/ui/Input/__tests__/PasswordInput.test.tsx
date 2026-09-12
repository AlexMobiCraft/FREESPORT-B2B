import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { Input } from '../Input';

describe('Input Password Toggle', () => {
  it('renders password input with obscured text by default', () => {
    render(<Input label="Password" type="password" value="secret123" onChange={() => {}} />);
    const input = screen.getByLabelText('Password');
    expect(input).toHaveAttribute('type', 'password');
  });

  it('toggles password visibility when eye icon is clicked', () => {
    render(<Input label="Password" type="password" value="secret123" onChange={() => {}} />);
    const input = screen.getByLabelText('Password');

    // Default state: password hidden
    expect(input).toHaveAttribute('type', 'password');

    // Click to show password
    // Using getByRole for more robust button finding
    const toggleButton = screen.getByRole('button', { name: /показать пароль/i });
    fireEvent.click(toggleButton);

    expect(input).toHaveAttribute('type', 'text');

    // Check for the new state label
    const hideButton = screen.getByRole('button', { name: /скрыть пароль/i });
    expect(hideButton).toBeInTheDocument();

    // Click to hide password
    fireEvent.click(hideButton);
    expect(input).toHaveAttribute('type', 'password');
  });

  it('does not show toggle button for non-password inputs', () => {
    render(<Input label="Email" type="email" value="test@example.com" onChange={() => {}} />);
    const toggleButton = screen.queryByRole('button', { name: /показать пароль/i });
    expect(toggleButton).not.toBeInTheDocument();
  });

  it('does not show toggle button when disabled', () => {
    render(<Input label="Password" type="password" value="secret" onChange={() => {}} disabled />);
    const toggleButton = screen.queryByRole('button', { name: /показать пароль/i });
    expect(toggleButton).not.toBeInTheDocument();
  });
});
