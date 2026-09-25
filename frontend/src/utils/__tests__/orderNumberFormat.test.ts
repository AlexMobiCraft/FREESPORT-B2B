import { describe, expect, it } from 'vitest';

import {
  formatOrderNumber,
  isCanonicalMasterOrderNumber,
  isCanonicalSubOrderNumber,
  normalizeOrderNumberInput,
} from '../orderNumberFormat';

describe('orderNumberFormat', () => {
  it('распознаёт канонический мастер-номер', () => {
    expect(isCanonicalMasterOrderNumber('0462026007')).toBe(true);
    expect(isCanonicalMasterOrderNumber('0462026000')).toBe(false);
  });

  it('распознаёт канонический номер субзаказа', () => {
    expect(isCanonicalSubOrderNumber('04620260071')).toBe(true);
    expect(isCanonicalSubOrderNumber('04620260070')).toBe(false);
  });

  it('форматирует мастер и субзаказ для UI', () => {
    expect(formatOrderNumber('0462026007')).toBe('4620-26007');
    expect(formatOrderNumber('04620260071')).toBe('04620-26007-1');
  });

  it('возвращает legacy-номер без изменений', () => {
    expect(formatOrderNumber('legacy-uuid')).toBe('legacy-uuid');
  });

  it('нормализует канонический и UI-ввод', () => {
    expect(normalizeOrderNumberInput('0462026007')).toBe('0462026007');
    expect(normalizeOrderNumberInput('4620-26007')).toBe('462026007');
    expect(normalizeOrderNumberInput('04620-26007-1')).toBe('04620260071');
    expect(normalizeOrderNumberInput('invalid')).toBeNull();
  });
});
