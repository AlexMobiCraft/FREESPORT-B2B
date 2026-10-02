/**
 * Ожидание восстановления сессии для клиентских запросов.
 *
 * AuthProvider рендерит страницу сразу, не дожидаясь инициализации авторизации,
 * чтобы сервер отдавал содержимое, а не спиннер. Но дети при монтировании грузят
 * данные, зависящие от роли (оптовые цены сервер режет по токену), а токен
 * попадает в store только после инициализации. Поэтому пока сессия
 * восстанавливается, apiClient придерживает запросы и отправляет их уже с токеном.
 *
 * Отдельный модуль — чтобы и api-client, и AuthProvider зависели от него,
 * а не друг от друга.
 */

let pending: Promise<void> | null = null;
let releasePending: (() => void) | null = null;
let holders = 0;

/**
 * Придерживает запросы до вызова возвращённой функции. Держателей может быть
 * несколько (StrictMode, перемонтирование Providers при переходе между route
 * group во время инициализации): запросы уходят, когда отпустили все.
 * Повторный вызов одного и того же release ничего не делает.
 */
export function holdUntilAuthReady(): () => void {
  if (!pending) {
    pending = new Promise<void>(resolve => {
      releasePending = resolve;
    });
  }
  holders += 1;

  let released = false;
  return () => {
    if (released) return;
    released = true;
    holders -= 1;
    if (holders === 0) {
      releasePending?.();
      pending = null;
      releasePending = null;
    }
  };
}

/**
 * Промис текущего ожидания или уже выполненный, если сессия не восстанавливается.
 */
export function waitForAuthReady(): Promise<void> {
  return pending ?? Promise.resolve();
}
