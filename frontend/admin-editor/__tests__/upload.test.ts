/**
 * Загрузка картинок: вставка из буфера, перетаскивание, узел загрузки,
 * блокировка отправки формы и ответы сервера.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { MAX_IMAGE_BYTES, MESSAGES } from '../src/constants';
import { UploadError, uploadImage } from '../src/upload';
import { CSRF_TOKEN, UPLOAD_URL, cleanup, dropEvent, imageFile, mount, pasteEvent } from './helpers';

const IMAGE_URL = '/media/content/images/2026/10/0f1e2d3c4b5a69788796a5b4c3d2e1f0.png';

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function submit(form: HTMLFormElement): boolean {
  const event = new Event('submit', { cancelable: true });
  form.dispatchEvent(event);
  return event.defaultPrevented;
}

beforeEach(() => {
  let counter = 0;
  vi.spyOn(URL, 'createObjectURL').mockImplementation(() => `blob:http://localhost/preview-${++counter}`);
  vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => undefined);
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('вставка из буфера', () => {
  it('успех: узел загрузки, затем картинка; отправка заблокирована на время загрузки', async () => {
    const response = deferred<string>();
    const upload = vi.fn(() => response.promise);
    const mounted = mount('<p>текст</p>', upload);
    mounted.editor.commands.setTextSelection(mounted.editor.state.doc.content.size - 1);
    const file = imageFile();

    expect(mounted.handlePaste(mounted.editor.view, pasteEvent([file]))).toBe(true);
    expect(upload).toHaveBeenCalledWith(UPLOAD_URL, file, CSRF_TOKEN);

    // Превью видно в редакторе, но не в textarea и не в режиме HTML.
    expect(mounted.root.querySelector('.rich-editor__prose img.rich-editor__uploading')?.getAttribute('src')).toBe(
      'blob:http://localhost/preview-1',
    );
    expect(mounted.textarea.value).toBe('<p>текст</p>');
    expect(mounted.textarea.value).not.toContain('blob:');
    expect(submit(mounted.form)).toBe(true);
    expect(mounted.root.querySelector('.rich-editor__error')?.textContent).toBe(MESSAGES.waitForUpload);
    expect(mounted.root.querySelector<HTMLButtonElement>('button[data-command="html"]')?.disabled).toBe(true);
    mounted.setHtmlMode(true);
    expect(mounted.isHtmlMode()).toBe(false);

    response.resolve(IMAGE_URL);
    await mounted.settled();

    expect(mounted.textarea.value).toBe(`<p>текст</p><img src="${IMAGE_URL}">`);
    expect(mounted.root.querySelector('.rich-editor__uploading')).toBeNull();
    expect(submit(mounted.form)).toBe(false);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:http://localhost/preview-1');
  });

  it('ошибка: узел удалён, текст ошибки у редактора, textarea без превью', async () => {
    const upload = vi.fn(() => Promise.reject(new UploadError('Файл не похож на картинку.')));
    const mounted = mount('<p>текст</p>', upload);

    mounted.handlePaste(mounted.editor.view, pasteEvent([imageFile()]));
    await mounted.settled();

    expect(mounted.root.querySelector('.rich-editor__uploading')).toBeNull();
    expect(mounted.editor.state.doc.toJSON().content).toHaveLength(1);
    expect(mounted.textarea.value).toBe('<p>текст</p>');
    const error = mounted.root.querySelector<HTMLElement>('.rich-editor__error');
    expect(error?.hidden).toBe(false);
    expect(error?.textContent).toBe('Файл не похож на картинку.');
    expect(submit(mounted.form)).toBe(false);
  });

  it('буфер с текстом (Word, браузер) — обычная вставка текста', () => {
    const upload = vi.fn();
    const mounted = mount('<p>текст</p>', upload);
    expect(mounted.handlePaste(mounted.editor.view, pasteEvent([imageFile()], 'абзац из Word'))).toBe(false);
    expect(mounted.handlePaste(mounted.editor.view, pasteEvent([]))).toBe(false);
    expect(upload).not.toHaveBeenCalled();
  });

  it('пустой тип файла (перетаскивание в Windows) уходит на сервер — формат решает он', async () => {
    const upload = vi.fn(async () => IMAGE_URL);
    const mounted = mount('<p>текст</p>', upload);
    const file = imageFile('photo.png', '');

    mounted.handlePaste(mounted.editor.view, pasteEvent([file]));
    await mounted.settled();

    expect(upload).toHaveBeenCalledWith(UPLOAD_URL, file, CSRF_TOKEN);
    expect(mounted.textarea.value).toContain(`<img src="${IMAGE_URL}">`);
  });

  it('неподходящий файл отклоняется до отправки', () => {
    const upload = vi.fn();
    const mounted = mount('<p>текст</p>', upload);

    mounted.handlePaste(mounted.editor.view, pasteEvent([imageFile('a.svg', 'image/svg+xml')]));
    expect(mounted.root.querySelector('.rich-editor__error')?.textContent).toBe(MESSAGES.wrongType);

    mounted.handlePaste(mounted.editor.view, pasteEvent([imageFile('big.jpg', 'image/jpeg', MAX_IMAGE_BYTES + 1)]));
    expect(mounted.root.querySelector('.rich-editor__error')?.textContent).toBe(MESSAGES.tooLarge);

    expect(upload).not.toHaveBeenCalled();
    expect(mounted.root.querySelector('.rich-editor__uploading')).toBeNull();
  });
});

describe('кнопка «Картинка»', () => {
  it('открывает выбор файла; выбранный файл загружается, поле выбора очищается', async () => {
    const response = deferred<string>();
    const upload = vi.fn(() => response.promise);
    const mounted = mount('<p>текст</p>', upload);
    const input = mounted.root.querySelector<HTMLInputElement>('input[type="file"]')!;
    const openDialog = vi.spyOn(input, 'click').mockImplementation(() => undefined);

    mounted.root.querySelector<HTMLButtonElement>('button[data-command="image"]')!.click();
    expect(openDialog).toHaveBeenCalledTimes(1);

    const file = imageFile();
    Object.defineProperty(input, 'files', { value: [file], configurable: true });
    input.dispatchEvent(new Event('change'));

    expect(upload).toHaveBeenCalledWith(UPLOAD_URL, file, CSRF_TOKEN);
    expect(mounted.root.querySelectorAll('.rich-editor__uploading')).toHaveLength(1);
    expect(input.value).toBe('');

    response.resolve(IMAGE_URL);
    await mounted.settled();
    expect(mounted.textarea.value).toContain(`<img src="${IMAGE_URL}">`);
  });
});

describe('перетаскивание', () => {
  it('файлы загружаются по одному узлу на файл', async () => {
    const urls = ['/media/content/images/2026/10/a.jpg', '/media/content/images/2026/10/b.webp'];
    const upload = vi.fn(async (_url: string, file: File) => urls[file.name === 'a.jpg' ? 0 : 1]);
    const mounted = mount('<p>текст</p>', upload);

    const handled = mounted.handleDrop(
      mounted.editor.view,
      dropEvent([imageFile('a.jpg', 'image/jpeg'), imageFile('b.webp', 'image/webp')]),
    );
    expect(handled).toBe(true);
    expect(mounted.root.querySelectorAll('.rich-editor__uploading')).toHaveLength(2);
    await mounted.settled();

    expect(mounted.textarea.value).toContain(`<img src="${urls[0]}"><img src="${urls[1]}">`);
  });

  it('перетаскивание без файлов — обычное перемещение текста', () => {
    const mounted = mount('<p>текст</p>', vi.fn());
    expect(mounted.handleDrop(mounted.editor.view, dropEvent([]))).toBe(false);
  });

  it('отмена после загрузки убирает картинку, повтор возвращает картинку, а не превью', async () => {
    const mounted = mount('<p>текст</p>', async () => IMAGE_URL);
    mounted.handleDrop(mounted.editor.view, dropEvent([imageFile()]));
    await mounted.settled();
    expect(mounted.textarea.value).toContain(`<img src="${IMAGE_URL}">`);

    mounted.editor.commands.undo();
    expect(mounted.textarea.value).toBe('<p>текст</p>');
    expect(mounted.root.querySelector('.rich-editor__uploading')).toBeNull();

    mounted.editor.commands.redo();
    expect(mounted.textarea.value).toContain(`<img src="${IMAGE_URL}">`);
    expect(mounted.root.querySelector('.rich-editor__uploading')).toBeNull();
    expect(mounted.root.querySelector(`.rich-editor__prose img[src="${IMAGE_URL}"]`)).not.toBeNull();
  });
});

describe('uploadImage', () => {
  function stubFetch(response: Response | Error) {
    const fetchMock = vi.fn(() => (response instanceof Error ? Promise.reject(response) : Promise.resolve(response)));
    vi.stubGlobal('fetch', fetchMock);
    return fetchMock;
  }

  it('POST с файлом и CSRF-токеном, без перехода по редиректу', async () => {
    const fetchMock = stubFetch(Response.json({ url: IMAGE_URL }));
    const file = imageFile();

    await expect(uploadImage(UPLOAD_URL, file, CSRF_TOKEN)).resolves.toBe(IMAGE_URL);

    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(UPLOAD_URL);
    expect(init.method).toBe('POST');
    expect(init.redirect).toBe('manual');
    const body = init.body as FormData;
    expect(body.get('csrfmiddlewaretoken')).toBe(CSRF_TOKEN);
    expect((body.get('image') as File).name).toBe('photo.png');
  });

  it.each([
    ['400 с текстом сервера', Response.json({ error: 'Файл больше 10 МБ.' }, { status: 400 }), 'Файл больше 10 МБ.'],
    ['403', new Response('', { status: 403 }), MESSAGES.forbidden],
    ['302 на вход', new Response(null, { status: 302 }), MESSAGES.session],
    ['500 без JSON', new Response('<html>', { status: 500 }), `${MESSAGES.failed} (код ответа 500).`],
    ['чужой URL в ответе', Response.json({ url: 'https://evil.example/x.png' }), `${MESSAGES.failed} (код ответа 200).`],
  ])('%s', async (_name, response, message) => {
    stubFetch(response);
    await expect(uploadImage(UPLOAD_URL, imageFile(), CSRF_TOKEN)).rejects.toThrow(message);
  });

  it('нет сети', async () => {
    stubFetch(new TypeError('Failed to fetch'));
    await expect(uploadImage(UPLOAD_URL, imageFile(), CSRF_TOKEN)).rejects.toThrow(MESSAGES.network);
  });
});
