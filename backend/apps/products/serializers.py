"""
Serializers для каталога товаров
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ValidationError
from django.db.models import Count, Q, Sum
from rest_framework import serializers

from .models import Attribute, AttributeValue, Brand, Category, ColorMapping, Product, ProductImage, ProductVariant

# Константы для отображения диапазонов остатков
STOCK_RANGE_LIMITS = {
    "LOW": 5,
    "MEDIUM": 19,
    "HIGH": 49,
}


class AttributeValueSerializer(serializers.ModelSerializer):
    """
    Serializer для значений атрибутов товара

    Возвращает структурированную информацию об атрибутах:
    - name: Название атрибута (из связанного Attribute)
    - value: Значение атрибута
    - slug: URL-совместимый идентификатор
    - type: Тип атрибута для будущей логики фильтрации
    """

    name = serializers.CharField(source="attribute.name", read_only=True)
    slug = serializers.CharField(source="attribute.slug", read_only=True)
    type = serializers.CharField(source="attribute.type", read_only=True)

    class Meta:
        model = AttributeValue
        fields = ["name", "value", "slug", "type"]
        read_only_fields = fields


if TYPE_CHECKING:
    from apps.users.models import User


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer для ProductVariant с роле-ориентированной ценой

    Поля:
    - current_price: цена для текущего пользователя (роле-ориентированная)
    - color_hex: hex-код цвета из ColorMapping
    - is_in_stock: computed property из модели
    - available_quantity: computed property из модели
    - attributes: объединенный список атрибутов (вариант + продукт с наследованием)
    """

    current_price = serializers.SerializerMethodField()
    color_hex = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)
    stock_range = serializers.SerializerMethodField()
    attributes = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    gallery_images = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "color_name",
            "size_value",
            "current_price",
            "color_hex",
            "stock_quantity",
            "is_in_stock",
            "available_quantity",
            "stock_range",
            "rrp",
            "msrp",
            "main_image",
            "gallery_images",
            "attributes",
        ]
        read_only_fields = fields  # Все поля read-only

    def to_representation(self, instance: ProductVariant) -> dict[str, Any]:
        """Логика скрытия полей RRP/MSRP для разных ролей"""
        data: dict[str, Any] = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Определяем роль (retail для анонимов)
        role = "retail"
        if user and user.is_authenticated:
            role = getattr(user, "role", "retail")

        # RRP/MSRP видят только оптовики (1-3), тренеры и админы
        # Представители федерации, розница и гости НЕ видят
        allowed_roles = [
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "trainer",
            "admin",
        ]
        if role not in allowed_roles:
            data.pop("rrp", None)
            data.pop("msrp", None)

        return data

    def get_stock_range(self, obj: ProductVariant) -> str | None:
        """
        Получить диапазон остатков (1-5, 6-19, 20-49, 50+)

        Args:
            obj: ProductVariant instance

        Returns:
            str | None: Строка диапазона или None если товара нет
        """
        quantity = obj.available_quantity

        quantity = obj.available_quantity

        if quantity <= 0:
            return None
        elif quantity <= STOCK_RANGE_LIMITS["LOW"]:
            return f"1 - {STOCK_RANGE_LIMITS['LOW']}"
        elif quantity <= STOCK_RANGE_LIMITS["MEDIUM"]:
            return f"{STOCK_RANGE_LIMITS['LOW'] + 1} - {STOCK_RANGE_LIMITS['MEDIUM']}"
        elif quantity <= STOCK_RANGE_LIMITS["HIGH"]:
            return f"{STOCK_RANGE_LIMITS['MEDIUM'] + 1} - {STOCK_RANGE_LIMITS['HIGH']}"
        else:
            return f"{STOCK_RANGE_LIMITS['HIGH'] + 1} и более"

    def get_main_image(self, obj: ProductVariant) -> str | None:
        """
        Получить URL основного изображения варианта

        Args:
            obj: ProductVariant instance

        Returns:
            str | None: URL изображения или None (относительный путь с /media/)
        """
        if obj.main_image:
            # Возвращаем относительный URL с /media/ префиксом
            # Nginx обработает этот путь
            return str(obj.main_image.url)
        return None

    def get_gallery_images(self, obj: ProductVariant) -> list[str]:
        """
        Получить список URL галереи изображений варианта

        Пути в gallery_images хранятся как относительные от /media/:
        - /products/variants/... → /media/products/variants/...

        Дубликаты и main_image исключаются из результата.

        Args:
            obj: ProductVariant instance

        Returns:
            list[str]: Список уникальных URL изображений с /media/ префиксом
        """
        if not obj.gallery_images or not isinstance(obj.gallery_images, list):
            return []

        # Получаем main_image для исключения дубликатов
        main_image_url = obj.main_image.url if obj.main_image else None
        # Извлекаем имя файла из main_image для сравнения
        main_image_filename = main_image_url.split("/")[-1] if main_image_url else None

        seen_filenames = set()
        if main_image_filename:
            seen_filenames.add(main_image_filename)

        result = []
        for img_url in obj.gallery_images:
            if not img_url:
                continue

            # Извлекаем имя файла для проверки дубликатов
            filename = img_url.split("/")[-1]
            if filename in seen_filenames:
                continue
            seen_filenames.add(filename)

            # Добавляем /media/ префикс если путь относительный
            if img_url.startswith("/products/"):
                result.append(f"/media{img_url}")
            elif not img_url.startswith("/media/") and not img_url.startswith(("http://", "https://")):
                result.append(f"/media/{img_url.lstrip('/')}")
            else:
                result.append(img_url)

        return result

    def get_current_price(self, obj: ProductVariant) -> str:
        """
        Получить роле-ориентированную цену для текущего пользователя

        Args:
            obj: ProductVariant instance

        Returns:
            str: Цена как строка (сериализация Decimal)
        """
        request = self.context.get("request")
        user: User | None = getattr(request, "user", None) if request else None

        price: Decimal = obj.get_price_for_user(user)
        return str(price)  # Сериализация Decimal → str

    def get_color_hex(self, obj: ProductVariant) -> str | None:
        """
        Получить hex-код цвета из ColorMapping

        Args:
            obj: ProductVariant instance

        Returns:
            str | None: Hex-код цвета или None если маппинг не найден
        """
        if not obj.color_name:
            return None

        # Кэшируем ColorMapping для избежания N+1 queries
        if not hasattr(self, "_color_mapping_cache"):
            self._color_mapping_cache = {mapping.name: mapping.hex_code for mapping in ColorMapping.objects.all()}

        return self._color_mapping_cache.get(obj.color_name)

    def get_attributes(self, obj: ProductVariant) -> list[dict[str, Any]]:
        """
        Получить атрибуты варианта с наследованием от продукта

        Логика наследования:
        1. Получаем атрибуты продукта
        2. Получаем атрибуты варианта
        3. Объединяем: если вариант имеет значение атрибута,
           оно переопределяет значение продукта
        4. Возвращаем комбинированный список

        Args:
            obj: ProductVariant instance

        Returns:
            list[dict]: Список атрибутов с полями name, value, slug, type
        """
        # Словарь для хранения атрибутов (ключ = attribute_id)
        attributes_dict: dict[int, AttributeValue] = {}

        # 1. Добавляем атрибуты продукта (базовые значения)
        if hasattr(obj.product, "prefetched_attributes"):
            # Используем prefetched данные если доступны
            for attr_value in obj.product.prefetched_attributes:
                attributes_dict[attr_value.attribute_id] = attr_value
        else:
            # Fallback на прямой запрос
            for attr_value in obj.product.attributes.select_related("attribute").all():
                attributes_dict[attr_value.attribute_id] = attr_value

        # 2. Переопределяем атрибутами варианта (приоритет выше)
        if hasattr(obj, "prefetched_attributes"):
            # Используем prefetched данные если доступны
            for attr_value in obj.prefetched_attributes:
                attributes_dict[attr_value.attribute_id] = attr_value
        else:
            # Fallback на прямой запрос
            for attr_value in obj.attributes.select_related("attribute").all():
                attributes_dict[attr_value.attribute_id] = attr_value

        # 3. Сериализуем объединенный список
        return AttributeValueSerializer(list(attributes_dict.values()), many=True).data  # type: ignore[return-value]


