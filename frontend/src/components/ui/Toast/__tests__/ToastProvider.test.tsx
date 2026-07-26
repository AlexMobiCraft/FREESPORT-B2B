/**
 * ToastProvider Tests
 * Design System v2.0
 */

import React from 'react';
import { render, screen, act } from '@testing-library/react';
import { ToastProvider, useToast } from '../ToastProvider';

describe('ToastProvider', () => {
  beforeEach(() => {
    // Очищаем document.body перед каждым тестом
    document.body.innerHTML = '';
  });

  it('throws error when useToast used outside provider', () => {
    // Suppress console.error для этого теста
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    const TestComponent = () => {
      useToast(); // Should throw
      return null;
    };

    expect(() => {
      render(<TestComponent />);
    }).toThrow('useToast must be used within ToastProvider');

    consoleSpy.mockRestore();
  });

  it('renders children', () => {
    render(
      <ToastProvider>
        <div>Test Content</div>
      </ToastProvider>
    );

    expect(screen.getByText('Test Content')).toBeInTheDocument();
  });

  it('provides toast context to children', () => {
    const TestComponent = () => {
      const context = useToast();
      return <div>{context ? 'Has Context' : 'No Context'}</div>;
    };

    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    expect(screen.getByText('Has Context')).toBeInTheDocument();
  });

  it('toast methods are callable', () => {
    const TestComponent = () => {
      const { toast } = useToast();

      return (
        <div>
          <span>Methods available: {typeof toast === 'function' ? 'yes' : 'no'}</span>
        </div>
      );
    };

    render(
      <ToastProvider>
        <TestComponent />
      </ToastProvider>
    );

    expect(screen.getByText('Methods available: yes')).toBeInTheDocument();
  });

  describe('success method', () => {
    it('displays success toast with message', () => {
      const TestComponent = () => {
        const { success } = useToast();
        return <button onClick={() => success('Success message')}>Show Success</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Success');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Success message')).toBeInTheDocument();
    });

    it('displays success toast with title and message', () => {
      const TestComponent = () => {
        const { success } = useToast();
        return (
          <button onClick={() => success('Operation completed', 'Success')}>Show Success</button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Success');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Success')).toBeInTheDocument();
      expect(screen.getByText('Operation completed')).toBeInTheDocument();
    });

    it('returns toast id', () => {
      let toastId = '';
      const TestComponent = () => {
        const { success } = useToast();
        return <button onClick={() => (toastId = success('Test'))}>Show Success</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Success');
      act(() => {
        button.click();
      });

      expect(toastId).toMatch(/^toast-/);
    });
  });

  describe('error method', () => {
    it('displays error toast with message', () => {
      const TestComponent = () => {
        const { error } = useToast();
        return <button onClick={() => error('Error occurred')}>Show Error</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Error');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Error occurred')).toBeInTheDocument();
    });

    it('displays error toast with title and message', () => {
      const TestComponent = () => {
        const { error } = useToast();
        return <button onClick={() => error('Something went wrong', 'Error')}>Show Error</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Error');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Error')).toBeInTheDocument();
      expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    });

    it('returns toast id', () => {
      let toastId = '';
      const TestComponent = () => {
        const { error } = useToast();
        return <button onClick={() => (toastId = error('Test'))}>Show Error</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Error');
      act(() => {
        button.click();
      });

      expect(toastId).toMatch(/^toast-/);
    });
  });

  describe('warning method', () => {
    it('displays warning toast with message', () => {
      const TestComponent = () => {
        const { warning } = useToast();
        return <button onClick={() => warning('Warning message')}>Show Warning</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Warning');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Warning message')).toBeInTheDocument();
    });

    it('displays warning toast with title and message', () => {
      const TestComponent = () => {
        const { warning } = useToast();
        return <button onClick={() => warning('Be careful', 'Warning')}>Show Warning</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Warning');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Warning')).toBeInTheDocument();
      expect(screen.getByText('Be careful')).toBeInTheDocument();
    });

    it('returns toast id', () => {
      let toastId = '';
      const TestComponent = () => {
        const { warning } = useToast();
        return <button onClick={() => (toastId = warning('Test'))}>Show Warning</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Warning');
      act(() => {
        button.click();
      });

      expect(toastId).toMatch(/^toast-/);
    });
  });

  describe('info method', () => {
    it('displays info toast with message', () => {
      const TestComponent = () => {
        const { info } = useToast();
        return <button onClick={() => info('Info message')}>Show Info</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Info');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Info message')).toBeInTheDocument();
    });

    it('displays info toast with title and message', () => {
      const TestComponent = () => {
        const { info } = useToast();
        return <button onClick={() => info('Useful information', 'Info')}>Show Info</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Info');
      act(() => {
        button.click();
      });

      expect(screen.getByText('Info')).toBeInTheDocument();
      expect(screen.getByText('Useful information')).toBeInTheDocument();
    });

    it('returns toast id', () => {
      let toastId = '';
      const TestComponent = () => {
        const { info } = useToast();
        return <button onClick={() => (toastId = info('Test'))}>Show Info</button>;
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      const button = screen.getByText('Show Info');
      act(() => {
        button.click();
      });

      expect(toastId).toMatch(/^toast-/);
    });
  });

  describe('dismiss method', () => {
    it('removes specific toast by id', () => {
      let toastId = '';
      const TestComponent = () => {
        const { success, dismiss } = useToast();
        return (
          <>
            <button onClick={() => (toastId = success('Toast to dismiss'))}>Add Toast</button>
            <button onClick={() => dismiss(toastId)}>Dismiss Toast</button>
          </>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      // Добавляем toast
      act(() => {
        screen.getByText('Add Toast').click();
      });

      expect(screen.getByText('Toast to dismiss')).toBeInTheDocument();

      // Удаляем toast
      act(() => {
        screen.getByText('Dismiss Toast').click();
      });

      expect(screen.queryByText('Toast to dismiss')).not.toBeInTheDocument();
    });

    it('does not affect other toasts', () => {
      let firstId = '';
      const TestComponent = () => {
        const { success, dismiss } = useToast();
        return (
          <>
            <button onClick={() => (firstId = success('First toast'))}>Add First</button>
            <button onClick={() => success('Second toast')}>Add Second</button>
            <button onClick={() => dismiss(firstId)}>Dismiss First</button>
          </>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      // Добавляем два toast
      act(() => {
        screen.getByText('Add First').click();
        screen.getByText('Add Second').click();
      });

      expect(screen.getByText('First toast')).toBeInTheDocument();
      expect(screen.getByText('Second toast')).toBeInTheDocument();

      // Удаляем первый
      act(() => {
        screen.getByText('Dismiss First').click();
      });

      expect(screen.queryByText('First toast')).not.toBeInTheDocument();
      expect(screen.getByText('Second toast')).toBeInTheDocument();
    });
  });

  describe('dismissAll method', () => {
    it('removes all toasts', () => {
      const TestComponent = () => {
        const { success, error, warning, dismissAll } = useToast();
        return (
          <>
            <button onClick={() => success('Success toast')}>Add Success</button>
            <button onClick={() => error('Error toast')}>Add Error</button>
            <button onClick={() => warning('Warning toast')}>Add Warning</button>
            <button onClick={dismissAll}>Dismiss All</button>
          </>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      // Добавляем три toast
      act(() => {
        screen.getByText('Add Success').click();
        screen.getByText('Add Error').click();
        screen.getByText('Add Warning').click();
      });

      expect(screen.getByText('Success toast')).toBeInTheDocument();
      expect(screen.getByText('Error toast')).toBeInTheDocument();
      expect(screen.getByText('Warning toast')).toBeInTheDocument();

      // Удаляем все
      act(() => {
        screen.getByText('Dismiss All').click();
      });

      expect(screen.queryByText('Success toast')).not.toBeInTheDocument();
      expect(screen.queryByText('Error toast')).not.toBeInTheDocument();
      expect(screen.queryByText('Warning toast')).not.toBeInTheDocument();
    });
  });

  describe('MAX_VISIBLE_TOASTS limit', () => {
    it('limits toasts to maximum of 5 visible', () => {
      const TestComponent = () => {
        const { info } = useToast();
        return (
          <button
            onClick={() => {
              // Добавляем 7 toast
              for (let i = 1; i <= 7; i++) {
                info(`Toast ${i}`);
              }
            }}
          >
            Add 7 Toasts
          </button>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      act(() => {
        screen.getByText('Add 7 Toasts').click();
      });

      // Первые два toast должны быть удалены
      expect(screen.queryByText('Toast 1')).not.toBeInTheDocument();
      expect(screen.queryByText('Toast 2')).not.toBeInTheDocument();

      // Последние 5 должны быть видимы
      expect(screen.getByText('Toast 3')).toBeInTheDocument();
      expect(screen.getByText('Toast 4')).toBeInTheDocument();
      expect(screen.getByText('Toast 5')).toBeInTheDocument();
      expect(screen.getByText('Toast 6')).toBeInTheDocument();
      expect(screen.getByText('Toast 7')).toBeInTheDocument();
    });

    it('removes oldest toasts when limit exceeded', () => {
      const TestComponent = () => {
        const { success } = useToast();
        return (
          <>
            <button onClick={() => success('Toast 1')}>Add 1</button>
            <button onClick={() => success('Toast 2')}>Add 2</button>
            <button onClick={() => success('Toast 3')}>Add 3</button>
            <button onClick={() => success('Toast 4')}>Add 4</button>
            <button onClick={() => success('Toast 5')}>Add 5</button>
            <button onClick={() => success('Toast 6')}>Add 6</button>
          </>
        );
      };

      render(
        <ToastProvider>
          <TestComponent />
        </ToastProvider>
      );

      // Добавляем 5 toast
      act(() => {
        screen.getByText('Add 1').click();
        screen.getByText('Add 2').click();
        screen.getByText('Add 3').click();
        screen.getByText('Add 4').click();
        screen.getByText('Add 5').click();
      });

      expect(screen.getByText('Toast 1')).toBeInTheDocument();
      expect(screen.getByText('Toast 5')).toBeInTheDocument();

      // Добавляем 6-й toast - первый должен исчезнуть
      act(() => {
        screen.getByText('Add 6').click();
      });

      expect(screen.queryByText('Toast 1')).not.toBeInTheDocument();
      expect(screen.getByText('Toast 2')).toBeInTheDocument();
      expect(screen.getByText('Toast 6')).toBeInTheDocument();
    });
  });
});
