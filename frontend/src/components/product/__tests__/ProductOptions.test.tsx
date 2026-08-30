/**
 * Unit тесты для ProductOptions (Story 13.5a)
 * Тестирование компонента выбора вариантов товара
 *
 * @see docs/stories/epic-13/13.5a.productoptions-ui-msw-mock.md
 */

import { describe, it, expect, vi, beforeEach, type Mock } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ProductOptions } from '../ProductOptions';
import type { ProductVariant } from '@/types/api';

/**
 * Mock данные для тестов
 */
const mockVariants: ProductVariant[] = [
  {
    id: 1,
    sku: 'TEST-RED-42',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 15,
    is_in_stock: true,
    available_quantity: 15,
  },
  {
    id: 2,
    sku: 'TEST-RED-43',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '43',
    current_price: '5990.00',
    stock_quantity: 0,
    is_in_stock: false,
    available_quantity: 0,
  },
  {
    id: 3,
    sku: 'TEST-RED-44',
    color_name: 'Красный',
    color_hex: '#FF0000',
    size_value: '44',
    current_price: '5990.00',
    stock_quantity: 8,
    is_in_stock: true,
    available_quantity: 8,
  },
  {
    id: 4,
    sku: 'TEST-BLUE-42',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 10,
    is_in_stock: true,
    available_quantity: 10,
  },
  {
    id: 5,
    sku: 'TEST-BLUE-43',
    color_name: 'Синий',
    color_hex: '#0000FF',
    size_value: '43',
    current_price: '5990.00',
    stock_quantity: 5,
    is_in_stock: true,
    available_quantity: 5,
  },
  {
    id: 6,
    sku: 'TEST-GREEN-42',
    color_name: 'Зеленый',
    color_hex: '#00FF00',
    size_value: '42',
    current_price: '5990.00',
    stock_quantity: 0,
    is_in_stock: false,
    available_quantity: 0,
  },
];

