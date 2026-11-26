import { describe, expect, it } from 'vitest';
import {
  getPhoneFormat,
  getPhoneFormatMessage,
  isValidPhone,
  normalizePhoneInput,
  phoneForCountryChange,
} from '../phone';

describe('getPhoneFormat', () => {
  it('Россия и Казахстан делят код +7', () => {
    expect(getPhoneFormat('Россия')).toBe(getPhoneFormat('Казахстан'));
    expect(getPhoneFormat('Россия').prefix).toBe('+7');
  });

  it('Беларусь — +375 и 9 цифр', () => {
    expect(getPhoneFormat('Беларусь')).toMatchObject({ prefix: '+375', digits: 9 });
  });

  it.each([undefined, null, '', 'Франция', 'toString'])('%s → формат России', country => {
    expect(getPhoneFormat(country).prefix).toBe('+7');
  });
});

describe('isValidPhone', () => {
  it.each([
    ['+79001234567', 'Россия', true],
    ['+77011234567', 'Казахстан', true],
    ['+375291234567', 'Беларусь', true],
    ['+375291234567', 'Россия', false],
    ['+79001234567', 'Беларусь', false],
    ['89001234567', 'Россия', false],
    ['+7900', 'Россия', false],
    ['+7', 'Россия', false],
    ['', 'Россия', false],
    ['+7 900 123 45 67', 'Россия', false],
    ['+790012345678', 'Россия', false],
    ['+37529123456', 'Беларусь', false],
    ['+79001234567', undefined, true],
  ])('%s / %s → %s', (phone, country, expected) => {
    expect(isValidPhone(phone, country)).toBe(expected);
  });
});

describe('getPhoneFormatMessage', () => {
  it('подставляет пример формата страны', () => {
    expect(getPhoneFormatMessage('Россия')).toBe('Укажите номер телефона в формате +79001234567');
    expect(getPhoneFormatMessage('Беларусь')).toBe(
      'Укажите номер телефона в формате +375291234567'
    );
  });
});

describe('normalizePhoneInput', () => {
  it.each([
    ['', 'Россия', '+7'],
    ['+', 'Россия', '+7'],
    ['+7900', 'Россия', '+7900'],
    ['89001234567', 'Россия', '+79001234567'],
    ['79001234567', 'Россия', '+79001234567'],
    ['9001234567', 'Россия', '+79001234567'],
    ['+7 (900) 123-45-67', 'Россия', '+79001234567'],
    ['+790012345678999', 'Россия', '+79001234567'],
    ['', 'Беларусь', '+375'],
    ['+37', 'Беларусь', '+375'],
    ['+3752912', 'Беларусь', '+3752912'],
    ['375291234567', 'Беларусь', '+375291234567'],
    ['80291234567', 'Беларусь', '+375291234567'],
    ['+375 29 123-45-67 99', 'Беларусь', '+375291234567'],
    ['+7+79001234567', 'Россия', '+79001234567'],
    ['+375+375291234567', 'Беларусь', '+375291234567'],
    ['+375291234567', 'Россия', '+7'],
    ['+79001234567', 'Беларусь', '+375'],
  ])('%j (%s) → %s', (value, country, expected) => {
    expect(normalizePhoneInput(value, country)).toBe(expected);
  });
});

describe('phoneForCountryChange', () => {
  it('пустое поле остаётся пустым', () => {
    expect(phoneForCountryChange('', 'Беларусь')).toBe('');
  });

  it('Россия ↔ Казахстан сохраняет цифры', () => {
    expect(phoneForCountryChange('+79001234567', 'Казахстан')).toBe('+79001234567');
  });

  it('+7 → Беларусь сбрасывает к +375', () => {
    expect(phoneForCountryChange('+79001234567', 'Беларусь')).toBe('+375');
  });

  it('+375 → Россия сбрасывает к +7', () => {
    expect(phoneForCountryChange('+375291234567', 'Россия')).toBe('+7');
  });

  it('+375 → Беларусь не меняет значение', () => {
    expect(phoneForCountryChange('+375291234567', 'Беларусь')).toBe('+375291234567');
  });
});
