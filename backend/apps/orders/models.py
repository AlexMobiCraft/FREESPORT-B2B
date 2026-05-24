"""
Модели заказов для платформы FREESPORT
Поддерживает B2B и B2C заказы с различными способами оплаты и доставки
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from apps.orders.constants import ORDER_STATUSES

if TYPE_CHECKING:
    from django.db.models.manager import RelatedManager

    from apps.products.models import Product as ProductType
    from apps.products.models import ProductVariant as ProductVariantType
    from apps.users.models import User as UserType

User = get_user_model()


class Order(models.Model):
    """Модель заказа.

    Хранит ключевые сведения о заказе, покупателе и оплате и используется как в B2C,
    так и в B2B-сценариях.

    Поля интеграции с 1С:
    - sent_to_1c: флаг отправки заказа в 1С
    - sent_to_1c_at: дата/время отправки в 1С
    - status_1c: оригинальный статус из 1С

    Поля VAT / Субзаказы:
    - parent_order: ссылка на мастер-заказ (только для субзаказов)
    - is_master: True — заказ видит клиент; False — технический субзаказ для 1С
    - vat_group: ставка НДС группы товаров в субзаказе (5 или 22)"""

    objects = models.Manager()

    if TYPE_CHECKING:
        items: RelatedManager["OrderItem"]
        order_number: str
        user: UserType | None
        customer_name: str
        customer_email: str
        customer_phone: str
        status: str
        total_amount: Decimal
        discount_amount: Decimal
        delivery_cost: Decimal
        delivery_address: str
        delivery_method: str
        customer_code_snapshot: str
        order_year: int | None
        customer_year_sequence: int | None
        suborder_sequence: int | None
        delivery_date: date | None
        tracking_number: str
        payment_method: str
        payment_status: str
        payment_id: str
        sent_to_1c: bool
        sent_to_1c_at: datetime | None
        status_1c: str
        export_skipped: bool
        paid_at: datetime | None
        shipped_at: datetime | None
        notes: str
        created_at: datetime
        updated_at: datetime
        parent_order: "Order | None"
        is_master: bool
        vat_group: "Decimal | None"
        sub_orders: "RelatedManager[Order]"

    ORDER_STATUSES = ORDER_STATUSES

    DELIVERY_METHODS = [
        ("pickup", "Самовывоз"),
        ("courier", "Курьерская доставка"),
        ("post", "Почтовая доставка"),
        ("transport_company", "Транспортная компания"),
        ("transport_schedule", "Транспортная компания (по расписанию)"),
    ]

    PAYMENT_METHODS = [
        ("card", "Банковская карта"),
        ("cash", "Наличные"),
        ("bank_transfer", "Банковский перевод"),
        ("payment_on_delivery", "Оплата при получении"),
    ]

    PAYMENT_STATUSES = [
        ("pending", "Ожидает оплаты"),
        ("paid", "Оплачен"),
        ("failed", "Ошибка оплаты"),
        ("refunded", "Возвращен"),
    ]

    # Идентификация заказа
    order_number = cast(
        str,
        models.CharField("Номер заказа", max_length=50, unique=True, editable=False),
    )
    customer_code_snapshot = cast(
        str,
        models.CharField("Снимок customer_code", max_length=5, blank=True, db_index=True),
    )
    order_year = cast(
        "int | None",
        models.PositiveSmallIntegerField("Год заказа", null=True, blank=True, db_index=True),
    )
    customer_year_sequence = cast(
        "int | None",
        models.PositiveSmallIntegerField("Порядковый номер заказа клиента в году", null=True, blank=True),
    )
    suborder_sequence = cast(
        "int | None",
        models.PositiveSmallIntegerField("Порядковый номер субзаказа", null=True, blank=True),
    )
    user = cast(
        "UserType | None",
        models.ForeignKey(
            User,
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name="orders",
            verbose_name="Пользователь",
        ),
    )

    # Информация о клиенте (для гостевых заказов)
    customer_name = cast(str, models.CharField("Имя клиента", max_length=200, blank=True))
    customer_email = cast(str, models.EmailField("Email клиента", blank=True))
    customer_phone = cast(str, models.CharField("Телефон клиента", max_length=20, blank=True))

    # Детали заказа
    status = cast(
        str,
        models.CharField("Статус заказа", max_length=50, choices=ORDER_STATUSES, default="pending"),
    )
    total_amount = cast(
        Decimal,
        models.DecimalField(
            "Общая сумма",
            max_digits=10,
            decimal_places=2,
            validators=[MinValueValidator(0)],
        ),
    )
    discount_amount = cast(
        Decimal,
        models.DecimalField(
            "Сумма скидки",
            max_digits=10,
            decimal_places=2,
            default=0,
            validators=[MinValueValidator(0)],
        ),
    )
    delivery_cost = cast(
        Decimal,
        models.DecimalField(
            "Стоимость доставки",
            max_digits=10,
            decimal_places=2,
            default=0,
            validators=[MinValueValidator(0)],
        ),
    )

    # Информация о доставке
    delivery_address = cast(str, models.TextField("Адрес доставки"))
    delivery_method = cast(
        str,
        models.CharField("Способ доставки", max_length=50, choices=DELIVERY_METHODS),
    )
    delivery_date = cast("date | None", models.DateField("Дата доставки", null=True, blank=True))
    tracking_number = cast(
        str,
        models.CharField(
            "Трек-номер",
            max_length=100,
            blank=True,
            help_text="Номер для отслеживания посылки",
        ),
    )
    # Информация об оплате
    payment_method = cast(str, models.CharField("Способ оплаты", max_length=50, choices=PAYMENT_METHODS))
    payment_status = cast(
        str,
        models.CharField("Статус оплаты", max_length=50, choices=PAYMENT_STATUSES, default="pending"),
    )
    payment_id = cast(str, models.CharField("ID платежа (ЮKassa)", max_length=100, blank=True))

    # Интеграция с 1С
    sent_to_1c = cast(
        bool,
        models.BooleanField("Отправлен в 1С", default=False),
    )
    sent_to_1c_at = cast(
        "datetime | None",
        models.DateTimeField("Дата и время отправки в 1С", null=True, blank=True),
    )
    status_1c = cast(
        str,
        models.CharField("Статус из 1С", max_length=255, blank=True, default=""),
    )
    export_skipped = cast(
        bool,
        models.BooleanField(
            "Пропущен при экспорте",
            default=False,
            help_text="Заказ не прошёл валидацию для экспорта в 1С (например, нет товаров)",
        ),
    )

    # VAT / Субзаказы
    parent_order = cast(
        "Order | None",
        models.ForeignKey(
            "self",
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name="sub_orders",
            verbose_name="Мастер-заказ",
            help_text="Заполнено только для дочерних субзаказов",
        ),
    )
    is_master = cast(
        bool,
        models.BooleanField(
            "Мастер-заказ",
            default=True,
            help_text="True — заказ видит клиент; False — технический субзаказ для 1С",
        ),
    )
    vat_group = cast(
        "Decimal | None",
        models.DecimalField(
            "Группа НДС (%)",
            max_digits=5,
            decimal_places=2,
            null=True,
            blank=True,
            help_text="Ставка НДС группы товаров в этом субзаказе (5 или 22)",
        ),
    )

    paid_at = cast(
        "datetime | None",
        models.DateTimeField("Дата оплаты", null=True, blank=True),
    )
    shipped_at = cast(
        "datetime | None",
        models.DateTimeField("Дата отгрузки", null=True, blank=True),
    )

    # Дополнительная информация
    notes = cast(str, models.TextField("Комментарии к заказу", blank=True))

    # Временные метки
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        """Метаданные Django ORM для модели `Order`."""

        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["order_number"]),
            models.Index(fields=["payment_status"]),
            models.Index(
                fields=["sent_to_1c", "created_at"],
                name="idx_order_sent_to_1c_created",
                condition=models.Q(sent_to_1c=False, export_skipped=False),
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["customer_code_snapshot", "order_year", "customer_year_sequence"],
                condition=Q(is_master=True, order_year__isnull=False, customer_year_sequence__isnull=False)
                & ~Q(customer_code_snapshot=""),
                name="uniq_master_order_customer_year_seq",
            ),
            models.UniqueConstraint(
                fields=["parent_order", "suborder_sequence"],
                condition=Q(is_master=False, parent_order__isnull=False, suborder_sequence__isnull=False),
                name="uniq_suborder_parent_sequence",
            ),
            models.CheckConstraint(
                condition=Q(customer_year_sequence__isnull=True)
                | (Q(customer_year_sequence__gte=1) & Q(customer_year_sequence__lte=999)),
                name="check_customer_year_sequence_range",
            ),
            models.CheckConstraint(
                condition=Q(suborder_sequence__isnull=True) | Q(suborder_sequence__gte=1),
                name="check_suborder_sequence_positive",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.order_number:
            self.order_number = Order.generate_order_number()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Заказ #{self.order_number}"

    @property
    def order_number_display(self) -> str:
        from apps.orders.services.order_numbering import format_order_number

        return format_order_number(self.order_number)

    @classmethod
    def generate_order_number(cls) -> str:
        """Генерация уникального номера заказа на основе UUID"""
        return str(uuid.uuid4())

    @property
    def subtotal(self) -> Decimal:
        """Подытог заказа без учета доставки и скидок"""
        return Decimal(sum(item.total_price for item in self.items.all()))

    @property
    def customer_display_name(self) -> str:
        """Отображаемое имя клиента"""
        user = self.user
        if user:
            full_name = getattr(user, "full_name", "") or ""
            email = getattr(user, "email", "") or ""
            return full_name or email
        return self.customer_name or self.customer_email

    @property
    def total_items(self) -> int:
        """Общее количество товаров в заказе"""
        return sum(item.quantity for item in self.items.all())

    @property
    def calculated_total(self) -> Decimal:
        """Рассчитанная общая сумма заказа"""
        return Decimal(sum(item.total_price for item in self.items.all()))

    @property
    def can_be_cancelled(self) -> bool:
        """Можно ли отменить заказ"""
        return self.status in ["pending", "confirmed"]

    def can_be_refunded(self) -> bool:
        """Можно ли вернуть заказ"""
        return self.status in ["delivered"] and self.payment_status == "paid"


class CustomerOrderSequence(models.Model):
    objects = models.Manager()

    if TYPE_CHECKING:
        customer_code: str
        year: int
        last_sequence: int

    customer_code = cast(str, models.CharField("Код клиента", max_length=5))
    year = cast(int, models.PositiveSmallIntegerField("Год"))
    last_sequence = cast(int, models.PositiveSmallIntegerField("Последняя последовательность", default=0))

    class Meta:
        verbose_name = "Счетчик заказов клиента"
        verbose_name_plural = "Счетчики заказов клиентов"
        db_table = "customer_order_sequences"
        constraints = [
            models.UniqueConstraint(fields=["customer_code", "year"], name="uniq_customer_order_sequence"),
        ]

    def __str__(self) -> str:
        return f"{self.customer_code}-{self.year}: {self.last_sequence}"


class OrderItem(models.Model):
    """Элемент заказа с информацией о товаре и зафиксированной цене."""

    objects = models.Manager()

    if TYPE_CHECKING:
        order: Order
        product: ProductType | None
        variant: ProductVariantType | None
        quantity: int
        unit_price: Decimal
        total_price: Decimal
        product_name: str
        product_sku: str
        variant_info: str
        vat_rate: "Decimal | None"
        created_at: datetime
        updated_at: datetime

    order = cast(
        Order,
        models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items", verbose_name="Заказ"),
    )
    product = cast(
        "ProductType | None",
        models.ForeignKey("products.Product", on_delete=models.CASCADE, verbose_name="Товар"),
    )
    variant = cast(
        "ProductVariantType | None",
        models.ForeignKey(
            "products.ProductVariant",
            on_delete=models.SET_NULL,
            null=True,
            blank=True,
            verbose_name="Вариант товара",
            help_text="SKU-вариант товара (размер, цвет)",
        ),
    )
    quantity = cast(
        int,
        models.PositiveIntegerField("Количество", validators=[MinValueValidator(1)]),
    )
    unit_price = cast(
        Decimal,
        models.DecimalField(
            "Цена за единицу",
            max_digits=10,
            decimal_places=2,
            validators=[MinValueValidator(0)],
        ),
    )
    total_price = cast(
        Decimal,
        models.DecimalField(
            "Общая стоимость",
            max_digits=10,
            decimal_places=2,
            validators=[MinValueValidator(0)],
        ),
    )

    # Снимок данных о продукте на момент заказа
    product_name = cast(str, models.CharField("Название товара", max_length=300))
    product_sku = cast(str, models.CharField("Артикул товара", max_length=100))
    variant_info = cast(
        str,
        models.CharField(
            "Информация о варианте",
            max_length=200,
            blank=True,
            help_text="Размер, цвет и др. характеристики варианта",
        ),
    )
    vat_rate = cast(
        "Decimal | None",
        models.DecimalField(
            "Ставка НДС (%)",
            max_digits=5,
            decimal_places=2,
            null=True,
            blank=True,
            help_text="Снимок ставки НДС варианта на момент создания заказа",
        ),
    )

    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        """Метаданные Django ORM для модели `OrderItem`."""

        verbose_name = "Элемент заказа"
        verbose_name_plural = "Элементы заказа"
        db_table = "order_items"
        unique_together = ("order", "variant")
        indexes = [
            models.Index(fields=["order", "variant"]),
        ]

    @staticmethod
    def build_snapshot(product: "ProductType | None", variant: "ProductVariantType | None") -> dict:
        """Формирует словарь snapshot-полей из продукта и варианта.

        Используется в save() и OrderCreateSerializer.create() для гарантии
        единообразного формирования product_name, product_sku, variant_info, vat_rate.
        """
        parts: list[str] = []
        if variant:
            if getattr(variant, "size_value", None):
                parts.append(f"Размер: {variant.size_value}")
            if getattr(variant, "color_name", None):
                parts.append(f"Цвет: {variant.color_name}")
        raw_vat = getattr(variant, "vat_rate", None) if variant else None
        if raw_vat is None and product is not None:
            raw_vat = getattr(product, "vat_rate", None)
        return {
            "product_name": product.name if product else "",
            "product_sku": getattr(variant, "sku", "") if variant else "",
            "variant_info": ", ".join(parts),
            "vat_rate": Decimal(str(raw_vat)) if raw_vat is not None else None,
        }

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Автоматически рассчитываем общую стоимость
        self.total_price = self.unit_price * self.quantity

        # Сохраняем снимок данных продукта (заполняем только незаполненные поля)
        if self._state.adding:
            snapshot = OrderItem.build_snapshot(self.product, self.variant)
            if not self.product_name:
                self.product_name = snapshot["product_name"]
            if not self.product_sku:
                self.product_sku = snapshot["product_sku"]
            if not self.variant_info:
                self.variant_info = snapshot["variant_info"]
            if self.vat_rate is None:
                self.vat_rate = snapshot["vat_rate"]

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        order = self.order
        order_number = getattr(order, "order_number", "")
        return f"{self.product_name} x{self.quantity} в заказе #{order_number}"
