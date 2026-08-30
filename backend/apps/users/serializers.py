"""
Serializers для API управления пользователями
"""

import logging
import re
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

logger = logging.getLogger(__name__)

PORTAL_LINK_CONFIRM_SALT = "portal-link-confirm"

PDP_CONSENT_REQUIRED_MESSAGE = "Необходимо согласие на обработку персональных данных."

INVALID_SELF_SERVICE_ROLE_MESSAGE = "Недопустимая роль для регистрации."


def get_self_service_roles() -> frozenset[str]:
    """
    Роли, которые заявитель вправе выбрать себе сам при регистрации.

    Это именно белый список, а не запрет отдельных ролей: `admin` дал бы метку
    администратора в интерфейсе, `unregistered` ставит только импорт 1С, и такой
    аккаунт не попал бы в admin-действие верификации (оно фильтрует B2B-роли).

    Базой служит `User.B2B_ROLES` — тот же источник истины, что у `is_b2b_user`
    и admin-действий, иначе списки разошлись бы при добавлении новой роли.
    Розница добавляется флагом `REGISTRATION_ALLOW_RETAIL`: сейчас она выключена
    (портал — B2B-площадка), но отключение временное, поэтому включение не должно
    требовать релиза. Единый источник для choices поля `role`, серверной проверки
    и ответа GET /api/v1/users/roles/.
    """
    roles = set(User.B2B_ROLES)

    if getattr(settings, "REGISTRATION_ALLOW_RETAIL", False):
        roles.add("retail")

    return frozenset(roles)


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
    # Роль объявлена явно, чтобы схема API перечисляла ровно то, что принимает
    # сервер: модельное поле дало бы все значения ROLE_CHOICES, включая admin и
    # unregistered. Список подставляется в __init__ — он зависит от настройки.
    role = serializers.ChoiceField(
        choices=[],
        required=True,
        error_messages={"invalid_choice": INVALID_SELF_SERVICE_ROLE_MESSAGE},
    )
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
            # Уникальность email проверяется вручную в validate(): порядок
            # проверок важен, сообщение об уже занятом адресе должно быть
            # единым для портальных аккаунтов и импортированных записей 1С.
            # Автогенерируемый UniqueValidator сработал бы раньше validate().
            "email": {"required": True, "validators": []},
            "first_name": {"required": True},
        }

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Список читается на каждое создание сериализатора, а не на импорт
        # модуля: иначе смена REGISTRATION_ALLOW_RETAIL (в том числе через
        # override_settings в тестах) не дошла бы до поля.
        # Пары (значение, подпись) из ROLE_CHOICES: плоский список ролей дал бы
        # в схеме подписи вида «trainer - trainer» вместо человекочитаемых.
        allowed = get_self_service_roles()
        self.fields["role"].choices = [choice for choice in User.ROLE_CHOICES if choice[0] in allowed]

    def validate_role(self, value: str) -> str:
        """
        Разрешает при регистрации только клиентские роли.

        Дублирует проверку `ChoiceField` намеренно: поле отсекает значение по
        списку, зафиксированному при создании сериализатора, а этот метод
        сверяется с актуальным. Роль обязательна (`required=True`) — у модели
        есть default="retail", и без этого запрос без поля создал бы розничный
        аккаунт в обход запрета.
        """
        if value not in get_self_service_roles():
            raise serializers.ValidationError(INVALID_SELF_SERVICE_ROLE_MESSAGE)
        return value

    def validate_tax_id(self, value: str) -> str:
        """
        Нормализация ИНН: остаются только ASCII-цифры.

        Разделители и пробелы (частый случай при копировании из счёта или 1С)
        убираются здесь, поэтому в поиске кандидатов и в БД оказывается
        значение, которое найдётся точным сравнением.
        Длина проверяется в validate(), т.к. зависит от страны регистрации.
        """
        if not value:
            return value

        return re.sub(r"[^0-9]", "", value)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Валидация полей"""
        # Проверка совпадения паролей
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Пароли не совпадают."})

        if not attrs.get("pdp_consent"):
            raise serializers.ValidationError({"pdp_consent": PDP_CONSENT_REQUIRED_MESSAGE})

        # Валидация B2B полей
        role = attrs.get("role", "retail")
        if role == "retail":
            # У розничного покупателя ИНН не запрашивается. Значение, оставшееся
            # в форме после переключения роли, отбрасываем: иначе матч по ИНН
            # (приоритет выше email) привязал бы заявку к чужому юрлицу из 1С.
            attrs["tax_id"] = ""
        else:
            # Для B2B пользователей требуется название компании
            if not attrs.get("company_name"):
                raise serializers.ValidationError(
                    {"company_name": ("Название компании обязательно для B2B " "пользователей.")}
                )

            # ИНН требуется для всех B2B ролей, включая trainer: по нему
            # менеджер сверяет заявку с контрагентом 1С при верификации, и по
            # нему же определяется региональный менеджер (region_routing).
            tax_id = attrs.get("tax_id")
            if not tax_id:
                raise serializers.ValidationError({"tax_id": "ИНН обязателен для B2B пользователей."})

            # Маска российского ИНН применима только к клиентам из РФ:
            # у Беларуси УНП — 9 цифр, у Казахстана БИН/ИИН — 12.
            if attrs.get("country", User.COUNTRY_RUSSIA) == User.COUNTRY_RUSSIA:
                if len(tax_id) not in [10, 12]:
                    raise serializers.ValidationError({"tax_id": "ИНН должен содержать 10 или 12 цифр."})
            elif not 8 <= len(tax_id) <= 12:
                raise serializers.ValidationError({"tax_id": "Налоговый номер должен содержать от 8 до 12 цифр."})

        resolver = CustomerIdentityResolver()
        attrs["email"] = resolver.normalize_email(attrs["email"]) or attrs["email"].strip().lower()

        # Email — единственный признак, по которому регистрация отклоняется
        # как дубль аккаунта: он уникален и принадлежит конкретному человеку.
        if User.objects.filter(email=attrs["email"]).exists():
            raise serializers.ValidationError({"email": "Пользователь с таким email уже существует."})

        # ИНН публичен (ЕГРЮЛ, счета, сайт компании), поэтому сам по себе
        # правом на контрагента 1С не является: заявка не привязывается к
        # найденной записи и ничего в ней не меняет. Связывание с 1С выполняет
        # менеджер при верификации — он сверяет реквизиты вне портала.
        if tax_id := attrs.get("tax_id"):
            self._reject_if_tax_id_belongs_to_account(resolver, tax_id)

        return attrs

    def _reject_if_tax_id_belongs_to_account(self, resolver: CustomerIdentityResolver, tax_id: str) -> None:
        """
        Отклоняет регистрацию, если ИНН уже принадлежит живому аккаунту.

        Записи, импортированные из 1С и не заведённые на портале, регистрацию
        не блокируют: по одному ИНН в 1С заводят десятки контрагентов
        (филиалы, точки, договоры), и отказ закрыл бы вход всей компании.
        """
        # Нормализация не через resolver.normalize_inn: тот принимает только
        # 10 и 12 цифр, а validate() допускает 8-12 для Беларуси и Казахстана,
        # и 9-значный УНП молча проскакивал бы проверку дублей.
        # validate_tax_id уже оставил в значении одни цифры.
        normalized_inn = tax_id.strip()
        if not normalized_inn:
            return

        candidates = resolver.find_by_tax_id(normalized_inn)
        if not candidates:
            return

        if any(not candidate.is_unlinked_1c_record for candidate in candidates):
            raise serializers.ValidationError({"tax_id": "Компания с данным ИНН уже зарегистрирована."})

        # Заявку пропускаем, но менеджеру нужен след: с каким контрагентом 1С
        # её предстоит связать при одобрении.
        logger.info(
            "Регистрация по ИНН %s: найдено %s непривязанных записей 1С (id=%s), связывание вручную",
            normalized_inn,
            len(candidates),
            [candidate.id for candidate in candidates],
        )

    def create(self, validated_data: dict[str, Any]) -> User:
        """Создание нового пользователя"""
        # Удаляем password_confirm из данных
        validated_data.pop("password_confirm")
        marketing_consent = validated_data.pop("marketing_consent", False)
        validated_data.pop("pdp_consent")

        # Извлекаем пароль
        password = validated_data.pop("password")

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
        НЕ ИСПОЛЬЗУЕТСЯ. Автопривязка отключена 2026-07-26.

        Метод ставил пароль на запись 1С, найденную по ИНН, а при несовпадении
        email отправлял ссылку подтверждения на адрес заявителя и затем
        переписывал на него email записи. ИНН публичен, а email заполнен лишь
        у 149 из 4606 записей 1С — то есть знание одного ИНН позволяло занять
        контрагента чужой компании.

        Оставлен в коде вместе с PortalLinkConfirmView по решению 2026-07-26:
        привязку могут вернуть, но только с настоящим доказательством права
        на компанию. Вызовов нет — регистрация создаёт обычную заявку.
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
