/**
 * Страж ручного типа `SubscribeRequest` (стори 41.11).
 *
 * Ручной тип в `types/api.ts` и сгенерированный из контракта
 * `types/api.generated.ts` описывают один payload `POST /subscribe/`, но живут
 * порознь: первый пишется руками, второй перегенерируется из `docs/api/openapi.yaml`.
 * Расхождение компилятор не ловит — оба типа валидны сами по себе.
 *
 * Со стори 41.11 подписка берёт два отдельных согласия (ПДн и рассылка), и у
 * каждого своя версия формулировки. Сервер отклоняет payload без любого из пяти
 * полей, а прежнее `consent_text_version` — признак бандла 41.9. Проверка
 * компиляционная: `@ts-expect-error` сам становится ошибкой `tsc`, если поле
 * снова сделают необязательным или вернут устаревшее. Негативные присваивания
 * стоят в ОБА типа — по образцу `register-request-contract.test.ts`.
 */

import { describe, expect, it } from 'vitest';

import { CONSENT_TEXT_VERSIONS } from '@/constants/consentTexts';
import type { SubscribeRequest } from '@/types/api';
import type { components } from '@/types/api.generated';

type GeneratedSubscribeRequest = components['schemas']['SubscribeRequest'];

const email = 'subscriber@example.com';
const pdpVersion = CONSENT_TEXT_VERSIONS.newsletterPdp;
const marketingVersion = CONSENT_TEXT_VERSIONS.newsletterMarketing;

describe('SubscribeRequest: два согласия и две версии формулировок', () => {
  it('payload из пяти полей принимают оба типа', () => {
    const manual: SubscribeRequest = {
      email,
      pdp_consent: true,
      marketing_consent: true,
      pdp_consent_text_version: pdpVersion,
      marketing_consent_text_version: marketingVersion,
    };
    const generated: GeneratedSubscribeRequest = manual;

    expect(generated.marketing_consent_text_version).toBe(manual.marketing_consent_text_version);
  });

  it('payload без marketing_consent не компилируется', () => {
    const withoutMarketingConsent = {
      email,
      pdp_consent: true,
      pdp_consent_text_version: pdpVersion,
      marketing_consent_text_version: marketingVersion,
    };

    // @ts-expect-error — согласие на рассылку при подписке обязательно.
    const manual: SubscribeRequest = withoutMarketingConsent;

    // @ts-expect-error — то же в сгенерированном типе.
    const generated: GeneratedSubscribeRequest = withoutMarketingConsent;

    expect(manual.pdp_consent).toBe(true);
    expect(generated.pdp_consent).toBe(true);
  });

  it('payload без marketing_consent_text_version не компилируется', () => {
    const withoutMarketingVersion = {
      email,
      pdp_consent: true,
      marketing_consent: true,
      pdp_consent_text_version: pdpVersion,
    };

    // @ts-expect-error — версия рассылки обязательна безусловно, в отличие от регистрации.
    const manual: SubscribeRequest = withoutMarketingVersion;

    // @ts-expect-error — то же в сгенерированном типе.
    const generated: GeneratedSubscribeRequest = withoutMarketingVersion;

    expect(manual.marketing_consent).toBe(true);
    expect(generated.marketing_consent).toBe(true);
  });

  it('прежнее поле consent_text_version в объектном литерале не компилируется', () => {
    const valid = {
      email,
      pdp_consent: true,
      marketing_consent: true,
      pdp_consent_text_version: pdpVersion,
      marketing_consent_text_version: marketingVersion,
    } as const;

    // Проверка лишнего свойства срабатывает только на объектном литерале,
    // поэтому поле дописано в литерал, а не взято готовой переменной.
    // @ts-expect-error — `consent_text_version` из контракта удалён (стори 41.11).
    const manual: SubscribeRequest = { ...valid, consent_text_version: pdpVersion };

    // @ts-expect-error — то же в сгенерированном типе.
    const generated: GeneratedSubscribeRequest = { ...valid, consent_text_version: pdpVersion };

    expect(manual.email).toBe(email);
    expect(generated.email).toBe(email);
  });
});
