"""
Главное фото товара на витрине: первое фото 1С (base_images) важнее фото варианта.

1С ставит основную картинку номенклатуры первой в goods.xml, а фото вариантов
остались от старого сканирования каталога и обменом не обновляются.
"""

import pytest

from apps.cart.models import CartItem
from apps.cart.serializers import CartItemSerializer
from apps.products.factories import ProductFactory
from apps.products.serializers import ProductListSerializer
from apps.products.utils.images import media_url, product_main_image_url
from apps.users.models import Favorite
from apps.users.serializers import FavoriteSerializer
from tests.conftest import get_unique_suffix


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("/products/base/a.jpg", "/media/products/base/a.jpg"),
        ("/media/products/a.jpg", "/media/products/a.jpg"),
        ("uploads/a.jpg", "/media/uploads/a.jpg"),
        ("/uploads/a.jpg", "/media/uploads/a.jpg"),
        ("https://cdn.example.com/a.jpg", "https://cdn.example.com/a.jpg"),
    ],
)
def test_media_url(path, expected):
    assert media_url(path) == expected


@pytest.mark.django_db
class TestProductMainImageUrl:
    @pytest.fixture
    def variant_image(self):
        return f"products/variants/{get_unique_suffix()}.jpg"

    def test_base_image_wins_over_variant_photo(self, variant_image):
        product = ProductFactory(
            base_images=["/products/base/front.jpg", "/products/base/back.jpg"],
            main_image=variant_image,
        )

        assert product_main_image_url(product, product.variants.get()) == "/media/products/base/front.jpg"

    def test_variant_photo_without_base_images(self, variant_image):
        product = ProductFactory(base_images=[], main_image=variant_image)

        assert product_main_image_url(product, product.variants.get()) == f"/media/{variant_image}"

    def test_variant_gallery_without_main_image(self):
        product = ProductFactory(base_images=[])
        variant = product.variants.get()
        variant.gallery_images = ["/products/variants/g.jpg"]

        assert product_main_image_url(product, variant) == "/media/products/variants/g.jpg"

    def test_none_without_any_photo(self):
        product = ProductFactory(base_images=[])

        assert product_main_image_url(product, product.variants.get()) is None
        assert product_main_image_url(product) is None


@pytest.mark.django_db
class TestShowcaseUsesFirstPhotoFrom1C:
    """Каталог, корзина и избранное показывают тот же кадр, что и карточка товара."""

    @pytest.fixture
    def product(self):
        return ProductFactory(
            base_images=["/products/base/front.jpg", "/products/base/back.jpg"],
            main_image=f"products/variants/{get_unique_suffix()}.jpg",
        )

    def test_catalog_list(self, product):
        assert ProductListSerializer(product).data["main_image"] == "/media/products/base/front.jpg"

    def test_cart_item(self, product):
        item = CartItem(variant=product.variants.get())

        assert CartItemSerializer().get_product(item)["image"] == "/media/products/base/front.jpg"

    def test_favorite(self, product):
        favorite = Favorite(product=product)

        assert FavoriteSerializer().get_product_image(favorite) == "/media/products/base/front.jpg"
