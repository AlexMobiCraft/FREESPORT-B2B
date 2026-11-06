/**
 * Круговой проход реальных форм контента прода: реквизиты (таблицы), статья,
 * сохранённая целым HTML-документом, и новость в Markdown.
 */

import { afterEach, describe, expect, it } from 'vitest';

import { demoteH1InHtml, isPlainText, plainTextToHtml } from '../src/content';
import { cleanup, fixture, mount, roundTrip, typeText } from './helpers';

afterEach(cleanup);

describe('текст без HTML', () => {
  const NEWS = fixture('news-markdown.txt');

  it('фикстура — как на проде: \\r\\n, есть &, нет <', () => {
    expect(NEWS).toContain('\r\n\r\n');
    expect(NEWS).toContain('&');
    expect(isPlainText(NEWS)).toBe(true);
  });

  it('блоки между пустыми строками — абзацы, одиночный перенос — <br>, Markdown виден как текст', () => {
    expect(plainTextToHtml(NEWS)).toBe(
      '<p>## **Фитнес-оборудование со скидками**</p>' +
        '<p>Хорошая форма начинается с правильного инвентаря. Гантели &amp; гири доступны по **специальным ценам** до конца месяца.</p>' +
        '<p>### **Гантели для силовых тренировок**</p>' +
        '<p>В ассортименте гантели разного веса —<br>от лёгких до тяжёлых.</p>' +
        '<p>* Сроки ограничены<br>* Количество — тоже</p>',
    );
  });

  it('textarea не меняется до действия, после правки — абзацы', () => {
    const mounted = mount(NEWS);
    expect(mounted.textarea.value).toBe(NEWS);
    expect(mounted.editor.state.doc.childCount).toBe(5);
    expect(mounted.editor.state.doc.child(0).type.name).toBe('paragraph');
    expect(mounted.editor.state.doc.child(0).textContent).toBe('## **Фитнес-оборудование со скидками**');

    mounted.editor.commands.setTextSelection(mounted.editor.state.doc.content.size - 1);
    typeText(mounted, '!');
    expect(mounted.textarea.value).toBe(`${plainTextToHtml(NEWS).slice(0, -4)}!</p>`);
  });

  it('> экранируется, пустое значение — пустой документ', () => {
    expect(plainTextToHtml('a > b')).toBe('<p>a &gt; b</p>');
    expect(plainTextToHtml('  \r\n \r\n')).toBe('');
  });
});

describe('h1 из буфера обмена', () => {
  it('demoteH1InHtml: h1 → h2 с содержимым, остальное не трогает', () => {
    expect(demoteH1InHtml('<h1 class="x">Заголовок <em>статьи</em></h1><p>текст</p>')).toBe(
      '<h2>Заголовок <em>статьи</em></h2><p>текст</p>'
    );
    expect(demoteH1InHtml('<p>без h1</p>')).toBe('<p>без h1</p>');
  });

  it('вставка HTML с h1 даёт h2 в textarea', () => {
    // Вставка в пустой абзац: блок из буфера заменяет его, а не вливается в текст.
    const mounted = mount('<p>текст</p><p></p>');
    mounted.editor.commands.setTextSelection(mounted.editor.state.doc.content.size - 1);
    mounted.root.dispatchEvent(new Event('paste'));
    mounted.editor.view.pasteHTML('<h1>X</h1>');

    expect(mounted.textarea.value).toBe('<p>текст</p><h2>X</h2>');
    expect(mounted.textarea.value).not.toContain('<h1');
  });
});

describe('реквизиты: таблицы', () => {
  const REQUISITES = fixture('requisites.html');

  it('таблица видна и редактируется, после правки — в HTML, class ячеек теряется', () => {
    const mounted = mount(REQUISITES);
    expect(mounted.textarea.value).toBe(REQUISITES);
    expect(mounted.root.querySelectorAll('.rich-editor__prose table')).toHaveLength(1);

    const cellText = mounted.root.querySelector('.rich-editor__prose td');
    expect(cellText?.textContent).toContain('Полное');

    mounted.editor.commands.setTextSelection(1);
    typeText(mounted, 'Реквизиты. ');
    const html = mounted.textarea.value;

    expect(html.startsWith('<p><strong>Реквизиты. Владелец сайта:&nbsp;</strong></p><p><br></p><table>')).toBe(true);
    expect(html.match(/<table>/g)).toHaveLength(1);
    expect(html.match(/<tr>/g)).toHaveLength(7);
    expect(html).toContain('<td><p><strong>Полное</strong></p><p><strong>Наименование</strong></p></td>');
    expect(html).toContain('+7&nbsp;900&nbsp;000 00 00');
    expect(html).not.toMatch(/class=|colgroup|<span|<b>|<a>|style=/);
    expect(html.endsWith('<p><strong>Пользователь сайта:</strong></p><p><br></p>')).toBe(true);
    expect(roundTrip(mounted, html)).toBe(html);
  });
});

describe('статья, сохранённая целым HTML-документом', () => {
  const ARTICLE = fixture('article-document.html');

  it('после первой правки — только содержимое body, h1 → h2', () => {
    const mounted = mount(ARTICLE);
    expect(mounted.textarea.value).toBe(ARTICLE);

    mounted.editor.commands.setTextSelection(mounted.editor.state.doc.content.size - 1);
    typeText(mounted, '!');
    const html = mounted.textarea.value;

    expect(html).toBe(
      '<h2>Как выбрать правильные кроссовки</h2>' +
        '<p>Выбор кроссовок — это вопрос комфорта и безопасности. Неподходящая обувь может привести к травмам.</p>' +
        '<h2>Типы покрытия</h2>' +
        '<ul><li><p><strong>Асфальт</strong> — нужна амортизация.</p></li>' +
        '<li><p><strong>Грунт</strong> — нужен протектор.</p></li></ul>' +
        '<p>Подберите пару в <a target="_blank" rel="noopener noreferrer nofollow" href="https://optisport.ru/catalog">каталоге</a>.!</p>',
    );
  });
});
