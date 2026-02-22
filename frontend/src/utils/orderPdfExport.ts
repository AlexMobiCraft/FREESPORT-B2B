/**
 * Утилита для экспорта заказа в PDF
 * Story 16.2 - AC6: Экспорт заказа в PDF (только для B2B)
 */

import { jsPDF } from 'jspdf';
import type { Order } from '@/types/order';

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
 * Генерирует PDF документ заказа для B2B пользователей
 */
export function generateOrderPdf(order: Order): void {
  const doc = new jsPDF({
    orientation: 'portrait',
    unit: 'mm',
    format: 'a4',
  });

  const pageWidth = doc.internal.pageSize.getWidth();
  const margin = 20;
  let yPosition = margin;

  // Заголовок документа
  doc.setFontSize(18);
  doc.setFont('helvetica', 'bold');
  doc.text(`Заказ №${order.order_number}`, pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 12;

  // Дата создания
  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.text(`Дата: ${formatDate(order.created_at)}`, pageWidth / 2, yPosition, { align: 'center' });
  yPosition += 15;

  // Информация о заказе
  doc.setFontSize(12);
  doc.setFont('helvetica', 'bold');
  doc.text('Информация о заказе', margin, yPosition);
  yPosition += 8;

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');

  const orderInfo = [
    `Статус: ${getStatusLabel(order.status)}`,
    `Способ оплаты: ${order.payment_method}`,
    `Статус оплаты: ${order.payment_status}`,
    `Способ доставки: ${order.delivery_method}`,
  ];

  orderInfo.forEach(line => {
    doc.text(line, margin, yPosition);
    yPosition += 6;
  });

  yPosition += 5;

  // Адрес доставки
  if (order.delivery_address) {
    doc.setFont('helvetica', 'bold');
    doc.text('Адрес доставки:', margin, yPosition);
    yPosition += 6;
    doc.setFont('helvetica', 'normal');
    doc.text(order.delivery_address, margin, yPosition);
    yPosition += 10;
  }

  // Информация о клиенте
  doc.setFont('helvetica', 'bold');
  doc.text('Получатель:', margin, yPosition);
  yPosition += 6;
  doc.setFont('helvetica', 'normal');
  doc.text(`${order.customer_name}`, margin, yPosition);
  yPosition += 5;
  doc.text(`Тел: ${order.customer_phone}`, margin, yPosition);
  yPosition += 5;
  doc.text(`Email: ${order.customer_email}`, margin, yPosition);
  yPosition += 15;

  // Таблица товаров
  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('Товары', margin, yPosition);
  yPosition += 8;

  // Заголовки таблицы
  doc.setFontSize(9);
  doc.setFont('helvetica', 'bold');
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
  doc.setFont('helvetica', 'normal');
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

  doc.setFont('helvetica', 'bold');
  doc.setFontSize(12);
  doc.text('Итого:', totalsX, yPosition);
  doc.text(formatPrice(order.total_amount), pageWidth - margin, yPosition, { align: 'right' });

  // Футер
  yPosition = 280;
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
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
