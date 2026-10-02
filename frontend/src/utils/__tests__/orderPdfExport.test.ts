/**
 * Regression-тесты для утилиты экспорта заказа в PDF (Story 34-2)
 * Проверяет локализацию delivery_method в генерируемом PDF-документе.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';

// Hoisted mocks — доступны внутри vi.mock factory
const mockSave = vi.hoisted(() => vi.fn());
const mockText = vi.hoisted(() => vi.fn());
const mockLine = vi.hoisted(() => vi.fn());

vi.mock('jspdf', () => ({
  jsPDF: function MockJsPDF() {
    return {
      setFontSize: vi.fn(),
      setFont: vi.fn(),
      setLineWidth: vi.fn(),
      setTextColor: vi.fn(),
      addFileToVFS: vi.fn(),
      addFont: vi.fn(),
      text: mockText,
      line: mockLine,
      addPage: vi.fn(),
      save: mockSave,
      internal: { pageSize: { getWidth: () => 210 } },
    };
  },
}));

// Мок fetch для загрузки шрифтов — новый Response на каждый вызов (MSW клонирует body)
vi.stubGlobal(
  'fetch',
  vi.fn().mockImplementation(() => Promise.resolve(new Response(new ArrayBuffer(0))))
);

import {
  getDeliveryMethodLabel,
  getPaymentMethodLabel,
  getPaymentStatusLabel,
  generateOrderPdf,
} from '../orderPdfExport';
import type { Order } from '@/types/order';

const baseOrder: Order = {
  id: 1,
  order_number: '0462026007',
  user: 1,
  customer_display_name: 'Иван Иванов',
  customer_name: 'Иван Иванов',
  customer_email: 'ivan@example.com',
  customer_phone: '+79001234567',
  status: 'pending',
  total_amount: '5000.00',
  discount_amount: '0.00',
  delivery_cost: '300.00',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1',
  delivery_method: 'courier',
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'pending',
  payment_id: '',
  notes: '',
  sent_to_1c: false,
  sent_to_1c_at: null,
  status_1c: '',
  is_master: true,
  vat_group: null,
  created_at: '2026-04-18T10:00:00Z',
  updated_at: '2026-04-18T10:00:00Z',
  items: [
    {
      id: 1,
      product: { id: 101, name: 'Тестовый товар' },
      variant: null,
      product_name: 'Тестовый товар',
      product_sku: 'SKU-001',
      variant_info: 'Размер: XL',
      quantity: 2,
      unit_price: '2000.00',
      total_price: '4000.00',
    },
  ],
  subtotal: '4000.00',
  total_items: 1,
  calculated_total: '4300.00',
  can_be_cancelled: true,
};

describe('getDeliveryMethodLabel', () => {
  it('локализует courier', () => {
    expect(getDeliveryMethodLabel('courier')).toBe('Курьерская доставка');
  });

  it('локализует pickup', () => {
    expect(getDeliveryMethodLabel('pickup')).toBe('Самовывоз');
  });

  it('локализует post', () => {
    expect(getDeliveryMethodLabel('post')).toBe('Почтовая доставка');
  });

  it('локализует transport_company (Story 34-2 regression)', () => {
    expect(getDeliveryMethodLabel('transport_company')).toBe('Транспортная компания');
  });

  it('локализует transport_schedule (Story 34-2 regression)', () => {
    expect(getDeliveryMethodLabel('transport_schedule')).toBe('Доставка по расписанию');
  });

  it('возвращает raw code для неизвестного значения', () => {
    expect(getDeliveryMethodLabel('unknown_method')).toBe('unknown_method');
  });
});

describe('getPaymentMethodLabel', () => {
  it('локализует card', () => {
    expect(getPaymentMethodLabel('card')).toBe('Банковская карта');
  });

  it('локализует cash', () => {
    expect(getPaymentMethodLabel('cash')).toBe('Наличные');
  });

  it('локализует bank_transfer (Story 34-2 regression)', () => {
    expect(getPaymentMethodLabel('bank_transfer')).toBe('Банковский перевод');
  });

  it('локализует payment_on_delivery (Story 34-2 regression)', () => {
    expect(getPaymentMethodLabel('payment_on_delivery')).toBe('Оплата при получении');
  });

  it('возвращает raw code для неизвестного значения', () => {
    expect(getPaymentMethodLabel('unknown')).toBe('unknown');
  });
});

describe('getPaymentStatusLabel', () => {
  it('локализует pending', () => {
    expect(getPaymentStatusLabel('pending')).toBe('Ожидает оплаты');
  });

  it('локализует paid', () => {
    expect(getPaymentStatusLabel('paid')).toBe('Оплачен');
  });

  it('локализует failed', () => {
    expect(getPaymentStatusLabel('failed')).toBe('Ошибка оплаты');
  });

  it('локализует refunded', () => {
    expect(getPaymentStatusLabel('refunded')).toBe('Возвращен');
  });

  it('возвращает raw code для неизвестного значения', () => {
    expect(getPaymentStatusLabel('unknown')).toBe('unknown');
  });
});

describe('generateOrderPdf — delivery_method локализация', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function getTextArgs(): string[] {
    return mockText.mock.calls.map((args: unknown[]) => args[0] as string);
  }

  it('выводит локализованный label для transport_company (Story 34-2 regression)', async () => {
    await generateOrderPdf({ ...baseOrder, delivery_method: 'transport_company' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Транспортная компания');
    expect(allText).not.toContain('transport_company');
  });

  it('выводит локализованный label для transport_schedule (Story 34-2 regression)', async () => {
    await generateOrderPdf({ ...baseOrder, delivery_method: 'transport_schedule' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Доставка по расписанию');
    expect(allText).not.toContain('transport_schedule');
  });

  it('выводит локализованный label для courier', async () => {
    await generateOrderPdf({ ...baseOrder, delivery_method: 'courier' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Курьерская доставка');
  });

  it('вызывает doc.save с именем файла на основе order_number', async () => {
    await generateOrderPdf(baseOrder);
    expect(mockSave).toHaveBeenCalledWith('order-0462026007.pdf');
  });

  it('выводит UI-формат номера заказа в заголовке PDF', async () => {
    await generateOrderPdf(baseOrder);
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Заказ №4620-26007');
  });

  it('выводит локализованный label для bank_transfer (Story 34-2 regression)', async () => {
    await generateOrderPdf({ ...baseOrder, payment_method: 'bank_transfer' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Банковский перевод');
    expect(allText).not.toContain('bank_transfer');
  });

  it('выводит локализованный label для payment_on_delivery (Story 34-2 regression)', async () => {
    await generateOrderPdf({ ...baseOrder, payment_method: 'payment_on_delivery' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Оплата при получении');
    expect(allText).not.toContain('payment_on_delivery');
  });

  it('выводит локализованный статус оплаты refunded (Story 34-2 regression)', async () => {
    await generateOrderPdf({ ...baseOrder, payment_status: 'refunded' });
    const allText = getTextArgs().join(' ');
    expect(allText).toContain('Возвращен');
    expect(allText).not.toContain('refunded');
  });
});
