import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { ContactSection } from '../ContactSection';
import { checkoutSchema, CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';

// Wrapper компонент для тестирования ContactSection
function ContactSectionWrapper({ defaultValues }: { defaultValues?: Partial<CheckoutFormInput> }) {
  const form = useForm<CheckoutFormInput, unknown, CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
    mode: 'onBlur',
    defaultValues: {
      email: defaultValues?.email || '',
      phone: defaultValues?.phone || '',
      firstName: defaultValues?.firstName || '',
      lastName: defaultValues?.lastName || '',
      city: '',
      street: '',
      house: '',
      apartment: '',
      postalCode: '',
      deliveryMethod: '',
      comment: '',
    },
  });

  return (
    <form>
      <ContactSection form={form} />
    </form>
  );
}

describe('ContactSection', () => {
  describe('Rendering', () => {
    it('должен отображать все поля контактных данных', () => {
      render(<ContactSectionWrapper />);

      expect(screen.getByLabelText('Email')).toBeInTheDocument();
      expect(screen.getByLabelText('Телефон')).toBeInTheDocument();
      expect(screen.getByLabelText('Имя')).toBeInTheDocument();
      expect(screen.getByLabelText('Фамилия')).toBeInTheDocument();
    });

    it('должен отображать заголовок секции', () => {
      render(<ContactSectionWrapper />);

      expect(screen.getByText('Контактные данные')).toBeInTheDocument();
    });
  });

  describe('Автозаполнение', () => {
    it('должен автозаполнять поля для авторизованных пользователей', () => {
      const defaultValues = {
        email: 'test@example.com',
        phone: '+79001234567',
        firstName: 'Иван',
        lastName: 'Петров',
      };

      render(<ContactSectionWrapper defaultValues={defaultValues} />);

      expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('+79001234567')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Иван')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Петров')).toBeInTheDocument();
    });
  });

  describe('Валидация Email', () => {
    it('должен показывать ошибку для некорректного email', async () => {
      render(<ContactSectionWrapper />);

      const emailInput = screen.getByLabelText('Email');
      fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Некорректный формат email');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен принимать корректный email', async () => {
      render(<ContactSectionWrapper />);

      const emailInput = screen.getByLabelText('Email');
      fireEvent.change(emailInput, { target: { value: 'valid@example.com' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        expect(screen.queryByText('Некорректный формат email')).not.toBeInTheDocument();
      });
    });

    it('должен показывать ошибку для пустого email', async () => {
      render(<ContactSectionWrapper />);

      const emailInput = screen.getByLabelText('Email');
      fireEvent.focus(emailInput);
      fireEvent.blur(emailInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Email обязателен');
        expect(errors.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Валидация Телефона', () => {
    it('должен показывать ошибку для некорректного формата телефона', async () => {
      render(<ContactSectionWrapper />);

      const phoneInput = screen.getByLabelText('Телефон');
      fireEvent.change(phoneInput, { target: { value: '1234567890' } });
      fireEvent.blur(phoneInput);

      await waitFor(() => {
        expect(screen.getByText(/Формат: \+7XXXXXXXXXX/)).toBeInTheDocument();
      });
    });

    it('должен принимать корректный формат телефона', async () => {
      render(<ContactSectionWrapper />);

      const phoneInput = screen.getByLabelText('Телефон');
      fireEvent.change(phoneInput, { target: { value: '+79001234567' } });
      fireEvent.blur(phoneInput);

      await waitFor(() => {
        // Подсказка "Формат: +7XXXXXXXXXX" отображается всегда как hint
        // Проверяем, что поле не имеет aria-invalid="true" (нет ошибки)
        expect(phoneInput).toHaveAttribute('aria-invalid', 'false');
      });
    });
  });

  describe('Валидация Имени и Фамилии', () => {
    it('должен показывать ошибку для имени < 2 символов', async () => {
      render(<ContactSectionWrapper />);

      const firstNameInput = screen.getByLabelText('Имя');
      fireEvent.change(firstNameInput, { target: { value: 'А' } });
      fireEvent.blur(firstNameInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Минимум 2 символа');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен принимать корректное имя', async () => {
      render(<ContactSectionWrapper />);

      const firstNameInput = screen.getByLabelText('Имя');
      fireEvent.change(firstNameInput, { target: { value: 'Иван' } });
      fireEvent.blur(firstNameInput);

      await waitFor(() => {
        expect(screen.queryByText('Минимум 2 символа')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    it('должен иметь aria-required для обязательных полей', () => {
      render(<ContactSectionWrapper />);

      const emailInput = screen.getByLabelText('Email');
      const phoneInput = screen.getByLabelText('Телефон');
      const firstNameInput = screen.getByLabelText('Имя');
      const lastNameInput = screen.getByLabelText('Фамилия');

      expect(emailInput).toHaveAttribute('aria-required', 'true');
      expect(phoneInput).toHaveAttribute('aria-required', 'true');
      expect(firstNameInput).toHaveAttribute('aria-required', 'true');
      expect(lastNameInput).toHaveAttribute('aria-required', 'true');
    });

    it('должен иметь правильный autocomplete для полей', () => {
      render(<ContactSectionWrapper />);

      const emailInput = screen.getByLabelText('Email');
      const phoneInput = screen.getByLabelText('Телефон');

      expect(emailInput).toHaveAttribute('autocomplete', 'email');
      expect(phoneInput).toHaveAttribute('autocomplete', 'tel');
    });
  });
});
