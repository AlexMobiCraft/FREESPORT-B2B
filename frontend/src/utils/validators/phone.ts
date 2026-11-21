/**
 * Форматы телефонных номеров по стране регистрации.
 *
 * Зеркало `backend/apps/users/phone.py`: сервер проверяет номер независимо,
 * поэтому таблицы нужно менять вместе. Россия и Казахстан делят код +7.
 */

export type PhoneCountry = 'Россия' | 'Беларусь' | 'Казахстан';

export interface PhoneFormat {
  /** Международный префикс, который поле подставляет и не даёт стереть */
  prefix: string;
  /** Сколько цифр идёт после префикса */
  digits: number;
  /** Начала номера, которые пользователь мог набрать вместо префикса (8…, 7…) */
  localPrefixes: string[];
  /** Пример для плейсхолдера и сообщения об ошибке */
  sample: string;
}

const RUSSIA_KAZAKHSTAN: PhoneFormat = {
  prefix: '+7',
  digits: 10,
  localPrefixes: ['7', '8'],
  sample: '+79001234567',
};

const BELARUS: PhoneFormat = {
  prefix: '+375',
  digits: 9,
  localPrefixes: ['375', '80'],
  sample: '+375291234567',
};

export const DEFAULT_PHONE_COUNTRY: PhoneCountry = 'Россия';

export const PHONE_FORMATS: Record<PhoneCountry, PhoneFormat> = {
  Россия: RUSSIA_KAZAKHSTAN,
  Казахстан: RUSSIA_KAZAKHSTAN,
  Беларусь: BELARUS,
};

/** Формат страны; неизвестное или не заданное значение — как Россия (default модели) */
export function getPhoneFormat(country?: string | null): PhoneFormat {
  if (country && Object.prototype.hasOwnProperty.call(PHONE_FORMATS, country)) {
    return PHONE_FORMATS[country as PhoneCountry];
  }
  return PHONE_FORMATS[DEFAULT_PHONE_COUNTRY];
}

export function isValidPhone(phone: string, country?: string | null): boolean {
  const { prefix, digits } = getPhoneFormat(country);
  return new RegExp(`^\\+${prefix.slice(1)}\\d{${digits}}$`).test(phone);
}

export function getPhoneFormatMessage(country?: string | null): string {
  return `Укажите номер телефона в формате ${getPhoneFormat(country).sample}`;
}

/**
 * Приводит ввод к виду «префикс + цифры» не длиннее формата.
 * Стёртая часть префикса возвращается на место, чтобы поле нельзя было опустошить.
 */
export function normalizePhoneInput(value: string, country?: string | null): string {
  const { prefix, digits, localPrefixes } = getPhoneFormat(country);

  let normalized = value;
  if (normalized.startsWith(prefix)) {
    // Полный номер вставили в поле с уже подставленным префиксом: «+7» + «+7900…»
    const rest = normalized.slice(prefix.length);
    if (rest.startsWith('+')) {
      return normalizePhoneInput(rest, country);
    }
  } else if (prefix.startsWith(normalized)) {
    normalized = prefix;
  } else if (normalized.startsWith('+')) {
    // Номер другой страны: склеивать его цифры с префиксом нельзя — получился бы чужой
    // номер, формально проходящий проверку. Оставляем один префикс, человек наберёт заново
    return prefix;
  } else {
    // Набрали 8900… / 7900… / 375… вместо +7 / +375: заменяем начало на префикс
    const onlyDigits = normalized.replace(/\D/g, '');
    const local = localPrefixes.find(p => onlyDigits.startsWith(p));
    normalized = prefix + (local ? onlyDigits.slice(local.length) : onlyDigits);
  }

  return prefix + normalized.slice(prefix.length).replace(/\D/g, '').slice(0, digits);
}

/**
 * Что оставить в поле при смене страны. Внутри одной группы префикса (+7:
 * Россия ↔ Казахстан) введённое сохраняется; при смене группы непустое поле
 * сбрасывается к префиксу новой страны, пустое остаётся пустым.
 */
export function phoneForCountryChange(current: string, nextCountry?: string | null): string {
  if (!current) {
    return current;
  }
  const { prefix } = getPhoneFormat(nextCountry);
  return current.startsWith(prefix) ? current : prefix;
}
