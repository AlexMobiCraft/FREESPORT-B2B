/**
 * Страж ручного типа `RegisterRequest` (стори 41.9, четвёртый круг ревью).
 *
 * Ручной тип в `types/api.ts` и сгенерированный из контракта
 * `types/api.generated.ts` описывают один и тот же payload `POST /auth/register/`,
 * но живут порознь: первый пишется руками, второй перегенерируется из
 * `docs/api/openapi.yaml`. Расхождение между ними компилятор не ловит — оба типа
 * валидны сами по себе.
 *
 * Здесь охраняется одно конкретное расхождение, найденное ревью: ручной тип
 * позволял отправить `marketing_consent: true` без `marketing_consent_text_version`,
 * хотя backend такой запрос отклоняет `400 consent_text_outdated`, а обе формы
 * версию всегда шлют. Проверка — компиляционная: `@ts-expect-error` сам становится
 * ошибкой `tsc`, если поле снова сделают необязательным.
 *
 * Негативные присваивания стоят в ОБА типа (пятый круг ревью): страж только ручного
 * типа остался бы зелёным, если бы необязательной версию сделала перегенерация
 * контракта. Сгенерированный тип сужается `Pick` до consent-полей, чтобы
 * единственной причиной ошибки компиляции было отсутствие версии, а не давние
 * расхождения прочих полей.
 */

import { describe, expect, it } from 'vitest';

import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';
import type { RegisterRequest } from '@/types/api';
import type { components } from '@/types/api.generated';

type GeneratedRegisterRequest = components['schemas']['UserRegistrationRequest'];

// Псевдонимы, а не `Pick<...>` прямо в аннотации: `@ts-expect-error` действует
// на одну следующую строку, а TS сообщает о несовместимом присваивании на строке
// с именем переменной — многострочная аннотация развела бы директиву и ошибку.
type GeneratedPdpConsent = Pick<GeneratedRegisterRequest, 'pdp_consent' | 'pdp_consent_text_version'>;
type GeneratedMarketingConsent = Pick<
  GeneratedRegisterRequest,
  'marketing_consent' | 'marketing_consent_text_version'
>;

/** Поля, общие для ручного и сгенерированного типа, без consent-полей. */
const identity = {
  email: 'b2b@example.com',
  password: 'Password123!',
  password_confirm: 'Password123!',
  first_name: 'Иван',
  last_name: 'Иванов',
  phone: '+79001234567',
  role: 'wholesale_level1',
} as const;

describe('RegisterRequest: версии формулировок согласия', () => {
  it('payload с обеими версиями принимают оба типа', () => {
    const manual: RegisterRequest = {
      ...identity,
      pdp_consent: true,
      pdp_consent_text_version: CONSENT_TEXT_VERSIONS.registrationPdp,
      marketing_consent: true,
      marketing_consent_text_version: CONSENT_TEXT_VERSIONS.registrationMarketing,
    };

    // Сверяются именно consent-поля: у остальных ручной и сгенерированный типы
    // расходятся давно и по другим причинам (`country` там — перечисление,
    // `email` допускает `null`), и тянуть это в страж версий согласия нечего.
    const generated: Pick<
      GeneratedRegisterRequest,
      'pdp_consent' | 'pdp_consent_text_version' | 'marketing_consent_text_version'
    > = manual;

    expect(generated.marketing_consent_text_version).toBe(manual.marketing_consent_text_version);
  });

  it('payload без версии маркетингового согласия не компилируется', () => {
    const withoutMarketingVersion = {
      ...identity,
      pdp_consent: true,
      pdp_consent_text_version: CONSENT_TEXT_VERSIONS.registrationPdp,
      marketing_consent: true,
    };

    // @ts-expect-error — `marketing_consent_text_version` обязателен: backend
    // отклоняет такой payload, и тип обязан не давать его собрать. Если ошибка
    // исчезнет, `tsc` упадёт на неиспользованном `@ts-expect-error` — это и есть
    // срабатывание стража.
    const manual: RegisterRequest = withoutMarketingVersion;

    // @ts-expect-error — то же в сгенерированном типе: версия обязана оставаться
    // обязательной и после перегенерации контракта.
    const generated: GeneratedMarketingConsent = withoutMarketingVersion;

    expect(manual.marketing_consent).toBe(true);
    expect(generated.marketing_consent).toBe(true);
  });

  it('версия ПДн обязательна в обоих типах', () => {
    const withoutPdpVersion = {
      ...identity,
      pdp_consent: true,
      marketing_consent: false,
      marketing_consent_text_version: CONSENT_TEXT_VERSIONS.registrationMarketing,
    };

    // @ts-expect-error — `pdp_consent_text_version` обязателен всегда, а не только
    // при маркетинговом согласии.
    const manual: RegisterRequest = withoutPdpVersion;

    // @ts-expect-error — то же в сгенерированном типе.
    const generated: GeneratedPdpConsent = withoutPdpVersion;

    expect(manual.pdp_consent).toBe(true);
    expect(generated.pdp_consent).toBe(true);
  });
});
