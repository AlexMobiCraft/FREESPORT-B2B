/**
 * Утилита для экспорта заказа в PDF
 * Story 16.2 - AC6: Экспорт заказа в PDF (только для B2B)
 */

import { jsPDF } from 'jspdf';
import type { Order } from '@/types/order';
import { formatOrderNumber } from '@/utils/orderNumberFormat';

async function loadFont(doc: jsPDF, url: string, name: string): Promise<void> {
  const res = await fetch(url);
  const buf = await res.arrayBuffer();
  const bytes = new Uint8Array(buf);
  let binary = '';
  const chunkSize = 8192;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunkSize));
  }
  const b64 = btoa(binary);
  doc.addFileToVFS(name, b64);
  doc.addFont(name, 'Arial', name === 'arialbd.ttf' ? 'bold' : 'normal');
}

/**
 * Форматирует дату в читаемый формат
 */
function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('ru-RU', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/**
 * Форматирует цену с валютой
 */
function formatPrice(price: string | number): string {
  const numPrice = typeof price === 'string' ? parseFloat(price) : price;
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    minimumFractionDigits: 2,
  }).format(numPrice);
}

/**
 * Получает русское название статуса заказа
 */
function getStatusLabel(status: string): string {
  const statusLabels: Record<string, string> = {
    pending: 'Новый',
    confirmed: 'Подтверждён',
    processing: 'В обработке',
    shipped: 'Отправлен',
    delivered: 'Доставлен',
    cancelled: 'Отменён',
    refunded: 'Возвращён',
  };
  return statusLabels[status] || status;
}

/**
 * Получает русское название способа доставки (Story 34-2)
 */
export function getDeliveryMethodLabel(method: string): string {
  const deliveryMethodLabels: Record<string, string> = {
    pickup: 'Самовывоз',
    courier: 'Курьерская доставка',
    post: 'Почтовая доставка',
    transport_company: 'Транспортная компания',
    transport_schedule: 'Доставка по расписанию',
  };
  return deliveryMethodLabels[method] || method;
}

/**
 * Получает русское название способа оплаты (Story 34-2)
 */
export function getPaymentMethodLabel(method: string): string {
  const paymentMethodLabels: Record<string, string> = {
    card: 'Банковская карта',
    cash: 'Наличные',
    bank_transfer: 'Банковский перевод',
    payment_on_delivery: 'Оплата при получении',
  };
  return paymentMethodLabels[method] || method;
}

/**
 * Получает русское название статуса оплаты (Story 34-2)
 */
export function getPaymentStatusLabel(status: string): string {
  const paymentStatusLabels: Record<string, string> = {
    pending: 'Ожидает оплаты',
    paid: 'Оплачен',
    failed: 'Ошибка оплаты',
    refunded: 'Возвращен',
  };
  return paymentStatusLabels[status] || status;
}

/**
 * Генерирует PDF документ заказа для B2B пользователей
 */
