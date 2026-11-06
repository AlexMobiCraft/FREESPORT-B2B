"""
Текущая акция из 1С: вид цен «АКЦИЯ …» → `ProductVariant.promo_price`.

Единственная точка, через которую меняется активность акционного `PriceType`:
импорт 1С (`VariantImportProcessor.process_price_types`) и админка
(`PriceTypeAdmin`). Инварианты:

- одновременно активен не более одного акционного типа — частичный
  `UniqueConstraint` `price_types_single_active_promo`;
- смена текущей акции (стала другой или не стало никакой) обнуляет
  `promo_price` у всех вариантов: цены прежней акции к новой не относятся;
- `Product.is_promo` выводится из данных (`sync_promo_flags`), руками не ставится.

Порядок блокировок (общий для всех, кто пишет акционное состояние; иначе взаимоблокировка):

1. состояние акции (advisory): исключительная — у смены акции, общая — у импорта цен;
2. строки товаров по возрастанию `pk` (`lock_products`, `lock_products_stable`);
3. строки вариантов (`lock_variant`, импорт цен, `UPDATE` сброса).

Сохранение и удаление варианта, сброс акции и пересчёт флагов идут в этом порядке.
Пакетное удаление и каскад от товара, бренда или категории (`models.py`) берут товары по
возрастанию `pk` заранее: Collector шлёт сигналы вариантов в порядке `pk` вариантов, а не товаров.
Владельца варианта до блокировки товара узнать можно только без блокировки, а он мог
смениться: после блокировки набор сверяется заново, и если вырос — блокировки откатываются
до точки сохранения и берутся с нуля (дозаблокировать меньший `pk`, держа больший, нельзя).
Тот же довод для составной операции в одной транзакции (товар вместе с инлайнами вариантов,
несколько вариантов подряд): блокировки внутри `lock_variant` не видят, что уже удерживает
внешняя транзакция, поэтому такая операция сама берёт всех владельцев до первой записи
(`lock_operation`). Так сделана `ProductAdmin.save_model`.

Модели импортируются внутри функций, как в `variant_import.py`: парсер берёт
отсюда правило распознавания и не должен тянуть ORM при импорте модуля.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Iterable
from decimal import Decimal
from typing import TYPE_CHECKING, Any, NamedTuple

from django.db import connection, transaction

if TYPE_CHECKING:
    from apps.products.models import PriceType

logger = logging.getLogger(__name__)

PROMO_FIELD = "promo_price"

# Ключ транзакционной advisory-блокировки «состояние текущей акции». Обычная
# блокировка строки не годится: когда активной акции нет, блокировать нечего,
# и два переключения одновременно проходят проверку.
PROMO_STATE_LOCK_KEY = 7_020_261_021

# Сколько товаров пересчитывает за раз `sync_promo_flags()` по всему каталогу: блокировки
# строк берутся пачкой в порядке `pk`, а не на весь каталог сразу.
PROMO_FLAG_CHUNK = 500


def is_promo_name(onec_name: str) -> bool:
    """Название акционного вида цен в 1С всегда начинается со слова «АКЦИЯ»."""
    return (onec_name or "").strip().lower().startswith("акция")


def _uuid1_time(onec_id: str | None) -> int | None:
    """Время создания объекта 1С из GUID (UUID v1), иначе None."""
    try:
        parsed = uuid.UUID(str(onec_id or "").strip())
    except ValueError:
        return None
    return parsed.time if parsed.version == 1 else None


def is_newer(candidate_onec_id: str, current_onec_id: str | None) -> bool:
    """
    Создан ли вид цен `candidate` в 1С позже, чем `current`.

    1С выдаёт GUID версии 1, в нём зашито время создания. Полная выгрузка
    присылает все типы белого списка, включая старую акцию без пометки удаления,
    поэтому текущую акцию по порядку прихода не определить. GUID не v1 (с любой
    стороны) сравнить нельзя — такой кандидат считается новее.
    """
    if not current_onec_id:
        return True
    candidate_time = _uuid1_time(candidate_onec_id)
    current_time = _uuid1_time(current_onec_id)
    if candidate_time is None or current_time is None:
        return True
    return candidate_time > current_time


def lock_promo_state(*, shared: bool = False) -> None:
    """
    Берёт блокировку состояния текущей акции до конца транзакции.

    Исключительная — у тех, кто меняет текущую акцию (`save_price_type`,
    `delete_price_types`): они выстраиваются в очередь, а чтение «до» идёт уже
    под блокировкой. Общая — у импорта цен, который пишет `promo_price`: пока
    он пишет, акцию никто не переключит, и наоборот. Вызывать внутри
    `transaction.atomic()`: вне транзакции блокировка снимается сразу.
    """
    function = "pg_advisory_xact_lock_shared" if shared else "pg_advisory_xact_lock"
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT {function}(%s)", [PROMO_STATE_LOCK_KEY])


def current_promo_type() -> PriceType | None:
    """Текущая акция: активный `PriceType` с `product_field="promo_price"`."""
    from apps.products.models import PriceType

    return PriceType.objects.filter(product_field=PROMO_FIELD, is_active=True).first()


class PriceTypeConflict(Exception):
    """Вид цен удалили, пока его правили: сохранение создало бы запись заново."""


def save_price_type(price_type: PriceType, *, changed_fields: Iterable[str] | None = None) -> bool:
    """
    Сохраняет вид цен, соблюдая правило одной текущей акции.

    Если запись становится текущей акцией, прежняя гасится ДО сохранения:
    в обратном порядке частичный `UniqueConstraint` дал бы `IntegrityError`.

    Args:
        price_type: сохраняемая запись.
        changed_fields: поля, которые менеджер изменил в форме админки. Запись
            перечитывается под блокировкой, и поверх свежего состояния кладутся только
            они: форма, открытая до переключения акции, не вернёт прежнюю акцию и не
            затрёт чужие правки. Без аргумента сохраняется весь объект — так делает
            импорт, читающий запись уже под блокировкой.

    Returns:
        True, если сменилась текущая акция и акционные цены сброшены.

    Raises:
        PriceTypeConflict: запись удалена другим запросом. Django превратил бы UPDATE
            по исчезнувшей строке в INSERT с прежним PK и вернул бы удалённый вид цен.
        ValueError: у существующей записи меняется GUID. Цены прежнего вида 1С остались бы
            у записи, которая теперь указывает на другой вид.
    """
    from apps.products.models import PriceType

    with transaction.atomic():
        lock_promo_state()
        stored = None
        if price_type.pk and not price_type._state.adding:
            stored = PriceType.objects.filter(pk=price_type.pk).first()
            if stored is None:
                raise PriceTypeConflict(f"Вид цен «{price_type.onec_name}» уже удалён")

        target = price_type
        if stored is not None:
            stored_onec_id = stored.onec_id
            if changed_fields is not None:
                model_fields = {field.name for field in PriceType._meta.fields}
                for name in changed_fields:
                    if name in model_fields:
                        setattr(stored, name, getattr(price_type, name))
                target = stored
            if target.onec_id != stored_onec_id:
                raise ValueError(f"GUID вида цен 1С не меняется: {stored_onec_id} → {target.onec_id}")

        before = current_promo_type()
        before_pk = before.pk if before else None

        becomes_current = target.product_field == PROMO_FIELD and bool(target.is_active)
        if becomes_current:
            others = PriceType.objects.filter(product_field=PROMO_FIELD, is_active=True)
            if target.pk:
                others = others.exclude(pk=target.pk)
            others.update(is_active=False)

        target.save()
        if target is not price_type:
            # Объект админки показывает то, что реально лежит в БД
            for field in PriceType._meta.fields:
                setattr(price_type, field.attname, getattr(target, field.attname))

        after_pk: int | None
        if becomes_current:
            after_pk = target.pk
        else:
            after_pk = None if before_pk == target.pk else before_pk

        if before_pk == after_pk:
            return False

        _reset_promo_state()

    logger.info(
        "Текущая акция сменилась: %s → %s, акционные цены сброшены",
        before.onec_name if before else "нет",
        target.onec_name if becomes_current else "нет",
    )
    return True


def activate(price_type: PriceType) -> bool:
    """Делает вид цен текущей акцией. True — акционные цены сброшены."""
    price_type.product_field = PROMO_FIELD
    price_type.is_active = True
    return save_price_type(price_type)


def deactivate_promo(price_type: PriceType) -> bool:
    """
    Гасит акционный вид цен (пометка удаления в 1С, снятие «Активный»).

    Цены сбрасываются, только если гасится текущая акция: пометка у уже
    неактивного типа ничего не обнуляет.
    """
    price_type.is_active = False
    return save_price_type(price_type)


def delete_price_types(price_types: Iterable[PriceType]) -> bool:
    """Удаляет виды цен. Удаление текущей акции сбрасывает акционные цены."""
    with transaction.atomic():
        lock_promo_state()
        before = current_promo_type()
        deleted_pks = set()
        for price_type in price_types:
            deleted_pks.add(price_type.pk)
            price_type.delete()

        if before is None or before.pk not in deleted_pks:
            return False

        _reset_promo_state()

    logger.info("Удалена текущая акция %s, акционные цены сброшены", before.onec_name)
    return True


def _reset_promo_state() -> None:
    """
    Смена текущей акции: `promo_price` обнуляется у всех вариантов, флаги «Акция» пересчитываются.

    Блокировки берутся в порядке «товары по `pk` → варианты» — так же, как при сохранении
    товара вместе с инлайнами в админке (сначала строка товара, потом его варианты).
    Обратный порядок (сначала сброс цен, потом блокировка товара) уходил с ним в
    взаимоблокировку. Состояние акции заблокировано исключительно, поэтому импорт цен, который
    держит её общей, новых `promo_price` за это время не запишет.

    Набор товаров собирается заново после блокировок (`lock_products_stable`): вариант с
    акционной ценой могли перенести в другой товар между сбором и блокировкой, и тогда сброс
    очистил бы его цену, а флаг нового владельца остался бы выставленным.
    """
    from apps.products.models import Product, ProductVariant

    def find_owners() -> set[int]:
        owners = set(ProductVariant.objects.filter(promo_price__isnull=False).values_list("product_id", flat=True))
        owners.update(Product.objects.filter(is_promo=True).values_list("pk", flat=True))
        return owners

    with transaction.atomic():
        ordered = lock_products_stable(find_owners)
        ProductVariant.objects.filter(promo_price__isnull=False).update(promo_price=None)
        _recompute_in_chunks(ordered)


def lock_products(product_ids: Iterable[int]) -> None:
    """
    Блокирует строки товаров (`FOR NO KEY UPDATE`) по возрастанию `pk` до конца транзакции.

    Все, кто держит несколько товаров сразу (пересчёт флагов, пакетное удаление вариантов),
    берут их в этом порядке: встречные операции не ждут друг друга по кругу. Пачками по
    `PROMO_FLAG_CHUNK` в том же порядке — длинный `IN (...)` не нужен.
    """
    from apps.products.models import Product

    ordered = sorted(set(product_ids))
    for start in range(0, len(ordered), PROMO_FLAG_CHUNK):
        chunk = ordered[start : start + PROMO_FLAG_CHUNK]
        list(Product.objects.select_for_update(no_key=True).filter(pk__in=chunk).order_by("pk").values_list("pk"))


class OwnersChanged(Exception):
    """Набор владельцев изменился, пока брались блокировки: блокировки откатываются, набор собирается заново."""


def _require_transaction() -> None:
    """Блокировки живут до конца транзакции: вне её они снимаются сразу и ничего не удерживают."""
    if not connection.in_atomic_block:
        raise RuntimeError("Блокировки товаров удерживаются до конца транзакции: вызывай внутри transaction.atomic()")


def lock_products_stable(find_ids: Callable[[], Iterable[int]]) -> list[int]:
    """
    Блокирует товары из `find_ids()` и возвращает их `pk`, когда набор больше не меняется.

    Набор собирается без блокировок (владельцы вариантов, акционных цен) и успевает измениться
    до того, как блокировки получены. Поэтому после блокировки он собирается ещё раз: совпал —
    готово, вырос — блокировки откатываются до точки сохранения и берутся заново. Перенос
    варианта идёт под блокировкой его прежнего товара (`lock_variant`), поэтому набор,
    совпавший при повторном сборе, остаётся таким до конца транзакции.
    """
    _require_transaction()
    while True:
        try:
            with transaction.atomic():
                ordered = sorted(set(find_ids()))
                lock_products(ordered)
                if not set(find_ids()) <= set(ordered):
                    raise OwnersChanged
                return ordered
        except OwnersChanged:
            continue


def lock_operation(*, product_ids: Iterable[int] = (), variant_pks: Iterable[int] = ()) -> list[int]:
    """
    Составная операция в одной транзакции: заранее блокирует всех владельцев, которых она затронет.

    Порядок «товары по возрастанию `pk`» соблюдают `lock_variant`, пересчёт и сброс акции, но каждый из
    них видит только свой вызов. Операция, которая в одной транзакции пишет товар B, а затем вариант
    товара A (сохранение товара вместе с инлайнами, несколько вариантов подряд), держит B и берёт A —
    против параллельного пересчёта (A, затем B) это взаимоблокировка. Поэтому такая операция до первой
    записи вызывает `lock_operation`: все её товары берутся по возрастанию разом, а последующие
    блокировки в `lock_variant` и пересчёте повторяются на уже удерживаемых строках и не ждут.

    Владельцы вариантов читаются без блокировки и успевают смениться, поэтому набор собирается ещё раз
    после блокировок (`lock_products_stable`).

    Args:
        product_ids: товары, которые операция запишет сама.
        variant_pks: варианты, которые она запишет; блокируются их текущие товары.

    Returns:
        `pk` заблокированных товаров по возрастанию.
    """
    from apps.products.models import ProductVariant

    own = set(product_ids)
    pks = list(variant_pks)

    def find_owners() -> set[int]:
        owners = set(own)
        if pks:
            owners.update(ProductVariant.objects.filter(pk__in=pks).order_by().values_list("product_id", flat=True))
        return owners

    return lock_products_stable(find_owners)


class VariantState(NamedTuple):
    """Строка варианта, прочитанная под блокировкой."""

    product_id: int
    is_active: bool
    promo_price: Decimal | None


def lock_variant(pk: int, *, extra_product_ids: Iterable[int | None] = ()) -> VariantState | None:
    """
    Блокирует товар варианта (и `extra_product_ids`), затем строку варианта; читает её состояние.

    Порядок «товар → вариант» тот же, что у сохранения товара с инлайнами и сброса акции.
    Владелец читается без блокировки, поэтому после блокировки строки он сверяется с
    заблокированными товарами: перенесли — всё откатывается до точки сохранения и повторяется.
    Состояние читается уже под блокировкой строки: вариант не отключат, не перенесут и не
    запишут ему акционную цену, пока вызывающий не завершил транзакцию.

    Args:
        pk: первичный ключ варианта.
        extra_product_ids: товары, которые вызывающий собирается затронуть ещё
            (новый владелец при переносе).

    Returns:
        Состояние строки или None, если варианта уже нет.
    """
    from apps.products.models import ProductVariant

    _require_transaction()
    extra = {product_id for product_id in extra_product_ids if product_id is not None}
    variants = ProductVariant.objects.filter(pk=pk).order_by()
    while True:
        try:
            with transaction.atomic():
                owners = {*variants.values_list("product_id", flat=True), *extra}
                lock_products(owners)
                locked = variants.select_for_update(no_key=True)
                row = locked.values_list("product_id", "is_active", "promo_price").first()
                if row is None:
                    return None
                if row[0] not in owners:
                    raise OwnersChanged
                return VariantState(*row)
        except OwnersChanged:
            continue


def _has_active_promo_variant() -> Any:
    from django.db.models import Exists, OuterRef

    from apps.products.models import ProductVariant

    return Exists(ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True, promo_price__gt=0))


def _recompute_locked(product_ids: list[int]) -> int:
    """
    Пересчитывает флаг у товаров: сначала блокировка их строк, затем расчёт по свежим данным.

    Порядок «блокировка → отдельный `UPDATE`» важен: оператор, начавшийся после получения
    блокировки, видит всё, что зафиксировали чужие транзакции за время ожидания. Одним
    оператором `UPDATE … WHERE NOT EXISTS (…)` флаг ушёл бы по снимку, взятому до ожидания.

    Блокировка `FOR NO KEY UPDATE`, а не `FOR UPDATE`: проверка внешнего ключа при
    вставке или переносе варианта берёт `FOR KEY SHARE` на строку товара и не должна
    ждать пересчёт. Строки блокируются по возрастанию `pk` (`lock_products`) — встречные
    переносы вариантов не уходят в взаимоблокировку.
    """
    from apps.products.models import Product

    if not product_ids:
        return 0
    has_promo = _has_active_promo_variant()
    with transaction.atomic():
        lock_products(product_ids)
        products = Product.objects.filter(pk__in=product_ids)
        turned_on = products.filter(has_promo, is_promo=False).update(is_promo=True)
        turned_off = products.filter(~has_promo, is_promo=True).update(is_promo=False)
    return turned_on + turned_off


def _recompute_in_chunks(ordered_ids: list[int]) -> int:
    """Пересчёт упорядоченного набора товаров пачками: блокировки идут в том же порядке `pk`."""
    changed = 0
    for start in range(0, len(ordered_ids), PROMO_FLAG_CHUNK):
        changed += _recompute_locked(ordered_ids[start : start + PROMO_FLAG_CHUNK])
    return changed


def sync_promo_flags(product_id: int | None = None, *, product_ids: Iterable[int] | None = None) -> int:
    """
    `Product.is_promo` = у товара есть активный вариант с `promo_price > 0`.

    Обновляются только расходящиеся строки.

    Пересчёт идёт под блокировкой строк товаров (`_recompute_locked`): две транзакции,
    отключающие по последнему акционному варианту, иначе каждая видела бы чужой вариант
    ещё активным и оставила флаг. Вторая получает блокировку после коммита первой и
    считает уже по свежим данным. Так же устроен пересчёт всего каталога — по пачкам
    расходящихся товаров: прежний единый `UPDATE` записывал бы результат по снимку,
    взятому до ожидания чужой блокировки.

    Args:
        product_id: пересчитать один товар (изменилась активность его варианта).
        product_ids: пересчитать несколько товаров (перенос варианта между товарами).
        Без аргументов — весь каталог (после импорта цен и смены акции).

    Returns:
        Количество товаров, у которых флаг изменился.
    """
    from apps.products.models import Product

    if product_id is not None or product_ids is not None:
        wanted = {pk for pk in (product_id, *(product_ids or ())) if pk is not None}
        return _recompute_in_chunks(sorted(wanted))

    has_promo = _has_active_promo_variant()
    diverging = set(Product.objects.filter(has_promo, is_promo=False).values_list("pk", flat=True))
    diverging.update(Product.objects.filter(~has_promo, is_promo=True).values_list("pk", flat=True))
    return _recompute_in_chunks(sorted(diverging))
