/**
 * Размер картинки: `width` в тексте, кнопки долей колонки, ручка в углу рамки,
 * ширина колонки редактора.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  DEFAULT_COLUMN_WIDTH,
  IMAGE_MAX_WIDTH,
  IMAGE_MIN_WIDTH,
  clampImageWidth,
  parseColumnWidth,
  parseImageWidth,
} from '../src/constants';
import { cleanup, click, mount, roundTrip } from './helpers';
import type { Mounted } from './helpers';

afterEach(cleanup);

const SRC = '/media/content/images/2026/10/a.png';

function mountWithImage(attributes = '', columnWidth?: number): Mounted {
  const mounted = mount(`<p>до</p><img src="${SRC}"${attributes}><p>после</p>`, undefined, columnWidth);
  // Картинка идёт сразу за первым абзацем.
  mounted.editor.commands.setNodeSelection(mounted.editor.state.doc.child(0).nodeSize);
  return mounted;
}

function frame(mounted: Mounted): HTMLElement {
  const element = mounted.root.querySelector<HTMLElement>('.rich-editor__image');
  if (!element) {
    throw new Error('нет рамки картинки');
  }
  return element;
}

/** Раскладки в happy-dom нет: ширину рамки берём из её `style.width`, как это сделал бы браузер. */
function fakeLayout(element: HTMLElement, fallback = 500): void {
  vi.spyOn(element, 'getBoundingClientRect').mockImplementation(
    () => ({ width: parseFloat(element.style.width) || fallback }) as DOMRect
  );
}

function pointer(type: string, clientX: number): PointerEvent {
  return new PointerEvent(type, { clientX, button: 0, bubbles: true, cancelable: true });
}

function drag(mounted: Mounted, from: number, to: number): void {
  const handle = frame(mounted).querySelector<HTMLElement>('[data-resize-handle]');
  if (!handle) {
    throw new Error('нет ручки размера');
  }
  handle.dispatchEvent(pointer('pointerdown', from));
  document.dispatchEvent(pointer('pointermove', to));
  document.dispatchEvent(pointer('pointerup', to));
}

describe('разбор и ограничения ширины', () => {
  it.each([
    ['400', 400],
    [' 400px ', 400],
    ['400PX', 400],
    ['5000', IMAGE_MAX_WIDTH],
    ['50%', null],
    ['auto', null],
    ['0', null],
    ['-5', null],
    ['10.5', null],
    ['', null],
    [null, null],
    [undefined, null],
  ])('parseImageWidth(%j) → %j', (value, expected) => {
    expect(parseImageWidth(value as string | null | undefined)).toBe(expected);
  });

  it('clampImageWidth держит между минимумом и оригиналом', () => {
    expect(clampImageWidth(5)).toBe(IMAGE_MIN_WIDTH);
    expect(clampImageWidth(700.4)).toBe(700);
    expect(clampImageWidth(9999)).toBe(IMAGE_MAX_WIDTH);
    expect(clampImageWidth(900, 640)).toBe(640);
    expect(clampImageWidth(900, 0)).toBe(900);
  });

  it('parseColumnWidth: без значения и мусор — колонка новостей', () => {
    expect(parseColumnWidth('1168')).toBe(1168);
    expect(parseColumnWidth(undefined)).toBe(DEFAULT_COLUMN_WIDTH);
    expect(parseColumnWidth('abc')).toBe(DEFAULT_COLUMN_WIDTH);
    expect(parseColumnWidth('50')).toBe(DEFAULT_COLUMN_WIDTH);
    expect(parseColumnWidth('99999')).toBe(DEFAULT_COLUMN_WIDTH);
  });
});

describe('width в тексте', () => {
  it('сохраняется после class: src alt class width', () => {
    const mounted = mount('');
    expect(roundTrip(mounted, '<img src="/a.png" alt="Мяч" width="400" class="align-left">')).toBe(
      '<img src="/a.png" alt="Мяч" class="align-left" width="400">'
    );
  });

  it.each([
    ['width="400px"', '<img src="/a.png" width="400">'],
    ['width="50%"', '<img src="/a.png">'],
    ['width="auto" height="300"', '<img src="/a.png">'],
    ['width="400" height="300"', '<img src="/a.png" width="400">'],
  ])('%s', (attributes, expected) => {
    const mounted = mount('');
    expect(roundTrip(mounted, `<img src="/a.png" ${attributes}>`)).toBe(expected);
  });

  it('без правок открытый текст с width не меняется', () => {
    const value = `<p>до</p><img src="${SRC}" class="align-right" width="300">`;
    const mounted = mount(value);
    mounted.editor.view.dispatch(mounted.editor.state.tr.insertText('нормализация', 1));
    expect(mounted.textarea.value).toBe(value);
  });
});

