"""
Визуальный редактор поля `content` новостей, статей и страниц в админке.

`RichEditorWidget` — обычный `textarea` с атрибутами, по которым бандл
`common/rich_editor/rich-editor.js` (исходник — `frontend/admin-editor/`) монтирует
редактор TipTap. Хранение не меняется: HTML в `TextField`, очистка bleach в
`save()` модели.

`RichContentAdminMixin` подключает виджет и даёт модели путь загрузки картинок
`<сайт>/<app>/<model>/upload-image/` в каждом сайте админки, где она
зарегистрирована. Доступ решают `admin_view` этого сайта и права add/change
на модель — отдельной проверки ролей нет.
"""

from __future__ import annotations

import hashlib
import io
import uuid
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin.widgets import AdminTextareaWidget
from django.core.exceptions import PermissionDenied
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.db import models
from django.http import HttpRequest, JsonResponse
from django.templatetags.static import static
from django.urls import URLPattern, path, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from PIL import Image, ImageOps, UnidentifiedImageError

RICH_CONTENT_FIELD = "content"

# Ширина колонки текста на сайте, px. Редактор делает текст такой же ширины, чтобы картинка
# в нём занимала столько же места, сколько на странице. Новости и статьи блога: `max-w-4xl`
# (896 px) без боковых отступов `lg:px-8` (frontend/src/app/(blue)/{news,blog}/[slug]/page.tsx).
# Страницы (`container` в `Card`) шире — см. `PageAdmin.rich_editor_column_width`.
DEFAULT_COLUMN_WIDTH = 832
RICH_CONTENT_HELP_TEXT = "Текст с оформлением и картинками. Кнопка «HTML» показывает исходный код."

EDITOR_JS = "common/rich_editor/rich-editor.js"
EDITOR_CSS = "common/rich_editor/rich-editor.css"
_STATIC_ROOT = Path(__file__).resolve().parent / "static"

CONTENT_IMAGES_DIR = "content/images"
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
MAX_IMAGE_SIDE = 1920

# Формат Pillow → расширение файла. MPO — снимок телефона (JPEG с превью внутри):
# Pillow открывает его как MPO, но это обычная статичная фотография.
_EXTENSIONS = {"JPEG": "jpg", "MPO": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}
_ALLOWED_FORMATS = ("JPEG", "PNG", "WEBP", "GIF")


class ContentImageError(ValueError):
    """Картинка отклонена; текст показывается сотруднику у редактора."""


def served_asset_path(name: str) -> Path:
    """Файл, который отдаёт nginx: собранный в `STATIC_ROOT`, если он есть, иначе исходник."""
    collected = Path(settings.STATIC_ROOT) / name if settings.STATIC_ROOT else None
    return collected if collected is not None and collected.is_file() else _STATIC_ROOT / name


@lru_cache(maxsize=16)
def _file_version(path: str, mtime_ns: int, size: int) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def asset_version(name: str) -> str:
    """Первые 12 символов sha256 отдаваемого файла бандла — `?v=` в `Media`.

    Имена static на проде без хеша, а nginx кэширует `/static/` на год, поэтому
    новая версия бандла должна получить новый URL. Хешируется файл, который
    реально отдаётся: при деплое backend перезапускается раньше `collectstatic`,
    и хеш исходника дал бы новый `?v=` старому файлу — его nginx закэшировал бы
    на год. Кэш — по пути, времени изменения и размеру: следующий
    `collectstatic` подхватывается без перезапуска.
    """
    path = served_asset_path(name)
    stat = path.stat()
    return _file_version(str(path), stat.st_mtime_ns, stat.st_size)


def versioned_static(name: str) -> str:
    return f"{static(name)}?v={asset_version(name)}"


class RichEditorWidget(AdminTextareaWidget):
    """`textarea` под визуальный редактор: `data-rich-editor`, адрес загрузки картинок
    и ширина колонки текста на сайте (`data-column-width`, px)."""

    def __init__(
        self,
        upload_url: str,
        attrs: dict[str, Any] | None = None,
        column_width: int = DEFAULT_COLUMN_WIDTH,
    ) -> None:
        self.upload_url = upload_url
        self.column_width = column_width
        super().__init__(
            attrs={
                "data-rich-editor": "",
                "data-upload-url": upload_url,
                "data-column-width": str(column_width),
                **(attrs or {}),
            }
        )

    @property
    def media(self) -> forms.Media:
        # Абсолютный путь Media не трогает: `?v=` не уходит в static() и не кодируется.
        return forms.Media(
            css={"all": [versioned_static(EDITOR_CSS)]},
            js=[versioned_static(EDITOR_JS)],
        )


def _reject_animation(image: Image.Image) -> None:
    # Координаты съёмки бывают и в EXIF, и в XMP.
    if image.getexif() or image.info.get("exif") or image.info.get("xmp"):
        raise ContentImageError(
            "В анимации есть метаданные EXIF или XMP (в них бывают координаты съёмки). "
            "Анимация сохраняется без пережатия, поэтому уберите метаданные и загрузите снова."
        )
    if max(image.size) > MAX_IMAGE_SIDE:
        raise ContentImageError(
            f"Анимация больше {MAX_IMAGE_SIDE} px по длинной стороне. "
            f"Анимации не уменьшаются автоматически — уменьшите до {MAX_IMAGE_SIDE} px и загрузите снова."
        )


