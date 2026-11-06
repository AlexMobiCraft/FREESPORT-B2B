"""Источник согласия ограничен перечислением на уровне БД (стори 41.9, ревью).

`CheckConstraint` из миграции 0019 отсекал только пустую строку, а Django
`choices` базы не касаются: прямой `objects.create(source="registartion")`
записал бы опечатку в юридически значимый журнал молча. Ограничение заменяется
проверкой принадлежности перечислению — она строго сильнее прежней (пустая
строка в список не входит), поэтому отдельное `..._source_required` не нужно.

Данные не переписываются: на момент миграции в `source` могут быть только
значения, проставленные кодом, и одноразовое `unknown` из 0019 — все они
входят в список. Если строка вне перечисления всё же найдётся, `AddConstraint`
упадёт при накате, и это правильный исход: чинить нужно данные, а не молча
принимать мусор в доказательстве согласия.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0019_userconsent_source_and_text_version"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="userconsent",
            name="userconsent_source_required",
        ),
        migrations.AddConstraint(
            model_name="userconsent",
            constraint=models.CheckConstraint(
                condition=models.Q(("source__in", ["newsletter", "registration", "1c_link", "unknown"])),
                name="userconsent_source_valid",
            ),
        ),
    ]
