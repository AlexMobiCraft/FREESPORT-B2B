"""
Визуальный редактор поля `content` в админке: загрузка картинок, виджет в формах
обоих сайтов и совместимость вывода редактора с санитайзером.

Матрица I/O — спека `spec-rich-content-editor.md`. Картинки собираются Pillow
в тесте: это не выгрузки 1С, реальные данные для них не нужны.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import re
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from PIL import ExifTags, Image

from apps.common import rich_editor
from apps.common.models import News
from apps.common.utils.html_sanitizer import sanitize_rich_html
from apps.pages.models import PAGE_HTML_ATTRIBUTES, PAGE_HTML_TAGS
from apps.users.models import User
from apps.users.staff_roles import MARKETING_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"
MARKETING_NEWS_UPLOAD = "/marketing/common/news/upload-image/"
MARKETING_BLOG_UPLOAD = "/marketing/common/blogpost/upload-image/"
ADMIN_NEWS_UPLOAD = "/admin/common/news/upload-image/"
ADMIN_PAGE_UPLOAD = "/admin/pages/page/upload-image/"
SAVED_URL = re.compile(r"^/media/content/images/\d{4}/\d{2}/[0-9a-f]{32}\.(png|jpg|webp|gif)$")

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")

# Эталон редактора лежит у тестов фронтенда; в тест-контейнер он смонтирован по тому
# же пути относительно backend/, что и в checkout репозитория (docker-compose.test.yml).
REFERENCE_HTML = (
    Path(__file__).resolve().parents[2].parent
    / "frontend"
    / "admin-editor"
    / "__tests__"
    / "fixtures"
    / "reference.html"
)


@pytest.fixture(autouse=True)
def role_groups():
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


@pytest.fixture(autouse=True)
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    return settings.MEDIA_ROOT


def saved_files(media_root: Path) -> list[Path]:
    return sorted(p for p in media_root.rglob("*") if p.is_file()) if media_root.exists() else []


def file_for(url: str, media_root: Path) -> Path:
    return media_root / url.removeprefix("/media/")


def make_marketer() -> User:
    user = User.objects.create_user(email=f"mkt_{get_unique_suffix()}@example.com", password=PASSWORD, is_staff=True)
    user.groups.add(Group.objects.get(name=MARKETING_GROUP))
    return user


@pytest.fixture
def marketer_client(client):
    client.force_login(make_marketer())
    return client


@pytest.fixture
def superuser_client(client):
    client.force_login(User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD))
    return client


# --------------------------------------------------------------------------
# Картинки
# --------------------------------------------------------------------------


def encode(image: Image.Image, image_format: str, **params) -> bytes:
    buffer = io.BytesIO()
    image.save(buffer, image_format, **params)
    return buffer.getvalue()


def gps_exif(orientation: int | None = None) -> Image.Exif:
    exif = Image.Exif()
    if orientation:
        exif[ExifTags.Base.Orientation] = orientation
    gps = exif.get_ifd(ExifTags.IFD.GPSInfo)
    gps[ExifTags.GPS.GPSLatitudeRef] = "N"
    gps[ExifTags.GPS.GPSLatitude] = (55.0, 45.0, 0.0)
    return exif


def animation_frames(size: tuple[int, int], count: int = 3) -> list[Image.Image]:
    return [Image.new("RGB", size, (40 * index, 80, 160)) for index in range(count)]


def animated(image_format: str, size: tuple[int, int] = (64, 48), **params) -> bytes:
    first, *rest = animation_frames(size)
    return encode(first, image_format, save_all=True, append_images=rest, duration=100, loop=0, **params)


def minimal_psd(width: int = 4, height: int = 4) -> bytes:
    """Несжатый RGB PSD: Pillow его открывает, но формат вне белого списка."""
    header = b"8BPS" + (1).to_bytes(2, "big") + b"\0" * 6 + (3).to_bytes(2, "big")
    header += height.to_bytes(4, "big") + width.to_bytes(4, "big") + (8).to_bytes(2, "big") + (3).to_bytes(2, "big")
    return header + b"\0\0\0\0" * 3 + b"\0\0" + b"\x80" * (3 * width * height)


def upload(client, url: str, data: bytes, name: str, content_type: str = "image/png"):
    return client.post(url, {"image": SimpleUploadedFile(name, data, content_type=content_type)})


# --------------------------------------------------------------------------
# Матрица I/O
# --------------------------------------------------------------------------


class TestUploadAccepted:
    def test_large_png_is_resized_to_1920(self, marketer_client, media_root):
        data = encode(Image.effect_noise((3000, 2000), 64), "PNG")
        assert 3 * 1024 * 1024 < len(data) <= rich_editor.MAX_IMAGE_BYTES

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "photo.png")

        assert response.status_code == 200
        url = response.json()["url"]
        assert SAVED_URL.match(url) and url.endswith(".png"), url
        with Image.open(file_for(url, media_root)) as saved:
            assert saved.size == (1920, 1280)

    def test_jpeg_is_rotated_by_exif_and_loses_exif_and_gps(self, marketer_client, media_root):
        data = encode(Image.new("RGB", (200, 100), (200, 30, 30)), "JPEG", exif=gps_exif(orientation=6))
        with Image.open(io.BytesIO(data)) as source:
            assert source.getexif().get_ifd(ExifTags.IFD.GPSInfo)

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "IMG_0001.JPG", "image/jpeg")

        assert response.status_code == 200
        url = response.json()["url"]
        assert url.endswith(".jpg")
        with Image.open(file_for(url, media_root)) as saved:
            assert saved.size == (100, 200)
            assert not saved.getexif()
            assert "exif" not in saved.info

    def test_phone_mpo_is_a_static_jpeg(self, marketer_client, media_root):
        """Снимок телефона Pillow открывает как MPO из двух кадров — это не анимация."""
        first, second = Image.new("RGB", (300, 200), "red"), Image.new("RGB", (60, 40), "blue")
        data = encode(first, "MPO", save_all=True, append_images=[second], exif=gps_exif())
        with Image.open(io.BytesIO(data)) as source:
            assert source.format == "MPO" and source.is_animated

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "IMG_0002.JPG", "image/jpeg")

        assert response.status_code == 200
        url = response.json()["url"]
        assert url.endswith(".jpg")
        with Image.open(file_for(url, media_root)) as saved:
            assert saved.format == "JPEG" and saved.size == (300, 200)
            assert not saved.getexif()

    def test_palette_png_keeps_transparency(self, marketer_client, media_root):
        image = Image.new("P", (20, 20), 1)
        image.putpalette([0, 0, 0, 255, 0, 0] + [0] * (254 * 3))
        data = encode(image, "PNG", transparency=0)

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "logo.png")

        assert response.status_code == 200
        with Image.open(file_for(response.json()["url"], media_root)) as saved:
            assert saved.mode == "P"
            assert saved.info.get("transparency") == 0

    def test_rgb_jpeg_keeps_icc_profile(self, marketer_client, media_root):
        from PIL import ImageCms

        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        data = encode(Image.new("RGB", (30, 20), "green"), "JPEG", icc_profile=profile)

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "p3.jpg", "image/jpeg")

        assert response.status_code == 200
        with Image.open(file_for(response.json()["url"], media_root)) as saved:
            assert saved.mode == "RGB"
            assert saved.info.get("icc_profile") == profile

    def test_cmyk_jpeg_becomes_rgb_without_profile(self, marketer_client, media_root):
        from PIL import ImageCms

        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        data = encode(Image.new("CMYK", (30, 20), (0, 50, 100, 0)), "JPEG", icc_profile=profile)
        with Image.open(io.BytesIO(data)) as source:
            assert source.mode == "CMYK" and source.info.get("icc_profile")

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "print.jpg", "image/jpeg")

        assert response.status_code == 200
        with Image.open(file_for(response.json()["url"], media_root)) as saved:
            assert saved.mode == "RGB"
            assert not saved.info.get("icc_profile")

    def test_static_webp_and_gif_are_reencoded_without_exif(self, marketer_client, media_root):
        webp = encode(Image.new("RGB", (40, 30)), "WEBP", exif=gps_exif())
        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, webp, "a.webp", "image/webp")
        assert response.status_code == 200
        with Image.open(file_for(response.json()["url"], media_root)) as saved:
            assert saved.format == "WEBP"
            assert "exif" not in saved.info

        gif = encode(Image.new("P", (40, 30)), "GIF")
        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, gif, "a.gif", "image/gif")
        assert response.status_code == 200
        assert response.json()["url"].endswith(".gif")

    def test_animated_gif_is_saved_byte_for_byte(self, marketer_client, media_root):
        data = animated("GIF")

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "anim.webp", "image/webp")

        assert response.status_code == 200
        url = response.json()["url"]
        # Расширение — по формату, а не по имени файла.
        assert url.endswith(".gif")
        assert file_for(url, media_root).read_bytes() == data

    @pytest.mark.parametrize("image_format, extension", [("WEBP", ".webp"), ("PNG", ".png")])
    def test_animated_webp_and_apng_are_kept(self, marketer_client, media_root, image_format, extension):
        data = animated(image_format)
        with Image.open(io.BytesIO(data)) as source:
            assert source.is_animated

        response = upload(marketer_client, MARKETING_BLOG_UPLOAD, data, "anim.bin", "image/png")

        assert response.status_code == 200
        url = response.json()["url"]
        assert url.endswith(extension)
        assert file_for(url, media_root).read_bytes() == data

    def test_superuser_uploads_into_page(self, superuser_client, media_root):
        response = upload(superuser_client, ADMIN_PAGE_UPLOAD, encode(Image.new("RGB", (10, 10)), "PNG"), "a.png")

        assert response.status_code == 200
        assert len(saved_files(media_root)) == 1


class TestUploadRejected:
    @pytest.mark.parametrize(
        "data, name",
        [
            (b"just some text, not an image", "evil.png"),
            (b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>', "vector.svg"),
            (minimal_psd(), "layers.psd"),
            (encode(Image.new("RGB", (10, 10)), "BMP"), "old.bmp"),
            (encode(Image.effect_noise((64, 64), 64), "PNG")[:300], "truncated.png"),
        ],
        ids=["text", "svg", "psd", "bmp", "truncated"],
    )
    def test_not_an_allowed_image(self, marketer_client, media_root, data, name):
        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, name)

        assert response.status_code == 400
        assert response.json()["error"]
        assert saved_files(media_root) == []

    def test_psd_fixture_is_a_real_psd(self):
        with Image.open(io.BytesIO(minimal_psd())) as image:
            assert image.format == "PSD"

    def test_animated_webp_with_exif(self, marketer_client, media_root):
        data = animated("WEBP", exif=gps_exif().tobytes())
        with Image.open(io.BytesIO(data)) as source:
            assert source.is_animated and source.info.get("exif")

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "anim.webp", "image/webp")

        assert response.status_code == 400
        assert "метаданные" in response.json()["error"]
        assert saved_files(media_root) == []

    @pytest.mark.parametrize("image_format", ["WEBP", "PNG"])
    def test_animation_with_xmp(self, marketer_client, media_root, image_format):
        xmp = (
            b'<x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
            b'<rdf:Description xmlns:exif="http://ns.adobe.com/exif/1.0/" exif:GPSLatitude="55,45.0N"/>'
            b"</rdf:RDF></x:xmpmeta>"
        )
        if image_format == "PNG":
            from PIL import PngImagePlugin

            info = PngImagePlugin.PngInfo()
            info.add_itxt("XML:com.adobe.xmp", xmp.decode())
            data = animated("PNG", pnginfo=info)
        else:
            data = animated("WEBP", xmp=xmp)
        with Image.open(io.BytesIO(data)) as source:
            assert source.is_animated and source.info.get("xmp")
            assert not source.getexif()

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "anim.bin", "image/webp")

        assert response.status_code == 400
        assert "метаданные" in response.json()["error"]
        assert saved_files(media_root) == []

    def test_animation_longer_than_1920(self, marketer_client, media_root):
        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, animated("GIF", (2400, 1350)), "big.gif", "image/gif")

        assert response.status_code == 400
        assert "1920" in response.json()["error"]
        assert saved_files(media_root) == []

    def test_file_over_10_mb_is_rejected_before_pillow(self, marketer_client, media_root, monkeypatch):
        def fail_open(*args, **kwargs):
            raise AssertionError("Pillow не должен открывать файл больше 10 МБ")

        monkeypatch.setattr(rich_editor.Image, "open", fail_open)
        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, b"\0" * (11 * 1024 * 1024), "huge.png")

        assert response.status_code == 400
        assert "10 МБ" in response.json()["error"]
        assert saved_files(media_root) == []

    @pytest.mark.parametrize(
        "size",
        [(12000, 12000), (8000, 6000)],
        ids=["decompression-bomb-warning", "over-40-mp"],
    )
    def test_too_many_pixels(self, marketer_client, media_root, size):
        data = encode(Image.new("1", size), "PNG")
        assert len(data) < rich_editor.MAX_IMAGE_BYTES

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, data, "bomb.png")

        assert response.status_code == 400
        assert "Мп" in response.json()["error"]
        assert saved_files(media_root) == []

    def test_missing_file(self, marketer_client, media_root):
        response = marketer_client.post(MARKETING_NEWS_UPLOAD, {})

        assert response.status_code == 400
        assert response.json()["error"]


class TestUploadAccess:
    PNG = encode(Image.new("RGB", (10, 10)), "PNG")

    def test_marketer_cannot_upload_into_admin_site(self, marketer_client, media_root):
        response = upload(marketer_client, ADMIN_NEWS_UPLOAD, self.PNG, "a.png")

        assert response.status_code == 302
        assert response["Location"].startswith("/admin/login/")
        assert saved_files(media_root) == []

    def test_staff_without_add_and_change_permission(self, marketer_client, media_root):
        # Права даёт группа: у сотрудника их снимаем в группе, вход в раздел остаётся.
        group = Group.objects.get(name=MARKETING_GROUP)
        group.permissions.remove(
            *Permission.objects.filter(content_type__app_label="common", codename__in=["add_news", "change_news"])
        )

        response = upload(marketer_client, MARKETING_NEWS_UPLOAD, self.PNG, "a.png")

        assert response.status_code == 403
        assert saved_files(media_root) == []
        # Право на статьи осталось — загрузка в статью проходит.
        assert upload(marketer_client, MARKETING_BLOG_UPLOAD, self.PNG, "a.png").status_code == 200

    @pytest.mark.parametrize("codename", ["add_news", "change_news"])
    def test_one_of_add_or_change_is_enough(self, marketer_client, media_root, codename):
        group = Group.objects.get(name=MARKETING_GROUP)
        other = {"add_news", "change_news"} - {codename}
        group.permissions.remove(*Permission.objects.filter(content_type__app_label="common", codename__in=other))

        assert upload(marketer_client, MARKETING_NEWS_UPLOAD, self.PNG, "a.png").status_code == 200

    def test_anonymous_goes_to_login(self, client, media_root):
        response = upload(client, MARKETING_NEWS_UPLOAD, self.PNG, "a.png")

        assert response.status_code == 302
        assert response["Location"].startswith("/marketing/login/")
        assert saved_files(media_root) == []

    def test_get_is_not_allowed(self, marketer_client):
        assert marketer_client.get(MARKETING_NEWS_UPLOAD).status_code == 405

    def test_get_is_not_allowed_in_admin(self, superuser_client):
        assert superuser_client.get(ADMIN_PAGE_UPLOAD).status_code == 405

    def test_csrf_is_required(self, media_root):
        from django.test import Client

        client = Client(enforce_csrf_checks=True)
        client.force_login(make_marketer())

        response = upload(client, MARKETING_NEWS_UPLOAD, self.PNG, "a.png")

        assert response.status_code == 403
        assert saved_files(media_root) == []


# --------------------------------------------------------------------------
# Виджет и URL в формах обоих сайтов
# --------------------------------------------------------------------------


def content_textarea(html: str) -> str:
    match = re.search(r'<textarea[^>]*name="content"[^>]*>', html)
    assert match, "в форме нет textarea content"
    return match.group(0)


class TestWidgetInForms:
    @pytest.mark.parametrize(
        "add_url, upload_url",
        [
            ("/marketing/common/news/add/", MARKETING_NEWS_UPLOAD),
            ("/marketing/common/blogpost/add/", MARKETING_BLOG_UPLOAD),
        ],
    )
    def test_marketing_site(self, marketer_client, add_url, upload_url):
        self._assert_editor(marketer_client.get(add_url), upload_url)

    @pytest.mark.parametrize(
        "add_url, upload_url, column_width",
        [
            ("/admin/common/news/add/", ADMIN_NEWS_UPLOAD, 832),
            ("/admin/common/blogpost/add/", "/admin/common/blogpost/upload-image/", 832),
            # Текст страницы на сайте лежит в `container` внутри `Card`: колонка шире, чем у новостей.
            ("/admin/pages/page/add/", ADMIN_PAGE_UPLOAD, 1168),
        ],
    )
    def test_admin_site(self, superuser_client, add_url, upload_url, column_width):
        self._assert_editor(superuser_client.get(add_url), upload_url, column_width)

    @staticmethod
    def _assert_editor(response, upload_url: str, column_width: int = rich_editor.DEFAULT_COLUMN_WIDTH) -> None:
        assert response.status_code == 200
        html = response.content.decode()
        textarea = content_textarea(html)
        assert "data-rich-editor" in textarea
        assert f'data-upload-url="{upload_url}"' in textarea
        # Редактор делает текст такой же ширины, как колонка на сайте: размер картинки совпадает.
        assert f'data-column-width="{column_width}"' in textarea
        assert "required" in textarea  # снимает сам редактор, без JS поле остаётся обязательным
        js_version = rich_editor.asset_version(rich_editor.EDITOR_JS)
        css_version = rich_editor.asset_version(rich_editor.EDITOR_CSS)
        assert f'src="/static/common/rich_editor/rich-editor.js?v={js_version}"' in html
        assert f'href="/static/common/rich_editor/rich-editor.css?v={css_version}"' in html
        assert rich_editor.RICH_CONTENT_HELP_TEXT in html
        assert "HTML или Markdown" not in html
        # Краткое описание и SEO — обычные поля.
        assert not re.search(
            r'<textarea[^>]*name="(excerpt|seo_description|meta_description)"[^>]*data-rich-editor', html
        )

    def test_unchanged_post_keeps_content_as_plain_textarea(self, marketer_client):
        """Сервер сохраняет то, что пришло в textarea: редактор без правок его не трогает."""
        original = "## **Заголовок**\r\n\r\nТекст & ещё текст."
        news = News.objects.create(title="Новость", slug=f"n-{get_unique_suffix()}", content=original)
        stored = News.objects.get(pk=news.pk).content

        response = marketer_client.post(
            f"/marketing/common/news/{news.pk}/change/",
            {
                "title": news.title,
                "slug": news.slug,
                "excerpt": "",
                "content": stored,
                "author": "",
                "category": "",
                "published_at_0": "",
                "published_at_1": "",
                "_save": "Сохранить",
            },
        )

        assert response.status_code == 302, response.content.decode()[:2000]
        assert News.objects.get(pk=news.pk).content == stored

    def test_erased_content_is_a_required_field_error(self, marketer_client):
        """Стёртый текст редактор отдаёт пустой строкой — обязательность проверяет форма Django."""
        news = News.objects.create(title="Новость", slug=f"n-{get_unique_suffix()}", content="<p>текст</p>")

        response = marketer_client.post(
            f"/marketing/common/news/{news.pk}/change/",
            {
                "title": news.title,
                "slug": news.slug,
                "excerpt": "",
                "content": "",
                "author": "",
                "category": "",
                "published_at_0": "",
                "published_at_1": "",
                "_save": "Сохранить",
            },
        )

        assert response.status_code == 200
        assert "content" in response.context["adminform"].form.errors
        assert News.objects.get(pk=news.pk).content == "<p>текст</p>"


class TestColumnWidth:
    def test_default_is_news_column(self):
        widget = rich_editor.RichEditorWidget(upload_url="/u/")
        assert widget.column_width == rich_editor.DEFAULT_COLUMN_WIDTH == 832
        assert widget.attrs["data-column-width"] == "832"

    def test_custom_width_reaches_the_attribute(self):
        widget = rich_editor.RichEditorWidget(upload_url="/u/", column_width=1168)
        assert widget.attrs["data-column-width"] == "1168"

    def test_marketing_admins_inherit_news_column(self):
        from apps.common.marketing_admin import MarketingBlogPostAdmin, MarketingNewsAdmin

        assert MarketingNewsAdmin.rich_editor_column_width == 832
        assert MarketingBlogPostAdmin.rich_editor_column_width == 832


class TestAssetVersion:
    @staticmethod
    def _version_in_media() -> str:
        rendered = rich_editor.RichEditorWidget(upload_url="/u/").media.render()
        match = re.search(r"rich-editor\.js\?v=([0-9a-f]{12})", rendered)
        assert match, rendered
        return match.group(1)

    @staticmethod
    def _sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:12]

    def test_without_collected_file_hashes_source(self, settings, tmp_path):
        settings.STATIC_ROOT = tmp_path / "staticfiles"
        source = Path(rich_editor.__file__).resolve().parent / "static" / rich_editor.EDITOR_JS

        assert rich_editor.served_asset_path(rich_editor.EDITOR_JS) == source
        assert self._version_in_media() == self._sha(source.read_bytes())

    def test_collected_file_wins_and_new_collectstatic_is_picked_up(self, settings, tmp_path):
        """До collectstatic отдаётся старый собранный файл — `?v=` обязан быть его хешем."""
        settings.STATIC_ROOT = tmp_path / "staticfiles"
        for name in (rich_editor.EDITOR_JS, rich_editor.EDITOR_CSS):
            (settings.STATIC_ROOT / name).parent.mkdir(parents=True, exist_ok=True)
            (settings.STATIC_ROOT / name).write_bytes(b"/* old */")
        collected = settings.STATIC_ROOT / rich_editor.EDITOR_JS

        old = self._version_in_media()
        assert old == self._sha(b"/* old */")

        # collectstatic без перезапуска процесса: другой размер и время изменения.
        collected.write_bytes(b"/* new bundle */")
        new = self._version_in_media()

        assert new == self._sha(b"/* new bundle */")
        assert new != old


# --------------------------------------------------------------------------
# Вывод редактора и санитайзер
# --------------------------------------------------------------------------


class TestEditorOutputPassesSanitizer:
    def test_reference_fixture_is_mounted(self):
        assert (
            REFERENCE_HTML.is_file()
        ), f"нет {REFERENCE_HTML}: в docker-compose.test.yml пропало монтирование фикстур фронтенда"

    def test_reference_html_is_unchanged_by_sanitizer(self):
        html = REFERENCE_HTML.read_text(encoding="utf-8")
        assert "<table>" in html and "<img" in html and "&nbsp;" in html

        assert sanitize_rich_html(html) == html
        assert sanitize_rich_html(html, tags=PAGE_HTML_TAGS, attributes=PAGE_HTML_ATTRIBUTES) == html

    def test_reference_html_survives_model_save(self):
        html = REFERENCE_HTML.read_text(encoding="utf-8")
        news = News.objects.create(title="Эталон", slug=f"ref-{get_unique_suffix()}", content=html)

        assert News.objects.get(pk=news.pk).content == html