class ProductImageSerializer(serializers.ModelSerializer):
    """
    Serializer для изображений товара
    """

    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["url", "alt_text", "is_main", "sort_order"]

    def get_url(self, obj):
        """Получить URL изображения с учетом контекста запроса"""
        if isinstance(obj, dict):
            return obj.get("url", "")

        # Если obj - это модель с полем изображения
        if hasattr(obj, "url"):
            url = obj.url
        elif hasattr(obj, "image") and hasattr(obj.image, "url"):
            url = obj.image.url
        else:
            return ""

        request = self.context.get("request")
        if request and hasattr(request, "build_absolute_uri"):
            return request.build_absolute_uri(url)
        return url


class BrandSerializer(serializers.ModelSerializer):
    """
    Serializer для брендов
    """

    slug = serializers.SlugField(required=False)
    image = serializers.SerializerMethodField()

    class Meta:
        model = Brand
        fields = ["id", "name", "slug", "image", "description", "website", "is_featured"]

    def get_image(self, obj: Brand) -> str | None:
        """Возвращает URL изображения или None."""
        if not obj.image:
            return None
        request = self.context.get("request")
        if request and hasattr(request, "build_absolute_uri"):
            return str(request.build_absolute_uri(obj.image.url))
        return str(obj.image.url)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Вызов модельной валидации Brand.clean() для проверки бизнес-правил.

        Создаёт временный экземпляр для валидации, не мутируя self.instance.
        Возвращает обновленные атрибуты, так как clean() может нормализовать данные.
        """
        instance: Brand
        if self.instance and not isinstance(self.instance, list):
            brand_instance = cast(Brand, self.instance)
            concrete_field_names = {f.name for f in Brand._meta.concrete_fields}  # type: ignore[attr-defined]
            merged = {
                name: getattr(brand_instance, name) for name in concrete_field_names if hasattr(brand_instance, name)
            }
            merged.update(attrs)
            instance = Brand(**{k: v for k, v in merged.items() if k in concrete_field_names})
            instance.pk = brand_instance.pk
        else:
            instance = Brand(**attrs)

        try:
            instance.clean()
        except ValidationError as e:
            raise serializers.ValidationError(e.message_dict)

        # Update attrs with any normalized values from clean()
        for key in attrs.keys():
            if hasattr(instance, key):
                attrs[key] = getattr(instance, key)

        return attrs


class BrandFeaturedSerializer(BrandSerializer):
    """Lightweight serializer для featured brands endpoint (без description).

    Наследует BrandSerializer, но переопределяет get_image для гарантии
    относительных URL (cache safety) и исключает description/is_featured.
    """

    class Meta(BrandSerializer.Meta):
        fields = ["id", "name", "slug", "image", "website"]

    def get_image(self, obj: Brand) -> str | None:
        """
        Возвращает относительный URL изображения для безопасного кэширования.

        Игнорирует request.build_absolute_uri, чтобы в кэш не попал
        Host-заголовок пользователя (cache poisoning protection).
        """
        if not obj.image:
            return None
        return str(obj.image.url)


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer для категорий с поддержкой иерархии
    """

    children = serializers.SerializerMethodField()
    products_count = serializers.SerializerMethodField()
    breadcrumbs = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "description",
            "image",
            "parent",
            "children",
            "products_count",
            "breadcrumbs",
            "is_active",
            "sort_order",
        ]

    def get_children(self, obj):
        """Получить дочерние категории"""
        if hasattr(obj, "prefetched_children"):
            # Если данные уже предзагружены
            children = obj.prefetched_children
            return CategorySerializer(children, many=True, context=self.context).data
        else:
            # Загружаем дочерние категории с подсчетом товаров
            children = (
                obj.children.filter(is_active=True)
                .annotate(products_count=Count("products", filter=Q(products__is_active=True)))
                .order_by("sort_order", "name")
            )

            return CategorySerializer(children, many=True, context=self.context).data

    def get_products_count(self, obj):
        """Получить количество активных товаров в категории"""
        if hasattr(obj, "products_count"):
            return obj.products_count
        return obj.products.filter(is_active=True).count()

    def get_breadcrumbs(self, obj):
        """Получить навигационную цепочку для категории"""
        breadcrumbs: list[dict[str, Any]] = []
        current = obj

        while current:
            breadcrumbs.insert(0, {"id": current.id, "name": current.name, "slug": current.slug})
            current = current.parent

        return breadcrumbs


