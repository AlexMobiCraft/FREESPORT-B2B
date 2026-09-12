import type { components } from '@/types/api.generated';

/**
 * Версии формулировок согласия, которые показывают формы (стори 41.9).
 *
 * Значения обязаны совпадать с действующими ревизиями реестра
 * `backend/apps/common/consent_texts.json`; расхождение ловит страж
 * `src/__tests__/consent-texts-registry.test.tsx`, который читает тот же файл.
 *
 * Почему версия зашита в бандл, а не запрашивается у сервера. Константа
 * собирается в тот же бандл, что и сам текст чекбокса, поэтому вкладка, открытая
 * до правки формулировки, отправит прежнюю версию — и сервер отклонит запрос с
 * требованием обновить страницу. Значение, полученное запросом в момент отправки,
 * было бы всегда актуальным и не отличало бы устаревшую вкладку от свежей.
 *
 * Границы: связка «версия ↔ отрисованный текст» держится только здесь, на
 * официальном фронтенде. Произвольный API-клиент пришлёт ту же строку, ничего не
 * показав, и сервер такой запрос примет — доказательством факта показа текста
 * конкретному человеку версия не является.
 */
export const CONSENT_TEXT_VERSIONS = {
  /** Единственный чекбокс форм подписки (SubscribeForm, ElectricSubscribeForm). */
  newsletter: '2026-08-30-77dbceafc3c487ffc24975cf2ce76778',
  /** Обязательный чекбокс ПДн форм регистрации (RegisterForm, B2BRegisterForm). */
  registrationPdp: '2026-09-09-de992f50b0456a90e96a66984010dd74',
  /** Необязательный маркетинговый чекбокс форм регистрации. */
  registrationMarketing: '2026-09-09-e26471e47eba2ba742a4f4488dfdda05',
} as const;

/**
 * Форма ответа берётся из контракта, а не описывается здесь заново: компонент
 * `ConsentTextOutdatedResponse` объявлен в `docs/api/openapi.yaml` (источник —
 * `backend/apps/common/api_schema.py`) и попадает в типы через `npm run generate:types`.
 * Поле `error` там — литерал `'consent_text_outdated'`, поэтому расхождение машинного
 * кода между сервером и фронтом становится ошибкой компиляции, а не поведением в проде.
 */
type ConsentTextOutdatedResponse = components['schemas']['ConsentTextOutdatedResponse'];

/**
 * Машинный код отказа, когда показанная формулировка устарела или версия не
 * пришла. Сервер отдаёт его верхним уровнем ответа `400`:
 * `{ error: 'consent_text_outdated', details: { <поле>: [сообщение] } }`.
 *
 * Код нужен именно на верхнем уровне: DRF-код ошибки (`ErrorDetail.code`) в JSON
 * не попадает, а у пропущенного поля он и вовсе `required`. Узнавать этот случай
 * по тексту сообщения нельзя — формулировку ошибки правят.
 *
 * Тип берётся из контракта: смена кода на сервере ломает компиляцию здесь.
 */
export const CONSENT_TEXT_OUTDATED_CODE: ConsentTextOutdatedResponse['error'] =
  'consent_text_outdated';

/** Запасной текст: показывается, если сервер не прислал сообщение в полях версии `details`. */
export const CONSENT_TEXT_OUTDATED_MESSAGE =
  'Текст согласия обновился. Обновите страницу и подтвердите согласие заново.';

/** Поля, которыми формы доказывают показанную формулировку. */
const CONSENT_TEXT_VERSION_FIELDS = [
  'consent_text_version',
  'pdp_consent_text_version',
  'marketing_consent_text_version',
];

/** Ответ сервера — отказ по устаревшей версии формулировки? */
export const isConsentTextOutdated = (data: unknown): data is ConsentTextOutdatedResponse =>
  !!data &&
  typeof data === 'object' &&
  (data as Partial<ConsentTextOutdatedResponse>).error === CONSENT_TEXT_OUTDATED_CODE;

/**
 * Сообщение для человека из ответа `consent_text_outdated`.
 * `null` — ответ не про версию формулировки, обрабатывать как обычную валидацию.
 *
 * Текст берётся ТОЛЬКО из полей версии; нет там строки — запасной
 * `CONSENT_TEXT_OUTDATED_MESSAGE`. Попутная ошибка из `details` (например, email)
 * требования обновить страницу не передаёт: человек поправит ввод, отправит ту же
 * устаревшую форму и получит тот же отказ.
 */
export const getConsentTextOutdatedMessage = (data: unknown): string | null => {
  if (!isConsentTextOutdated(data)) {
    return null;
  }

  // Тип из контракта обещает `details`, но данные пришли по сети: проверка
  // остаётся, потому что сузили мы `unknown`, а не результат валидации.
  const details: Record<string, unknown> | undefined = data.details;
  if (details && typeof details === 'object') {
    for (const field of CONSENT_TEXT_VERSION_FIELDS) {
      const messages = details[field];
      if (Array.isArray(messages) && typeof messages[0] === 'string' && messages[0]) {
        return messages[0];
      }
    }
  }

  return CONSENT_TEXT_OUTDATED_MESSAGE;
};
