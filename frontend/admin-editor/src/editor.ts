/**
 * Визуальный редактор поля `content` в Django-админке (TipTap 3 без React).
 *
 * Источник правды для формы — исходный `textarea`. Редактор пишет в него только
 * после действия сотрудника (ввод, вставка, перетаскивание, кнопка тулбара):
 * транзакции нормализации ProseMirror значение не трогают, поэтому сохранение
 * без правок отправляет ровно то, что было в поле.
 */

import { Editor, getSchema } from '@tiptap/core';
import { TextSelection } from '@tiptap/pm/state';
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
import type { EditorView } from '@tiptap/pm/view';

import { MESSAGES, clampImageWidth, isAllowedHref, parseColumnWidth } from './constants';
import type { ImageAlignment } from './constants';
import { demoteH1InHtml, parseContent } from './content';
import { buildExtensions } from './extensions';
import { serializeForTextarea } from './serialize';
import { createToolbar, presetWidth } from './toolbar';
import type { ToolbarState } from './toolbar';
import { UploadError, uploadImage, validateImageFile } from './upload';

export type UploadFn = (uploadUrl: string, file: File, csrfToken: string) => Promise<string>;

export interface RichEditorOptions {
  upload?: UploadFn;
}

export interface RichEditorController {
  editor: Editor;
  root: HTMLElement;
  textarea: HTMLTextAreaElement;
  /** Обработчики ProseMirror; вынесены, чтобы тесты могли вызвать их напрямую. */
  handlePaste(view: EditorView, event: ClipboardEvent): boolean;
  handleDrop(view: EditorView, event: DragEvent): boolean;
  uploadFiles(files: File[], position?: number): Promise<void>;
  /** Промис, который выполняется, когда все начатые загрузки закончились. */
  settled(): Promise<void>;
  isHtmlMode(): boolean;
  setHtmlMode(on: boolean): void;
  destroy(): void;
}

// Клавиши, которые только двигают курсор или выделение, текст не меняют.
const NAVIGATION_KEYS = new Set([
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
  'Home',
  'End',
  'PageUp',
  'PageDown',
  'Shift',
  'Control',
  'Alt',
  'Meta',
  'CapsLock',
  'Escape',
  'ContextMenu',
]);

function isEditingKey(event: KeyboardEvent): boolean {
  if (NAVIGATION_KEYS.has(event.key) || /^F\d{1,2}$/.test(event.key)) {
    return false;
  }
  // Копирование и «выделить всё» текст не меняют.
  const mod = event.ctrlKey || event.metaKey;
  return !(mod && !event.shiftKey && ['c', 'a', 'с', 'ф'].includes(event.key.toLowerCase()));
}

function imageFiles(list: FileList | null | undefined): File[] {
  return Array.from(list ?? []);
}

let uploadCounter = 0;

