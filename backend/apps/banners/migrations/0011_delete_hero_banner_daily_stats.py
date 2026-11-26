"""
Удаляет накопленную статистику показов и кликов баннеров шапки.

Для ОРД и маркетинга считаются только маркетинговые баннеры слайдера
(`type = marketing`); с этой версии сервер отбрасывает события остальных
баннеров (`apps.banners.services.record_events`). Миграция удаляет строки,
собранные раньше, — только у баннеров, которые сейчас существуют и имеют
`type = hero`, и только нерекламные (пустые ERID и наименование рекламодателя).
Баннер шапки рекламным быть не может (`Banner.clean`), поэтому рекламная строка
hero-баннера собрана, пока он был маркетинговым, — это показы рекламы для ОРД,
они остаются. Строки удалённых баннеров (`banner_id IS NULL`) тоже остаются: тип
по снимку не определить.

Обратная миграция ничего не делает: удалённые строки не восстановить.
"""

from django.db import migrations


def delete_hero_banner_daily_stats(apps, schema_editor):
    alias = schema_editor.connection.alias
    BannerDailyStat = apps.get_model("banners", "BannerDailyStat")
    BannerDailyStat.objects.using(alias).filter(banner__type="hero", erid="", advertiser_name="").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0010_sync_banner_daily_stat_snapshots"),
    ]

    operations = [
        migrations.RunPython(delete_hero_banner_daily_stats, migrations.RunPython.noop),
    ]
