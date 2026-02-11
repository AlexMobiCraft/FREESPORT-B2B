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
 * pickup | courier | post | transport
 */
export type DeliveryMethodCode = 'pickup' | 'courier' | 'post' | 'transport_company';

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
 * Элемент заказа (контракт backend OrderItemSerializer)
 */
export interface OrderItem {
  id: number;
  product: number; // product ID
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
 * Payload для создания заказа
 * Маппится из CheckoutFormData + CartItem[]
 */
export interface CreateOrderPayload {
  // Контактные данные
  email: string;
  phone: string;
  first_name: string;
  last_name: string;

  // Адрес доставки
  delivery_address: string;

  // Способ доставки
  delivery_method: string;

  // Способ оплаты
  payment_method: string;

  // Товары из корзины (используем variant_id из cartStore)
  items: Array<{
    variant_id: number;
    quantity: number;
  }>;

  // Комментарий
  comment?: string;
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
