import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { AddressSection } from '../AddressSection';
import { checkoutSchema, CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import type { Address } from '@/types/address';

interface WrapperProps {
  defaultValues?: Partial<CheckoutFormInput>;
  addresses?: Address[];
  selectedAddressId?: number | null;
  onSelectAddress?: (id: number) => void;
  showSaveCheckbox?: boolean;
  saveAddress?: boolean;
  onToggleSaveAddress?: (value: boolean) => void;
}

// Wrapper компонент для тестирования AddressSection
function AddressSectionWrapper({
  defaultValues,
  addresses,
  selectedAddressId,
  onSelectAddress,
  showSaveCheckbox,
  saveAddress,
  onToggleSaveAddress,
}: WrapperProps) {
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
      <AddressSection
        form={form}
        addresses={addresses}
        selectedAddressId={selectedAddressId}
        onSelectAddress={onSelectAddress}
        showSaveCheckbox={showSaveCheckbox}
        saveAddress={saveAddress}
        onToggleSaveAddress={onToggleSaveAddress}
      />
    </form>
  );
}

function makeAddress(overrides: Partial<Address> = {}): Address {
  return {
    id: 1,
    address_type: 'shipping',
    full_name: 'Иван Иванов',
    phone: '+79001234567',
    city: 'Москва',
    street: 'Ленина',
    building: '10',
    building_section: '',
    apartment: '5',
    postal_code: '123456',
    is_default: false,
    full_address: '123456, Москва, Ленина, 10, кв. 5',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
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

  describe('Селектор сохранённых адресов', () => {
    it('не отображается, если addresses не передан', () => {
      render(<AddressSectionWrapper />);
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
    });

    it('не отображается при наличии одного адреса', () => {
      render(
        <AddressSectionWrapper
          addresses={[makeAddress({ id: 1, is_default: true })]}
          selectedAddressId={1}
          onSelectAddress={() => {}}
        />
      );
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
    });

    it('отображает все адреса в виде карточек при addresses.length > 1', () => {
      const addresses = [
        makeAddress({ id: 1, is_default: true, full_name: 'Иван' }),
        makeAddress({ id: 2, full_name: 'Петр' }),
        makeAddress({ id: 3, full_name: 'Сидор' }),
      ];
      render(
        <AddressSectionWrapper
          addresses={addresses}
          selectedAddressId={1}
          onSelectAddress={() => {}}
        />
      );
      const selector = screen.getByTestId('address-selector');
      expect(selector).toBeInTheDocument();
      const cards = screen.getAllByTestId('address-card-option');
      expect(cards).toHaveLength(3);
    });

    it('помечает выбранную карточку через aria-checked', () => {
      const addresses = [
        makeAddress({ id: 1 }),
        makeAddress({ id: 2 }),
      ];
      render(
        <AddressSectionWrapper
          addresses={addresses}
          selectedAddressId={2}
          onSelectAddress={() => {}}
        />
      );
      const cards = screen.getAllByTestId('address-card-option');
      expect(cards[0]).toHaveAttribute('aria-checked', 'false');
      expect(cards[1]).toHaveAttribute('aria-checked', 'true');
    });

    it('вызывает onSelectAddress при клике по карточке', () => {
      const onSelect = vi.fn();
      const addresses = [makeAddress({ id: 1 }), makeAddress({ id: 2 })];
      render(
        <AddressSectionWrapper
          addresses={addresses}
          selectedAddressId={1}
          onSelectAddress={onSelect}
        />
      );
      const cards = screen.getAllByTestId('address-card-option');
      fireEvent.click(cards[1]);
      expect(onSelect).toHaveBeenCalledWith(2);
    });
  });

  describe('Чекбокс «Запомнить адрес»', () => {
    it('не отображается по умолчанию', () => {
      render(<AddressSectionWrapper />);
      expect(screen.queryByTestId('save-address-checkbox-wrapper')).not.toBeInTheDocument();
    });

    it('отображается при showSaveCheckbox=true', () => {
      render(
        <AddressSectionWrapper showSaveCheckbox saveAddress={false} onToggleSaveAddress={() => {}} />
      );
      expect(screen.getByTestId('save-address-checkbox-wrapper')).toBeInTheDocument();
      expect(screen.getByLabelText(/Запомнить этот адрес в профиле/)).toBeInTheDocument();
    });

    it('вызывает onToggleSaveAddress при клике', () => {
      const onToggle = vi.fn();
      render(
        <AddressSectionWrapper showSaveCheckbox saveAddress={false} onToggleSaveAddress={onToggle} />
      );
      const checkbox = screen.getByLabelText(/Запомнить этот адрес в профиле/);
      fireEvent.click(checkbox);
      expect(onToggle).toHaveBeenCalledWith(true);
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
