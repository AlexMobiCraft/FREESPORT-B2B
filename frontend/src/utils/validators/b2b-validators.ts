/**
 * B2B Validators
 * Story 28.2 - Поток регистрации B2B
 *
 * Валидаторы для ИНН и ОГРН
 * MVP: Проверка длины и числового формата
 */

/**
 * Валидация ИНН (Идентификационный номер налогоплательщика)
 *
 * Правила:
 * - ИНН юридического лица: 10 цифр
 * - ИНН физического лица/ИП: 12 цифр
 * - Только цифры
 *
 * @param value - ИНН для валидации
 * @returns true если валидный, иначе false
 */
export function validateINN(value: string): boolean {
  // Проверка на пустоту
  if (!value || value.trim() === '') {
    return false;
  }

  // Удаляем пробелы
  const cleanValue = value.trim();

  // Проверка, что только цифры
  if (!/^\d+$/.test(cleanValue)) {
    return false;
  }

  // Проверка длины (10 или 12 цифр)
  const length = cleanValue.length;
  return length === 10 || length === 12;
}

/**
 * Валидация ОГРН (Основной государственный регистрационный номер)
 *
 * Правила:
 * - ОГРН юридического лица: 13 цифр
 * - ОГРНИП (для ИП): 15 цифр
 * - Только цифры
 *
 * @param value - ОГРН для валидации
 * @returns true если валидный, иначе false
 */
export function validateOGRN(value: string): boolean {
  // Проверка на пустоту
  if (!value || value.trim() === '') {
    return false;
  }

  // Удаляем пробелы
  const cleanValue = value.trim();

  // Проверка, что только цифры
  if (!/^\d+$/.test(cleanValue)) {
    return false;
  }

  // Проверка длины (13 или 15 цифр)
  const length = cleanValue.length;
  return length === 13 || length === 15;
}

/**
 * Получить сообщение об ошибке для невалидного ИНН
 */
export function getINNErrorMessage(value: string): string {
  if (!value || value.trim() === '') {
    return 'ИНН обязателен';
  }

  const cleanValue = value.trim();

  if (!/^\d+$/.test(cleanValue)) {
    return 'ИНН должен содержать только цифры';
  }

  const length = cleanValue.length;
  if (length !== 10 && length !== 12) {
    return 'ИНН должен содержать 10 цифр (юр. лицо) или 12 цифр (ИП)';
  }

  return 'Неверный формат ИНН';
}

/**
 * Получить сообщение об ошибке для невалидного ОГРН
 */
export function getOGRNErrorMessage(value: string): string {
  if (!value || value.trim() === '') {
    return 'ОГРН обязателен';
  }

  const cleanValue = value.trim();

  if (!/^\d+$/.test(cleanValue)) {
    return 'ОГРН должен содержать только цифры';
  }

  const length = cleanValue.length;
  if (length !== 13 && length !== 15) {
    return 'ОГРН должен содержать 13 цифр (юр. лицо) или 15 цифр (ОГРНИП)';
  }

  return 'Неверный формат ОГРН';
}
