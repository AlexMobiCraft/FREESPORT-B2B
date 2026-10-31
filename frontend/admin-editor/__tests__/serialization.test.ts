/**
 * Эталонный HTML редактора: всё, что умеет тулбар, плюс символы, на которых
 * расходятся сериализаторы браузера и html5lib. Тот же файл бэкенд прогоняет
 * через `sanitize_rich_html` и ждёт его без изменений
 * (`backend/tests/unit/test_rich_editor_upload.py`).
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import { click, cleanup, fixture, mount, roundTrip, selectAllText, typeText } from './helpers';
import type { Mounted } from './helpers';

const REFERENCE = fixture('reference.html');

// Словарь эталона: теги и атрибуты, которые редактор вообще может вывести.
function vocabulary(html: string): Map<string, Set<string>> {
  const template = document.createElement('template');
  template.innerHTML = html;
  const result = new Map<string, Set<string>>();
  template.content.querySelectorAll('*').forEach((element) => {
    const tag = element.tagName.toLowerCase();
    const attributes = result.get(tag) ?? new Set<string>();
    Array.from(element.attributes).forEach((attribute) => attributes.add(attribute.name));
    result.set(tag, attributes);
  });
  return result;
}

const REFERENCE_VOCABULARY = vocabulary(REFERENCE);

function expectWithinReference(html: string): void {
  vocabulary(html).forEach((attributes, tag) => {
    expect(REFERENCE_VOCABULARY.has(tag), `тег ${tag} вне эталона`).toBe(true);
    attributes.forEach((name) => {
      expect(REFERENCE_VOCABULARY.get(tag)?.has(name), `атрибут ${tag}[${name}] вне эталона`).toBe(true);
    });
  });
}

/** Результат правки: эталонный словарь и неподвижная точка разбора. */
function expectStable(mounted: Mounted): string {
  const html = mounted.textarea.value;
  expect(roundTrip(mounted, html)).toBe(html);
  expectWithinReference(html);
  return html;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('эталонный HTML', () => {
  it('однострочный файл без перевода строки в конце', () => {
    expect(REFERENCE).not.toMatch(/[\r\n]/);
  });

  it('неподвижная точка редактора', () => {
    const mounted = mount(REFERENCE);
    expect(roundTrip(mounted, REFERENCE)).toBe(REFERENCE);

    typeText(mounted, ' ');
    mounted.editor.commands.undo();
    expect(mounted.textarea.value).toBe(REFERENCE);
  });

  it('содержит то, на чём расходятся сериализаторы', () => {
    for (const piece of [
      '&nbsp;',
      'href="https://optisport.ru/catalog?a=1&amp;b=2"',
      'alt="Мяч &quot;Pro&quot; &amp; сетка &lt;5 м&gt;"',
      '3 &lt; 5 &amp; 7 &gt; 2',
      'кириллица',
      '⚽🏆',
      'target="_blank" rel="noopener noreferrer nofollow"',
    ]) {
      expect(REFERENCE).toContain(piece);
    }
  });

  it('нет style, data-* и title у картинок', () => {
    expect(REFERENCE).not.toMatch(/\sstyle=|\sdata-|<img[^>]*\stitle=/);
  });
});

describe('кнопки тулбара дают HTML из эталона', () => {
  const cases: Array<[string, string]> = [
    ['heading2', '<h2>текст</h2>'],
    ['heading3', '<h3>текст</h3>'],
    ['heading4', '<h4>текст</h4>'],
    ['bold', '<p><strong>текст</strong></p>'],
    ['italic', '<p><em>текст</em></p>'],
    ['underline', '<p><u>текст</u></p>'],
    ['strike', '<p><s>текст</s></p>'],
    ['bulletList', '<ul><li><p>текст</p></li></ul>'],
    ['orderedList', '<ol><li><p>текст</p></li></ol>'],
    ['blockquote', '<blockquote><p>текст</p></blockquote>'],
  ];

  it.each(cases)('%s', (command, expected) => {
    const mounted = mount('<p>текст</p>');
    selectAllText(mounted);
    click(mounted, command);
    expect(expectStable(mounted)).toBe(expected);
  });

  it('ссылка: адрес с & экранируется, протокол без схемы — https', () => {
    const mounted = mount('<p>каталог</p>');
    selectAllText(mounted);
    const prompt = vi.fn().mockReturnValueOnce('optisport.ru/catalog?a=1&b=2').mockReturnValueOnce('');
    vi.stubGlobal('prompt', prompt);
    click(mounted, 'link');
    expect(expectStable(mounted)).toBe(
      '<p><a target="_blank" rel="noopener noreferrer nofollow" href="https://optisport.ru/catalog?a=1&amp;b=2">каталог</a></p>',
    );

    selectAllText(mounted);
    click(mounted, 'link');
    expect(prompt).toHaveBeenLastCalledWith(expect.any(String), 'https://optisport.ru/catalog?a=1&b=2');
    expect(mounted.textarea.value).toBe('<p>каталог</p>');
  });

  it('ссылка на путь сайта — без target и rel', () => {
    const mounted = mount('<p>каталог</p>');
    selectAllText(mounted);
    vi.stubGlobal('prompt', vi.fn(() => '/catalog'));
    click(mounted, 'link');
    expect(expectStable(mounted)).toBe('<p><a href="/catalog">каталог</a></p>');
  });

  it('внутренняя ссылка из старого HTML теряет target и rel, внешняя получает', () => {
    const mounted = mount('');
    expect(
      roundTrip(
        mounted,
        '<p><a href="/blog" target="_blank" rel="nofollow">свой</a> <a href="https://e.com">чужой</a></p>'
      )
    ).toBe(
      '<p><a href="/blog">свой</a> ' +
        '<a target="_blank" rel="noopener noreferrer nofollow" href="https://e.com">чужой</a></p>'
    );
  });

  it('ссылка: javascript: не ставится, показана ошибка', () => {
    const mounted = mount('<p>каталог</p>');
    selectAllText(mounted);
    vi.stubGlobal('prompt', vi.fn(() => 'javascript:alert(1)'));
    click(mounted, 'link');
    expect(mounted.editor.isActive('link')).toBe(false);
    expect(mounted.root.querySelector('.rich-editor__error')?.textContent).toContain('https://');
  });

  it('таблица: вставка, строки и столбцы до и после, удаление', () => {
    const mounted = mount('<p>текст</p>');
    click(mounted, 'insertTable');
    let html = expectStable(mounted);
    expect(html.match(/<tr>/g)).toHaveLength(3);
    expect(html.match(/<th>/g)).toHaveLength(3);
    expect(html).not.toMatch(/style|colgroup|<col/);

    for (const command of ['addRowBefore', 'addRowAfter', 'addColumnBefore', 'addColumnAfter']) {
      click(mounted, command);
    }
    html = expectStable(mounted);
    expect(html.match(/<tr>/g)).toHaveLength(5);
    expect(html.match(/<tr>(.*?)<\/tr>/)?.[1].match(/<t[hd]>/g)).toHaveLength(5);

    click(mounted, 'deleteRow');
    click(mounted, 'deleteColumn');
    html = expectStable(mounted);
    expect(html.match(/<tr>/g)).toHaveLength(4);

    click(mounted, 'deleteTable');
    expect(mounted.textarea.value).not.toContain('<table>');
  });

  it('выравнивание картинки: класс align-*, повторный клик снимает', () => {
    const mounted = mount('<p>до</p><img src="/media/content/images/2026/10/a.png"><p>после</p>');
    const imagePosition = mounted.editor.state.doc.child(0).nodeSize;
    mounted.editor.commands.setNodeSelection(imagePosition);

    click(mounted, 'align-right');
    expect(expectStable(mounted)).toContain('<img src="/media/content/images/2026/10/a.png" class="align-right">');
    click(mounted, 'align-left');
    expect(mounted.textarea.value).toContain('class="align-left"');
    click(mounted, 'align-center');
    expect(mounted.textarea.value).toContain('class="align-center"');
    click(mounted, 'align-center');
    expect(mounted.textarea.value).toContain('<img src="/media/content/images/2026/10/a.png">');
  });

  it('выравнивание недоступно без выбранной картинки', () => {
    const mounted = mount('<p>текст</p>');
    const button = mounted.root.querySelector<HTMLButtonElement>('button[data-command="align-left"]');
    expect(button?.disabled).toBe(true);
  });

  it('отмена и повтор', () => {
    const mounted = mount('<p>текст</p>');
    selectAllText(mounted);
    click(mounted, 'bold');
    expect(mounted.textarea.value).toBe('<p><strong>текст</strong></p>');
    click(mounted, 'undo');
    expect(mounted.textarea.value).toBe('<p>текст</p>');
    click(mounted, 'redo');
    expect(mounted.textarea.value).toBe('<p><strong>текст</strong></p>');
  });
});

describe('что схема не держит', () => {
  it('h1 → h2, h5/h6 и div/span — абзацы, атрибуты вне схемы отбрасываются', () => {
    const mounted = mount('');
    expect(
      roundTrip(
        mounted,
        '<h1 id="top">Заголовок</h1><h5>Пятый</h5><div class="block"><span style="color:red">текст</span></div>' +
          '<img src="/a.png" title="t" width="10" height="99" class="foo align-right"><a href="#top">якорь</a>' +
          '<img src="data:image/png;base64,AAAA"><img src="blob:http://localhost/1">' +
          '<img src="file:///C:/Users/x/AppData/Local/Temp/msohtmlclip1/01/clip_image002.png">' +
          '<img src="cid:image001.png@01DA0000"><img src="//evil.example/x.png">' +
          '<img src="https://optisport.ru/media/a.png">' +
          '<table style="width:100%"><colgroup><col style="min-width:25px"></colgroup>' +
          '<tr><td class="x" style="text-align:center" colwidth="120" data-x="1">ячейка</td></tr></table>',
      ),
    ).toBe(
      '<h2>Заголовок</h2><p>Пятый</p><p>текст</p><img src="/a.png" class="align-right" width="10"><p>якорь</p>' +
        '<img src="https://optisport.ru/media/a.png">' +
        '<table><tbody><tr><td><p>ячейка</p></td></tr></tbody></table>',
    );
  });
});
