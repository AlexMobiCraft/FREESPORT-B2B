/**
 * TypeScript типы для заказов
 * Story 15.2: Интеграция с Orders API
 */

/**
 * Статус заказа (backend использует эти значения)
 */
export type OrderStatus =
  | 'pending' // Ожидает обработки ("Новый" в UI)
  | 'confirmed' // Подтвержден
  | 'processing' // В обработке
  | 'shipped' // Отправлен
  | 'delivered' // Доставлен
  | 'cancelled' // Отменен
  | 'refunded'; // Возвращен

/**
 * Способ доставки (backend возвращает строку-код)
 * pickup | courier | post | transport_company | transport_schedule
 */
export type DeliveryMethodCode =
  | 'pickup'
  | 'courier'
  | 'post'
  | 'transport_company'
  | 'transport_schedule';

/**
 * Адрес доставки (backend возвращает как строку)
 * Frontend хранит структуру для формы, но API возвращает текст
 */
export interface DeliveryAddressInput {
  city: string;
  street: string;
  house: string;
  apartment?: string;
  postal_code: string;
}

/**
 * Информация о варианте товара в заказе
 */
export interface OrderItemVariant {
  id: number;
  sku: string;
  color_name: string | null;
  size_value: string | null;
  is_active: boolean;
}

/**
 * Вложенный объект товара в элементе заказа (depth=1 в OrderItemSerializer).
 * Содержит минимальный набор полей Product, используемых в клиентском коде.
 */
export interface OrderItemProduct {
  id: number;
  name: string;
}

/**
 * Элемент заказа (контракт backend OrderItemSerializer)
 */
export interface OrderItem {
  id: number;
  product: OrderItemProduct; // nested product object (depth=1 в сериализаторе)
  variant: OrderItemVariant | null; // variant object (depth=1 в сериализаторе)
  product_name: string;
  product_sku: string;
  variant_info: string; // "Размер: XL, Цвет: Красный"
  quantity: number;
  unit_price: string; // Decimal как строка
  total_price: string; // Decimal как строка
}

/**
 * Полный заказ (контракт backend OrderDetailSerializer)
 */
export interface Order {
  id: number;
  order_number: string;
  user: number | null;
  customer_display_name: string;
  customer_name: string;
  customer_email: string;
  customer_phone: string;
  status: OrderStatus;
  total_amount: string; // Decimal как строка
  discount_amount: string;
  delivery_cost: string;
  delivery_address: string; // Текстовое поле
  delivery_method: DeliveryMethodCode;
  delivery_date: string | null;
  tracking_number: string;
  payment_method: string;
  payment_status: string;
  payment_id: string;
  notes: string;
  // Story 34-1/34-2: поля 1С и VAT-split (OrderDetailSerializer)
  sent_to_1c: boolean;
  sent_to_1c_at: string | null;
  status_1c: string;
  is_master: boolean;
  vat_group: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  subtotal: string;
  total_items: number;
  calculated_total: string;
  can_be_cancelled: boolean;
}

/**
 * Ответ при создании заказа (тот же OrderDetailSerializer)
 */
export type CreateOrderResponse = Order;

/**
 * Payload для создания заказа (контракт OrderCreateSerializer)
 * Маппится из CheckoutFormData; backend строит заказ из server-side корзины.
 */
export interface CreateOrderPayload {
  // Контактные данные (соответствуют полям модели Order)
  customer_email: string;
  customer_phone: string;
  customer_name: string; // "FirstName LastName"

  // Адрес доставки
  delivery_address: string;

  // Способ доставки
  delivery_method: string;

  // Способ оплаты
  payment_method: string;

  // Комментарий (поле notes на модели)
  notes?: string;

  // @deprecated Поле backward-compatible; сервер всегда устанавливает discount_amount=0
  // (promo-система не реализована). Поле принимается, но игнорируется backend.
  // Используй promo_code для передачи промо-кода; скидка будет вычислена сервером.
  discount_amount?: string;

  // Промо-код (stub Story 34-2 [Review][Patch]): принимается сервером, discount пока всегда 0.
  // Когда promo-система появится, backend будет проверять код и вычислять скидку.
  promo_code?: string | null;
}

/**
 * Ответ GET /api/v1/orders/ — контракт OrderListSerializer.
 * Узкий набор полей (без items, delivery_cost и т.д.).
 */
export interface OrderListItem {
  id: number;
  user: number | null;
  order_number: string;
  customer_display_name: string;
  status: OrderStatus;
  total_amount: string;
  delivery_method: DeliveryMethodCode;
  payment_method: string;
  payment_status: string;
  is_master: boolean;
  vat_group: string | null;
  sent_to_1c: boolean;
  created_at: string;
  total_items: number;
}

/**
 * Ошибка валидации от API
 */
export interface OrderValidationError {
  error: string;
  details?: {
    items?: string[];
    [key: string]: string[] | undefined;
  };
}

/**
 * Ошибка аутентификации от API
 */
export interface OrderAuthError {
  error: string;
  message: string;
}
