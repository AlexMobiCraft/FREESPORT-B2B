/**
 * Сообщение об устаревшей формулировке согласия (стори 41.9, пятый круг ревью).
 *
 * Ответ `consent_text_outdated` лечится только обновлением страницы. Попутная
 * ошибка из `details` (например, email) такого совета не даёт: человек исправит
 * адрес, отправит ту же устаревшую форму и получит тот же отказ. Поэтому текст
 * берётся только из полей версии, а если там строки нет — показывается запасной.
 */

import { describe, expect, it } from 'vitest';

import {
  CONSENT_TEXT_OUTDATED_CODE,
  CONSENT_TEXT_OUTDATED_MESSAGE,
  getConsentTextOutdatedMessage,
} from '@/constants/consentTexts';

const EMAIL_ERROR = 'Введите правильный адрес электронной почты.';
const SERVER_MESSAGE = 'Текст согласия обновился. Обновите страницу.';

describe('getConsentTextOutdatedMessage', () => {
  it('ответ без машинного кода — обычная валидация, а не устаревшая формулировка', () => {
    expect(getConsentTextOutdatedMessage({ email: [EMAIL_ERROR] })).toBeNull();
    expect(getConsentTextOutdatedMessage(null)).toBeNull();
  });

  it('берёт сообщение поля версии, даже если попутная ошибка стоит в details первой', () => {
    expect(
      getConsentTextOutdatedMessage({
        error: CONSENT_TEXT_OUTDATED_CODE,
        details: { email: [EMAIL_ERROR], consent_text_version: [SERVER_MESSAGE] },
      })
    ).toBe(SERVER_MESSAGE);
  });

  it('без поля версии в details показывает запасной текст, а не попутную ошибку', () => {
    expect(
      getConsentTextOutdatedMessage({
        error: CONSENT_TEXT_OUTDATED_CODE,
        details: { email: [EMAIL_ERROR] },
      })
    ).toBe(CONSENT_TEXT_OUTDATED_MESSAGE);
  });

  it.each([
    ['пустой массив', []],
    ['пустая строка', ['']],
    ['не строка', [42]],
    ['не массив', SERVER_MESSAGE],
  ])(
    'поле версии без строки (%s) даёт запасной текст, а не попутную ошибку',
    (_case, versionMessages) => {
      expect(
        getConsentTextOutdatedMessage({
          error: CONSENT_TEXT_OUTDATED_CODE,
          details: { pdp_consent_text_version: versionMessages, email: [EMAIL_ERROR] },
        })
      ).toBe(CONSENT_TEXT_OUTDATED_MESSAGE);
    }
  );

  it('без details показывает запасной текст', () => {
    expect(getConsentTextOutdatedMessage({ error: CONSENT_TEXT_OUTDATED_CODE })).toBe(
      CONSENT_TEXT_OUTDATED_MESSAGE
    );
  });
});
