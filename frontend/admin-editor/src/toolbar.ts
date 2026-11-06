/**
 * Тулбар редактора: описание кнопок и их состояние.
 */

import type { Editor } from '@tiptap/core';

import { HTML_MODE_HINT, IMAGE_ALIGNMENTS, IMAGE_SIZE_PRESETS } from './constants';
import type { ImageAlignment } from './constants';

export interface ToolbarActions {
  editLink(): void;
  pickImage(): void;
  alignImage(align: ImageAlignment): void;
  /** Ширина выбранной картинки долей колонки текста; `null` — исходный размер. */
  resizeImage(fraction: number | null): void;
  toggleHtmlMode(): void;
}

export interface ToolbarState {
  htmlMode: boolean;
  uploading: boolean;
  /** Ширина колонки текста на сайте, px: от неё считаются доли ширины картинки. */
  columnWidth: number;
}

/** Ширина картинки в пикселях для доли колонки; общая для кнопок и их состояния. */
export function presetWidth(fraction: number, columnWidth: number): number {
  return Math.round(columnWidth * fraction);
}

interface ButtonSpec {
  command: string;
  label: string;
  title: string;
  run(editor: Editor, actions: ToolbarActions): void;
  isActive?(editor: Editor, state: ToolbarState): boolean;
  isEnabled?(editor: Editor, state: ToolbarState): boolean;
  /** Кнопка работает и в режиме HTML (только сама кнопка «HTML»). */
  inHtmlMode?: boolean;
  /** Кнопка не меняет текст сама: флаг действия ставит обработчик (ссылка, картинка, HTML). */
  deferred?: boolean;
}

const inTable = (editor: Editor) => editor.isActive('table');

const ALIGN_LABELS: Record<ImageAlignment, [string, string]> = {
  left: ['⇤', 'Картинка слева, текст обтекает справа'],
  center: ['↔', 'Картинка по центру'],
  right: ['⇥', 'Картинка справа, текст обтекает слева'],
};