class ProductListSerializer(serializers.ModelSerializer):
    """
    Serializer для списка товаров (базовая модель Product)

    Примечание: Product - это базовая модель товара без цен и остатков.
    Цены и остатки хранятся в ProductVariant.
    Для получения вариантов используйте вложенное поле 'variants'
    в ProductDetailSerializer.

    Вычисляемые поля для обратной совместимости (данные из вариантов):
    - retail_price, opt1_price, opt2_price, opt3_price: цены из первого варианта
    - stock_quantity: суммарное количество на складе по всем вариантам
    - is_in_stock: есть ли хотя бы один вариант в наличии
    - main_image: изображение из первого варианта или base_images
    - can_be_ordered: можно ли заказать товар
    """

    brand = BrandSerializer(read_only=True)
    category: Any = serializers.StringRelatedField(read_only=True)
    specifications = serializers.JSONField(read_only=True)
    attributes = serializers.SerializerMethodField()

    # Вычисляемые поля для обратной совместимости с frontend
    retail_price = serializers.SerializerMethodField()
    opt1_price = serializers.SerializerMethodField()
    opt2_price = serializers.SerializerMethodField()
    opt3_price = serializers.SerializerMethodField()
    stock_quantity = serializers.SerializerMethodField()
    is_in_stock = serializers.SerializerMethodField()
    main_image = serializers.SerializerMethodField()
    can_be_ordered = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    rrp = serializers.SerializerMethodField()
    msrp = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "brand",
            "category",
            "description",
            "short_description",
            "specifications",
            "base_images",
            "is_featured",
            # Story 11.0: Маркетинговые флаги для бейджей
            "is_hit",
            "is_new",
            "is_sale",
            "is_promo",
            "is_premium",
            "discount_percent",
            "created_at",
            "attributes",
            # Вычисляемые поля из вариантов (обратная совместимость)
            "retail_price",
            "opt1_price",
            "opt2_price",
            "opt3_price",
            "stock_quantity",
            "is_in_stock",
            "main_image",
            "can_be_ordered",
            "current_price",
            "sku",
            "rrp",
            "msrp",
        ]
        read_only_fields = [
            "is_hit",
            "is_new",
            "is_sale",
            "is_promo",
            "is_premium",
            "discount_percent",
        ]

    def _get_first_variant(self, obj: Product) -> "ProductVariant | None":
        """Получить первый вариант товара с ценой > 0 (кэшированный или из БД)"""
        # Используем prefetched данные
        if hasattr(obj, "first_variant_list") and obj.first_variant_list:
            # Ищем сначала вариант с ненулевой розничной ценой
            valid_variants = [v for v in obj.first_variant_list if v.retail_price > 0]
            if valid_variants:
                return cast("ProductVariant", valid_variants[0])
            # Если нет с розничной, берем любой (с любой другой ценой)
            return cast("ProductVariant", obj.first_variant_list[0])
        # Fallback на прямой запрос с фильтрацией
        return (
            obj.variants.filter(
                Q(retail_price__gt=0)
                | Q(opt1_price__gt=0)
                | Q(opt2_price__gt=0)
                | Q(opt3_price__gt=0)
                | Q(trainer_price__gt=0)
                | Q(federation_price__gt=0)
            )
            .order_by("retail_price")
            .first()
        )

    def get_retail_price(self, obj: Product) -> float:
        """Получить розничную цену из первого варианта"""
        variant = self._get_first_variant(obj)
        if variant:
            return float(variant.retail_price)
        return 0.0

    def get_current_price(self, obj: Product) -> str:
        """Получить актуальную цену на основе роли пользователя"""
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None
        variant = self._get_first_variant(obj)
        if not variant:
            return "0.00"

        price = variant.get_price_for_user(user)
        return f"{price:.2f}"

    def to_representation(self, instance):
        """Логика скрытия полей для разных ролей"""
        data = super().to_representation(instance)
        request = self.context.get("request")
        user = getattr(request, "user", None) if request else None

        # Определяем роль пользователя (по умолчанию retail для анонимов)
        role = "retail"
        if user and user.is_authenticated:
            role = getattr(user, "role", "retail")

        # Скрываем RRP и MSRP для розничных пользователей, гостей и федераций
        allowed_roles = [
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "trainer",
            "admin",
        ]
        if role not in allowed_roles:
            data.pop("rrp", None)
            data.pop("msrp", None)
        return data

    def get_sku(self, obj: Product) -> str:
        """Получить артикул первого варианта"""
        variant = self._get_first_variant(obj)
        return variant.sku if variant else ""

    def get_rrp(self, obj: Product) -> float | None:
        """Получить РРЦ первого варианта"""
        variant = self._get_first_variant(obj)
        return float(variant.rrp) if variant and variant.rrp else None

    def get_msrp(self, obj: Product) -> float | None:
        """Получить МРЦ первого варианта"""
        variant = self._get_first_variant(obj)
        return float(variant.msrp) if variant and variant.msrp else None

    def get_opt1_price(self, obj: Product) -> float:
        """Получить оптовую цену уровня 1 из первого варианта"""
        variant = self._get_first_variant(obj)
        if variant and variant.opt1_price:
            return float(variant.opt1_price)
        return 0.0

    def get_opt2_price(self, obj: Product) -> float:
        """Получить оптовую цену уровня 2 из первого варианта"""
        variant = self._get_first_variant(obj)
        if variant and variant.opt2_price:
            return float(variant.opt2_price)
        return 0.0

    def get_opt3_price(self, obj: Product) -> float:
        """Получить оптовую цену уровня 3 из первого варианта"""
        variant = self._get_first_variant(obj)
        if variant and variant.opt3_price:
            return float(variant.opt3_price)
        return 0.0

    def get_stock_quantity(self, obj: Product) -> int:
        """Получить суммарное количество на складе по всем вариантам"""
        # Используем аннотированное значение если доступно
        if hasattr(obj, "total_stock") and obj.total_stock is not None:
            return int(obj.total_stock)
        # Fallback на агрегацию
        # Fallback на агрегацию
        result = obj.variants.aggregate(total=Sum("stock_quantity"))
        return int(result["total"] or 0)

    def get_is_in_stock(self, obj: Product) -> bool:
        """Проверить наличие товара (любой вариант в наличии)"""
        # Используем аннотированное значение если доступно
        if hasattr(obj, "has_stock"):
            return bool(obj.has_stock)
        # Используем prefetched данные
        if hasattr(obj, "first_variant_list") and obj.first_variant_list:
            return any(v.stock_quantity > 0 for v in obj.first_variant_list)
        # Fallback на проверку в БД
        return obj.variants.filter(stock_quantity__gt=0).exists()

    def get_main_image(self, obj: Product) -> str | None:
        """
        Получить основное изображение из первого варианта или base_images

        Возвращает относительный URL с /media/ префиксом
        """
        variant = self._get_first_variant(obj)
        if variant and variant.main_image:
            # Возвращаем URL, а не ImageField объект
            return str(variant.main_image.url)
        # Fallback на base_images
        if obj.base_images and isinstance(obj.base_images, list) and obj.base_images:
            img_url = obj.base_images[0]
            # Добавляем /media/ префикс если путь начинается с /products/
            if img_url.startswith("/products/"):
                return f"/media{img_url}"
            elif not img_url.startswith("/media/") and not img_url.startswith(("http://", "https://")):
                return f"/media/{img_url.lstrip('/')}"
            return str(img_url)
        return None

    def get_can_be_ordered(self, obj: Product) -> bool:
        """Проверить можно ли заказать товар"""
        return self.get_is_in_stock(obj)

    def get_attributes(self, obj: Product) -> list[dict[str, Any]]:
        """
        Получить атрибуты продукта

        Args:
            obj: Product instance

        Returns:
            list[dict]: Список атрибутов с полями name, value, slug, type
        """
        if hasattr(obj, "prefetched_attributes"):
            # Используем prefetched данные если доступны
            attr_values = obj.prefetched_attributes
        else:
            # Fallback на прямой запрос
            attr_values = obj.attributes.select_related("attribute").all()

        return [
            {
                "name": attr_value.attribute.name,
                "value": attr_value.value,
                "slug": attr_value.attribute.slug,
                "type": attr_value.attribute.type,
            }
            for attr_value in attr_values
        ]


