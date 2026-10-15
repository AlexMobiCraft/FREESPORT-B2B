import { describe, it, expect } from 'vitest';
import { extractBodyContent, htmlToPlainText, toMetaDescription } from '../htmlContent';

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

const NBSP = String.fromCharCode(0xa0);

describe('htmlToPlainText', () => {
  it('переводит <br> во всех написаниях и </p> в перевод строки', () => {
    expect(htmlToPlainText('А<br>Б<br/>В<br />Г</p>Д<BR>Е')).toBe('А\nБ\nВ\nГ\nД\nЕ');
  });

  it('удаляет вложенные теги и комментарии', () => {
    expect(htmlToPlainText('<p>Мяч <b>для <i>футбола</i></b><!-- служебное --></p>')).toBe(
      'Мяч для футбола'
    );
  });

  it('декодирует сущности, &amp; — последним', () => {
    expect(htmlToPlainText('x &amp; &lt;y&gt; &quot;z&quot; &#39;q&#39;&nbsp;w &amp;lt;')).toBe(
      'x & <y> "z" \'q\' w &lt;'
    );
  });

  it('не принимает знак «меньше» в тексте за тег', () => {
    expect(htmlToPlainText('размер < 5 и > 3')).toBe('размер < 5 и > 3');
  });

  it('сохраняет переводы строк и убирает лишние пустые строки', () => {
    expect(htmlToPlainText('  Строка 1  \r\n\n\n\n  Строка 2\nСтрока 3 ')).toBe(
      'Строка 1\n\nСтрока 2\nСтрока 3'
    );
  });

  it('схлопывает неразрывные пробелы внутри строки', () => {
    expect(htmlToPlainText(`А${NBSP}${NBSP} Б`)).toBe('А Б');
  });

  it('возвращает пустую строку для пустого ввода и строки из одних тегов', () => {
    expect(htmlToPlainText('')).toBe('');
    expect(htmlToPlainText(null)).toBe('');
    expect(htmlToPlainText(undefined)).toBe('');
    expect(htmlToPlainText('<br><br/><p></p>')).toBe('');
  });
});

describe('htmlToPlainText — разметка из 1С', () => {
  it('не склеивает соседние блоки списков, заголовков и абзацев', () => {
    expect(htmlToPlainText('<ul><li>Материал: NBR</li><li>Размер: 183 см</li></ul>')).toBe(
      'Материал: NBR\nРазмер: 183 см'
    );
    expect(htmlToPlainText('<h3>Состав</h3>Хлопок')).toBe('Состав\nХлопок');
    expect(htmlToPlainText('а<p>б')).toBe('а\nб');
  });

  it('переводит строку на <br> с атрибутами и не путает его с другими тегами', () => {
    expect(htmlToPlainText('NBR<br clear="all">Размер')).toBe('NBR\nРазмер');
    expect(htmlToPlainText('<pre>код</pre>')).toBe('код');
  });

  it('разделяет ячейки таблицы пробелом', () => {
    expect(htmlToPlainText('<table><tr><td>Вес</td><td>1 кг</td></tr></table>')).toBe('Вес 1 кг');
  });

  it('вырезает <style> и <script> вместе с содержимым', () => {
    expect(htmlToPlainText('<style>.a{color:red}</style>Текст<script>alert(1)</script>')).toBe(
      'Текст'
    );
  });

  it('удаляет DOCTYPE', () => {
    expect(htmlToPlainText('<!DOCTYPE html>Текст')).toBe('Текст');
  });

  it('декодирует именованные и числовые сущности', () => {
    expect(htmlToPlainText('&laquo;Мяч&raquo; &mdash; 5&ndash;7 лет&hellip; &#171;&#x27;&#039;')).toBe(
      '«Мяч» — 5–7 лет… «\'\''
    );
  });

  it('не превращает декодированный текст в теги и оставляет неизвестные сущности', () => {
    expect(htmlToPlainText('&lt;b&gt;жирный&lt;/b&gt; &foo; &#0;')).toBe('<b>жирный</b> &foo; &#0;');
  });
});

describe('toMetaDescription', () => {
  it('схлопывает пробелы и переводы строк', () => {
    expect(toMetaDescription('А\nБ\n\n  В\tГ')).toBe('А Б В Г');
  });

  it('не трогает текст не длиннее лимита', () => {
    const text = 'а'.repeat(160);
    expect(toMetaDescription(text)).toBe(text);
  });

  it('обрезает по границе слова, не разрывая слово', () => {
    const text = `${'слово '.repeat(30)}конец`;
    const result = toMetaDescription(text);
    expect(result.length).toBeLessThanOrEqual(160);
    expect(result.endsWith('слово')).toBe(true);
    expect(text.startsWith(result)).toBe(true);
  });

  it('оставляет слово целиком, если срез пришёлся ровно на пробел', () => {
    const text = `${'а'.repeat(160)} хвост`;
    expect(toMetaDescription(text)).toBe('а'.repeat(160));
  });

  it('убирает висящую запятую в конце', () => {
    const text = `${'а'.repeat(150)}, ${'б'.repeat(20)}`;
    expect(toMetaDescription(text)).toBe('а'.repeat(150));
  });

  it('жёстко обрезает одно слово длиннее лимита', () => {
    expect(toMetaDescription('ж'.repeat(200))).toBe('ж'.repeat(160));
  });

  it('сохраняет целое слово, если за срезом знак препинания', () => {
    const text = `${'а'.repeat(155)} слов. Дальше`;
    expect(toMetaDescription(text)).toBe(`${'а'.repeat(155)} слов`);
  });

  it('убирает висящую открывающую скобку и кавычку', () => {
    // Срез приходится сразу за «(» / «« », следующий символ — не буква
    expect(toMetaDescription(`${'а'.repeat(158)} («Б»)`)).toBe('а'.repeat(158));
    expect(toMetaDescription(`${'а'.repeat(158)} «(б)»`)).toBe('а'.repeat(158));
  });

  it('не оставляет половину суррогатной пары при жёсткой обрезке', () => {
    const emoji = String.fromCodePoint(0x1f600);
    const result = toMetaDescription(`${'ж'.repeat(159)}${emoji}${'ж'.repeat(10)}`);
    expect(result).toBe('ж'.repeat(159));
  });

  it('учитывает переданный лимит', () => {
    expect(toMetaDescription('один два три', 7)).toBe('один');
  });
});
