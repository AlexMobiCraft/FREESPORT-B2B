/**
 * DeliveryOptions Component Tests
 * Story 15.3b: Frontend DeliveryOptions Component
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { DeliveryOptions } from '../DeliveryOptions';
import { checkoutSchema, CheckoutFormData, CheckoutFormInput } from '@/schemas/checkoutSchema';
import deliveryService from '@/services/deliveryService';

// Mock deliveryService with Vitest
vi.mock('@/services/deliveryService');

const mockMethods = [
  {
    id: 'courier',
    name: 'Курьер',
    description: 'Доставка до двери',
    icon: '🚚',
    is_available: true,
  },
  {
    id: 'pickup',
    name: 'Самовывоз',
    description: 'Забрать из пункта выдачи',
    icon: '🏪',
    is_available: true,
  },
  {
    id: 'transport_company',
    name: 'Транспортная компания',
    description: 'Отправка ТК',
    icon: '📦',
    is_available: false, // Недоступен для тестирования disabled состояния
  },
];

// Wrapper компонент для тестирования DeliveryOptions
function DeliveryOptionsWrapper({
  defaultDeliveryMethod = '',
}: {
  defaultDeliveryMethod?: string;
}) {
  const form = useForm<CheckoutFormInput, unknown, CheckoutFormData>({
    resolver: zodResolver(checkoutSchema),
    mode: 'onBlur',
    defaultValues: {
      email: '',
      phone: '',
      firstName: '',
      lastName: '',
      city: '',
      street: '',
      house: '',
      apartment: '',
      postalCode: '',
      deliveryMethod: defaultDeliveryMethod,
      comment: '',
    },
  });

  return (
    <form>
      <DeliveryOptions form={form} />
    </form>
  );
}

describe('DeliveryOptions', () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  describe('Loading State', () => {
    it('отображает skeleton с aria-label при загрузке', () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockImplementation(
        () => new Promise(() => {}) // Никогда не резолвится
      );

      render(<DeliveryOptionsWrapper />);

      const loadingElement = screen.getByRole('status');
      expect(loadingElement).toHaveAttribute('aria-label', 'Загрузка способов доставки');
    });

    it('отображает анимированный skeleton placeholder', () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockImplementation(() => new Promise(() => {}));

      render(<DeliveryOptionsWrapper />);

      const loadingElement = screen.getByRole('status');
      expect(loadingElement).toHaveClass('animate-pulse');
    });

    it('отображает заголовок секции при загрузке', () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockImplementation(() => new Promise(() => {}));

      render(<DeliveryOptionsWrapper />);

      expect(screen.getByText('Способ доставки')).toBeInTheDocument();
    });
  });

  describe('Success State', () => {
    beforeEach(() => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue(mockMethods);
    });

    it('отображает все способы доставки после загрузки', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Курьер')).toBeInTheDocument();
        expect(screen.getByText('Самовывоз')).toBeInTheDocument();
        expect(screen.getByText('Транспортная компания')).toBeInTheDocument();
      });
    });

    it('отображает иконки для каждого способа доставки', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('🚚')).toBeInTheDocument();
        expect(screen.getByText('🏪')).toBeInTheDocument();
        expect(screen.getByText('📦')).toBeInTheDocument();
      });
    });

    it('отображает описания способов доставки', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Доставка до двери')).toBeInTheDocument();
        expect(screen.getByText('Забрать из пункта выдачи')).toBeInTheDocument();
        expect(screen.getByText('Отправка ТК')).toBeInTheDocument();
      });
    });

    it('показывает "Уточняется администратором" для каждого способа', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const priceTexts = screen.getAllByText(/уточняется администратором/i);
        expect(priceTexts).toHaveLength(3);
      });
    });

    it('НЕ показывает числовую стоимость (₽ или руб)', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.queryByText(/₽/)).not.toBeInTheDocument();
        expect(screen.queryByText(/руб/i)).not.toBeInTheDocument();
      });
    });

    it('рендерит radiogroup с правильными aria атрибутами', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const radiogroup = screen.getByRole('radiogroup');
        expect(radiogroup).toHaveAttribute('aria-label', 'Выбор способа доставки');
      });
    });

    it('отображает заголовок секции', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Способ доставки')).toBeInTheDocument();
      });
    });

    it('отображает информационное сообщение', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText(/стоимость доставки будет рассчитана/i)).toBeInTheDocument();
      });
    });
  });

  describe('Selection', () => {
    beforeEach(() => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue(mockMethods);
    });

    it('позволяет выбрать способ доставки', async () => {
      const user = userEvent.setup();
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Курьер')).toBeInTheDocument();
      });

      const courierRadio = screen.getByRole('radio', { name: /курьер/i });
      await user.click(courierRadio);

      expect(courierRadio).toBeChecked();
    });

    it('позволяет переключать между способами доставки', async () => {
      const user = userEvent.setup();
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Курьер')).toBeInTheDocument();
      });

      const courierRadio = screen.getByRole('radio', { name: /курьер/i });
      const pickupRadio = screen.getByRole('radio', { name: /самовывоз/i });

      await user.click(courierRadio);
      expect(courierRadio).toBeChecked();
      expect(pickupRadio).not.toBeChecked();

      await user.click(pickupRadio);
      expect(pickupRadio).toBeChecked();
      expect(courierRadio).not.toBeChecked();
    });

    it('блокирует недоступные способы доставки', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const transportRadio = screen.getByRole('radio', { name: /транспортная компания/i });
        expect(transportRadio).toBeDisabled();
      });
    });
  });

  describe('Error State', () => {
    it('показывает сообщение об ошибке при сбое загрузки', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockRejectedValue(new Error('Network error'));

      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText(/не удалось загрузить/i)).toBeInTheDocument();
      });
    });

    it('рендерит ошибку с ролью alert', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockRejectedValue(new Error('Network error'));

      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const errorElement = screen.getByRole('alert');
        expect(errorElement).toBeInTheDocument();
      });
    });

    it('отображает заголовок секции при ошибке', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockRejectedValue(new Error('Network error'));

      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Способ доставки')).toBeInTheDocument();
      });
    });
  });

  describe('Empty State', () => {
    it('корректно обрабатывает пустой список методов', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue([]);

      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const radiogroup = screen.getByRole('radiogroup');
        expect(radiogroup).toBeInTheDocument();
        expect(screen.queryByRole('radio')).not.toBeInTheDocument();
      });
    });
  });

  describe('Accessibility', () => {
    beforeEach(() => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue(mockMethods);
    });

    it('каждый radio имеет aria-describedby для описания', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const courierRadio = screen.getByRole('radio', { name: /курьер/i });
        expect(courierRadio).toHaveAttribute('aria-describedby', 'courier-description');
      });
    });

    it('секция имеет aria-labelledby для заголовка', async () => {
      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        const section =
          screen.getByRole('region', { hidden: true }) ||
          document.querySelector('section[aria-labelledby="delivery-section"]');
        expect(section).toBeInTheDocument();
      });
    });
  });

  describe('API Integration', () => {
    it('вызывает getDeliveryMethods при монтировании', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue(mockMethods);

      render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(deliveryService.getDeliveryMethods).toHaveBeenCalledTimes(1);
      });
    });

    it('не вызывает API повторно при ре-рендере', async () => {
      vi.mocked(deliveryService.getDeliveryMethods).mockResolvedValue(mockMethods);

      const { rerender } = render(<DeliveryOptionsWrapper />);

      await waitFor(() => {
        expect(screen.getByText('Курьер')).toBeInTheDocument();
      });

      rerender(<DeliveryOptionsWrapper />);

      // API должен быть вызван только один раз
      expect(deliveryService.getDeliveryMethods).toHaveBeenCalledTimes(1);
    });
  });
});