class ProductDetailSerializer(ProductListSerializer):
    """
    Serializer для детальной информации о товаре с расширенными полями
    """

    images = serializers.SerializerMethodField()
    related_products = serializers.SerializerMethodField()
    category_breadcrumbs = serializers.SerializerMethodField()
    specifications = serializers.JSONField(read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description",
            "specifications",
            "images",
            "related_products",
            "category_breadcrumbs",
            "seo_title",
            "seo_description",
            "variants",
        ]

    def to_representation(self, instance):
        """Гарантируем использование логики скрытия полей из родительского класса"""
        return super().to_representation(instance)

    def get_images(self, obj):
        """
        Получить галерею изображений из base_images

        Product использует base_images (JSONField) - список URL изображений из 1С.
        Первое изображение считается основным.

        Пути в base_images хранятся как относительные от /media/:
        - /products/base/... → /media/products/base/...
        """
        images = []
        request = self.context.get("request")

        # base_images - это список URL изображений
        if obj.base_images and isinstance(obj.base_images, list):
            for idx, img_url in enumerate(obj.base_images):
                url = img_url

                # Формируем абсолютный URL от корня сервера
                if not img_url.startswith(("http://", "https://")):
                    # Добавляем /media/ префикс если путь начинается с /products/
                    if img_url.startswith("/products/"):
                        img_url = f"/media{img_url}"
                    elif not img_url.startswith("/media/"):
                        img_url = f"/media/{img_url.lstrip('/')}"

                    # Строим абсолютный URL от корня
                    if request and hasattr(request, "build_absolute_uri"):
                        url = request.build_absolute_uri(img_url)
                    else:
                        url = img_url

                images.append(
                    {
                        "url": url,
                        "alt_text": f"{obj.name} - изображение {idx + 1}",
                        "is_main": idx == 0,  # Первое изображение - основное
                    }
                )

        return images

    def get_related_products(self, obj):
        """Получить связанные товары из той же категории или бренда"""
        # Сначала товары из той же категории
        related_by_category = (
            Product.objects.filter(category=obj.category, is_active=True)
            .exclude(id=obj.id)
            .select_related("brand", "category")[:5]
        )

        # Если меньше 5, добавляем товары того же бренда
        if len(related_by_category) < 5:
            related_by_brand = (
                Product.objects.filter(brand=obj.brand, is_active=True)
                .exclude(id__in=[obj.id] + [p.id for p in related_by_category])
                .select_related("brand", "category")[: 5 - len(related_by_category)]
            )

            related_products = list(related_by_category) + list(related_by_brand)
        else:
            related_products = list(related_by_category)

        return ProductListSerializer(related_products, many=True, context=self.context).data

    def get_category_breadcrumbs(self, obj):
        """Получить навигационную цепочку для категории товара"""
        breadcrumbs: list[dict[str, Any]] = []
        current = obj.category

        while current:
            breadcrumbs.insert(0, {"id": current.id, "name": current.name, "slug": current.slug})
            current = current.parent

        return breadcrumbs


