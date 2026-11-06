/**
 * B2B Validators Tests
 * Story 28.2 - Поток регистрации B2B
 *
 * Unit-тесты для валидаторов ИНН и ОГРН
 * AC 7: Unit-тесты для логики валидации ИНН/ОГРН
 */

import { describe, it, expect } from 'vitest';
import {
  validateINN,
  validateOGRN,
  getINNErrorMessage,
  getOGRNErrorMessage,
} from '@/utils/validators/b2b-validators';

describe('validateINN', () => {
  describe('Valid cases', () => {
    it('should accept valid 10-digit INN (юр. лицо)', () => {
      expect(validateINN('1234567890')).toBe(true);
      expect(validateINN('9876543210')).toBe(true);
      expect(validateINN('5000456789')).toBe(true);
    });

    it('should accept valid 12-digit INN (ИП)', () => {
      expect(validateINN('123456789012')).toBe(true);
      expect(validateINN('987654321098')).toBe(true);
      expect(validateINN('500045678901')).toBe(true);
    });

    it('should trim whitespace', () => {
      expect(validateINN('  1234567890  ')).toBe(true);
      expect(validateINN(' 123456789012 ')).toBe(true);
    });
  });

  describe('Invalid cases', () => {
    it('should reject empty string', () => {
      expect(validateINN('')).toBe(false);
      expect(validateINN('   ')).toBe(false);
    });

    it('should reject non-numeric characters', () => {
      expect(validateINN('123abc7890')).toBe(false);
      expect(validateINN('12-34-56-78')).toBe(false);
      expect(validateINN('1234 5678 90')).toBe(false);
    });

    it('should reject wrong length', () => {
      expect(validateINN('123')).toBe(false); // Too short
      expect(validateINN('123456789')).toBe(false); // 9 digits
      expect(validateINN('12345678901')).toBe(false); // 11 digits
      expect(validateINN('1234567890123')).toBe(false); // 13 digits
      expect(validateINN('12345678901234567890')).toBe(false); // Too long
    });

    it('should reject special characters', () => {
      expect(validateINN('1234567890!')).toBe(false);
      expect(validateINN('123456789@')).toBe(false);
      expect(validateINN('#1234567890')).toBe(false);
    });
  });
});

describe('validateOGRN', () => {
  describe('Valid cases', () => {
    it('should accept valid 13-digit OGRN (юр. лицо)', () => {
      expect(validateOGRN('1234567890123')).toBe(true);
      expect(validateOGRN('9876543210987')).toBe(true);
      expect(validateOGRN('1027700035769')).toBe(true);
    });

    it('should accept valid 15-digit OGRNIP', () => {
      expect(validateOGRN('123456789012345')).toBe(true);
      expect(validateOGRN('987654321098765')).toBe(true);
      expect(validateOGRN('312774604500011')).toBe(true);
    });

    it('should trim whitespace', () => {
      expect(validateOGRN('  1234567890123  ')).toBe(true);
      expect(validateOGRN(' 123456789012345 ')).toBe(true);
    });
  });

  describe('Invalid cases', () => {
    it('should reject empty string', () => {
      expect(validateOGRN('')).toBe(false);
      expect(validateOGRN('   ')).toBe(false);
    });

    it('should reject non-numeric characters', () => {
      expect(validateOGRN('123abc7890123')).toBe(false);
      expect(validateOGRN('12-34-56-78-90-12-3')).toBe(false);
      expect(validateOGRN('1234 5678 90123')).toBe(false);
    });

    it('should reject wrong length', () => {
      expect(validateOGRN('123')).toBe(false); // Too short
      expect(validateOGRN('123456789012')).toBe(false); // 12 digits
      expect(validateOGRN('12345678901234')).toBe(false); // 14 digits
      expect(validateOGRN('1234567890123456')).toBe(false); // 16 digits
      expect(validateOGRN('12345678901234567890')).toBe(false); // Too long
    });

    it('should reject special characters', () => {
      expect(validateOGRN('1234567890123!')).toBe(false);
      expect(validateOGRN('12345678901@3')).toBe(false);
      expect(validateOGRN('#1234567890123')).toBe(false);
    });
  });
});

describe('getINNErrorMessage', () => {
  it('should return appropriate error for empty INN', () => {
    expect(getINNErrorMessage('')).toBe('ИНН обязателен');
    expect(getINNErrorMessage('   ')).toBe('ИНН обязателен');
  });

  it('should return error for non-numeric INN', () => {
    expect(getINNErrorMessage('123abc7890')).toBe('ИНН должен содержать только цифры');
    expect(getINNErrorMessage('12-34-56-78-90')).toBe('ИНН должен содержать только цифры');
  });

  it('should return error for wrong length INN', () => {
    const message = getINNErrorMessage('123456789'); // 9 digits
    expect(message).toBe('ИНН должен содержать 10 цифр (юр. лицо) или 12 цифр (ИП)');
  });
});

describe('getOGRNErrorMessage', () => {
  it('should return appropriate error for empty OGRN', () => {
    expect(getOGRNErrorMessage('')).toBe('ОГРН обязателен');
    expect(getOGRNErrorMessage('   ')).toBe('ОГРН обязателен');
  });

  it('should return error for non-numeric OGRN', () => {
    expect(getOGRNErrorMessage('123abc7890123')).toBe('ОГРН должен содержать только цифры');
    expect(getOGRNErrorMessage('12-34-56-78-90-12-3')).toBe('ОГРН должен содержать только цифры');
  });

  it('should return error for wrong length OGRN', () => {
    const message = getOGRNErrorMessage('123456789012'); // 12 digits
    expect(message).toBe('ОГРН должен содержать 13 цифр (юр. лицо) или 15 цифр (ОГРНИП)');
  });
});
