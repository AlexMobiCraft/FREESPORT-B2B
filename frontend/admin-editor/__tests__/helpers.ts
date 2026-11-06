import { readFileSync } from 'fs';
import { resolve } from 'path';

import { mountRichEditor } from '../src/editor';
import type { RichEditorController, UploadFn } from '../src/editor';
import { parseContent } from '../src/content';
import { serializeDoc } from '../src/serialize';

export const UPLOAD_URL = '/marketing/common/news/upload-image/';
export const CSRF_TOKEN = 'test-csrf-token';

export function fixture(name: string): string {
  // Vitest запускается из frontend/ (корень vitest.config.mts).
  return readFileSync(resolve(process.cwd(), 'admin-editor', '__tests__', 'fixtures', name), 'utf-8');
}

export interface Mounted extends RichEditorController {
  form: HTMLFormElement;
}

/** Форма админки: textarea с data-атрибутами виджета и CSRF-токен. */
export function mount(value: string, upload?: UploadFn, columnWidth?: number): Mounted {
  const form = document.createElement('form');
  const csrf = document.createElement('input');
  csrf.type = 'hidden';
  csrf.name = 'csrfmiddlewaretoken';
  csrf.value = CSRF_TOKEN;
  const textarea = document.createElement('textarea');
  textarea.name = 'content';
  textarea.required = true;
  textarea.dataset.richEditor = '';
  textarea.dataset.uploadUrl = UPLOAD_URL;
  if (columnWidth !== undefined) {
    textarea.dataset.columnWidth = String(columnWidth);
  }
  textarea.value = value;
  form.append(csrf, textarea);
  document.body.append(form);
  const controller = mountRichEditor(textarea, upload ? { upload } : {});
  return { ...controller, form };
}

/** Действие сотрудника с клавиатуры: событие доходит до обёртки, затем команда меняет текст. */
export function typeText(mounted: Mounted, text: string): void {
  mounted.editor.view.dom.dispatchEvent(new KeyboardEvent('keydown', { key: text[0], bubbles: true }));
  mounted.editor.commands.insertContent(text);
}

export function click(mounted: Mounted, command: string): void {
  const button = mounted.root.querySelector<HTMLButtonElement>(`button[data-command="${command}"]`);
  if (!button) {
    throw new Error(`нет кнопки ${command}`);
  }
  button.click();
}

export function selectAllText(mounted: Mounted): void {
  const { doc } = mounted.editor.state;
  mounted.editor.commands.setTextSelection({ from: 1, to: doc.content.size - 1 });
}

/** Разбор и сериализация тем же путём, что в редакторе. */
export function roundTrip(mounted: Mounted, html: string): string {
  return serializeDoc(parseContent(html, mounted.editor.schema));
}

export function imageFile(name = 'photo.png', type = 'image/png', size = 1024): File {
  return new File([new Uint8Array(size)], name, { type });
}

export function pasteEvent(files: File[], text = ''): ClipboardEvent {
  return {
    clipboardData: { files, getData: (format: string) => (format === 'text/plain' ? text : '') },
    preventDefault: () => undefined,
  } as unknown as ClipboardEvent;
}

export function dropEvent(files: File[]): DragEvent {
  return {
    dataTransfer: { files },
    clientX: 10,
    clientY: 10,
    preventDefault: () => undefined,
  } as unknown as DragEvent;
}

export function cleanup(): void {
  document.body.innerHTML = '';
}
