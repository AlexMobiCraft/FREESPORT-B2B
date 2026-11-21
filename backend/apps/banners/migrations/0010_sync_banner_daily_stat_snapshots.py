"""
Выравнивает снимок баннера в накопленных строках дневной статистики.

До этой миграции строка хранила название и реквизиты рекламодателя на момент
события, и после переименования у одного баннера в статистике были разные
названия. Теперь сохранение баннера переписывает снимок во всех его строках
(`apps.banners.services.sync_daily_stat_snapshots`); миграция делает то же
для строк, накопленных раньше.

Логика — копия сервиса на исторических моделях: миграции не импортируют
изменяемый код приложения. Строки удалённых баннеров (`banner_id IS NULL`) не
трогаются. Обратная миграция ничего не делает: прежние снимки не сохранены.
"""

from django.db import migrations


def sync_banner_daily_stat_snapshots(apps, schema_editor):
    alias = schema_editor.connection.alias
    Banner = apps.get_model("banners", "Banner")
    BannerDailyStat = apps.get_model("banners", "BannerDailyStat")

    stats = BannerDailyStat.objects.using(alias)
    banner_ids = stats.filter(banner_id__isnull=False).values("banner_id")
    for banner in Banner.objects.using(alias).filter(pk__in=banner_ids).order_by("pk"):
        rows = stats.filter(banner_id=banner.pk)
        rows.exclude(banner_title=banner.title).update(banner_title=banner.title)
        if banner.is_advertisement and banner.advertiser_name:
            (
                rows.exclude(advertiser_name="")
                .exclude(advertiser_name=banner.advertiser_name, advertiser_inn=banner.advertiser_inn)
                .update(advertiser_name=banner.advertiser_name, advertiser_inn=banner.advertiser_inn)
            )


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0009_banner_daily_stat_permissions"),
    ]

    operations = [
        migrations.RunPython(sync_banner_daily_stat_snapshots, migrations.RunPython.noop),
    ]
