/**
 * Точка входа бандла. Django выводит {{ media }} в <head>, поэтому на настоящей
 * странице скрипт выполняется до разбора формы и монтирует редактор по DOMContentLoaded.
 */

import { afterEach, expect, it } from 'vitest';

import { cleanup } from './helpers';

afterEach(() => {
  cleanup();
  delete (document as { readyState?: unknown }).readyState;
});

it('монтирует редактор по DOMContentLoaded, если документ ещё грузится', async () => {
  Object.defineProperty(document, 'readyState', { value: 'loading', configurable: true });
  document.body.innerHTML =
    '<form><textarea name="content" data-rich-editor data-upload-url="/u/">текст</textarea></form>';

  await import('../src/index');
  expect(document.querySelectorAll('.rich-editor')).toHaveLength(0);

  document.dispatchEvent(new Event('DOMContentLoaded'));
  expect(document.querySelectorAll('.rich-editor')).toHaveLength(1);
});
