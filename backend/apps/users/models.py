"""
Модели пользователей для платформы FREESPORT
Включает кастомную User модель с ролевой системой B2B/B2C
"""

from typing import TYPE_CHECKING, Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import RegexValidator
from django.db import models

if TYPE_CHECKING:
    pass  # Используется для type hints


class UserManager(BaseUserManager["User"]):
    """
    Кастомный менеджер для модели User с email аутентификацией
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        """Создание обычного пользователя"""
        if not email:
            raise ValueError("Email обязателен для создания пользователя")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> "User":
        """Создание суперпользователя"""
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True.")

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Кастомная модель пользователя с email аутентификацией
    Поддерживает роли для B2B и B2C пользователей
    """

    if TYPE_CHECKING:
        # Type hints для автогенерируемых Django методов
        def get_role_display(self) -> str:
            """Отображение названия роли пользователя"""
            role_map = {
                "retail": "Розничный покупатель",
                "wholesale_level1": "Оптовик уровень 1",
                "wholesale_level2": "Оптовик уровень 2",
                "wholesale_level3": "Оптовик уровень 3",
                "trainer": "Тренер/Фитнес-клуб",
                "federation_rep": "Представитель федерации",
                "admin": "Администратор",
            }
            return role_map.get(self.role, self.role)

    # Роли пользователей согласно архитектурной документации
    ROLE_CHOICES = [
        ("retail", "Розничный покупатель"),
        ("wholesale_level1", "Оптовик уровень 1"),
        ("wholesale_level2", "Оптовик уровень 2"),
        ("wholesale_level3", "Оптовик уровень 3"),
        ("trainer", "Тренер/Фитнес-клуб"),
        ("federation_rep", "Представитель федерации"),
        ("admin", "Администратор"),
    ]

    # Убираем username, используем email для авторизации
    username = None  # type: ignore[assignment]
    email: models.EmailField = models.EmailField("Email адрес", unique=True, blank=True, null=True)

    # Дополнительные поля
    role = models.CharField(
        "Роль пользователя",
        max_length=20,
        choices=ROLE_CHOICES,
        default="retail",
    )

    phone_regex = RegexValidator(
        regex=r"^\+7\d{10}$",
        message="Номер телефона должен быть в формате: '+79001234567'",
    )
    phone = models.CharField(
        "Номер телефона",
        validators=[phone_regex],
        max_length=255,  # Увеличено для поддержки нескольких телефонов из 1С
        blank=True,
    )

    # B2B поля
    company_name = models.CharField(
        "Название компании",
        max_length=200,
        blank=True,
        help_text="Для B2B пользователей",
    )

    tax_id = models.CharField("ИНН", max_length=12, blank=True, help_text="ИНН для B2B пользователей")

    # Статус верификации для B2B
    is_verified = models.BooleanField(
        "Верифицирован",
        default=False,
        help_text="B2B пользователи требуют верификации администратором",
    )

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    # 1C Integration fields
    SYNC_STATUS_CHOICES = [
        ("pending", "Ожидает синхронизации"),
        ("synced", "Синхронизирован"),
        ("error", "Ошибка синхронизации"),
        ("conflict", "Конфликт данных"),
    ]

    VERIFICATION_STATUS_CHOICES = [
        ("unverified", "Не верифицирован"),
        ("verified", "Верифицирован"),
        ("pending", "Ожидает верификации"),
    ]

    onec_id = models.CharField(
        "ID в 1С",
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Уникальный идентификатор клиента в 1С",
    )
    onec_guid = models.UUIDField(
        "GUID в 1С",
        blank=True,
        null=True,
        unique=True,
        help_text="Уникальный GUID клиента в 1С",
    )
    sync_status = models.CharField(
        "Статус синхронизации",
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default="pending",
        help_text="Статус синхронизации с 1С",
    )
    created_in_1c = models.BooleanField(
        "Создан в 1С",
        default=False,
        help_text="Указывает, что пользователь был создан в 1С",
    )
    needs_1c_export = models.BooleanField(
        "Требует экспорта в 1С",
        default=False,
        help_text="Требует экспорта данных в 1С",
    )
    last_sync_at = models.DateTimeField(
        "Последняя синхронизация",
        null=True,
        blank=True,
        help_text="Дата и время последней синхронизации с 1С",
    )
    last_sync_from_1c = models.DateTimeField(
        "Последняя синхронизация из 1С",
        null=True,
        blank=True,
        help_text="Дата и время последнего импорта данных из 1С",
    )
    sync_error_message = models.TextField(
        "Ошибка синхронизации",
        blank=True,
        help_text="Сообщение об ошибке при синхронизации с 1С",
    )
    verification_status = models.CharField(
        "Статус верификации",
        max_length=20,
        choices=VERIFICATION_STATUS_CHOICES,
        default="unverified",
        help_text="Статус верификации клиента из 1С",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects: UserManager = UserManager()  # type: ignore[misc,assignment]

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"
        db_table = "users"

    def __str__(self) -> str:
        return f"{self.email or ''} ({self.get_role_display()})"

    @property
    def full_name(self) -> str:
        """Полное имя пользователя"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_b2b_user(self) -> bool:
        """Является ли пользователь B2B клиентом"""
        b2b_roles = [
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "trainer",
            "federation_rep",
        ]
        return self.role in b2b_roles

    @property
    def is_wholesale_user(self) -> bool:
        """Является ли пользователь оптовым покупателем"""
        wholesale_roles = [
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
        ]
        return self.role in wholesale_roles

    @property
    def wholesale_level(self) -> int | None:
        """Возвращает уровень оптового покупателя (1, 2, 3) или None"""
        if self.role.startswith("wholesale_level"):
            # Извлекаем число из 'wholesale_level1', 'wholesale_level2', etc.
            level_part = self.role.replace("wholesale_level", "")
            return int(level_part) if level_part.isdigit() else None
        return None


class Company(models.Model):
    """
    Модель компании для B2B пользователей
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company",
        verbose_name="Пользователь",
    )

    legal_name = models.CharField("Юридическое название", max_length=255, blank=True)
    tax_id = models.CharField("ИНН", max_length=12, blank=True)
    kpp = models.CharField("КПП", max_length=9, blank=True)
    legal_address = models.TextField("Юридический адрес", blank=True)

    # Банковские реквизиты
    bank_name = models.CharField("Название банка", max_length=200, blank=True)
    bank_bik = models.CharField("БИК банка", max_length=9, blank=True)
    account_number = models.CharField("Расчетный счет", max_length=20, blank=True)

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Компания"
        verbose_name_plural = "Компании"
        db_table = "companies"

    def __str__(self) -> str:
        return f"{self.legal_name} (ИНН: {self.tax_id})"


