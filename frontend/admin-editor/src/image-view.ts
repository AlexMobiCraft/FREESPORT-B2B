/**
 * Вид картинки в редакторе: рамка с ручкой изменения размера.
 *
 * Только для редактора: в HTML сериализатор отдаёт обычный `img` (`renderHTML` в
 * `extensions.ts`), поэтому рамка и ручка в текст не попадают. Размер хранится как
 * `width` в пикселях; ограничения по ширине (`max-width`, обтекание не шире половины
 * колонки) задаёт CSS, те же правила, что у `.rich-content` на сайте.
 */

import type { Editor } from '@tiptap/core';
import type { Node as ProseMirrorNode } from '@tiptap/pm/model';
import type { NodeView } from '@tiptap/pm/view';

import { IMAGE_ALIGNMENTS, clampImageWidth } from './constants';

const HANDLE_ATTRIBUTE = 'data-resize-handle';

export class ImageView implements NodeView {
  readonly dom: HTMLElement;
  private readonly image: HTMLImageElement;
  private readonly handle: HTMLElement;
  private node: ProseMirrorNode;
  private stopDrag: (() => void) | null = null;

  constructor(
    node: ProseMirrorNode,
    private readonly getPos: () => number | undefined,
    private readonly editor: Editor
  ) {
    this.node = node;
    this.dom = document.createElement('div');
    this.dom.className = 'rich-editor__image';

    this.image = document.createElement('img');
    // Тащится вся рамка как узел ProseMirror, а не «голая» картинка браузера.
    this.image.draggable = false;

    this.handle = document.createElement('span');
    this.handle.className = 'rich-editor__resize-handle';
    this.handle.setAttribute(HANDLE_ATTRIBUTE, '');
    this.handle.title = 'Потяните, чтобы изменить размер';
    this.handle.addEventListener('pointerdown', event => this.startResize(event));
    // На случай браузера, который шлёт mousedown и после отмены pointerdown: без этого
    // нажатие на ручку начало бы перетаскивание рамки или выделение текста.
    this.handle.addEventListener('mousedown', event => event.preventDefault());

    this.dom.append(this.image, this.handle);
    this.render();
  }

  update(node: ProseMirrorNode): boolean {
    if (node.type !== this.node.type) {
      return false;
    }
    this.node = node;
    this.render();
    return true;
  }

  // Рамка меняет собственный style и классы; ProseMirror не должен считать это правкой.
  ignoreMutation(): boolean {
    return true;
  }

  // Ручку обрабатываем сами: иначе ProseMirror начал бы перетаскивание узла.
  stopEvent(event: Event): boolean {
    return event.target instanceof Node && this.handle.contains(event.target);
  }

  destroy(): void {
    this.stopDrag?.();
  }

  private render(): void {
    const { src, alt, align, width } = this.node.attrs as {
      src: string | null;
      alt: string | null;
      align: string | null;
      width: number | null;
    };
    if (src) {
      if (this.image.getAttribute('src') !== src) {
        this.image.setAttribute('src', src);
      }
    } else {
      this.image.removeAttribute('src');
    }
    this.image.alt = alt ?? '';
    for (const value of IMAGE_ALIGNMENTS) {
      this.dom.classList.toggle(`align-${value}`, align === value);
    }
    this.dom.style.width = width ? `${width}px` : '';
  }

  /**
   * Ширина меняется по горизонтали. Левый край у картинки справа привязан к колонке,
   * поэтому её ручка слева; у выровненной по центру край сдвигается вдвое медленнее
   * указателя, и дельта удваивается.
   */
  private startResize(event: PointerEvent): void {
    if (event.button !== undefined && event.button !== 0) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();

    const align = this.node.attrs.align as string | null;
    const direction = align === 'right' ? -1 : 1;
    const factor = align === 'center' ? 2 : 1;
    const startX = event.clientX;
    const startWidth = this.dom.getBoundingClientRect().width || Number(this.node.attrs.width) || 0;
    const natural = this.image.naturalWidth;

    this.dom.dataset.resizing = '';

    let moved = false;
    const onMove = (move: PointerEvent) => {
      moved = true;
      const width = clampImageWidth(
        startWidth + direction * factor * (move.clientX - startX),
        natural
      );
      this.dom.style.width = `${width}px`;
    };
    const finish = (commit: boolean) => {
      document.removeEventListener('pointermove', onMove);
      document.removeEventListener('pointerup', onUp);
      document.removeEventListener('pointercancel', onCancel);
      delete this.dom.dataset.resizing;
      this.stopDrag = null;
      // Нажатие на ручку без движения размер не меняет и в текст ничего не пишет.
      if (commit && moved) {
        this.commit(natural);
      } else {
        this.render();
      }
    };
    const onUp = () => finish(true);
    const onCancel = () => finish(false);

    document.addEventListener('pointermove', onMove);
    document.addEventListener('pointerup', onUp);
    document.addEventListener('pointercancel', onCancel);
    this.stopDrag = () => finish(false);
  }

  /** Записывает в документ ширину, которую браузер реально показал (с учётом `max-width`). */
  private commit(natural: number): void {
    const pos = this.getPos();
    if (pos === undefined) {
      return;
    }
    const shown =
      Math.round(this.dom.getBoundingClientRect().width) || parseInt(this.dom.style.width, 10);
    if (!shown) {
      this.render();
      return;
    }
    this.editor
      .chain()
      .setNodeSelection(pos)
      .updateAttributes('image', { width: clampImageWidth(shown, natural) })
      .run();
  }
}