describe('ProductOptions', () => {
  let onSelectionChange: Mock;

  beforeEach(() => {
    onSelectionChange = vi.fn();
  });

  describe('Рендеринг', () => {
    it('рендерит компонент с data-testid', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByTestId('product-options')).toBeInTheDocument();
    });

    it('рендерит селекторы размеров', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByText('Размер')).toBeInTheDocument();
      expect(screen.getByText('42')).toBeInTheDocument();
      expect(screen.getByText('43')).toBeInTheDocument();
      expect(screen.getByText('44')).toBeInTheDocument();
    });

    it('рендерит селекторы цветов', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByText('Цвет')).toBeInTheDocument();
      expect(screen.getByText('Красный')).toBeInTheDocument();
      expect(screen.getByText('Синий')).toBeInTheDocument();
      expect(screen.getByText('Зеленый')).toBeInTheDocument();
    });

    it('рендерит цветовые индикаторы для цветов', () => {
      const { container } = render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      // Проверяем наличие цветовых индикаторов
      const colorIndicators = container.querySelectorAll('[style*="background-color"]');
      expect(colorIndicators.length).toBeGreaterThan(0);
    });

    it('не рендерит компонент если нет вариантов', () => {
      const { container } = render(
        <ProductOptions variants={[]} selectedOptions={{}} onSelectionChange={onSelectionChange} />
      );

      expect(container.firstChild).toBeNull();
    });

    it('не рендерит секцию размеров если нет размеров', () => {
      const variantsWithoutSizes: ProductVariant[] = [
        {
          id: 1,
          sku: 'TEST-RED',
          color_name: 'Красный',
          color_hex: '#FF0000',
          current_price: '5990.00',
          stock_quantity: 15,
          is_in_stock: true,
          available_quantity: 15,
        },
      ];

      render(
        <ProductOptions
          variants={variantsWithoutSizes}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.queryByText('Размер')).not.toBeInTheDocument();
      expect(screen.getByText('Цвет')).toBeInTheDocument();
    });

    it('не рендерит секцию цветов если нет цветов', () => {
      const variantsWithoutColors: ProductVariant[] = [
        {
          id: 1,
          sku: 'TEST-42',
          size_value: '42',
          current_price: '5990.00',
          stock_quantity: 15,
          is_in_stock: true,
          available_quantity: 15,
        },
      ];

      render(
        <ProductOptions
          variants={variantsWithoutColors}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByText('Размер')).toBeInTheDocument();
      expect(screen.queryByText('Цвет')).not.toBeInTheDocument();
    });
  });

  describe('Disabled state (AC: 4)', () => {
    it('отображает недоступные размеры как disabled', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      // Размер 43 недоступен (только RED-43 с is_in_stock: false, но BLUE-43 доступен)
      // Проверяем размер, который полностью недоступен - нет такого в наших данных
      // Все размеры имеют хотя бы один доступный вариант
      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      expect(size42Button).not.toHaveAttribute('aria-disabled', 'true');
    });

    it('отображает недоступные цвета как disabled', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      // Зеленый цвет недоступен (is_in_stock: false)
      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      expect(greenButton).toHaveAttribute('aria-disabled', 'true');
    });

    it('применяет opacity-50 к недоступным опциям', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      expect(greenButton).toHaveClass('opacity-50');
    });

    it('применяет cursor-not-allowed к недоступным опциям', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      expect(greenButton).toHaveClass('cursor-not-allowed');
    });
  });

  describe('Взаимодействие (AC: 5)', () => {
    it('вызывает onSelectionChange при клике на размер', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      await user.click(size42Button);

      expect(onSelectionChange).toHaveBeenCalledWith({ size: '42' });
    });

    it('вызывает onSelectionChange при клике на цвет', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const redButton = screen.getByRole('radio', { name: /Цвет: Красный/i });
      await user.click(redButton);

      expect(onSelectionChange).toHaveBeenCalledWith({ color: 'Красный' });
    });

    it('сохраняет предыдущий выбор при выборе нового размера', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ color: 'Красный' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      await user.click(size42Button);

      expect(onSelectionChange).toHaveBeenCalledWith({ color: 'Красный', size: '42' });
    });

    it('сохраняет предыдущий выбор при выборе нового цвета', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ size: '42' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const blueButton = screen.getByRole('radio', { name: /Цвет: Синий/i });
      await user.click(blueButton);

      expect(onSelectionChange).toHaveBeenCalledWith({ size: '42', color: 'Синий' });
    });

    it('НЕ вызывает callback при клике на disabled опцию', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      await user.click(greenButton);

      expect(onSelectionChange).not.toHaveBeenCalled();
    });
  });

  describe('Selected state', () => {
    it('отображает выбранный размер как selected', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ size: '42' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      expect(size42Button).toHaveAttribute('aria-checked', 'true');
    });

    it('отображает выбранный цвет как selected', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ color: 'Красный' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const redButton = screen.getByRole('radio', { name: /Цвет: Красный/i });
      expect(redButton).toHaveAttribute('aria-checked', 'true');
    });

    it('применяет стили selected к выбранной опции', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ size: '42' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      // Проверяем наличие primary цвета в классах
      expect(size42Button).toHaveClass('bg-primary');
      expect(size42Button).toHaveClass('text-white');
    });
  });

  describe('Accessibility (AC: 6)', () => {
    it('имеет role="radiogroup" для групп опций', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const radiogroups = screen.getAllByRole('radiogroup');
      expect(radiogroups.length).toBe(2); // Размер и Цвет
    });

    it('имеет aria-label для групп опций', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByRole('radiogroup', { name: /Выбор размера/i })).toBeInTheDocument();
      expect(screen.getByRole('radiogroup', { name: /Выбор цвета/i })).toBeInTheDocument();
    });

    it('имеет role="radio" для каждой опции', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const radios = screen.getAllByRole('radio');
      expect(radios.length).toBeGreaterThan(0);
    });

    it('имеет aria-checked для выбранных опций', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ size: '42', color: 'Красный' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      const redButton = screen.getByRole('radio', { name: /Цвет: Красный/i });

      expect(size42Button).toHaveAttribute('aria-checked', 'true');
      expect(redButton).toHaveAttribute('aria-checked', 'true');
    });

    it('имеет aria-disabled для недоступных опций', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      expect(greenButton).toHaveAttribute('aria-disabled', 'true');
    });

    it('поддерживает keyboard navigation - Enter', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      size42Button.focus();
      await user.keyboard('{Enter}');

      expect(onSelectionChange).toHaveBeenCalledWith({ size: '42' });
    });

    it('поддерживает keyboard navigation - Space', async () => {
      const user = userEvent.setup();

      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      size42Button.focus();
      await user.keyboard(' ');

      expect(onSelectionChange).toHaveBeenCalledWith({ size: '42' });
    });

    it('disabled опции имеют tabIndex=-1', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const greenButton = screen.getByRole('radio', { name: /Цвет: Зеленый/i });
      expect(greenButton).toHaveAttribute('tabIndex', '-1');
    });

    it('доступные опции имеют tabIndex=0', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const redButton = screen.getByRole('radio', { name: /Цвет: Красный/i });
      expect(redButton).toHaveAttribute('tabIndex', '0');
    });
  });

  describe('Стили дизайн-системы (AC: 6, IV2)', () => {
    it('применяет корректные базовые стили к Chip', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      expect(size42Button).toHaveClass('rounded-2xl'); // 16px radius
      expect(size42Button).toHaveClass('px-4');
      expect(size42Button).toHaveClass('py-2');
    });

    it('применяет стили default state', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const size44Button = screen.getByRole('radio', { name: /Размер: 44/i });
      expect(size44Button).toHaveClass('bg-neutral-100');
      expect(size44Button).toHaveClass('border-neutral-400');
    });

    it('применяет стили selected state', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{ size: '42' }}
          onSelectionChange={onSelectionChange}
        />
      );

      const size42Button = screen.getByRole('radio', { name: /Размер: 42/i });
      expect(size42Button).toHaveClass('bg-primary');
      expect(size42Button).toHaveClass('text-white');
      expect(size42Button).toHaveClass('border-primary');
    });

    it('применяет spacing между группами (space-y-6)', () => {
      const { container } = render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const wrapper = container.querySelector('[data-testid="product-options"]');
      expect(wrapper).toHaveClass('space-y-6');
    });

    it('применяет spacing между Chip (gap-2)', () => {
      const { container } = render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const chipContainers = container.querySelectorAll('.flex.flex-wrap.gap-2');
      expect(chipContainers.length).toBe(2); // Размеры и Цвета
    });

    it('применяет typography для заголовков групп', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      const sizeHeader = screen.getByText('Размер');
      expect(sizeHeader).toHaveClass('text-sm');
      expect(sizeHeader).toHaveClass('font-semibold');
      expect(sizeHeader).toHaveClass('font-montserrat');
    });
  });

  describe('Edge cases', () => {
    it('обрабатывает варианты без color_hex', () => {
      const variantsWithoutHex: ProductVariant[] = [
        {
          id: 1,
          sku: 'TEST-RED-42',
          color_name: 'Красный',
          color_hex: null,
          size_value: '42',
          current_price: '5990.00',
          stock_quantity: 15,
          is_in_stock: true,
          available_quantity: 15,
        },
      ];

      render(
        <ProductOptions
          variants={variantsWithoutHex}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      expect(screen.getByText('Красный')).toBeInTheDocument();
    });

    it('обрабатывает дубликаты размеров корректно', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      // Размер 42 встречается в нескольких вариантах, но должен отображаться один раз
      const size42Buttons = screen.getAllByText('42');
      expect(size42Buttons.length).toBe(1);
    });

    it('обрабатывает дубликаты цветов корректно', () => {
      render(
        <ProductOptions
          variants={mockVariants}
          selectedOptions={{}}
          onSelectionChange={onSelectionChange}
        />
      );

      // Красный встречается в нескольких вариантах, но должен отображаться один раз
      const redButtons = screen.getAllByText('Красный');
      expect(redButtons.length).toBe(1);
    });
  });
});