const GROUPS: ButtonSpec[][] = [
  [
    {
      command: 'undo',
      label: '↶',
      title: 'Отменить',
      run: editor => editor.chain().focus().undo().run(),
      isEnabled: editor => editor.can().undo(),
    },
    {
      command: 'redo',
      label: '↷',
      title: 'Повторить',
      run: editor => editor.chain().focus().redo().run(),
      isEnabled: editor => editor.can().redo(),
    },
  ],
  ([2, 3, 4] as const).map(level => ({
    command: `heading${level}`,
    label: `H${level}`,
    title: `Заголовок ${level}-го уровня`,
    run: (editor: Editor) => editor.chain().focus().toggleHeading({ level }).run(),
    isActive: (editor: Editor) => editor.isActive('heading', { level }),
  })),
  [
    {
      command: 'bold',
      label: 'Ж',
      title: 'Жирный',
      run: editor => editor.chain().focus().toggleBold().run(),
      isActive: editor => editor.isActive('bold'),
    },
    {
      command: 'italic',
      label: 'К',
      title: 'Курсив',
      run: editor => editor.chain().focus().toggleItalic().run(),
      isActive: editor => editor.isActive('italic'),
    },
    {
      command: 'underline',
      label: 'Ч',
      title: 'Подчёркнутый',
      run: editor => editor.chain().focus().toggleUnderline().run(),
      isActive: editor => editor.isActive('underline'),
    },
    {
      command: 'strike',
      label: 'З',
      title: 'Зачёркнутый',
      run: editor => editor.chain().focus().toggleStrike().run(),
      isActive: editor => editor.isActive('strike'),
    },
  ],
  [
    {
      command: 'bulletList',
      label: '•',
      title: 'Маркированный список',
      run: editor => editor.chain().focus().toggleBulletList().run(),
      isActive: editor => editor.isActive('bulletList'),
    },
    {
      command: 'orderedList',
      label: '1.',
      title: 'Нумерованный список',
      run: editor => editor.chain().focus().toggleOrderedList().run(),
      isActive: editor => editor.isActive('orderedList'),
    },
    {
      command: 'blockquote',
      label: '«»',
      title: 'Цитата',
      run: editor => editor.chain().focus().toggleBlockquote().run(),
      isActive: editor => editor.isActive('blockquote'),
    },
    {
      command: 'link',
      label: 'Ссылка',
      title: 'Ссылка: выделите текст и укажите адрес; пустой адрес убирает ссылку',
      run: (_editor, actions) => actions.editLink(),
      isActive: editor => editor.isActive('link'),
      deferred: true,
    },
  ],
  [
    {
      command: 'insertTable',
      label: 'Таблица',
      title: 'Вставить таблицу 3×3 со строкой заголовков',
      run: editor =>
        editor.chain().focus().insertTable({ rows: 3, cols: 3, withHeaderRow: true }).run(),
      isEnabled: editor => !inTable(editor),
    },
    {
      command: 'addRowBefore',
      label: '+↑',
      title: 'Строка выше',
      run: editor => editor.chain().focus().addRowBefore().run(),
      isEnabled: inTable,
    },
    {
      command: 'addRowAfter',
      label: '+↓',
      title: 'Строка ниже',
      run: editor => editor.chain().focus().addRowAfter().run(),
      isEnabled: inTable,
    },
    {
      command: 'addColumnBefore',
      label: '+←',
      title: 'Столбец слева',
      run: editor => editor.chain().focus().addColumnBefore().run(),
      isEnabled: inTable,
    },
    {
      command: 'addColumnAfter',
      label: '+→',
      title: 'Столбец справа',
      run: editor => editor.chain().focus().addColumnAfter().run(),
      isEnabled: inTable,
    },
    {
      command: 'deleteRow',
      label: '−строка',
      title: 'Удалить строку',
      run: editor => editor.chain().focus().deleteRow().run(),
      isEnabled: inTable,
    },
    {
      command: 'deleteColumn',
      label: '−столбец',
      title: 'Удалить столбец',
      run: editor => editor.chain().focus().deleteColumn().run(),
      isEnabled: inTable,
    },
    {
      command: 'deleteTable',
      label: '−таблица',
      title: 'Удалить таблицу',
      run: editor => editor.chain().focus().deleteTable().run(),
      isEnabled: inTable,
    },
  ],
  [
    {
      command: 'image',
      label: 'Картинка',
      title:
        'Вставить картинку (JPEG, PNG, WEBP, GIF до 10 МБ). Можно вставить из буфера или перетащить',
      run: (_editor, actions) => actions.pickImage(),
      deferred: true,
    },
    ...IMAGE_ALIGNMENTS.map(
      (align): ButtonSpec => ({
        command: `align-${align}`,
        label: ALIGN_LABELS[align][0],
        title: ALIGN_LABELS[align][1],
        run: (_editor, actions) => actions.alignImage(align),
        isActive: editor => editor.isActive('image', { align }),
        isEnabled: editor => editor.isActive('image'),
      })
    ),
  ],
  [
    ...IMAGE_SIZE_PRESETS.map(
      (fraction): ButtonSpec => ({
        command: `size-${Math.round(fraction * 100)}`,
        label: `${Math.round(fraction * 100)}%`,
        title: `Ширина картинки — ${Math.round(fraction * 100)}% колонки текста. Размер можно менять и за уголок рамки`,
        run: (_editor, actions) => actions.resizeImage(fraction),
        isActive: (editor, state) =>
          editor.isActive('image', { width: presetWidth(fraction, state.columnWidth) }),
        isEnabled: editor => editor.isActive('image'),
      })
    ),
    {
      command: 'size-auto',
      label: 'Авто',
      title: 'Исходный размер картинки, но не шире колонки текста',
      run: (_editor, actions) => actions.resizeImage(null),
      isActive: editor => editor.isActive('image') && editor.getAttributes('image').width == null,
      isEnabled: editor => editor.isActive('image'),
    },
  ],
  [
    {
      command: 'html',
      label: 'HTML',
      title: HTML_MODE_HINT,
      run: (_editor, actions) => actions.toggleHtmlMode(),
      isActive: (_editor, state) => state.htmlMode,
      isEnabled: (_editor, state) => !state.uploading,
      inHtmlMode: true,
      deferred: true,
    },
  ],
];

export interface Toolbar {
  element: HTMLElement;
  refresh(state: ToolbarState): void;
}

export function createToolbar(
  editor: Editor,
  actions: ToolbarActions,
  onUserAction: () => void
): Toolbar {
  const element = document.createElement('div');
  element.className = 'rich-editor__toolbar';
  element.setAttribute('role', 'toolbar');
  element.setAttribute('aria-label', 'Оформление текста');

  const buttons: Array<[HTMLButtonElement, ButtonSpec]> = [];

  for (const group of GROUPS) {
    const groupElement = document.createElement('span');
    groupElement.className = 'rich-editor__group';
    for (const spec of group) {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = `rich-editor__button rich-editor__button--${spec.command}`;
      button.dataset.command = spec.command;
      button.textContent = spec.label;
      button.title = spec.title;
      button.setAttribute('aria-label', spec.title);
      // Клик не должен забирать фокус и выделение у текста.
      button.addEventListener('mousedown', event => event.preventDefault());
      button.addEventListener('click', () => {
        if (button.disabled) {
          return;
        }
        if (!spec.deferred) {
          onUserAction();
        }
        spec.run(editor, actions);
      });
      groupElement.append(button);
      buttons.push([button, spec]);
    }
    element.append(groupElement);
  }

  return {
    element,
    refresh(state) {
      for (const [button, spec] of buttons) {
        const available = spec.inHtmlMode || !state.htmlMode;
        button.disabled = !available || (spec.isEnabled ? !spec.isEnabled(editor, state) : false);
        if (spec.isActive) {
          button.setAttribute('aria-pressed', String(available && spec.isActive(editor, state)));
        }
      }
    },
  };
}
