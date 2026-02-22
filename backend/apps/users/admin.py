"""
Django Admin конфигурация для управления пользователями
Включает UserAdmin с поддержкой B2B верификации и интеграции с 1С
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html

from apps.common.models import AuditLog

from .models import Address, Company, Favorite, User


class CompanyInline(admin.StackedInline):
    """Inline для отображения информации о компании B2B пользователя"""

    model = Company
    can_delete = False
    verbose_name = "Информация о компании"
    verbose_name_plural = "Информация о компании"
    classes = ["collapse"]  # Скрыт по умолчанию

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "legal_name",
                    "tax_id",
                    "kpp",
                    "legal_address",
                )
            },
        ),
        (
            "Банковские реквизиты",
            {
                "fields": (
                    "bank_name",
                    "bank_bik",
                    "account_number",
                ),
                "classes": ("collapse",),
            },
        ),
    )


class AddressInline(admin.TabularInline):
    """Inline для отображения адресов пользователя"""

    model = Address
    extra = 0
    fields = (
        "address_type",
        "full_name",
        "phone",
        "city",
        "street",
        "building",
        "building_section",
        "apartment",
        "is_default",
    )
    readonly_fields = ("created_at",)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Кастомный Admin для модели User с поддержкой:
    - B2B верификации
    - Интеграции с 1С
    - Массовых операций (approve, reject, block)
    - AuditLog для критичных действий
    """

    # Оптимизация N+1 queries
    list_select_related = ["company"]

    # Удобный выбор групп и разрешений (two-panel selector)
    filter_horizontal = ("groups", "user_permissions")

    # Отображение в списке
    list_display = [
        "email",
        "full_name",
        "role_display",
        "verification_status_display",
        "phone",
        "created_at",
    ]

    # Фильтры
    list_filter = [
        "role",
        "is_verified",
        "verification_status",
        "created_at",
        "is_active",
        "is_staff",
    ]

    # Поиск
    search_fields = [
        "email",
        "first_name",
        "last_name",
        "phone",
        "company_name",
        "tax_id",
    ]

    # Сортировка по умолчанию
    ordering = ["-created_at"]

    # Readonly поля (integration данные)
    readonly_fields = [
        "onec_id",
        "onec_guid",
        "last_sync_at",
        "last_sync_from_1c",
        "created_at",
        "updated_at",
        "company_legal_address",
    ]

    # Fieldsets для детального просмотра/редактирования
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "phone",
                )
            },
        ),
        (
            "B2B данные",
            {
                "fields": (
                    "company_name",
                    "tax_id",
                    "company_legal_address",
                    "is_verified",
                    "verification_status",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Роль и статус",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        (
            "Права доступа",
            {
                "fields": (
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
                "description": "Группы определяют набор прав для пользователя. "
                "Пользователь получает все права, назначенные каждой из его групп.",
            },
        ),
        (
            "Интеграция с 1С",
            {
                "fields": (
                    "onec_id",
                    "onec_guid",
                    "sync_status",
                    "created_in_1c",
                    "needs_1c_export",
                    "last_sync_at",
                    "last_sync_from_1c",
                    "sync_error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Временные метки",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "last_login",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Fieldsets для создания нового пользователя
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "password1",
                    "password2",
                    "role",
                ),
            },
        ),
    )

    # Inlines
    inlines = [CompanyInline, AddressInline]

    # Admin actions
    actions = [
        "approve_b2b_users",
        "reject_b2b_users",
        "block_users",
    ]

    # Custom display methods

    @admin.display(description="Юридический адрес компании")
    def company_legal_address(self, obj: User) -> str:
        """Отображение юридического адреса из связанной компании"""
        if hasattr(obj, "company") and obj.company:
            return obj.company.legal_address or "-"
        return "-"

    @admin.display(description="ФИО")
    def full_name(self, obj: User) -> str:
        """Отображение полного имени пользователя"""
        return obj.full_name or "-"

    @admin.display(description="Роль")
    def role_display(self, obj: User) -> str:
        """Отображение роли с цветовой индикацией"""
        role_colors = {
            "retail": "#6c757d",  # серый
            "wholesale_level1": "#0dcaf0",  # голубой
            "wholesale_level2": "#0d6efd",  # синий
            "wholesale_level3": "#6610f2",  # фиолетовый
            "trainer": "#198754",  # зеленый
            "federation_rep": "#fd7e14",  # оранжевый
            "admin": "#dc3545",  # красный
        }
        color = role_colors.get(obj.role, "#6c757d")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_role_display(),
        )

    @admin.display(description="Статус верификации")
    def verification_status_display(self, obj: User) -> str:
        """Отображение статуса верификации с иконками"""
        if obj.verification_status == "verified" or obj.is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> Верифицирован',
                "",
            )
        elif obj.verification_status == "pending":
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳</span> Ожидает',
                "",
            )
        else:
            return format_html(
                '<span style="color: gray;">○</span> Не верифицирован',
                "",
            )

    # Admin actions с permissions и AuditLog

    @admin.action(description="✓ Верифицировать выбранных B2B пользователей")
    def approve_b2b_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовая верификация B2B пользователей"""
        # Input validation: проверка наличия B2B пользователей
        b2b_users = queryset.filter(
            role__in=[
                "wholesale_level1",
                "wholesale_level2",
                "wholesale_level3",
                "trainer",
                "federation_rep",
            ]
        )

        if not b2b_users.exists():
            self.message_user(
                request,
                "Не выбрано ни одного B2B пользователя для верификации",
                level="warning",
            )
            return

        # Проверка на суперпользователей
        if b2b_users.filter(is_superuser=True).exists():
            self.message_user(
                request,
                "Нельзя изменять статус верификации суперпользователей",
                level="error",
            )
            return

        count = 0
        for user in b2b_users:
            user.is_verified = True
            user.verification_status = "verified"
            user.save(update_fields=["is_verified", "verification_status", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="approve_b2b",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "verified": True,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(
            request,
            f"Успешно верифицировано {count} B2B пользователей",
            level="success",
        )

    @admin.action(description="✗ Отклонить верификацию выбранных B2B пользователей")
    def reject_b2b_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовый отказ в верификации B2B пользователей"""
        # Input validation: проверка наличия B2B пользователей
        b2b_users = queryset.filter(
            role__in=[
                "wholesale_level1",
                "wholesale_level2",
                "wholesale_level3",
                "trainer",
                "federation_rep",
            ]
        )

        if not b2b_users.exists():
            self.message_user(
                request,
                "Не выбрано ни одного B2B пользователя для отклонения",
                level="warning",
            )
            return

        # Проверка на суперпользователей
        if b2b_users.filter(is_superuser=True).exists():
            self.message_user(
                request,
                "Нельзя изменять статус верификации суперпользователей",
                level="error",
            )
            return

        count = 0
        for user in b2b_users:
            user.is_verified = False
            user.verification_status = "unverified"
            user.save(update_fields=["is_verified", "verification_status", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="reject_b2b",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "verified": False,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(request, f"Отклонена верификация {count} B2B пользователей", level="warning")

    @admin.action(description="🚫 Заблокировать выбранных пользователей")
    def block_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовая блокировка пользователей"""
        # Input validation: проверка наличия пользователей для блокировки
        if not queryset.exists():
            self.message_user(
                request,
                "Не выбрано ни одного пользователя для блокировки",
                level="warning",
            )
            return

        # Фильтруем суперпользователей
        users_to_block = queryset.exclude(is_superuser=True)

        if not users_to_block.exists():
            self.message_user(
                request,
                "Нельзя блокировать суперпользователей",
                level="error",
            )
            return

        count = 0
        for user in users_to_block:
            if user.is_superuser:
                continue  # Дополнительная защита

            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="block_user",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "blocked": True,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(request, f"Заблокировано {count} пользователей", level="success")

    # Helper methods

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
        return str(ip)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin для модели Company"""

    list_display = ["legal_name", "tax_id", "user", "created_at"]
    search_fields = ["legal_name", "tax_id", "user__email"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin для модели Address"""

    list_display = ["user", "address_type", "city", "is_default", "created_at"]
    list_filter = ["address_type", "is_default", "city"]
    search_fields = ["user__email", "full_name", "city", "street"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Admin для модели Favorite"""

    list_display = ["user", "product", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "product__name"]
    readonly_fields = ["created_at"]
