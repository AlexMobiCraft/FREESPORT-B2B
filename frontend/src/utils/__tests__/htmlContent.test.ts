import { describe, it, expect } from 'vitest';
import { extractBodyContent } from '../htmlContent';

describe('extractBodyContent', () => {
  it('возвращает содержимое <body> из полного HTML-документа', () => {
    const html = '<html><head><style>body{color:red}</style></head><body><p>Контент</p></body></html>';
    expect(extractBodyContent(html)).toBe('<p>Контент</p>');
  });

  it('возвращает исходную строку если <body> отсутствует', () => {
    const html = '<p>Текст политики с <strong>HTML</strong>.</p>';
    expect(extractBodyContent(html)).toBe(html);
  });

  it('возвращает пустую строку при null/undefined', () => {
    expect(extractBodyContent(null as unknown as string)).toBe('');
    expect(extractBodyContent(undefined as unknown as string)).toBe('');
  });

  it('обрезает пробелы по краям', () => {
    const html = '<body>\n  <p>Контент</p>\n</body>';
    expect(extractBodyContent(html)).toBe('<p>Контент</p>');
  });
});
