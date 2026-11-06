"""Аудитируемость журнала согласий: источник и версия текста (стори 41.9).

Миграция написана вручную. У полей `source` и `consent_text_version` в модели
намеренно нет `default` — иначе забытое значение тихо записалось бы как
«неизвестно». Из-за этого `makemigrations` ушёл бы в интерактивный вопрос про
одноразовое значение; здесь оно задано явно: `default="unknown"` вместе с
`preserve_default=False` заполняет существующие строки и не попадает в модель.

Строки, созданные до миграции, сохраняются и помечаются как `unknown`: на
2026-08-30 в `common_userconsent` на проде было 0 строк, но удалять журнал
согласий нельзя даже теоретически — это уничтожение доказательства.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0018_seed_manager_routing_rules"),
    ]

    operations = [
        migrations.AddField(
            model_name="userconsent",
            name="source",
            field=models.CharField(
                choices=[
                    ("newsletter", "Подписка на рассылку"),
                    ("registration", "Регистрация"),
                    ("1c_link", "Регистрация с привязкой к записи 1С"),
                    ("unknown", "Неизвестен (запись до внедрения аудита)"),
                ],
                db_index=True,
                default="unknown",
                help_text="Где человек дал согласие: подписка, регистрация, привязка к 1С",
                max_length=20,
                verbose_name="Источник согласия",
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="userconsent",
            name="consent_text_version",
            field=models.CharField(
                db_index=True,
                default="unknown",
                help_text=(
                    "Версия формулировки чекбокса из реестра apps/common/consent_texts.json "
                    "(вид «метка-хеш»). Отдельна от policy_version: та описывает политику ПДн, "
                    "эта — формулировку чекбокса, действовавшую при записи и совпавшую с версией из запроса."
                ),
                max_length=64,
                verbose_name="Версия текста согласия",
            ),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name="userconsent",
            constraint=models.CheckConstraint(
                condition=~models.Q(("source", "")),
                name="userconsent_source_required",
            ),
        ),
        migrations.AddConstraint(
            model_name="userconsent",
            constraint=models.CheckConstraint(
                condition=~models.Q(("consent_text_version", "")),
                name="userconsent_text_version_required",
            ),
        ),
    ]
