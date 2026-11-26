# Акционная цена из 1С: поле варианта, вид цен «АКЦИЯ …» и единственная текущая акция

import uuid
from decimal import Decimal

import django.core.validators
from django.db import migrations, models
from django.db.models import Exists, OuterRef

PROMO_FIELD = "promo_price"


def _is_promo_name(onec_name):
    # То же правило, что apps.products.services.promo.is_promo_name. Не SQL ILIKE:
    # dev-БД создана с --lc-ctype=C, и там Postgres кириллицу по регистру не сворачивает.
    return (onec_name or "").strip().lower().startswith("акция")


def _uuid1_time(onec_id):
    try:
        parsed = uuid.UUID(str(onec_id or "").strip())
    except ValueError:
        return None
    return parsed.time if parsed.version == 1 else None


def map_promo_price_types(apps, schema_editor):
    """
    Сопоставляет полю `promo_price` акционные виды цен, уже лежащие в справочнике.

    Нужен, если белый список выгрузки сохранят и выгрузят до деплоя: тогда тип
    ляжет с `product_field=""`. Активной остаётся самая новая по GUID акция из
    активных, остальные гасятся — иначе constraint ниже не встанет.

    Заодно снимает прежние ручные отметки «Акция»: теперь `Product.is_promo` выводится из
    акционных цен, ручного управления нет, а `promo_price` только что появилась и пуста у
    всех вариантов. Отметка без подкрепляющей цены осталась бы до первого импорта цен.
    Это делается и в каталоге без акционных видов цен. Обратно отметки не вернуть.
    """
    Product = apps.get_model("products", "Product")
    ProductVariant = apps.get_model("products", "ProductVariant")
    PriceType = apps.get_model("products", "PriceType")

    backed = Exists(ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True, promo_price__gt=0))
    Product.objects.filter(is_promo=True).exclude(backed).update(is_promo=False)

    promo_types = [pt for pt in PriceType.objects.all() if _is_promo_name(pt.onec_name)]
    if not promo_types:
        return

    active = [pt for pt in promo_types if pt.is_active]
    # GUID не v1 сравнить нельзя — такой тип считается новее (как promo.is_newer)
    newest = max(active, key=lambda pt: (_uuid1_time(pt.onec_id) is None, _uuid1_time(pt.onec_id) or 0), default=None)

    for pt in promo_types:
        pt.product_field = PROMO_FIELD
        pt.is_active = newest is not None and pt.pk == newest.pk
        pt.save(update_fields=["product_field", "is_active"])


def unmap_promo_price_types(apps, schema_editor):
    """Возвращает акционным типам пустое поле: без promo_price цены этого вида пропускаются."""
    PriceType = apps.get_model("products", "PriceType")
    PriceType.objects.filter(product_field=PROMO_FIELD).update(product_field="")


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0057_catalog_category_order"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="promo_price",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Цена текущей акции из 1С (вид цен «АКЦИЯ …»). Действует для всех ролей. "
                    "Ставит и снимает только импорт 1С."
                ),
                max_digits=10,
                null=True,
                validators=[django.core.validators.MinValueValidator(Decimal("0"))],
                verbose_name="Акционная цена",
            ),
        ),
        migrations.AlterField(
            model_name="pricetype",
            name="product_field",
            field=models.CharField(
                choices=[
                    ("retail_price", "Розничная цена"),
                    ("opt1_price", "Оптовая цена уровень 1"),
                    ("opt2_price", "Оптовая цена уровень 2"),
                    ("opt3_price", "Оптовая цена уровень 3"),
                    ("opt4_price", "Оптовая цена уровень 4"),
                    ("trainer_price", "Цена для тренера"),
                    ("federation_price", "Цена для представителя федерации"),
                    ("rrp", "Рекомендованная розничная цена"),
                    ("msrp", "Максимальная рекомендованная цена"),
                    ("promo_price", "Акционная цена"),
                ],
                help_text="Поле Product, в которое мапится эта цена",
                max_length=50,
                verbose_name="Поле в модели Product",
            ),
        ),
        migrations.RunPython(map_promo_price_types, reverse_code=unmap_promo_price_types),
        migrations.AddConstraint(
            model_name="pricetype",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_active", True), ("product_field", "promo_price")),
                fields=("product_field",),
                name="price_types_single_active_promo",
            ),
        ),
    ]