describe('рамка картинки в редакторе', () => {
  it('повторяет width и выравнивание, а в текст не попадает', () => {
    const value = `<p>до</p><img src="${SRC}" class="align-right" width="300"><p>после</p>`;
    const mounted = mount(value);
    const element = frame(mounted);

    expect(element.style.width).toBe('300px');
    expect(element.classList.contains('align-right')).toBe(true);
    expect(element.querySelector('img')?.getAttribute('src')).toBe(SRC);
    expect(mounted.textarea.value).toBe(value);
  });

  it('выравнивание и ширина обновляются вместе с узлом, выделение не теряется', () => {
    const mounted = mountWithImage();
    click(mounted, 'align-left');
    click(mounted, 'size-50');

    const element = frame(mounted);
    expect(element.classList.contains('align-left')).toBe(true);
    expect(element.style.width).toBe('416px');
    expect(element.classList.contains('ProseMirror-selectednode')).toBe(true);
  });

  it('ширина колонки выставляется переменной --rich-editor-column', () => {
    expect(mount('<p>a</p>', undefined, 1168).root.style.getPropertyValue('--rich-editor-column')).toBe(
      '1168px'
    );
    cleanup();
    expect(mount('<p>a</p>').root.style.getPropertyValue('--rich-editor-column')).toBe(
      `${DEFAULT_COLUMN_WIDTH}px`
    );
  });
});

describe('кнопки размера', () => {
  it.each([
    ['size-25', 208],
    ['size-50', 416],
    ['size-75', 624],
  ])('%s: доля колонки новостей (832 px) → %i px', (command, width) => {
    const mounted = mountWithImage();
    click(mounted, command);
    expect(mounted.textarea.value).toBe(`<p>до</p><img src="${SRC}" width="${width}"><p>после</p>`);
    expect(mounted.root.querySelector(`button[data-command="${command}"]`)?.getAttribute('aria-pressed')).toBe(
      'true'
    );
  });

  it('доля считается от колонки страницы (1168 px)', () => {
    const mounted = mountWithImage('', 1168);
    click(mounted, 'size-50');
    expect(mounted.textarea.value).toContain('width="584"');
  });

  it('«Авто» возвращает исходный размер', () => {
    const mounted = mountWithImage(' width="300"');
    const auto = mounted.root.querySelector<HTMLButtonElement>('button[data-command="size-auto"]');
    expect(auto?.getAttribute('aria-pressed')).toBe('false');

    click(mounted, 'size-auto');
    expect(mounted.textarea.value).toBe(`<p>до</p><img src="${SRC}"><p>после</p>`);
    expect(frame(mounted).style.width).toBe('');
    expect(auto?.getAttribute('aria-pressed')).toBe('true');
  });

  it('не растягивает картинку больше оригинала', () => {
    const mounted = mountWithImage();
    Object.defineProperty(frame(mounted).querySelector('img'), 'naturalWidth', { value: 300 });
    click(mounted, 'size-75');
    expect(mounted.textarea.value).toContain('width="300"');
  });

  it('недоступны без выбранной картинки', () => {
    const mounted = mount('<p>текст</p>');
    for (const command of ['size-25', 'size-50', 'size-75', 'size-auto']) {
      expect(mounted.root.querySelector<HTMLButtonElement>(`button[data-command="${command}"]`)?.disabled).toBe(
        true
      );
    }
  });

  it('отмена возвращает прежнюю ширину', () => {
    const mounted = mountWithImage(' width="300"');
    click(mounted, 'size-50');
    expect(mounted.textarea.value).toContain('width="416"');
    click(mounted, 'undo');
    expect(mounted.textarea.value).toContain('width="300"');
  });
});

