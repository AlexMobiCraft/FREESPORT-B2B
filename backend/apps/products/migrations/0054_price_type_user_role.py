# Справочник видов цен: роль портала для оптовых видов цен и «Тренерской»

from django.conf import settings
from django.db import migrations

# Роли, у которых на портале есть собственный вид цен.
# Исключены намеренно:
#   retail, admin      — оба отображаются на «РРЦ»; user_role у РРЦ обязан
#                        остаться пустым, иначе контрагенты-маркетплейсы на
#                        этом виде цен уедут в retail (решение 1 задания);
#   federation_rep     — вид цен «Партнер» на портал не выгружается, записи
#                        PriceType не имеет; роль остаётся ручной.
ROLES_WITH_PRICE_TYPE = (
    "wholesale_level1",
    "wholesale_level2",
    "wholesale_level3",
    "wholesale_level4",
    "trainer",
)

# GUID «Опт 4»: роль этой записи выставила миграция 0053 вместе с самой
# записью, поэтому reverse здесь её не гасит.
OPT4_ONEC_ID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"


def _targets():
    """[(guid, onec_name, role)] по настройкам ONEC_EXCHANGE."""
    cfg = getattr(settings, "ONEC_EXCHANGE", {})
    by_role = cfg.get("PRICE_TYPE_BY_ROLE", {})
    id_by_name = cfg.get("PRICE_TYPE_ID_BY_NAME", {})

    targets = []
    for role in ROLES_WITH_PRICE_TYPE:
        onec_name = by_role.get(role)
        if not onec_name:
            continue
        guid = str(id_by_name.get(onec_name, "")).strip().lower()
        targets.append((guid, onec_name, role))
    return targets


def set_user_roles(apps, schema_editor):
    """
    Проставляет user_role оптовым видам цен и «Тренерской».

    Обновляются только записи с ПУСТЫМ user_role: поле редактируется
    менеджером из админки, и слепой update() затёр бы ручную настройку.
    Отсутствующие записи НЕ создаются — справочник наполняет импорт
    priceLists из 1С.
    """
    PriceType = apps.get_model("products", "PriceType")

    for guid, onec_name, role in _targets():
        # Основной ключ поиска — GUID: наименование вида цен в 1С могут
        # переименовать, и запись в БД разойдётся с настройками.
        qs = PriceType.objects.filter(onec_id__iexact=guid) if guid else PriceType.objects.none()
        if not qs.exists():
            qs = PriceType.objects.filter(onec_name=onec_name)
        qs.filter(user_role="").update(user_role=role)


def clear_user_roles(apps, schema_editor):
    """
    Гасит роли, проставленные этой миграцией.

    ОГРАНИЧЕНИЕ (осознанное, решение Alex по review-находке стори 40.2):
    происхождение значения нигде не хранится — поля-маркера у PriceType нет,
    а заводить его означало бы схемную миграцию, выходящую за объём стори.
    Поэтому reverse гасит и роль, выставленную менеджером вручную, если она
    СОВПАЛА с ожидаемой. Роль, отличную от ожидаемой, reverse не трогает.
    Цена ошибки мала: reverse запускается только при откате на 0053, а
    повторное применение 0054 вернёт ровно то же значение.
    """
    PriceType = apps.get_model("products", "PriceType")

    for guid, onec_name, role in _targets():
        if guid == OPT4_ONEC_ID:
            continue
        qs = PriceType.objects.filter(onec_id__iexact=guid) if guid else PriceType.objects.none()
        if not qs.exists():
            qs = PriceType.objects.filter(onec_name=onec_name)
        qs.filter(user_role=role).update(user_role="")


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0053_seed_price_type_opt4"),
    ]

    operations = [
        migrations.RunPython(set_user_roles, reverse_code=clear_user_roles),
    ]
