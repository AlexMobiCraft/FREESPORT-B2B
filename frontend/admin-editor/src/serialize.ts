/**
 * HTML для `textarea`: документ ProseMirror в строку.
 *
 * Сериализатор свой, а не `innerHTML`: браузеры и happy-dom по-разному экранируют
 * `<` и `>` в атрибутах, а сервер прогоняет текст через bleach (html5lib). Правила
 * ниже — те, при которых `sanitize_rich_html(x) == x`: в тексте `&`, `<`, `>`,
 * в атрибутах ещё `"`, неразрывный пробел — `&nbsp;`.
 */

import { DOMSerializer } from '@tiptap/pm/model';
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';

import { UPLOAD_MARKER } from './constants';

const VOID_ELEMENTS = new Set([
  'area',
  'br',
  'col',
  'embed',
  'hr',
  'img',
  'source',
  'track',
  'wbr',
]);

const ELEMENT_NODE = 1;
const TEXT_NODE = 3;

function escapeText(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/ /g, '&nbsp;');
}

function escapeAttribute(value: string): string {
  return escapeText(value).replace(/"/g, '&quot;');
}

function serializeNode(node: Node): string {
  if (node.nodeType === TEXT_NODE) {
    return escapeText(node.nodeValue ?? '');
  }
  if (node.nodeType !== ELEMENT_NODE) {
    return '';
  }
  const element = node as Element;
  if (element.hasAttribute(UPLOAD_MARKER)) {
    return '';
  }
  const tag = element.tagName.toLowerCase();
  let html = `<${tag}`;
  for (const attribute of Array.from(element.attributes)) {
    html += ` ${attribute.name}="${escapeAttribute(attribute.value)}"`;
  }
  html += '>';
  if (VOID_ELEMENTS.has(tag)) {
    return html;
  }
  for (const child of Array.from(element.childNodes)) {
    html += serializeNode(child);
  }
  return `${html}</${tag}>`;
}

export function serializeDoc(doc: ProseMirrorNode): string {
  const fragment = DOMSerializer.fromSchema(doc.type.schema).serializeFragment(doc.content, {
    document,
  });
  return Array.from(fragment.childNodes).map(serializeNode).join('');
}

/** Пустой документ — пустая строка, а не `<p></p>`: обязательность проверяет сервер. */
export function serializeForTextarea(doc: ProseMirrorNode): string {
  const html = serializeDoc(doc);
  return /^(?:<p><\/p>)*$/.test(html) ? '' : html;
}
