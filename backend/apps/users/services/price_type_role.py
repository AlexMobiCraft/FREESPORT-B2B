"""
Разрешение роли портала по виду цен из соглашения 1С.

Источник маппинга — редактируемый из админки справочник ``PriceType``
(поле ``user_role``). Обратное направление (роль → вид цен при экспорте
заказа) живёт в ``settings.ONEC_EXCHANGE["PRICE_TYPE_BY_ROLE"]`` и этим
модулем не затрагивается; согласованность двух направлений держит
тест-сторож (FR-40-13).
"""

from __future__ import annotations

from typing import Mapping, NamedTuple

from apps.products.models import PriceType

# Значение реквизита СоглашениеСтатус, которым 1С сообщает об отсутствии
# действующего соглашения (вторая редакция патча расширения БУС).
AGREEMENT_STATUS_NONE = "НетСоглашения"

REASON_RESOLVED = "resolved"
REASON_NO_DATA = "no_data"
REASON_NO_AGREEMENT = "no_agreement"
REASON_UNKNOWN = "unknown_price_type"
REASON_AMBIGUOUS = "ambiguous"


class RoleResolution(NamedTuple):
    """Результат разрешения роли. ``role is None`` → роль не менять."""

    role: str | None
    reason: str
    matched: list[str]


def load_price_type_role_map() -> dict[str, str]:
    """
    Читает справочник видов цен одним запросом.

    Вызывается один раз на сессию импорта, результат передаётся в
    ``resolve_role_from_price_types`` параметром ``role_map``.

    Кэшировать результат на уровне модуля или через ``lru_cache``
    ЗАПРЕЩЕНО: маппинг правится менеджером из админки, а Celery-воркер
    живёт долго и продолжил бы отдавать отменённое значение.

    Ключ приводится к нижнему регистру, а уникальность ``onec_id`` в
    PostgreSQL регистрозависима — значит, две записи с одним GUID в разном
    регистре легальны для БД и схлопнулись бы в один ключ. Если роли у них
    расходятся, победитель определялся бы порядком выборки, то есть
    произвольно; такие GUID исключаются из маппинга целиком, и резолвер
    отвечает по ним ``unknown_price_type`` — роль не применяется. Форма
    админки заводить регистровых двойников не даёт (``PriceTypeAdminForm``),
    но записи, созданные до неё или импортом, отсеиваются здесь.
    """
    rows = PriceType.objects.filter(is_active=True).exclude(user_role="").values_list("onec_id", "user_role")

    mapping: dict[str, str] = {}
    conflicting: set[str] = set()
    for onec_id, user_role in rows:
        key = str(onec_id).strip().lower()
        if key in mapping and mapping[key] != user_role:
            conflicting.add(key)
        mapping[key] = user_role

    if conflicting:
        return {key: role for key, role in mapping.items() if key not in conflicting}
    return mapping


def resolve_role_from_price_types(
    price_type_ids: list[str],
    agreement_status: str = "",
    *,
    role_map: Mapping[str, str] | None = None,
) -> RoleResolution:
    """
    Определяет роль портала по списку GUID видов цен контрагента.

    Args:
        price_type_ids: GUID видов цен из выгрузки (уже дедуплицированы
            парсером, стори 40.1).
        agreement_status: значение реквизита СоглашениеСтатус как есть.
        role_map: готовый маппинг GUID → роль. Если не передан, читается
            из БД — по запросу на вызов.

    Returns:
        RoleResolution: ``role=None`` во всех случаях, кроме ``resolved``.
    """
    # Ветка статуса безусловно приоритетна: 1С прямо сообщила, что
    # действующего соглашения нет. Комбинация «НетСоглашения + непустой
    # GUID» второй редакцией патча не порождается; если она всё же
    # придёт, это дефект выгрузки, и молчаливо выдавать по ней роль
    # опаснее, чем не выдавать никакой.
    if agreement_status.strip().casefold() == AGREEMENT_STATUS_NONE.casefold():
        return RoleResolution(None, REASON_NO_AGREEMENT, [])

    normalized = [str(guid).strip().lower() for guid in price_type_ids if str(guid).strip()]
    if not normalized:
        return RoleResolution(None, REASON_NO_DATA, [])

    mapping = load_price_type_role_map() if role_map is None else role_map

    # Вид цен, известный порталу, но с пустым user_role (РРЦ, МРЦ), в
    # маппинг не попадает вовсе — он трактуется наравне с неизвестным
    # (решение 1 задания): иначе маркетплейсы на РРЦ уехали бы в retail.
    matched = [guid for guid in normalized if mapping.get(guid)]

    if not matched:
        return RoleResolution(None, REASON_UNKNOWN, [])

    if len(matched) > 1:
        # Два разных вида цен — два разных соглашения в 1С. Совпадение
        # ролей сегодня не делает ситуацию однозначной: маппинг
        # редактируем и может разойтись завтра.
        return RoleResolution(None, REASON_AMBIGUOUS, matched)

    return RoleResolution(mapping[matched[0]], REASON_RESOLVED, matched)