export async function generateOrderPdf(order: Order): Promise<void> {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });
  const formattedOrderNumber = formatOrderNumber(order.order_number);

  await loadFont(doc, '/fonts/arial.ttf', 'arial.ttf');
  await loadFont(doc, '/fonts/arialbd.ttf', 'arialbd.ttf');

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  let yPosition = margin;

  // Заголовок документа
  doc.setFontSize(18);
  doc.setFont('Arial', 'bold');
  doc.text(`Заказ №${formattedOrderNumber}`, pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 12;

  // Дата создания
  doc.setFontSize(10);
  doc.setFont('Arial', 'normal');
  doc.text(`Дата: ${formatDate(order.created_at)}`, pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 15;

  // Информация о заказе
  doc.setFontSize(12);
  doc.setFont('Arial', 'bold');
  doc.text('Информация о заказе', margin, yPosition);
  yPosition += 8;

  doc.setFontSize(10);
  doc.setFont('Arial', 'normal');

  const orderInfo = [
    `Статус: ${getStatusLabel(order.status)}`,
    `Способ оплаты: ${getPaymentMethodLabel(order.payment_method)}`,
    `Статус оплаты: ${getPaymentStatusLabel(order.payment_status)}`,
    `Способ доставки: ${getDeliveryMethodLabel(order.delivery_method)}`,
  ];

  orderInfo.forEach(line => {
    doc.text(line, margin, yPosition);
    yPosition += 6;
  });

  yPosition += 5;

  // Адрес доставки
  if (order.delivery_address) {
    doc.setFont('Arial', 'bold');
    doc.text('Адрес доставки:', margin, yPosition);
    yPosition += 6;
    doc.setFont('Arial', 'normal');
    doc.text(order.delivery_address, margin, yPosition);
    yPosition += 10;
  }

  // Информация о клиенте
  doc.setFont('Arial', 'bold');
  doc.text('Получатель:', margin, yPosition);
  yPosition += 6;
  doc.setFont('Arial', 'normal');
  doc.text(`${order.customer_name}`, margin, yPosition);
  yPosition += 5;
  doc.text(`Тел: ${order.customer_phone}`, margin, yPosition);
  yPosition += 5;
  doc.text(`Email: ${order.customer_email}`, margin, yPosition);
  yPosition += 15;

  // Таблица товаров
  doc.setFont('Arial', 'bold');
  doc.setFontSize(12);
  doc.text('Товары', margin, yPosition);
  yPosition += 8;

  // Заголовки таблицы
  doc.setFontSize(9);
  doc.setFont('Arial', 'bold');
  const colWidths = [80, 25, 30, 35];
  const headers = ['Наименование', 'Кол-во', 'Цена', 'Сумма'];
  let xPos = margin;

  headers.forEach((header, i) => {
    doc.text(header, xPos, yPosition);
    xPos += colWidths[i];
  });
  yPosition += 2;

  // Линия под заголовком
  doc.setLineWidth(0.3);
  doc.line(margin, yPosition, pageWidth - margin, yPosition);
  yPosition += 5;

  // Строки товаров
  doc.setFont('Arial', 'normal');
  order.items.forEach(item => {
    // Проверяем, нужна ли новая страница
    if (yPosition > 270) {
      doc.addPage();
      yPosition = margin;
    }

    xPos = margin;

    // Название товара (с переносом если длинное)
    const productName =
      item.product_name.length > 40
        ? item.product_name.substring(0, 37) + '...'
        : item.product_name;
    doc.text(productName, xPos, yPosition);
    xPos += colWidths[0];

    doc.text(item.quantity.toString(), xPos, yPosition);
    xPos += colWidths[1];

    doc.text(formatPrice(item.unit_price), xPos, yPosition);
    xPos += colWidths[2];

    doc.text(formatPrice(item.total_price), xPos, yPosition);

    // Добавляем информацию о варианте если есть
    if (item.variant_info) {
      yPosition += 4;
      doc.setFontSize(8);
      doc.setTextColor(100);
      doc.text(`  ${item.variant_info}`, margin, yPosition);
      doc.setFontSize(9);
      doc.setTextColor(0);
    }

    yPosition += 6;
  });

  // Линия над итогами
  yPosition += 3;
  doc.line(margin, yPosition, pageWidth - margin, yPosition);
  yPosition += 8;

  // Итоги
  doc.setFontSize(10);
  const totalsX = pageWidth - margin - 60;

  if (order.discount_amount && parseFloat(order.discount_amount) > 0) {
    doc.text('Скидка:', totalsX, yPosition);
    doc.text(`-${formatPrice(order.discount_amount)}`, pageWidth - margin, yPosition, {
      align: 'right',
    });
    yPosition += 6;
  }

  if (order.delivery_cost && parseFloat(order.delivery_cost) > 0) {
    doc.text('Доставка:', totalsX, yPosition);
    doc.text(formatPrice(order.delivery_cost), pageWidth - margin, yPosition, { align: 'right' });
    yPosition += 6;
  }

  doc.setFont('Arial', 'bold');
  doc.setFontSize(12);
  doc.text('Итого:', totalsX, yPosition);
  doc.text(formatPrice(order.total_amount), pageWidth - margin, yPosition, { align: 'right' });

  // Футер
  yPosition = 280;
  doc.setFontSize(8);
  doc.setFont('Arial', 'normal');
  doc.setTextColor(128);
  doc.text(
    `Документ сформирован ${new Date().toLocaleString('ru-RU')} | FREESPORT`,
    pageWidth / 2,
    yPosition,
    { align: 'center' }
  );

  // Сохраняем PDF
  doc.save(`order-${order.order_number}.pdf`);
}
