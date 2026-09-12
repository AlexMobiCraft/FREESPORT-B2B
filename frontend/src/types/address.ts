/**
 * Типы для работы с адресами доставки
 * Story 16.3: Управление адресами доставки
 */

/** Тип адреса */
export type AddressType = 'shipping' | 'legal';

/**
 * Интерфейс адреса доставки (API Response)
 */
export interface Address {
  id: number;
  address_type: AddressType;
  full_name: string;
  phone: string;
  city: string;
  street: string;
  building: string;
  building_section: string;
  apartment: string;
  postal_code: string;
  is_default: boolean;
  full_address: string; // read-only, computed
  created_at: string;
  updated_at: string;
}

/**
 * Данные формы для создания/редактирования адреса
 */
export interface AddressFormData {
  address_type: AddressType;
  full_name: string;
  phone: string;
  city: string;
  street: string;
  building: string;
  building_section?: string;
  apartment?: string;
  postal_code: string;
  is_default?: boolean;
}

/**
 * Ошибки валидации адреса от API
 */
export interface AddressValidationErrors {
  address_type?: string[];
  full_name?: string[];
  phone?: string[];
  city?: string[];
  street?: string[];
  building?: string[];
  building_section?: string[];
  apartment?: string[];
  postal_code?: string[];
  is_default?: string[];
  non_field_errors?: string[];
}