def _reencode(image: Image.Image, image_format: str) -> bytes:
    """Статичная картинка: поворот по EXIF, не больше 1920 px, сохранение без метаданных."""
    image = ImageOps.exif_transpose(image)
    image.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE), Image.Resampling.LANCZOS)
    # Из сведений файла остаются только прозрачность и цветовой профиль:
    # EXIF, XMP и текстовые блоки (там бывают координаты) не переносятся.
    kept: dict[str | tuple[int, int], Any] = {
        key: image.info[key] for key in ("transparency", "icc_profile") if key in image.info
    }
    image.info = kept

    output = io.BytesIO()
    if image_format in ("JPEG", "MPO"):
        icc_profile = kept.get("icc_profile")
        if image.mode not in ("RGB", "L"):
            # Профиль CMYK к RGB не подходит: после конвертации — без профиля (sRGB).
            image = image.convert("RGB")
            icc_profile = None
        image.save(output, "JPEG", quality=85, optimize=True, icc_profile=icc_profile)
    elif image_format == "PNG":
        image.save(output, "PNG", optimize=True)
    elif image_format == "WEBP":
        image.save(output, "WEBP", quality=85, icc_profile=kept.get("icc_profile", ""))
    else:
        image.save(output, "GIF", optimize=True)
    return output.getvalue()


def save_content_image(upload: UploadedFile) -> str:
    """
    Проверяет и сохраняет картинку из текста; возвращает относительный URL `/media/…`.

    Формат определяет Pillow (только JPEG, PNG, WEBP, GIF), а не имя и тип из
    запроса. Статичные картинки всегда перекодируются — EXIF и GPS уходят;
    анимации сохраняются байт-в-байт, поэтому с EXIF или больше 1920 px отклоняются.
    """
    if upload.size is None or upload.size > MAX_IMAGE_BYTES:
        raise ContentImageError("Картинка больше 10 МБ — уменьшите её и загрузите снова.")
    data = upload.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise ContentImageError("Картинка больше 10 МБ — уменьшите её и загрузите снова.")

    too_large = ContentImageError("Картинка слишком большая по числу точек (больше 40 Мп). Уменьшите её.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            image = Image.open(io.BytesIO(data), formats=_ALLOWED_FORMATS)
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise too_large
            image_format = image.format or ""
            animated = bool(getattr(image, "is_animated", False)) and image_format != "MPO"
            if animated:
                _reject_animation(image)
                content = data
            else:
                image.load()
                content = _reencode(image, image_format)
    except ContentImageError:
        raise
    except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise too_large from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise ContentImageError("Файл не похож на картинку JPEG, PNG, WEBP или GIF.") from exc

    extension = _EXTENSIONS.get(image_format)
    if extension is None:
        raise ContentImageError("Файл не похож на картинку JPEG, PNG, WEBP или GIF.")
    name = f"{CONTENT_IMAGES_DIR}/{timezone.localdate():%Y/%m}/{uuid.uuid4().hex}.{extension}"
    saved = default_storage.save(name, ContentFile(content))
    return str(default_storage.url(saved))


class RichContentAdminMixin(admin.ModelAdmin):
    """Визуальный редактор поля `content` и загрузка картинок для admin-класса модели.

    Ставится первым в MRO: `get_urls` добавляет путь до родительских, иначе его
    перехватил бы catch-all `<path:object_id>/` у `ModelAdmin`.
    """

    # Ширина колонки текста на сайте (px); у модели с другой версткой страницы — своя.
    rich_editor_column_width: int = DEFAULT_COLUMN_WIDTH

    def _upload_url_name(self) -> str:
        opts = self.model._meta
        return f"{opts.app_label}_{opts.model_name}_upload_image"

    def get_urls(self) -> list[URLPattern]:
        view = self.admin_site.admin_view(require_POST(self.upload_image_view))
        return [
            path("upload-image/", view, name=self._upload_url_name()),
            *super().get_urls(),
        ]

    def upload_image_view(self, request: HttpRequest) -> JsonResponse:
        if not (self.has_add_permission(request) or self.has_change_permission(request)):
            raise PermissionDenied
        upload = request.FILES.get("image")
        if upload is None:
            return JsonResponse({"error": "Файл картинки не получен."}, status=400)
        try:
            url = save_content_image(upload)
        except ContentImageError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"url": url})

    def formfield_for_dbfield(self, db_field: models.Field, request: HttpRequest, **kwargs: Any) -> Any:
        if db_field.name == RICH_CONTENT_FIELD:
            upload_url = reverse(f"{self.admin_site.name}:{self._upload_url_name()}")
            kwargs["widget"] = RichEditorWidget(upload_url=upload_url, column_width=self.rich_editor_column_width)
            # help_text модели говорит «HTML или Markdown»; меняется в форме, без миграции.
            kwargs["help_text"] = RICH_CONTENT_HELP_TEXT
        return super().formfield_for_dbfield(db_field, request, **kwargs)
