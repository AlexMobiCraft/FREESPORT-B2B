import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { AddressSection } from '../AddressSection';
import { checkoutSchema, CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';

// Wrapper компонент для тестирования AddressSection
function AddressSectionWrapper({ defaultValues }: { defaultValues?: Partial<CheckoutFormInput> }) {
  const form = useForm<CheckoutFormInput, unknown, CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
    mode: 'onBlur',
    defaultValues: {
      email: '',
      phone: '',
      firstName: '',
      lastName: '',
      city: defaultValues?.city || '',
      street: defaultValues?.street || '',
      house: defaultValues?.house || '',
      buildingSection: defaultValues?.buildingSection || '',
      apartment: defaultValues?.apartment || '',
      postalCode: defaultValues?.postalCode || '',
      deliveryMethod: '',
      comment: '',
    },
  });

  return (
    <form>
      <AddressSection form={form} />
    </form>
  );
}

describe('AddressSection', () => {
  describe('Rendering', () => {
    it('должен отображать все поля адреса', () => {
      render(<AddressSectionWrapper />);

      expect(screen.getByLabelText('Город')).toBeInTheDocument();
      expect(screen.getByLabelText('Улица')).toBeInTheDocument();
      expect(screen.getByLabelText('Дом')).toBeInTheDocument();
      expect(screen.getByLabelText('Корпус')).toBeInTheDocument();
      expect(screen.getByLabelText('Кв./офис')).toBeInTheDocument();
      expect(screen.getByLabelText('Почтовый индекс')).toBeInTheDocument();
    });

    it('должен отображать заголовок секции', () => {
      render(<AddressSectionWrapper />);

      expect(screen.getByText('Адрес доставки')).toBeInTheDocument();
    });
  });

  describe('Автозаполнение из сохранённого адреса', () => {
    it('должен автозаполнять поля адреса', () => {
      const defaultValues = {
        city: 'Москва',
        street: 'Ленина',
        house: '10',
        apartment: '25',
        postalCode: '123456',
      };

      render(<AddressSectionWrapper defaultValues={defaultValues} />);

      expect(screen.getByDisplayValue('Москва')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Ленина')).toBeInTheDocument();
      expect(screen.getByDisplayValue('10')).toBeInTheDocument();
      expect(screen.getByDisplayValue('25')).toBeInTheDocument();
      expect(screen.getByDisplayValue('123456')).toBeInTheDocument();
    });
  });

  describe('Валидация почтового индекса', () => {
    it('должен показывать ошибку для индекса != 6 цифр', async () => {
      render(<AddressSectionWrapper />);

      const postalCodeInput = screen.getByLabelText('Почтовый индекс');
      fireEvent.change(postalCodeInput, { target: { value: '12345' } });
      fireEvent.blur(postalCodeInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText(/Индекс должен содержать ровно 6 цифр/);
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен показывать ошибку для нецифрового индекса', async () => {
      render(<AddressSectionWrapper />);

      const postalCodeInput = screen.getByLabelText('Почтовый индекс');
      fireEvent.change(postalCodeInput, { target: { value: 'ABCDEF' } });
      fireEvent.blur(postalCodeInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText(/Индекс должен содержать ровно 6 цифр/);
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен принимать корректный индекс (6 цифр)', async () => {
      render(<AddressSectionWrapper />);

      const postalCodeInput = screen.getByLabelText('Почтовый индекс');
      fireEvent.change(postalCodeInput, { target: { value: '123456' } });
      fireEvent.blur(postalCodeInput);

      await waitFor(() => {
        expect(screen.queryByText(/Индекс должен содержать ровно 6 цифр/)).not.toBeInTheDocument();
      });
    });
  });

  describe('Валидация обязательных полей адреса', () => {
    it('должен показывать ошибку для пустого города', async () => {
      render(<AddressSectionWrapper />);

      const cityInput = screen.getByLabelText('Город');
      fireEvent.focus(cityInput);
      fireEvent.blur(cityInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Минимум 2 символа');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен показывать ошибку для пустой улицы', async () => {
      render(<AddressSectionWrapper />);

      const streetInput = screen.getByLabelText('Улица');
      fireEvent.focus(streetInput);
      fireEvent.blur(streetInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Минимум 3 символа');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен показывать ошибку для пустого дома', async () => {
      render(<AddressSectionWrapper />);

      const houseInput = screen.getByLabelText('Дом');
      fireEvent.focus(houseInput);
      fireEvent.blur(houseInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only для accessibility)
        const errors = screen.getAllByText('Обязательное поле');
        expect(errors.length).toBeGreaterThan(0);
      });
    });
  });

  describe('Необязательные поля', () => {
    it('квартира должна быть необязательной', () => {
      render(<AddressSectionWrapper />);

      const apartmentInput = screen.getByLabelText('Кв./офис');
      expect(apartmentInput).not.toHaveAttribute('aria-required', 'true');
    });

    it('не должен показывать ошибку для пустой квартиры', async () => {
      render(<AddressSectionWrapper />);

      const apartmentInput = screen.getByLabelText('Кв./офис');
      fireEvent.focus(apartmentInput);
      fireEvent.blur(apartmentInput);

      await waitFor(() => {
        // Проверяем, что нет ошибок
        const apartmentLabel = screen.getByText('Кв./офис');
        expect(apartmentLabel.closest('div')).not.toHaveClass('error');
      });
    });
  });

  describe('Accessibility', () => {
    it('должен иметь aria-required для обязательных полей', () => {
      render(<AddressSectionWrapper />);

      const cityInput = screen.getByLabelText('Город');
      const streetInput = screen.getByLabelText('Улица');
      const houseInput = screen.getByLabelText('Дом');
      const postalCodeInput = screen.getByLabelText('Почтовый индекс');

      expect(cityInput).toHaveAttribute('aria-required', 'true');
      expect(streetInput).toHaveAttribute('aria-required', 'true');
      expect(houseInput).toHaveAttribute('aria-required', 'true');
      expect(postalCodeInput).toHaveAttribute('aria-required', 'true');
    });

    it('должен иметь maxLength для почтового индекса', () => {
      render(<AddressSectionWrapper />);

      const postalCodeInput = screen.getByLabelText('Почтовый индекс');
      expect(postalCodeInput).toHaveAttribute('maxLength', '6');
    });
  });
});
