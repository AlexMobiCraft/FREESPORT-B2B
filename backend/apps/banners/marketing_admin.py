"""
Раздел маркетинга `/marketing/` — баннеры (стори 42.6).

Родительский `BannerAdmin` с полным доступом; отличие одно — нет ссылки
«Смотреть на сайте» (единое правило всех моделей раздела).

Модуль импортируется из `BannersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/banners/admin.py`.
"""

from __future__ import annotations

from apps.banners.admin import BannerAdmin
from apps.banners.models import Banner
from freesport.admin_site import marketing_site


class MarketingBannerAdmin(BannerAdmin):
    view_on_site = False


marketing_site.register(Banner, MarketingBannerAdmin)