class CategoryTreeSerializer(serializers.ModelSerializer):
    """
    Специальный serializer для дерева категорий (корневые категории)
    """

    children = serializers.SerializerMethodField()
    products_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = [
            "id",
            "name",
            "slug",
            "image",
            "children",
            "products_count",
            "sort_order",
        ]

    def get_children(self, obj):
        """Рекурсивно получить все дочерние категории"""
        children = (
            obj.children.filter(is_active=True)
            .annotate(products_count=Count("products", filter=Q(products__is_active=True)))
            .order_by("sort_order", "name")
        )

        return CategoryTreeSerializer(children, many=True, context=self.context).data


class AttributeValueFilterSerializer(serializers.ModelSerializer):
    """
    Serializer для значений атрибутов в фильтрах каталога.

    Используется для endpoint /api/v1/catalog/filters/ для построения
    фильтров на фронтенде на основе активных атрибутов.
    """

    class Meta:
        model = AttributeValue
        fields = ["id", "value", "slug"]


class AttributeFilterSerializer(serializers.ModelSerializer):
    """
    Serializer для атрибутов в фильтрах каталога.

    Возвращает список активных атрибутов с их значениями для построения
    фильтров в каталоге товаров.

    Fields:
    - id: ID атрибута
    - name: Название атрибута
    - slug: URL-совместимый идентификатор
    - values: Список значений атрибута
    """

    values = serializers.SerializerMethodField()

    class Meta:
        model = Attribute
        fields = ["id", "name", "slug", "values"]

    def get_values(self, obj: Attribute) -> list[dict[str, Any]]:
        """
        Получить все значения атрибута.

        Args:
            obj: Attribute instance

        Returns:
            List[dict]: Список значений атрибута
        """
        return AttributeValueFilterSerializer(obj.values.all(), many=True).data  # type: ignore[return-value]
