/**
 * Настройки оформления заказа (`/checkout`).
 *
 * Выбор способа доставки временно отключён (решение владельца 16.11.2026):
 * способ и стоимость доставки согласует персональный специалист после оформления заказа.
 * Пока флаг выключен, форма не запрашивает `/delivery/methods/`, вместо
 * радиокнопок показывает плашку, а заказ уходит с `DEFAULT_DELIVERY_METHOD`
 * (`by_agreement` — «Согласуется с персональным специалистом», `delivery_cost` = 0).
 *
 * Как вернуть выбор: поставить `DELIVERY_METHOD_SELECTION_ENABLED = true`
 * и выкатить релиз (PR в develop → синк в main). Компонент `DeliveryOptions`,
 * `deliveryService` и справочник способов на backend не удалялись — блок
 * заработает как раньше. Значение `by_agreement`, сохранённое в черновике
 * формы, при включённом выборе сбрасывается, и покупатель выбирает способ сам.
 */

import type { DeliveryMethodCode } from '@/types/order';

/** Показывать ли на `/checkout` выбор способа доставки. */
export const DELIVERY_METHOD_SELECTION_ENABLED: boolean = false;

/** Способ доставки заказа, пока выбор выключен. */
export const DEFAULT_DELIVERY_METHOD: DeliveryMethodCode = 'by_agreement';
