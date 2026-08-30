"""Журнал бонусов переживает удаление тренера и заказа.

`user` и `order` больше не каскадят: ссылки обнуляются, а читаемость записи
обеспечивают снимки email/имени тренера и номера заказа. Ключ идемпотентности
начисления переезжает с FK на снимок номера — в PostgreSQL NULL-ы различны,
поэтому констрейнт по обнулённому FK перестал бы защищать от повторного
начисления за то же экономическое событие.

Дополнительно `accrual_status` ограничивается нетерминальными статусами:
выбор `cancelled` настроил бы начисление бонусов за отменённые заказы.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def fill_snapshots(apps, schema_editor):
    """Заполняет снимки для уже существующих операций журнала."""
    BonusTransaction = apps.get_model("bonuses", "BonusTransaction")

    for row in BonusTransaction.objects.select_related("user", "order").iterator():
        updated_fields = []

        if row.user_id and not row.user_email_snapshot and not row.user_name_snapshot:
            user = row.user
            row.user_email_snapshot = (user.email or "")[:254]
            row.user_name_snapshot = f"{user.first_name} {user.last_name}".strip()[:255]
            updated_fields += ["user_email_snapshot", "user_name_snapshot"]

        if row.order_id and not row.order_number_snapshot:
            row.order_number_snapshot = (row.order.order_number or "")[:50]
            updated_fields.append("order_number_snapshot")

        if updated_fields:
            row.save(update_fields=updated_fields)


def normalize_accrual_status(apps, schema_editor):
    """Сбрасывает терминальный `accrual_status` на `delivered`.

    Нужно до установки CheckConstraint: если настройки уже сохранены
    с `cancelled`/`refunded`, миграция иначе не применится.
    """
    BonusProgramSettings = apps.get_model("bonuses", "BonusProgramSettings")
    BonusProgramSettings.objects.filter(accrual_status__in=["cancelled", "refunded"]).update(
        accrual_status="delivered"
    )


def noop(apps, schema_editor):
    """Обратная миграция данных не требуется — снимки безвредны."""


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("bonuses", "0002_bonusprogramsettings_program_start_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="bonustransaction",
            name="user_email_snapshot",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Снимок на момент операции: сохраняет читаемость журнала "
                    "после удаления учётной записи"
                ),
                max_length=254,
                verbose_name="Email тренера (снимок)",
            ),
        ),
        migrations.AddField(
            model_name="bonustransaction",
            name="user_name_snapshot",
            field=models.CharField(
                blank=True,
                help_text="Снимок на момент операции",
                max_length=255,
                verbose_name="Имя тренера (снимок)",
            ),
        ),
        migrations.AddField(
            model_name="bonustransaction",
            name="order_number_snapshot",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="Ключ идемпотентности начисления: переживает удаление заказа",
                max_length=50,
                verbose_name="Номер заказа (снимок)",
            ),
        ),
        migrations.RunPython(fill_snapshots, noop),
        migrations.AlterField(
            model_name="bonustransaction",
            name="user",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="bonus_transactions",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Тренер",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="bonustransaction",
            name="uniq_bonus_accrual_per_order",
        ),
        migrations.AddConstraint(
            model_name="bonustransaction",
            constraint=models.UniqueConstraint(
                condition=models.Q(("transaction_type", "accrual"), models.Q(("order_number_snapshot", ""), _negated=True)),
                fields=("order_number_snapshot",),
                name="uniq_bonus_accrual_per_order_number",
            ),
        ),
        migrations.RunPython(normalize_accrual_status, noop),
        migrations.AlterField(
            model_name="bonusprogramsettings",
            name="accrual_status",
            field=models.CharField(
                choices=[
                    ("pending", "Ожидает обработки"),
                    ("confirmed", "Подтвержден"),
                    ("processing", "В обработке"),
                    ("shipped", "Отправлен"),
                    ("delivered", "Доставлен"),
                ],
                default="delivered",
                help_text="Начисление происходит при переходе мастер-заказа в этот статус",
                max_length=50,
                verbose_name="Статус заказа для начисления",
            ),
        ),
        migrations.AddConstraint(
            model_name="bonusprogramsettings",
            constraint=models.CheckConstraint(
                condition=models.Q(("accrual_status__in", ("cancelled", "refunded")), _negated=True),
                name="check_bonus_accrual_status_not_terminal",
            ),
        ),
    ]