describe('ручка в углу рамки', () => {
  it('перетаскивание меняет width в тексте', () => {
    const mounted = mountWithImage();
    fakeLayout(frame(mounted));

    drag(mounted, 100, 40);

    // Ручка справа: движение влево сужает картинку, 500 − 60.
    expect(mounted.textarea.value).toBe(`<p>до</p><img src="${SRC}" width="440"><p>после</p>`);
    expect(frame(mounted).style.width).toBe('440px');
    expect(frame(mounted).hasAttribute('data-resizing')).toBe(false);
  });

  it('у картинки справа ручка слева, направление обратное', () => {
    const mounted = mountWithImage(' class="align-right"');
    fakeLayout(frame(mounted));

    drag(mounted, 100, 40);

    expect(mounted.textarea.value).toContain('class="align-right" width="560"');
  });

  it('у картинки по центру смещение удваивается', () => {
    const mounted = mountWithImage(' class="align-center"');
    fakeLayout(frame(mounted));

    drag(mounted, 100, 130);

    expect(mounted.textarea.value).toContain('class="align-center" width="560"');
  });

  it('не уже минимума и не шире оригинала', () => {
    const mounted = mountWithImage();
    Object.defineProperty(frame(mounted).querySelector('img'), 'naturalWidth', { value: 640 });
    fakeLayout(frame(mounted));

    drag(mounted, 100, -2000);
    expect(mounted.textarea.value).toContain(`width="${IMAGE_MIN_WIDTH}"`);

    drag(mounted, 100, 5000);
    expect(mounted.textarea.value).toContain('width="640"');
  });

  it('в текст записывается ширина, которую показал браузер с учётом max-width', () => {
    const mounted = mountWithImage();
    const element = frame(mounted);
    // Колонка 832: сколько ни тяни, больше не покажется.
    vi.spyOn(element, 'getBoundingClientRect').mockImplementation(
      () => ({ width: Math.min(parseFloat(element.style.width) || 500, 832) }) as DOMRect
    );

    drag(mounted, 100, 1100);

    expect(mounted.textarea.value).toContain('width="832"');
  });

  it('нажатие без движения текст не меняет', () => {
    const value = `<p>до</p><img src="${SRC}"><p>после</p>`;
    const mounted = mountWithImage();
    fakeLayout(frame(mounted));

    const handle = frame(mounted).querySelector<HTMLElement>('[data-resize-handle]');
    handle?.dispatchEvent(pointer('pointerdown', 100));
    document.dispatchEvent(pointer('pointerup', 100));

    expect(mounted.textarea.value).toBe(value);
    expect(frame(mounted).hasAttribute('data-resizing')).toBe(false);
  });

  it('отмена жеста возвращает прежнюю ширину', () => {
    const value = `<p>до</p><img src="${SRC}" width="300"><p>после</p>`;
    const mounted = mountWithImage(' width="300"');
    fakeLayout(frame(mounted));

    const handle = frame(mounted).querySelector<HTMLElement>('[data-resize-handle]');
    handle?.dispatchEvent(pointer('pointerdown', 100));
    document.dispatchEvent(pointer('pointermove', 20));
    expect(frame(mounted).style.width).toBe('220px');
    document.dispatchEvent(pointer('pointercancel', 20));

    expect(frame(mounted).style.width).toBe('300px');
    expect(mounted.textarea.value).toBe(value);
  });

  it('после жеста слушатели документа сняты', () => {
    const mounted = mountWithImage();
    fakeLayout(frame(mounted));
    drag(mounted, 100, 80);
    const written = mounted.textarea.value;

    document.dispatchEvent(pointer('pointermove', 0));
    document.dispatchEvent(pointer('pointerup', 0));

    expect(frame(mounted).style.width).toBe('480px');
    expect(mounted.textarea.value).toBe(written);
  });

  it('правая кнопка мыши размер не меняет', () => {
    const mounted = mountWithImage();
    fakeLayout(frame(mounted));
    const handle = frame(mounted).querySelector<HTMLElement>('[data-resize-handle]');

    handle?.dispatchEvent(new PointerEvent('pointerdown', { clientX: 100, button: 2, bubbles: true }));
    document.dispatchEvent(pointer('pointermove', 20));
    document.dispatchEvent(pointer('pointerup', 20));

    expect(mounted.textarea.value).toBe(`<p>до</p><img src="${SRC}"><p>после</p>`);
  });
});
