"""Выбор главного фото товара для витрины."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apps.products.models import Product, ProductVariant


def media_url(path: str) -> str:
    """Путь из JSON-полей с фото (`/products/...`) → URL под `/media/`."""
    if path.startswith("/products/"):
        return f"/media{path}"
    if not path.startswith("/media/") and not path.startswith(("http://", "https://")):
        return f"/media/{path.lstrip('/')}"
    return path


def product_main_image_url(product: Product, variant: ProductVariant | None = None) -> str | None:
    """
    Главное фото товара: первое из `base_images`, затем фото варианта.

    1С присылает фото только в goods.xml и ставит основную картинку номенклатуры
    (`ФайлКартинки`) первой, а импорт сохраняет этот порядок в `base_images`.
    Фото вариантов остались от старого сканирования каталога и обменом не
    обновляются, поэтому они лишь запасной источник — иначе каталог показывал бы
    не тот кадр, что карточка товара.
    """
    if product.base_images and isinstance(product.base_images, list) and product.base_images[0]:
        return media_url(str(product.base_images[0]))
    if variant is None:
        return None
    if variant.main_image:
        return str(variant.main_image.url)
    if variant.gallery_images and isinstance(variant.gallery_images, list) and variant.gallery_images[0]:
        return media_url(str(variant.gallery_images[0]))
    return None
