"""
Раздел маркетинга `/marketing/` — баннеры (стори 42.6) и их статистика
показов и кликов для отчётности в ОРД (только просмотр и выгрузка CSV).

Родительский `BannerAdmin` с полным доступом; отличие одно — нет ссылки
«Смотреть на сайте» (единое правило всех моделей раздела).

Модуль импортируется из `BannersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/banners/admin.py`.
"""

from __future__ import annotations

from apps.banners.admin import BannerAdmin, BannerDailyStatAdmin
from apps.banners.models import Banner, BannerDailyStat
from freesport.admin_site import marketing_site


class MarketingBannerAdmin(BannerAdmin):
    view_on_site = False


marketing_site.register(Banner, MarketingBannerAdmin)


class MarketingBannerDailyStatAdmin(BannerDailyStatAdmin):
    view_on_site = False


marketing_site.register(BannerDailyStat, MarketingBannerDailyStatAdmin)
