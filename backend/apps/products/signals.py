"""
Signals products: кэш featured brands (Brand) и флаг «Акция» (ProductVariant).

Инвалидация кэша featured brands при изменении Brand.

Сохранение бренда, который был или стал избранным, после commit сбрасывает и
ISR-кэш главной Next (`/home`): она рендерит избранные бренды на сервере и без
сброса показала бы правку только через час (стори 42.6).

LIMITATION: QuerySet.update() и bulk_create/bulk_update обходят Django signals,
поэтому кэш НЕ инвалидируется при массовых операциях. Для таких случаев
необходимо вручную вызывать cache.delete(FEATURED_BRANDS_CACHE_KEY).
"""

from typing import Any

from django.core.cache import cache
from django.db import connection, transaction
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.dispatch import receiver

from apps.common.services.nextjs_revalidate import HOME_PAGE_PATH, revalidate_nextjs_path_in_background

from .constants import FEATURED_BRANDS_CACHE_KEY
from .models import Brand, ProductVariant
from .services import promo

# Поля Brand, влияющие на featured endpoint payload.
_FEATURED_RELEVANT_FIELDS = frozenset({"is_featured", "is_active", "name", "slug", "image", "website"})


def _on_featured_change(*, reset_api_cache: bool, was_featured: bool, is_featured: bool) -> None:
    """После commit сбрасывает кэш featured endpoint и, для избранного бренда, ISR главной.

    Неизбранный бренд на главной не виден, а импорт 1С правит name/is_active у
    многих брендов: без условия каждый прогон слал бы запрос в Next на каждый.
    """
    refresh_home = was_featured or is_featured
    if not (reset_api_cache or refresh_home):
        return

    def _after_commit() -> None:
        # Сначала кэш API: пересборка главной читает featured endpoint.
        if reset_api_cache:
            cache.delete(FEATURED_BRANDS_CACHE_KEY)
        if refresh_home:
            revalidate_nextjs_path_in_background(HOME_PAGE_PATH)

    transaction.on_commit(_after_commit)


@receiver(pre_save, sender=Brand)
def track_brand_previous_state(sender, instance, **kwargs):
    """Сохраняет предыдущее состояние полей Brand перед save для сравнения в post_save."""
    if instance.pk:
        try:
            old = Brand.objects.filter(pk=instance.pk).values(*_FEATURED_RELEVANT_FIELDS).first()
            instance._pre_save_state = old
        except Exception:
            instance._pre_save_state = None
    else:
        # Новый объект — всегда инвалидируем если is_featured=True
        instance._pre_save_state = None


@receiver(post_save, sender=Brand)
def invalidate_featured_brands_cache_on_save(sender, instance, created, **kwargs):
    """Очищает кэш featured brands только если изменились релевантные поля.

    Оптимизация: если обновлено только поле вроде description, инвалидация
    не происходит, предотвращая cache thrashing.

    Использует transaction.on_commit чтобы кэш очищался только после
    успешного коммита транзакции, предотвращая race condition.
    """
    if created:
        _on_featured_change(
            reset_api_cache=instance.is_featured and instance.is_active,
            was_featured=False,
            is_featured=instance.is_featured,
        )
        return

    old = getattr(instance, "_pre_save_state", None)
    if old is None:
        # Не удалось загрузить предыдущее состояние — безопасная инвалидация
        _on_featured_change(reset_api_cache=True, was_featured=True, is_featured=instance.is_featured)
        return

    # Проверяем, изменились ли релевантные поля
    changed = False
    for field in _FEATURED_RELEVANT_FIELDS:
        old_value = old.get(field)
        new_value = getattr(instance, field)
        # ImageField хранится как строка пути
        if hasattr(new_value, "name"):
            new_value = new_value.name
        if str(old_value) != str(new_value):
            changed = True
            break

    _on_featured_change(
        reset_api_cache=changed,
        was_featured=bool(old.get("is_featured")),
        is_featured=instance.is_featured,
    )


@receiver(post_delete, sender=Brand)
def invalidate_featured_brands_cache_on_delete(sender, instance, **kwargs):
    """Очищает кэш featured brands при удалении Brand.

    Инвалидирует только если удалённый бренд мог быть в featured выдаче.
    """
    _on_featured_change(
        reset_api_cache=instance.is_featured and instance.is_active,
        was_featured=instance.is_featured,
        is_featured=instance.is_featured,
    )


def _saves_field(update_fields: Any, *names: str) -> bool:
    """Записывает ли этот `save()` поле (при `update_fields=None` пишутся все)."""
    return update_fields is None or any(name in update_fields for name in names)


def _has_promo_price(promo_price: Any) -> bool:
    return promo_price is not None and promo_price > 0


