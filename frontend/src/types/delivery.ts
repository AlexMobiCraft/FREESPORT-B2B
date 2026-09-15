/**
 * Способ доставки, получаемый от API
 * Синхронизировано с Story 15.3a (Backend Delivery API)
 */
export interface DeliveryMethod {
  id: string;
  name: string;
  description: string;
  icon: string; // Emoji или CSS класс иконки для UI отображения
  is_available: boolean;
}
