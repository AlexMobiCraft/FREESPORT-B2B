/**
 * Маппинг адреса между API (snake_case) и формой checkout (camelCase).
 *
 * Единая точка трансформации: предотвращает рассинхронизацию полей,
 * когда сторонние компоненты пытаются конвертировать данные ad-hoc.
 *
 * API поля   ↔ форма:
 *   building          ↔ house
 *   building_section  ↔ buildingSection
 *   postal_code       ↔ postalCode
 *   full_name         ↔ firstName + lastName (split по первому пробелу)
 *   phone, city, street, apartment — без переименования
 */

import type { Address, AddressFormData } from '@/types/address';
import type { CheckoutFormData } from '@/schemas/checkoutSchema';

/**
 * Поля формы, относящиеся к адресу + контактам, которые могут быть
 * автозаполнены из сохранённого Address.
 */
export type CheckoutAddressFields = Pick<
  CheckoutFormData,
  | 'firstName'
  | 'lastName'
  | 'phone'
  | 'city'
  | 'street'
  | 'house'
  | 'buildingSection'
  | 'apartment'
  | 'postalCode'
>;

function splitFullName(fullName: string | null | undefined): {
  firstName: string;
  lastName: string;
} {
  if (!fullName) return { firstName: '', lastName: '' };
  const trimmed = fullName.trim();
  if (!trimmed) return { firstName: '', lastName: '' };
  const spaceIdx = trimmed.indexOf(' ');
  if (spaceIdx === -1) return { firstName: trimmed, lastName: '' };
  return {
    firstName: trimmed.slice(0, spaceIdx),
    lastName: trimmed.slice(spaceIdx + 1).trim(),
  };
}

/**
 * Преобразует Address (ответ API) в значения полей формы checkout.
 * Используется при автозаполнении формы выбранным сохранённым адресом.
 */
export function addressToFormValues(address: Address): CheckoutAddressFields {
  const { firstName, lastName } = splitFullName(address.full_name);
  return {
    firstName,
    lastName,
    phone: address.phone,
    city: address.city,
    street: address.street,
    house: address.building,
    buildingSection: address.building_section ?? '',
    apartment: address.apartment ?? '',
    postalCode: address.postal_code,
  };
}

/**
 * Преобразует данные формы checkout в payload для POST /users/addresses/.
 * Используется при сохранении нового адреса в профиль после оформления заказа.
 *
 * @param data - валидированные данные формы
 * @param options.isDefault - флаг is_default для нового адреса
 *   (true при отсутствии других адресов у пользователя — first save)
 */
export function formValuesToAddressPayload(
  data: CheckoutFormData,
  options: { isDefault: boolean }
): AddressFormData {
  return {
    address_type: 'shipping',
    full_name: `${data.firstName} ${data.lastName}`.trim(),
    phone: data.phone,
    city: data.city,
    street: data.street,
    building: data.house,
    building_section: data.buildingSection ?? '',
    apartment: data.apartment ?? '',
    postal_code: data.postalCode,
    is_default: options.isDefault,
  };
}

/**
 * Сравнивает поля формы со значениями из сохранённого адреса.
 * Возвращает true, если хотя бы одно адресное поле формы отличается от
 * соответствующего поля Address — то есть пользователь правил данные вручную
 * после автозаполнения.
 *
 * Контактные поля (firstName/lastName/phone) тоже учитываются, поскольку
 * Address их хранит.
 */
export function isFormDirtyVsAddress(values: CheckoutAddressFields, address: Address): boolean {
  const expected = addressToFormValues(address);
  return (
    values.firstName !== expected.firstName ||
    values.lastName !== expected.lastName ||
    values.phone !== expected.phone ||
    values.city !== expected.city ||
    values.street !== expected.street ||
    values.house !== expected.house ||
    (values.buildingSection ?? '') !== expected.buildingSection ||
    (values.apartment ?? '') !== expected.apartment ||
    values.postalCode !== expected.postalCode
  );
}
