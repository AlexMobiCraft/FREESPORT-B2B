import { describe, it, expect } from 'vitest';
import { isPlaceholderBrand } from '../brand';

describe('isPlaceholderBrand', () => {
  it.each(['bez-tm', 'bez-brenda', 'no-brand'])('считает заглушкой slug %s', slug => {
    expect(isPlaceholderBrand('Любое имя', slug)).toBe(true);
  });

  it.each([
    ['пустое имя', ''],
    ['имя из пробелов', '   '],
    ['имя «-»', '-'],
    ['имя « - »', ' - '],
    ['null', null],
    ['undefined', undefined],
  ])('считает заглушкой %s', (_, name) => {
    expect(isPlaceholderBrand(name, 'boybo')).toBe(true);
  });

  it.each(['Без ТМ', 'без  тм', ' БЕЗ ТМ ', 'Без бренда', 'No Brand'])(
    'узнаёт заглушку по имени «%s» при постороннем slug',
    name => {
      expect(isPlaceholderBrand(name, 'bez-tm-2')).toBe(true);
    }
  );

  it('сравнивает slug без учёта регистра и пробелов по краям', () => {
    expect(isPlaceholderBrand('Что-то', ' BEZ-TM ')).toBe(true);
  });

  it('не считает заглушкой настоящий бренд', () => {
    expect(isPlaceholderBrand('BoyBo', 'boybo')).toBe(false);
  });

  it('не считает заглушкой бренд без slug', () => {
    expect(isPlaceholderBrand('BoyBo')).toBe(false);
    expect(isPlaceholderBrand('BoyBo', '')).toBe(false);
  });
});