@receiver(pre_save, sender=ProductVariant)
def remember_stored_variant_state(sender, instance, update_fields=None, raw=False, **kwargs):
    """
    Перед записью блокирует товар и строку варианта и читает, чем она была: активность, товар, цена.

    Сверять изменение со снимком экземпляра нельзя: он мог быть загружен давно (форма админки,
    долгая задача), и за это время другой запрос отключил вариант или перенёс его в другой
    товар. Читать строку без блокировки тоже нельзя: между чтением и записью её успевает
    изменить другой запрос — отключить, перенести или записать акционную цену, — и пересчёт
    флагов пойдёт по состоянию, которого уже нет. Поэтому товары (прежний и новый) и строка
    блокируются в общем порядке (`promo.lock_variant`) до записи и держатся до конца
    транзакции: её открывает `ProductVariant.save()`, он же откатит запись, если пересчёт упадёт.

    Блокировка нужна, только если `save()` пишет активность или товар: импорт цен
    (`update_fields=["promo_price"]`) лишних запросов не получает. Вызов `save_base()` напрямую,
    мимо `save()`, идёт без транзакции — удержать блокировки там нечем, флаг не пересчитывается.
    """
    instance._promo_stored_state = None
    if raw or instance._state.adding or not instance.pk:
        return
    saves_product = _saves_field(update_fields, "product", "product_id")
    if not (saves_product or _saves_field(update_fields, "is_active")):
        return
    if not connection.in_atomic_block:
        return
    instance._promo_stored_state = promo.lock_variant(
        instance.pk, extra_product_ids=[instance.product_id] if saves_product else []
    )


@receiver(post_save, sender=ProductVariant)
def sync_promo_flag_on_variant_change(sender, instance, created, update_fields=None, **kwargs):
    """
    Включение, отключение и перенос варианта с акционной ценой пересчитывают флаг «Акция» товара.

    `sync_promo_flags` учитывает только активные варианты, а правка активности или товара
    в админке или импортом сама пересчёта не запускает. Вариант без акционной цены флаг не
    меняет — импорт переключает активность тысяч таких вариантов, пересчёта по ним нет.
    Новые варианты и цены ведёт импорт цен (`sync_promo_flags` в конце шага).

    Сравнение идёт с состоянием строки до записи (`remember_stored_variant_state`), а не с
    экземпляром. Оба товара — прежний и новый — пересчитываются одним вызовом: они уже
    заблокированы в порядке `pk`, и встречные переносы (A→B и B→A) не ждут друг друга по кругу.

    Акционная цена, которую этот же `save()` записывает вместе с активностью или товаром
    (`update_fields=["is_active", "promo_price"]`), считается по новому значению: вариант без цены
    в строке мог получить её этим сохранением, и тогда флаг тоже нужно пересчитать.
    """
    stored = instance.__dict__.pop("_promo_stored_state", None)
    if created or stored is None:
        return

    had_promo = _has_promo_price(stored.promo_price)
    has_promo = _has_promo_price(instance.promo_price) if _saves_field(update_fields, "promo_price") else had_promo
    if not (had_promo or has_promo):
        return

    is_active = instance.is_active if _saves_field(update_fields, "is_active") else stored.is_active
    product_id = instance.product_id if _saves_field(update_fields, "product", "product_id") else stored.product_id
    if is_active == stored.is_active and product_id == stored.product_id and has_promo == had_promo:
        return
    promo.sync_promo_flags(product_ids={product_id, stored.product_id})


@receiver(pre_delete, sender=ProductVariant)
def remember_deleted_variant_state(sender, instance, **kwargs):
    """
    Перед удалением блокирует товар и строку варианта и читает из БД его товар и акционную цену.

    Экземпляр мог устареть (товар сменил другой запрос) или быть загружен без `product_id`
    (`only`/`defer`). Флаг товара поводом для пересчёта тоже быть не может: параллельный
    пересчёт мог ещё не выставить его для удаляемого варианта. Блокировки берутся в том же
    порядке, что у сохранения варианта и сброса акции (`promo.lock_variant`): иначе удаление,
    державшее строку и ждавшее товар, уходило со сбросом акции во взаимоблокировку. Они же не
    дают импорту цен записать акционную цену между чтением и удалением.
    """
    instance._promo_deleted_state = promo.lock_variant(instance.pk) if connection.in_atomic_block else None


@receiver(post_delete, sender=ProductVariant)
def sync_promo_flag_on_variant_delete(sender, instance, **kwargs):
    """
    Удаление варианта с акционной ценой пересчитывает флаг «Акция» его товара.

    Пересчёт идёт под блокировкой строки товара: проверять, стоит ли флаг сейчас, до
    блокировки нельзя — параллельный пересчёт мог выставить его по варианту, которого после
    коммита уже нет.
    """
    stored = instance.__dict__.pop("_promo_deleted_state", None)
    if stored is None:
        return
    if _has_promo_price(stored.promo_price):
        promo.sync_promo_flags(product_id=stored.product_id)
