"""
Serializers для API управления пользователями
"""

from decimal import Decimal
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core import signing
from rest_framework import serializers

from apps.orders.models import Order

from .models import Address, Company, Favorite, User
from .services.identity_resolution import CustomerIdentityResolver
from .tasks import (
    send_admin_verification_email,
    send_manager_region_email,
    send_portal_link_confirmation_email,
    send_user_pending_email,
)

PORTAL_LINK_CONFIRM_SALT = "portal-link-confirm"

PDP_CONSENT_REQUIRED_MESSAGE = "Необходимо согласие на обработку персональных данных."


class UserRegistrationSerializer(serializers.ModelSerializer):
    """
    Serializer для регистрации новых пользователей
    """

    password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    pdp_consent = serializers.BooleanField(
        write_only=True,
        required=True,
        error_messages={
            "required": PDP_CONSENT_REQUIRED_MESSAGE,
            "invalid": PDP_CONSENT_REQUIRED_MESSAGE,
            "null": PDP_CONSENT_REQUIRED_MESSAGE,
        },
    )
    marketing_consent = serializers.BooleanField(write_only=True, required=False, default=False)

    class Meta:
        model = User
        fields = [
            "email",
            "password",
            "password_confirm",
            "first_name",
            "last_name",
            "phone",
            "role",
            "company_name",
            "tax_id",
            "country",
            "pdp_consent",
            "marketing_consent",
        ]
        extra_kwargs = {
            # Уникальность email проверяется вручную в validate() через
            # CustomerIdentityResolver — это позволяет привязать регистрацию
            # к существующей 1С-записи вместо жёсткого отказа. Автогенерируемый
            # UniqueValidator сработал бы раньше validate() и заблокировал сценарий.
            "email": {"required": True, "validators": []},
            "first_name": {"required": True},
        }

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Валидация полей"""
        # Проверка совпадения паролей
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})

        if not attrs.get("pdp_consent"):
            raise serializers.ValidationError({"pdp_consent": PDP_CONSENT_REQUIRED_MESSAGE})

        # Валидация B2B полей
        role = attrs.get("role", "retail")
        if role != "retail":
            # Для B2B пользователей требуется название компании
            if not attrs.get("company_name"):
                raise serializers.ValidationError(
                    {"company_name": ("Название компании обязательно для B2B " "пользователей.")}
                )

            # Для оптовиков и представителей федерации требуется ИНН
            if role.startswith("wholesale") or role == "federation_rep":
                if not attrs.get("tax_id"):
                    raise serializers.ValidationError(
                        {"tax_id": ("ИНН обязателен для оптовых покупателей и " "представителей федерации.")}
                    )

        resolver = CustomerIdentityResolver()
        attrs["email"] = resolver.normalize_email(attrs["email"]) or attrs["email"].strip().lower()

        matched_customer, method = resolver.identify_customer({"email": attrs["email"], "tax_id": attrs.get("tax_id")})

        if matched_customer is not None:
            if (
                matched_customer.created_in_1c
                and matched_customer.verification_status == "unverified"
                and matched_customer.role != "retail"
            ):
                # B2B-клиент из 1С без пароля — привязываем регистрацию вместо
                # создания дубля (см. create()). Строго "unverified", а не
                # "!= verified": запись, уже переведённая в pending этой же
                # фичей (заявка ждёт одобрения администратора), повторно не
                # матчится — иначе второй заявитель может перезаписать пароль
                # до одобрения (round 4, 2026-07-09).
                if (
                    attrs["email"] != resolver.normalize_email(matched_customer.email)
                    and User.objects.filter(email=attrs["email"]).exists()
                ):
                    # Новый email формы уже занят другим аккаунтом — отклоняем
                    # сразу, а не на confirm-клике (иначе там IntegrityError).
                    raise serializers.ValidationError({"email": "Пользователь с таким email уже существует."})
                self._matched_1c_customer = matched_customer
            else:
                # Дубликат (портальный аккаунт/уже верифицированная 1С-запись/
                # уже pending через эту фичу) или retail-матч по email из 1С —
                # временно вне скоупа (round 3)
                if method == "tax_id":
                    raise serializers.ValidationError({"tax_id": "Компания с данным ИНН уже зарегистрирована."})
                raise serializers.ValidationError({"email": "Пользователь с таким email уже существует."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> User:
        """Создание нового пользователя"""
        # Удаляем password_confirm из данных
        validated_data.pop("password_confirm")
        marketing_consent = validated_data.pop("marketing_consent", False)
        validated_data.pop("pdp_consent")

        # Извлекаем пароль
        password = validated_data.pop("password")

        matched_customer = getattr(self, "_matched_1c_customer", None)
        if matched_customer is not None:
            return self._link_matched_1c_customer(matched_customer, validated_data["email"], password)

        # Создаем пользователя
        user = User.objects.create_user(password=password, **validated_data)

        # Устанавливаем статусы на основе роли
        if user.role == "retail":
            # Розничные покупатели получают немедленный доступ
            user.is_active = True
            user.verification_status = "verified"
            user.is_verified = True
        else:
            # B2B пользователи требуют верификации
            user.is_active = False
            user.verification_status = "pending"
            user.is_verified = False

        user.save()

        # Асинхронная отправка email уведомлений для B2B (Story 29.4)
        if user.role != "retail":
            send_admin_verification_email.delay(user.id)
            send_user_pending_email.delay(user.id)
            # Дополнительно — уведомление регионального менеджера по стране/ИНН.
            send_manager_region_email.delay(user.id)

        user._marketing_consent = marketing_consent  # type: ignore[attr-defined]
        return user

    def _link_matched_1c_customer(self, customer: User, form_email: str, password: str) -> User:
        """
        Привязывает регистрацию к существующей 1С-записи вместо создания дубля.

        "1C wins": ФИО/роль/компания формы не применяются к найденной записи.
        Email — единственное исключение, и то лишь после подтверждения владения
        новым адресом (см. PortalLinkConfirmView).
        """
        resolver = CustomerIdentityResolver()
        existing_email = resolver.normalize_email(customer.email)

        if form_email == existing_email:
            # Email совпадает — пароль и переход в pending одной атомарной
            # операцией (иначе возникает окно с рабочим паролем без блокировки
            # входа, т.к. UserLoginView проверяет только verification_status).
            customer.set_password(password)
            customer.verification_status = "pending"
            customer.save(update_fields=["password", "verification_status"])
            send_admin_verification_email.delay(customer.id)
            # Дополнительно — уведомление регионального менеджера по стране/ИНН.
            send_manager_region_email.delay(customer.id)
            customer._pending_admin_review = True  # type: ignore[attr-defined]
        else:
            # Email отличается — пароль пока не сохраняем, ссылка уходит на
            # НОВЫЙ email формы (доказывает лишь его живость).
            token = signing.dumps(
                {"user_id": customer.id, "new_email": form_email},
                salt=PORTAL_LINK_CONFIRM_SALT,
            )
            confirm_url = f"{settings.SITE_URL}/portal-link/confirm/{token}/"
            send_portal_link_confirmation_email.delay(customer.id, form_email, confirm_url)
            customer._pending_link_confirmation = True  # type: ignore[attr-defined]

        return customer


class PortalLinkConfirmSerializer(serializers.Serializer):
    """
    Serializer для подтверждения привязки 1С-клиента к регистрации на портале
    (случай, когда email формы отличался от email в 1С).
    """

    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "Пароли не совпадают."})
        return attrs


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer для входа пользователя
    """

    email = serializers.EmailField()
    password = serializers.CharField(style={"input_type": "password"})

    def validate(self, attrs):
        """Валидация данных для входа"""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        email = attrs.get("email")
        password = attrs.get("password")

        if email and password:
            # Epic 29.2: Получаем пользователя напрямую (включая неактивных)
            # для проверки verification_status в UserLoginView
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    "Неверный email или пароль.",
                    code="authorization",
                )

            # Проверяем пароль
            if not user.check_password(password):
                raise serializers.ValidationError(
                    "Неверный email или пароль.",
                    code="authorization",
                )

            # Примечание: Проверка is_active и verification_status выполняется
            # в UserLoginView для обеспечения правильной обработк (403 для pending)

            attrs["user"] = user
            return attrs
        else:
            raise serializers.ValidationError("Необходимо указать email и пароль.", code="authorization")


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer для просмотра и обновления профиля пользователя
    """

    full_name = serializers.CharField(read_only=True)
    is_b2b_user = serializers.BooleanField(read_only=True)
    is_wholesale_user = serializers.BooleanField(read_only=True)
    wholesale_level = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "full_name",
            "phone",
            "role",
            "company_name",
            "tax_id",
            "is_verified",
            "is_b2b_user",
            "is_wholesale_user",
            "wholesale_level",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "email",
            "role",
            "is_verified",
            "created_at",
            "updated_at",
        ]

    def validate_tax_id(self, value):
        """Валидация ИНН"""
        if value:
            # Простая валидация длины ИНН (10 или 12 цифр)
            if not value.isdigit() or len(value) not in [10, 12]:
                raise serializers.ValidationError("ИНН должен содержать 10 или 12 цифр.")
        return value

    def to_representation(self, instance):
        """Conditionally remove company_name and tax_id for non-B2B users."""
        ret = super().to_representation(instance)
        if not instance.is_b2b_user:
            ret.pop("company_name", None)
            ret.pop("tax_id", None)
        return ret


class AddressSerializer(serializers.ModelSerializer):
    """
    Serializer для адресов пользователя
    """

    full_address = serializers.CharField(read_only=True)

    class Meta:
        model = Address
        fields = [
            "id",
            "address_type",
            "full_name",
            "phone",
            "city",
            "street",
            "building",
            "apartment",
            "postal_code",
            "is_default",
            "full_address",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_postal_code(self, value):
        """Валидация почтового индекса"""
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Почтовый индекс должен содержать 6 цифр.")
        return value

    def save(self, **kwargs):
        """Автоматически устанавливаем пользователя из контекста"""
        if "user" in self.context:
            kwargs["user"] = self.context["user"]
        return super().save(**kwargs)


class CompanySerializer(serializers.ModelSerializer):
    """
    Serializer для компании B2B пользователя
    """

    class Meta:
        model = Company
        fields = [
            "id",
            "legal_name",
            "tax_id",
            "kpp",
            "legal_address",
            "bank_name",
            "bank_bik",
            "account_number",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_tax_id(self, value):
        """Валидация ИНН компании"""
        if not value.isdigit() or len(value) not in [10, 12]:
            raise serializers.ValidationError("ИНН должен содержать 10 или 12 цифр.")
        return value

    def validate_kpp(self, value):
        """Валидация КПП"""
        if value and (not value.isdigit() or len(value) != 9):
            raise serializers.ValidationError("КПП должен содержать 9 цифр.")
        return value


class UserDashboardSerializer(serializers.Serializer):
    """
    Serializer для персонального дашборда пользователя
    """

    user_info = UserProfileSerializer(read_only=True)
    orders_count = serializers.IntegerField(read_only=True)
    favorites_count = serializers.IntegerField(read_only=True)
    addresses_count = serializers.IntegerField(read_only=True)

    # Дополнительная статистика для B2B
    total_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, required=False)
    avg_order_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True, required=False)

    # Статус верификации для B2B
    verification_status = serializers.CharField(read_only=True, required=False)

    def to_representation(self, instance: Any) -> dict[str, Any]:
        """Conditionally remove B2B fields for non-B2B users."""
        ret = cast(dict[str, Any], super().to_representation(instance))
        user = instance.user_info
        if user and not user.is_b2b_user:
            ret.pop("total_order_amount", None)
            ret.pop("avg_order_amount", None)
            ret.pop("verification_status", None)
        return ret


class FavoriteSerializer(serializers.ModelSerializer):
    """
    Serializer для избранных товаров.

    Данные о цене, SKU и изображении получаются из первого активного
    ProductVariant, т.к. эти поля хранятся на уровне варианта, а не Product.
    """

    product_name = serializers.CharField(source="product.name", read_only=True)
    product_price = serializers.SerializerMethodField()
    product_image = serializers.SerializerMethodField()
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    product_sku = serializers.SerializerMethodField()

    class Meta:
        model = Favorite
        fields = [
            "id",
            "product",
            "product_name",
            "product_price",
            "product_image",
            "product_slug",
            "product_sku",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def _get_first_active_variant(self, product: Any) -> Any:
        """Получить первый активный вариант товара."""
        return product.variants.filter(is_active=True).first()

    def get_product_price(self, obj: Favorite) -> str | None:
        """
        Получить розничную цену из первого активного варианта товара.
        Возвращает строку для совместимости с DecimalField.
        """
        variant = self._get_first_active_variant(obj.product)
        if variant and variant.retail_price is not None:
            return str(variant.retail_price)
        return None

    def get_product_sku(self, obj: Favorite) -> str | None:
        """
        Получить SKU из первого активного варианта товара.
        """
        variant = self._get_first_active_variant(obj.product)
        if variant:
            return str(variant.sku)
        return None

    def get_product_image(self, obj: Favorite) -> str | None:
        """
        Получить изображение товара из ProductVariant или Product.base_images.
        Epic 13/14: изображения хранятся в ProductVariant.main_image
        с fallback на Product.base_images.
        """
        product = obj.product
        # Пробуем получить изображение из первого активного варианта
        first_variant = self._get_first_active_variant(product)
        if first_variant and first_variant.main_image:
            return str(first_variant.main_image)
        # Fallback на base_images
        if product.base_images and len(product.base_images) > 0:
            return str(product.base_images[0])
        return None


class FavoriteCreateSerializer(serializers.ModelSerializer):
    """
    Serializer для добавления товара в избранное
    """

    class Meta:
        model = Favorite
        fields = ["product"]

    def validate_product(self, value):
        """Проверка существования товара"""
        from apps.products.models import Product

        if not Product.objects.filter(id=value.id, is_active=True).exists():
            raise serializers.ValidationError("Товар не найден или недоступен.")
        return value

    def validate(self, attrs):
        """Проверка на дублирование в избранном"""
        user = self.context["request"].user
        product = attrs["product"]

        if Favorite.objects.filter(user=user, product=product).exists():
            raise serializers.ValidationError({"product": "Товар уже добавлен в избранное."})

        return attrs

    def create(self, validated_data):
        """Создание записи в избранном"""
        validated_data["user"] = self.context["request"].user
        return super().create(validated_data)


class OrderHistorySerializer(serializers.ModelSerializer):
    """
    Serializer для истории заказов пользователя
    """

    items_count = serializers.SerializerMethodField()
    customer_display_name = serializers.ReadOnlyField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "total_amount",
            "discount_amount",
            "delivery_cost",
            "items_count",
            "customer_display_name",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_items_count(self, obj: Order) -> int:
        """Получение количества товаров в заказе"""
        return int(obj.total_items)


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Serializer для запроса на сброс пароля
    """

    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        """Нормализация email"""
        return value.lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Serializer для подтверждения сброса пароля
    """

    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(
        write_only=True,
        validators=[validate_password],
        style={"input_type": "password"},
    )

    def validate_new_password(self, value: str) -> str:
        """Валидация нового пароля"""
        return value


class ValidateTokenSerializer(serializers.Serializer):
    """
    Serializer для валидации токена сброса пароля
    """

    uid = serializers.CharField()
    token = serializers.CharField()


class LogoutSerializer(serializers.Serializer):
    """
    Serializer для logout endpoint.

    Валидирует refresh token для его инвалидации через blacklist механизм.
    """

    refresh = serializers.CharField(required=True, help_text="Refresh token для инвалидации")

    def validate_refresh(self, value: str) -> str:
        """Валидация refresh токена"""
        if not value:
            raise serializers.ValidationError("Refresh token не может быть пустым")
        return value
