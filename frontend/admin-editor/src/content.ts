/**
 * Разбор значения `textarea` в документ ProseMirror.
 */

import { DOMParser as ProseMirrorDOMParser } from '@tiptap/pm/model';
import type { Node as ProseMirrorNode, Schema } from '@tiptap/pm/model';

// Пустая строка, в том числе из одних пробелов: граница абзацев голого текста.
const BLANK_LINES = /(?:\r?\n[ \t]*){2,}/;
const LINE_BREAK = /\r?\n/g;

function escapeText(text: string): string {
  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

/**
 * Текст без единого `<` — не HTML: так на проде хранятся новости в Markdown.
 *
 * Разбор как HTML схлопнул бы переносы в один абзац, поэтому блоки между пустыми
 * строками становятся абзацами, а одиночный перенос — `<br>`. Разметку Markdown
 * (`##`, `**`) редактор не конвертирует: она видна как текст.
 */
export function plainTextToHtml(value: string): string {
  return value
    .split(BLANK_LINES)
    .map(block => block.trim())
    .filter(block => block !== '')
    .map(block => `<p>${escapeText(block).replace(LINE_BREAK, '<br>')}</p>`)
    .join('');
}

export function isPlainText(value: string): boolean {
  return !value.includes('<');
}

/** `h1` в схеме нет: заголовок страницы уже выводит сайт, в тексте он становится `h2`. */
export function demoteH1(root: ParentNode): void {
  root.querySelectorAll('h1').forEach(h1 => {
    const h2 = h1.ownerDocument.createElement('h2');
    h2.append(...Array.from(h1.childNodes));
    h1.replaceWith(h2);
  });
}

/** То же для HTML из буфера обмена (`transformPastedHTML`). */
export function demoteH1InHtml(html: string): string {
  if (!/<h1[\s>]/i.test(html)) {
    return html;
  }
  const template = document.createElement('template');
  template.innerHTML = html;
  demoteH1(template.content);
  return template.innerHTML;
}

/**
 * Документ из значения `textarea`.
 *
 * HTML разбирается целым документом: у статей, сохранённых целым HTML, берётся
 * только `body` — `head` с `title`, `meta` и `style` в текст не попадает.
 */
export function parseContent(value: string, schema: Schema): ProseMirrorNode {
  const html = isPlainText(value) ? plainTextToHtml(value) : value;
  const dom = new window.DOMParser().parseFromString(html, 'text/html');
  demoteH1(dom.body);
  return ProseMirrorDOMParser.fromSchema(schema).parse(dom.body);
}
