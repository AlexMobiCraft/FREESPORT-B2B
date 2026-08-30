"""Story 36.1: Django не должен раздавать legacy-каталоги обмена 1С под MEDIA_URL.

Каталоги `1c_import`/`1c_temp` вынесены в приватный `ONEC_PRIVATE_DIR`, но
media-том переживает деплой: файлы незавершённых обменов, записанные до переезда,
физически остаются под `MEDIA_ROOT`. В DEBUG `django.conf.urls.static()` отдаёт
весь `MEDIA_ROOT` целиком — то есть development-сервер воспроизводил ровно ту
дыру, которую nginx уже закрыл 404-правилами. Тест фиксирует guard в urlconf
и его приоритет над `static()` (AC-2).
"""

import importlib

import pytest
from django.test import override_settings
from django.urls import clear_url_caches, resolve

import freesport.urls as urls_module

pytestmark = pytest.mark.unit

LEGACY_PATHS = (
    "/media/1c_import/prices/prices_1.xml",
    "/media/1c_temp/abc123session/goods.xml",
)


class TestLegacyOneCMediaUrlGuard:
    """Legacy-пути обмена 1С обязаны резолвиться в 404-guard, а не в раздачу файлов."""

    @pytest.mark.parametrize("path", LEGACY_PATHS)
    def test_guard_registered_in_root_urlconf(self, path: str) -> None:
        match = resolve(path)
        assert (
            match.func is urls_module.legacy_onec_media_gone
        ), f"{path} резолвится в {match.func!r}, а не в 404-guard обмена 1С"

    @pytest.mark.parametrize("path", LEGACY_PATHS)
    def test_guard_wins_over_debug_static_serving(self, path: str) -> None:
        """При DEBUG=True static() добавляет раздачу MEDIA_ROOT — guard должен быть раньше."""
        try:
            with override_settings(DEBUG=True):
                reloaded = importlib.reload(urls_module)
                clear_url_caches()

                match = resolve(path, urlconf=reloaded)
                assert match.func is reloaded.legacy_onec_media_gone, (
                    f"В DEBUG-режиме {path} обслуживается {match.func!r} — "
                    "legacy-файлы обмена 1С снова раздаются по media-URL"
                )
        finally:
            importlib.reload(urls_module)
            clear_url_caches()

    def test_ordinary_media_files_still_served_in_debug(self) -> None:
        """Guard закрывает только каталоги обмена, обычные media остаются доступны."""
        try:
            with override_settings(DEBUG=True):
                reloaded = importlib.reload(urls_module)
                clear_url_caches()

                match = resolve("/media/products/photo.jpg", urlconf=reloaded)
                assert match.func is not reloaded.legacy_onec_media_gone
        finally:
            importlib.reload(urls_module)
            clear_url_caches()

    @pytest.mark.django_db
    def test_guard_returns_404_over_http(self, client) -> None:
        """Сквозная проверка кода ответа, а не только резолвинга.

        django_db нужен из-за ATOMIC_REQUESTS=True в тестовых настройках:
        обработчик открывает транзакцию до вызова view.
        """
        response = client.get("/media/1c_import/prices/prices_1.xml")
        assert response.status_code == 404
