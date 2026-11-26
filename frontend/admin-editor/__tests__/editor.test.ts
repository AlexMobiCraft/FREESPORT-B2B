/**
 * Поведение редактора как поля формы: textarea меняется только после действия
 * сотрудника, пустой текст, режим HTML.
 */

import { afterEach, describe, expect, it } from 'vitest';

import { mountAll } from '../src/editor';
import { HTML_MODE_HINT } from '../src/constants';
import { click, cleanup, fixture, mount, selectAllText, typeText } from './helpers';

afterEach(cleanup);

const FIXTURES = ['reference.html', 'requisites.html', 'article-document.html', 'news-markdown.txt'];

describe('без действия сотрудника textarea не меняется', () => {
  it.each(FIXTURES)('%s: монтирование и нормализация', (name) => {
    const value = fixture(name);
    const mounted = mount(value);
    expect(mounted.textarea.value).toBe(value);

    // Программная транзакция — как нормализация ProseMirror или плагин.
    const { state } = mounted.editor;
    mounted.editor.view.dispatch(state.tr.insertText('нормализация', 1));
    mounted.editor.commands.focus();
    mounted.editor.view.dom.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowDown', bubbles: true }));
    mounted.editor.commands.setContent('<p>другое</p>');
    expect(mounted.textarea.value).toBe(value);
  });

  it('снимает required, проверку пустоты оставляет серверу', () => {
    const mounted = mount('<p>текст</p>');
    expect(mounted.textarea.required).toBe(false);
    expect(mounted.textarea.hasAttribute('required')).toBe(false);
  });

  it('textarea остаётся в форме и уходит с ней', () => {
    const mounted = mount('<p>текст</p>');
    expect(mounted.textarea.form).toBe(mounted.form);
    expect(new FormData(mounted.form).get('content')).toBe('<p>текст</p>');
  });
});

describe('действие сотрудника', () => {
  it('ввод пишет HTML в textarea', () => {
    const mounted = mount('<p>текст</p>');
    mounted.editor.commands.setTextSelection(3);
    typeText(mounted, 'X');
    expect(mounted.textarea.value).toBe('<p>теXкст</p>');
  });

  it('стёртый текст — пустая строка, а не <p></p>', () => {
    const mounted = mount('<p>текст</p><p>ещё</p>');
    selectAllText(mounted);
    mounted.editor.view.dom.dispatchEvent(new KeyboardEvent('keydown', { key: 'Backspace', bubbles: true }));
    mounted.editor.commands.deleteSelection();
    expect(mounted.editor.isEmpty).toBe(true);
    expect(mounted.textarea.value).toBe('');
  });

  it('только пустые абзацы — тоже пустая строка', () => {
    const mounted = mount('<p>a</p>');
    selectAllText(mounted);
    typeText(mounted, ' ');
    mounted.editor.commands.setContent('<p></p><p></p>');
    expect(mounted.textarea.value).toBe('');
  });
});

describe('режим HTML', () => {
  it('подсказка у кнопки — текст из спеки', () => {
    const mounted = mount('<p>текст</p>');
    const button = mounted.root.querySelector<HTMLButtonElement>('button[data-command="html"]');
    expect(button?.title).toBe(HTML_MODE_HINT);
  });

  it('показывает исходный код textarea, остальные кнопки недоступны', () => {
    const value = fixture('article-document.html');
    const mounted = mount(value);
    click(mounted, 'html');

    expect(mounted.isHtmlMode()).toBe(true);
    expect(mounted.textarea.style.display).toBe('');
    expect(mounted.textarea.value).toBe(value);
    expect(mounted.root.querySelector<HTMLButtonElement>('button[data-command="bold"]')?.disabled).toBe(true);
    expect(mounted.root.querySelector('button[data-command="html"]')?.getAttribute('aria-pressed')).toBe('true');
  });

  it('возврат без правки ничего не меняет', () => {
    const value = fixture('article-document.html');
    const mounted = mount(value);
    click(mounted, 'html');
    click(mounted, 'html');
    expect(mounted.isHtmlMode()).toBe(false);
    expect(mounted.textarea.style.display).toBe('none');
    expect(mounted.textarea.value).toBe(value);
  });

  it('правка видна в визуальном режиме, лишнее отброшено', () => {
    const mounted = mount('<p>текст</p>');
    click(mounted, 'html');
    mounted.textarea.value = '<div class="x"><h1>Новый</h1><p style="color:red">абзац</p></div>';
    click(mounted, 'html');

    expect(mounted.root.querySelector('.rich-editor__prose h2')?.textContent).toBe('Новый');
    expect(mounted.textarea.value).toBe('<h2>Новый</h2><p>абзац</p>');
  });
});

describe('монтирование на странице', () => {
  it('mountAll находит textarea[data-rich-editor] один раз', () => {
    document.body.innerHTML =
      '<form><textarea data-rich-editor data-upload-url="/u/">a</textarea><textarea name="excerpt">b</textarea></form>';
    expect(mountAll(document)).toHaveLength(1);
    expect(mountAll(document)).toHaveLength(0);
    expect(document.querySelectorAll('.rich-editor')).toHaveLength(1);
  });
});