export function mountRichEditor(
  textarea: HTMLTextAreaElement,
  options: RichEditorOptions = {}
): RichEditorController {
  const upload = options.upload ?? uploadImage;
  const uploadUrl = textarea.dataset.uploadUrl ?? '';
  const columnWidth = parseColumnWidth(textarea.dataset.columnWidth);
  const form = textarea.form;

  // Пустоту проверяет сервер: скрытое обязательное поле браузер не дал бы отправить.
  textarea.required = false;
  textarea.removeAttribute('required');

  const root = document.createElement('div');
  root.className = 'rich-editor';
  // Текст в редакторе той же ширины, что на сайте: картинка выглядит там так же, как здесь.
  root.style.setProperty('--rich-editor-column', `${columnWidth}px`);
  const content = document.createElement('div');
  content.className = 'rich-editor__content';
  const errorBox = document.createElement('div');
  errorBox.className = 'rich-editor__error';
  errorBox.setAttribute('role', 'alert');
  errorBox.hidden = true;
  const fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.accept = 'image/jpeg,image/png,image/webp,image/gif';
  fileInput.multiple = true;
  fileInput.hidden = true;

  textarea.replaceWith(root);
  textarea.classList.add('rich-editor__source');
  textarea.style.display = 'none';

  let userActed = false;
  let htmlMode = false;
  let htmlSnapshot = '';
  let pending = 0;
  let inFlight: Promise<void>[] = [];

  const markUserAction = () => {
    userActed = true;
  };

  const extensions = buildExtensions();

  const showError = (message: string) => {
    errorBox.textContent = message;
    errorBox.hidden = false;
  };
  const clearError = () => {
    errorBox.textContent = '';
    errorBox.hidden = true;
  };

  const syncTextarea = () => {
    textarea.value = editor.isEmpty ? '' : serializeForTextarea(editor.state.doc);
  };

  const findPlaceholder = (uploadId: string): { node: ProseMirrorNode; pos: number } | null => {
    let found: { node: ProseMirrorNode; pos: number } | null = null;
    editor.state.doc.descendants((node, pos) => {
      if (found) {
        return false;
      }
      if (node.type.name === 'imageUpload' && node.attrs.uploadId === uploadId) {
        found = { node, pos };
        return false;
      }
      return true;
    });
    return found;
  };

  const csrfToken = (): string =>
    (
      form?.querySelector<HTMLInputElement>('input[name="csrfmiddlewaretoken"]')?.value ?? ''
    ).trim();

  const uploadOne = async (file: File, uploadId: string, previewSrc: string) => {
    try {
      const url = await upload(uploadUrl, file, csrfToken());
      const found = findPlaceholder(uploadId);
      // Узел мог исчезнуть (удалён вместе с текстом) — тогда картинку не вставляем.
      if (found) {
        // Узел загрузки — вне истории; картинка — обычный шаг: отмена убирает её,
        // повтор возвращает картинку, а не превью с отозванным blob.
        const removal = editor.state.tr.delete(found.pos, found.pos + found.node.nodeSize);
        editor.view.dispatch(removal.setMeta('addToHistory', false));
        const image = editor.schema.nodes.image.create({ src: url });
        editor.view.dispatch(editor.state.tr.insert(found.pos, image));
      }
    } catch (error) {
      const found = findPlaceholder(uploadId);
      if (found) {
        const tr = editor.state.tr.delete(found.pos, found.pos + found.node.nodeSize);
        editor.view.dispatch(tr.setMeta('addToHistory', false));
      }
      showError(error instanceof UploadError ? error.message : MESSAGES.failed);
    } finally {
      URL.revokeObjectURL(previewSrc);
      pending -= 1;
      refresh();
    }
  };

  const uploadFiles = (files: File[], position?: number): Promise<void> => {
    if (htmlMode || files.length === 0) {
      return Promise.resolve();
    }
    markUserAction();
    clearError();
    const accepted: File[] = [];
    for (const file of files) {
      const problem = validateImageFile(file);
      if (problem) {
        showError(problem);
      } else {
        accepted.push(file);
      }
    }
    if (accepted.length === 0) {
      return Promise.resolve();
    }

    let tr = editor.state.tr;
    if (position !== undefined) {
      tr = tr.setSelection(
        TextSelection.near(tr.doc.resolve(Math.min(position, tr.doc.content.size)))
      );
    }
    const started: Array<[File, string, string]> = [];
    for (const file of accepted) {
      uploadCounter += 1;
      const uploadId = `upload-${Date.now()}-${uploadCounter}`;
      const previewSrc = URL.createObjectURL(file);
      tr = tr.replaceSelectionWith(
        editor.schema.nodes.imageUpload.create({ uploadId, previewSrc })
      );
      started.push([file, uploadId, previewSrc]);
    }
    pending += started.length;
    editor.view.dispatch(tr.scrollIntoView().setMeta('addToHistory', false));
    refresh();

    const batch = Promise.all(
      started.map(([file, uploadId, previewSrc]) => uploadOne(file, uploadId, previewSrc))
    ).then(() => undefined);
    inFlight.push(batch);
    return batch;
  };

  const handlePaste = (_view: EditorView, event: ClipboardEvent): boolean => {
    const data = event.clipboardData;
    const files = imageFiles(data?.files);
    // Из Word и браузера вместе с текстом приходит картинка-снимок: текст важнее.
    if (files.length === 0 || (data?.getData('text/plain') ?? '').trim() !== '') {
      return false;
    }
    event.preventDefault();
    void uploadFiles(files);
    return true;
  };

  const handleDrop = (view: EditorView, event: DragEvent): boolean => {
    const files = imageFiles(event.dataTransfer?.files);
    if (files.length === 0) {
      return false;
    }
    event.preventDefault();
    let position: number | undefined;
    try {
      position = view.posAtCoords({ left: event.clientX, top: event.clientY })?.pos;
    } catch {
      // Без раскладки (тесты, скрытый редактор) координат нет — вставка в позицию курсора.
      position = undefined;
    }
    void uploadFiles(files, position);
    return true;
  };

  const editor = new Editor({
    element: content,
    extensions,
    // Схема для разбора — та же конфигурация расширений; в редактор уходит JSON.
    content: parseContent(textarea.value, getSchema(extensions)).toJSON(),
    editorProps: {
      attributes: {
        class: 'rich-editor__prose',
        'aria-label': 'Текст',
      },
      handlePaste: (view, event) => handlePaste(view, event),
      handleDrop: (view, event) => handleDrop(view, event as DragEvent),
      transformPastedHTML: html => demoteH1InHtml(html),
    },
    onUpdate: () => {
      if (userActed && !htmlMode) {
        syncTextarea();
      }
    },
  });

  const setHtmlMode = (on: boolean) => {
    if (on === htmlMode || (on && pending > 0)) {
      return;
    }
    clearError();
    if (on) {
      htmlMode = true;
      htmlSnapshot = textarea.value;
      content.style.display = 'none';
      textarea.style.display = '';
      textarea.focus();
    } else {
      htmlMode = false;
      textarea.style.display = 'none';
      content.style.display = '';
      if (textarea.value !== htmlSnapshot) {
        editor.commands.setContent(parseContent(textarea.value, editor.schema).toJSON(), {
          emitUpdate: false,
        });
        markUserAction();
        syncTextarea();
      }
      editor.commands.focus();
    }
    refresh();
  };

  const editLink = () => {
    const current = (editor.getAttributes('link').href as string | undefined) ?? '';
    const answer = window.prompt(
      'Адрес ссылки: https://…, mailto:… или /путь на этом сайте',
      current
    );
    if (answer === null) {
      return;
    }
    let href = answer.trim();
    markUserAction();
    if (href === '') {
      editor.chain().focus().extendMarkRange('link').unsetLink().run();
      return;
    }
    // «optisport.ru/catalog» без протокола — внешний адрес, а не путь.
    if (!/^[a-z][a-z0-9+.-]*:/i.test(href) && !href.startsWith('/')) {
      href = `https://${href}`;
    }
    if (!isAllowedHref(href)) {
      showError(MESSAGES.badLink);
      return;
    }
    clearError();
    if (editor.state.selection.empty && !editor.isActive('link')) {
      editor
        .chain()
        .focus()
        .insertContent({ type: 'text', text: href, marks: [{ type: 'link', attrs: { href } }] })
        .run();
      return;
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href }).run();
  };

  const alignImage = (align: ImageAlignment) => {
    if (!editor.isActive('image')) {
      return;
    }
    markUserAction();
    const next = editor.isActive('image', { align }) ? null : align;
    editor.chain().focus().updateAttributes('image', { align: next }).run();
  };

  const resizeImage = (fraction: number | null) => {
    if (!editor.isActive('image')) {
      return;
    }
    markUserAction();
    // Больше оригинала не растягиваем: на сайте такая картинка размыта.
    const natural =
      (editor.view.nodeDOM(editor.state.selection.from) as HTMLElement | null)?.querySelector('img')
        ?.naturalWidth ?? 0;
    const width =
      fraction === null ? null : clampImageWidth(presetWidth(fraction, columnWidth), natural);
    editor.chain().focus().updateAttributes('image', { width }).run();
  };

  const toolbar = createToolbar(
    editor,
    {
      editLink,
      pickImage: () => fileInput.click(),
      alignImage,
      resizeImage,
      toggleHtmlMode: () => setHtmlMode(!htmlMode),
    },
    markUserAction
  );

  const toolbarState = (): ToolbarState => ({ htmlMode, uploading: pending > 0, columnWidth });
  function refresh() {
    toolbar.refresh(toolbarState());
  }

  fileInput.addEventListener('change', () => {
    const files = imageFiles(fileInput.files);
    fileInput.value = '';
    void uploadFiles(files);
  });

  // Флаг ставится в фазе перехвата на обёртке — раньше, чем ProseMirror обработает событие.
  const onKeydown = (event: Event) => {
    if (event.target !== textarea && isEditingKey(event as KeyboardEvent)) {
      markUserAction();
    }
  };
  const onEdit = (event: Event) => {
    if (event.target !== textarea) {
      markUserAction();
    }
  };
  root.addEventListener('keydown', onKeydown, true);
  for (const type of ['beforeinput', 'paste', 'drop', 'cut']) {
    root.addEventListener(type, onEdit, true);
  }
  // Захват ручки размера — начало правки; простой клик по картинке текст не меняет.
  root.addEventListener(
    'pointerdown',
    event => {
      if ((event.target as Element | null)?.closest?.('[data-resize-handle]')) {
        markUserAction();
      }
    },
    true
  );

  const onSubmit = (event: SubmitEvent) => {
    if (pending > 0) {
      event.preventDefault();
      event.stopImmediatePropagation();
      showError(MESSAGES.waitForUpload);
    }
  };
  form?.addEventListener('submit', onSubmit, true);

  editor.on('transaction', refresh);
  editor.on('selectionUpdate', refresh);

  root.append(toolbar.element, content, textarea, errorBox, fileInput);
  refresh();

  return {
    editor,
    root,
    textarea,
    handlePaste,
    handleDrop,
    uploadFiles,
    settled: async () => {
      while (inFlight.length > 0) {
        const current = inFlight;
        inFlight = [];
        await Promise.all(current);
      }
    },
    isHtmlMode: () => htmlMode,
    setHtmlMode,
    destroy: () => {
      form?.removeEventListener('submit', onSubmit, true);
      editor.destroy();
      textarea.style.display = '';
      textarea.classList.remove('rich-editor__source');
      root.replaceWith(textarea);
    },
  };
}

/** Монтирует редактор на каждый `textarea[data-rich-editor]` страницы. */
export function mountAll(scope: ParentNode = document): RichEditorController[] {
  return Array.from(scope.querySelectorAll<HTMLTextAreaElement>('textarea[data-rich-editor]'))
    .filter(textarea => textarea.dataset.richEditorMounted === undefined)
    .map(textarea => {
      textarea.dataset.richEditorMounted = '';
      return mountRichEditor(textarea);
    });
}