class Address(models.Model):
    """
    Модель адресов для пользователей
    """

    ADDRESS_TYPES = [
        ("shipping", "Адрес доставки"),
        ("legal", "Юридический адрес"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="addresses",
        verbose_name="Пользователь",
    )

    address_type = models.CharField("Тип адреса", max_length=10, choices=ADDRESS_TYPES, default="shipping")

    full_name = models.CharField("Полное имя получателя", max_length=100)
    phone = models.CharField("Телефон", max_length=12)
    city = models.CharField("Город", max_length=100)
    street = models.CharField("Улица", max_length=200)
    building = models.CharField("Дом", max_length=10)
    building_section = models.CharField("Корпус/строение", max_length=20, blank=True)
    apartment = models.CharField("Квартира/офис", max_length=10, blank=True)
    postal_code = models.CharField("Почтовый индекс", max_length=6)

    is_default = models.BooleanField("Адрес по умолчанию", default=False)

    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Адрес"
        verbose_name_plural = "Адреса"
        db_table = "addresses"
        # Убираем неправильное unique_together ограничение

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Переопределяем save для корректной логики is_default.
        Если этот адрес устанавливается как основной, снимаем флаг
        со всех других адресов того же типа для этого пользователя.
        """
        # Обрабатываем логику is_default перед сохранением
        if self.is_default and hasattr(self, "user") and self.user:
            # Сбросить флаг is_default у всех других адресов
            # этого же типа для этого пользователя
            Address.objects.filter(user=self.user, address_type=self.address_type).exclude(pk=self.pk).update(
                is_default=False
            )

        # Сохраняем объект
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.full_name} - {self.city}, {self.street} {self.building}"

    @property
    def full_address(self) -> str:
        """Полный адрес строкой"""
        parts = [self.postal_code, self.city, self.street, self.building]
        if self.building_section:
            parts.append(f"корп. {self.building_section}")
        if self.apartment:
            parts.append(f"кв. {self.apartment}")
        return ", ".join(parts)


class Favorite(models.Model):
    """
    Модель избранных товаров пользователей
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="favorites",
        verbose_name="Пользователь",
    )

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="favorited_by",
        verbose_name="Товар",
    )

    created_at = models.DateTimeField("Дата добавления", auto_now_add=True)

    class Meta:
        verbose_name = "Избранное"
        verbose_name_plural = "Избранные товары"
        db_table = "favorites"
        unique_together = ("user", "product")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.user.email or ''} - {self.product.name}"
