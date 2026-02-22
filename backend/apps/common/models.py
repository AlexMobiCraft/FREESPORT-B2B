from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    pass  # Используется для type hints


class TimeStampedModel(models.Model):
    """Абстрактная модель с полями created_at и updated_at."""

    created_at: models.DateTimeField = models.DateTimeField(
        _("Дата создания"),
        auto_now_add=True,
        help_text="Дата и время создания записи",
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        _("Дата обновления"),
        auto_now=True,
        help_text="Дата и время последнего обновления записи",
    )

    class Meta:
        abstract = True


class SyncLog(TimeStampedModel):
    """Базовая модель для логов синхронизации."""

    sync_type = models.CharField(
        _("Тип синхронизации"),
        max_length=50,
        db_index=True,
        help_text="Тип операции синхронизации (импорт, экспорт и т.д.)",
    )
    status = models.CharField(
        _("Статус"),
        max_length=20,
        db_index=True,
        help_text="Текущий статус операции",
    )
    started_at: models.DateTimeField = models.DateTimeField(
        _("Начало"),
        auto_now_add=True,
        db_index=True,
        help_text="Время начала операции",
    )
    completed_at: models.DateTimeField = models.DateTimeField(
        _("Завершение"),
        null=True,
        blank=True,
        help_text="Время завершения операции (успешно)",
    )
    records_processed = models.PositiveIntegerField(
        _("Обработано записей"),
        default=0,
        help_text="Количество обработанных записей",
    )
    errors_count = models.PositiveIntegerField(
        _("Количество ошибок"),
        default=0,
        help_text="Количество обнаруженных ошибок",
    )
    error_details = models.JSONField(
        _("Детали ошибок"),
        default=dict,
        blank=True,
        help_text="Детальная информация об ошибках в формате JSON",
    )
    duration_ms = models.PositiveIntegerField(
        _("Длительность (мс)"),
        null=True,
        blank=True,
        help_text="Время выполнения в миллисекундах",
    )
    correlation_id = models.UUIDField(
        _("ID корреляции"),
        unique=True,
        db_index=True,
        null=True,
        blank=True,
        help_text="Уникальный идентификатор для группы связанных операций",
    )

    class Meta:
        verbose_name = _("Лог синхронизации")
        verbose_name_plural = _("Логи синхронизации")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["correlation_id", "started_at"]),
            models.Index(fields=["sync_type", "status", "started_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.sync_type} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"


class CustomerSyncLog(TimeStampedModel):
    """Лог синхронизации конкретного клиента."""

    class OperationType(models.TextChoices):
        """Типы операций синхронизации."""

        CREATED = "created", _("Создан")
        UPDATED = "updated", _("Обновлен")
        SKIPPED = "skipped", _("Пропущен")
        ERROR = "error", _("Ошибка")
        IMPORT_FROM_1C = "import_from_1c", _("Импорт из 1С")
        EXPORT_TO_1C = "export_to_1c", _("Экспорт в 1С")
        CUSTOMER_IDENTIFICATION = "customer_identification", _("Идентификация клиента")
        CONFLICT_RESOLUTION = "conflict_resolution", _("Разрешение конфликта")
        SYNC_CHANGES = "sync_changes", _("Синхронизация изменений")
        BATCH_OPERATION = "batch_operation", _("Пакетная операция")
        DATA_VALIDATION = "data_validation", _("Валидация данных")
        NOTIFICATION_FAILED = "notification_failed", _("Ошибка уведомления")

    class StatusType(models.TextChoices):
        """Статусы операций синхронизации."""

        SUCCESS = "success", _("Успешно")
        FAILED = "failed", _("Ошибка")
        ERROR = "error", _("Ошибка")
        WARNING = "warning", _("Предупреждение")
        SKIPPED = "skipped", _("Пропущено")
        PENDING = "pending", _("Ожидание")

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Клиент"),
        help_text="Связанный пользователь",
    )
    operation_type = models.CharField(
        _("Тип операции"),
        max_length=50,
        choices=OperationType.choices,
        db_index=True,
        help_text="Тип операции с клиентом",
    )
    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=StatusType.choices,
        db_index=True,
        help_text="Статус операции",
    )
    details = models.JSONField(
        _("Детали"),
        default=dict,
        blank=True,
        help_text="Детальная информация об операции в формате JSON",
    )
    duration_ms = models.PositiveIntegerField(
        _("Длительность (мс)"),
        null=True,
        blank=True,
        help_text="Время выполнения в миллисекундах",
    )
    correlation_id = models.UUIDField(
        _("ID корреляции"),
        db_index=True,
        help_text="ID для группировки связанных операций",
    )
    session = models.CharField(
        _("Сессия"),
        max_length=255,
        db_index=True,
        help_text="Идентификатор сессии пользователя",
    )
    ip_address = models.GenericIPAddressField(
        _("IP адрес"),
        null=True,
        blank=True,
        help_text="IP адрес клиента",
    )
    user_agent = models.TextField(
        _("User Agent"),
        blank=True,
        help_text="User Agent строка браузера",
    )
    onec_id = models.CharField(
        _("ID в 1С"),
        max_length=36,
        db_index=True,
        help_text="Идентификатор клиента в системе 1С",
    )
    error_message = models.TextField(
        _("Сообщение об ошибке"),
        blank=True,
        help_text="Текстовое описание ошибки",
    )

    class Meta:
        verbose_name = _("Лог синхронизации клиента")
        verbose_name_plural = _("Логи синхронизации клиентов")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["correlation_id", "created_at"]),
            models.Index(fields=["customer", "operation_type", "created_at"]),
        ]

    def __str__(self) -> str:
        date_str = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.operation_type} - {self.customer} ({date_str})"

    def get_duration_display(self) -> str:
        """Отображение длительности в человекочитаемом формате."""
        if self.duration_ms is None:
            return str(_("Не определено"))

        if self.duration_ms < 1000:
            return str(_("Менее 1 секунды"))
        elif self.duration_ms < 60000:
            seconds = self.duration_ms / 1000
            return str(_(f"{seconds:.1f} сек"))
        elif self.duration_ms < 3600000:
            minutes = self.duration_ms // 60000
            seconds = (self.duration_ms % 60000) // 1000
            return str(_(f"{minutes} мин {seconds} сек"))
        else:
            hours = self.duration_ms // 3600000
            minutes = (self.duration_ms % 3600000) // 60000
            return str(_(f"{hours} ч {minutes} мин"))

    @property
    def correlation_id_short(self) -> str:
        """Короткая версия correlation_id для отображения в списках."""
        return str(self.correlation_id)[:8] + "..." if self.correlation_id else "-"

    @property
    def customer_email(self) -> str:
        """Email клиента, если доступен."""
        if self.customer:
            customer: Any = self.customer
            if hasattr(customer, "email"):
                return str(customer.email or "")
        return str(_("Нет email"))

    @property
    def customer_name(self) -> str:
        """Имя клиента для отображения."""
        if self.customer:
            customer: Any = self.customer
            if hasattr(customer, "get_full_name"):
                return str(customer.get_full_name())
            return str(customer)
        return str(_("Неизвестный клиент"))


class SyncConflict(TimeStampedModel):
    """Модель для отслеживания конфликтов синхронизации."""

    # ...
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Клиент"),
        help_text="Клиент, с которым связан конфликт",
    )
    conflict_type = models.CharField(
        _("Тип конфликта"),
        max_length=50,
        db_index=True,
        help_text="Тип обнаруженного конфликта данных",
    )
    resolution_strategy = models.CharField(
        _("Стратегия разрешения"),
        max_length=50,
        db_index=True,
        help_text="Выбранная стратегия разрешения конфликта",
    )
    is_resolved = models.BooleanField(
        _("Разрешен"),
        default=False,
        db_index=True,
        help_text="Флаг разрешения конфликта",
    )
    resolved_at = models.DateTimeField(
        _("Дата разрешения"),
        null=True,
        blank=True,
        help_text="Дата и время разрешения конфликта",
    )
    details = models.JSONField(
        _("Детали"),
        default=dict,
        blank=True,
        help_text="Детальная информация о конфликте в формате JSON",
    )

    class Meta:
        verbose_name = _("Конфликт синхронизации")
        verbose_name_plural = _("Конфликты синхронизации")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer", "conflict_type", "created_at"]),
            models.Index(fields=["is_resolved", "resolved_at"]),
        ]

    def __str__(self) -> str:
        date_str = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.conflict_type} - {self.customer} ({date_str})"


class AuditLog(TimeStampedModel):
    """Аудит лог действий пользователей."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_("Пользователь"),
        help_text="Пользователь, выполнивший действие",
    )
    action = models.CharField(
        _("Действие"),
        max_length=50,
        db_index=True,
        help_text="Тип действия (создание, обновление, удаление)",
    )
    resource_type = models.CharField(
        _("Тип ресурса"),
        max_length=50,
        db_index=True,
        help_text="Тип измененного ресурса",
    )
    resource_id = models.CharField(
        _("ID ресурса"),
        max_length=50,
        db_index=True,
        help_text="Идентификатор измененного ресурса",
    )
    details = models.JSONField(
        _("Детали"),
        default=dict,
        blank=True,
        help_text="Детальная информация об действии в формате JSON",
    )
    ip_address = models.GenericIPAddressField(
        _("IP адрес"),
        null=True,
        blank=True,
        help_text="IP адрес пользователя",
    )
    user_agent = models.TextField(
        _("User Agent"),
        blank=True,
        help_text="User Agent строка браузера",
    )

    class Meta:
        verbose_name = _("Аудит лог")
        verbose_name_plural = _("Аудит логи")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "action", "created_at"]),
            models.Index(fields=["resource_type", "resource_id", "created_at"]),
        ]

    def __str__(self) -> str:
        date_str = self.created_at.strftime("%Y-%m-%d %H:%M")
        return f"{self.user} - {self.action} {self.resource_type} ({date_str})"

    @property
    def changes(self) -> dict[str, Any]:
        """Получить словарь изменений из деталей."""
        return cast(dict[str, Any], self.details.get("changes", {}))

    @staticmethod
    def log_action(
        user: Any,
        action: str,
        resource_type: str,
        resource_id: Any,
        details: dict | None = None,
        changes: dict | None = None,
        ip_address: str | None = None,
        user_agent: str = "",
    ) -> "AuditLog":
        """
        Утилита для создания записи в аудит логе.

        Args:
            user: Пользователь, выполнивший действие
            action: Тип действия (approve_b2b, reject_b2b, etc.)
            resource_type: Тип затронутого ресурса (User, Product, etc.)
            resource_id: ID затронутого ресурса
            details: Дополнительные детали
            changes: Словарь изменений (старое -> новое)
            ip_address: IP адрес клиента
            user_agent: User Agent строка

        Returns:
            Созданный объект AuditLog
        """
        if details is None:
            details = {}

        if changes:
            details["changes"] = changes

        return AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id),
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
        )


class Category(models.Model):
    """
    Модель категории для новостей и других типов контента.
    Поддерживает иерархическую структуру и SEO-оптимизацию.
    """

    name = models.CharField(
        _("Название"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text="Название категории (уникальное)",
    )
    slug = models.SlugField(
        _("URL-идентификатор"),
        max_length=100,
        unique=True,
        db_index=True,
        help_text="URL-дружественный идентификатор (генерируется из названия)",
    )
    description = models.TextField(
        _("Описание"),
        blank=True,
        help_text="SEO-описание категории для мета-тегов",
    )
    meta_keywords = models.TextField(
        _("Meta-ключевые слова"),
        blank=True,
        help_text="SEO-ключевые слова через запятую",
    )
    meta_description = models.TextField(
        _("Meta-описание"),
        blank=True,
        help_text="SEO-описание для поисковых систем",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Родительская категория"),
        help_text="Родительская категория для иерархии",
    )
    is_active = models.BooleanField(
        _("Активна"),
        default=True,
        db_index=True,
        help_text="Флаг активности категории",
    )
    created_at = models.DateTimeField(
        _("Дата создания"),
        auto_now_add=True,
        help_text="Дата и время создания категории",
    )
    updated_at = models.DateTimeField(
        _("Дата обновления"),
        auto_now=True,
        help_text="Дата и время последнего обновления категории",
    )

    class Meta:
        verbose_name = _("Категория")
        verbose_name_plural = _("Категории")
        ordering = ["name"]
        indexes = [
            models.Index(fields=["parent", "name"]),
            models.Index(fields=["is_active", "name"]),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        """Возвращает абсолютный URL категории."""
        from django.conf import settings
        from django.urls import reverse

        if self.parent:
            return reverse("common:category-detail", kwargs={"slug": self.slug})
        else:
            return reverse("common:category-list")

    def clean(self):
        """Валидация модели."""
        super().clean()
        if self.parent and self.parent == self:
            from django.core.exceptions import ValidationError

            raise ValidationError(
                _("Категория не может быть родительской для самой себя"),
                code="self_parent",
            )


class Newsletter(models.Model):
    """Модель для подписки на email-рассылку."""

    email = models.EmailField(
        _("Email"),
        unique=True,
        db_index=True,
        help_text="Email адрес для подписки",
    )
    is_active = models.BooleanField(
        _("Активна"),
        default=True,
        db_index=True,
        help_text="Флаг активности подписки",
    )
    subscribed_at = models.DateTimeField(
        _("Дата подписки"),
        auto_now_add=True,
        help_text="Дата и время подписки",
    )
    unsubscribed_at = models.DateTimeField(
        _("Дата отписки"),
        null=True,
        blank=True,
        help_text="Дата и время отписки от рассылки",
    )
    ip_address = models.GenericIPAddressField(
        _("IP адрес"),
        null=True,
        blank=True,
        help_text="IP адрес при подписке/отписке",
    )
    user_agent = models.TextField(
        _("User Agent"),
        blank=True,
        help_text="User Agent строка браузера",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Пользователь"),
        help_text="Пользователь, если подписка создана через аутентификацию",
    )

    class Meta:
        verbose_name = _("Подписка на рассылку")
        verbose_name_plural = _("Подписки на рассылку")
        ordering = ["-subscribed_at"]
        indexes = [
            models.Index(fields=["email", "is_active"]),
            models.Index(fields=["is_active", "subscribed_at"]),
        ]

    def __str__(self) -> str:
        return self.email

    def unsubscribe(self):
        """Деактивирует подписку."""
        self.is_active = False
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["is_active", "unsubscribed_at"])

    def clean(self):
        """Валидация email адреса."""
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()


class News(models.Model):
    """
    Модель новости для системы управления контентом.
    Поддерживает категории, автора, изображение и публикацию.
    """

    title: models.CharField = models.CharField(
        "Заголовок",
        max_length=200,
        db_index=True,
        help_text="Заголовок новости (отображается в списке и заголовке страницы)",
    )
    slug: models.SlugField = models.SlugField(
        "URL-идентификатор",
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Уникальный идентификатор для URL (генерируется из заголовка)",
    )
    excerpt: models.TextField = models.TextField(
        "Краткое описание",
        blank=True,
        help_text="Краткое описание новости для превью (до 200 символов)",
    )
    content: models.TextField = models.TextField(
        "Содержание",
        help_text="Полное содержимое новости (HTML или Markdown)",
    )
    image: models.ImageField = models.ImageField(
        "Изображение",
        upload_to="news/images/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Изображение для новости (опционально)",
    )
    author: models.CharField = models.CharField(
        "Автор",
        max_length=100,
        blank=True,
        help_text="Имя автора (опционально)",
    )
    category: models.ForeignKey = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="news",
        verbose_name="Категория",
        help_text="Категория новости (выбор из существующих)",
        null=True,
        blank=True,
        db_index=True,
    )
    is_published: models.BooleanField = models.BooleanField(
        "Опубликовано",
        default=False,
        db_index=True,
        help_text="Флаг публикации новости",
    )
    published_at: models.DateTimeField = models.DateTimeField(
        "Дата публикации",
        null=True,
        blank=True,
        help_text="Дата и время публикации новости",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
        help_text="Дата и время создания записи",
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        "Дата обновления",
        auto_now_add=True,
        help_text="Дата и время последнего обновления записи",
    )

    class Meta:
        verbose_name = _("Новость")
        verbose_name_plural = _("Новости")
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["is_published", "published_at"]),
            models.Index(fields=["category", "published_at"]),
        ]

    def __str__(self) -> str:
        return str(self.title)

    def get_absolute_url(self) -> str:
        """Возвращает абсолютный URL новости."""
        from django.conf import settings
        from django.urls import reverse

        return reverse("common:news-detail", kwargs={"slug": self.slug})


class BlogPost(models.Model):
    """
    Модель статьи блога для системы управления контентом.
    Поддерживает категории, автора, изображение, публикацию и SEO-оптимизацию.
    """

    title: models.CharField = models.CharField(
        "Заголовок",
        max_length=200,
        db_index=True,
        help_text="Заголовок статьи (отображается в списке и заголовке страницы)",
    )
    slug: models.SlugField = models.SlugField(
        "URL-идентификатор",
        max_length=200,
        unique=True,
        db_index=True,
        help_text="Уникальный идентификатор для URL (генерируется из заголовка)",
    )
    subtitle: models.CharField = models.CharField(
        "Подзаголовок",
        max_length=200,
        blank=True,
        help_text="Подзаголовок статьи (опционально)",
    )
    excerpt: models.TextField = models.TextField(
        "Краткое описание",
        blank=True,
        help_text="Краткое описание статьи для превью (до 200 символов)",
    )
    content: models.TextField = models.TextField(
        "Содержание",
        help_text="Полное содержимое статьи (HTML или Markdown)",
    )
    image: models.ImageField = models.ImageField(
        "Изображение",
        upload_to="blog/images/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Изображение для статьи (опционально)",
    )
    author: models.CharField = models.CharField(
        "Автор",
        max_length=100,
        blank=True,
        help_text="Имя автора (опционально)",
    )
    category: models.ForeignKey = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="blog_posts",
        verbose_name="Категория",
        help_text="Категория статьи (выбор из существующих)",
        null=True,
        blank=True,
        db_index=True,
    )
    is_published: models.BooleanField = models.BooleanField(
        "Опубликовано",
        default=False,
        db_index=True,
        help_text="Флаг публикации статьи",
    )
    published_at: models.DateTimeField = models.DateTimeField(
        "Дата публикации",
        null=True,
        blank=True,
        help_text="Дата и время публикации статьи",
    )
    meta_title: models.CharField = models.CharField(
        "SEO заголовок",
        max_length=200,
        blank=True,
        help_text="SEO заголовок для поисковых систем (опционально)",
    )
    meta_description: models.TextField = models.TextField(
        "SEO описание",
        blank=True,
        help_text="SEO описание для поисковых систем (опционально)",
    )
    created_at: models.DateTimeField = models.DateTimeField(
        "Дата создания",
        auto_now_add=True,
        help_text="Дата и время создания записи",
    )
    updated_at: models.DateTimeField = models.DateTimeField(
        "Дата обновления",
        auto_now=True,
        help_text="Дата и время последнего обновления записи",
    )

    class Meta:
        verbose_name = _("Статья блога")
        verbose_name_plural = _("Статьи блога")
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["is_published", "published_at"]),
            models.Index(fields=["category", "published_at"]),
        ]

    def __str__(self) -> str:
        return str(self.title)

    def get_absolute_url(self) -> str:
        """Возвращает абсолютный URL статьи блога."""
        from django.conf import settings
        from django.urls import reverse

        return reverse("blog-detail", kwargs={"slug": self.slug})


class NotificationRecipient(TimeStampedModel):
    """
    Получатель email-уведомлений системы.

    Позволяет гибко управлять списком получателей различных типов уведомлений
    через Django Admin без необходимости менять settings.ADMINS.
    """

    email = models.EmailField(
        _("Email"),
        unique=True,
        db_index=True,
        help_text="Email адрес получателя уведомлений",
    )
    name = models.CharField(
        _("Имя"),
        max_length=100,
        blank=True,
        help_text="Имя получателя для персонализации писем",
    )
    is_active = models.BooleanField(
        _("Активен"),
        default=True,
        db_index=True,
        help_text="Флаг активности получателя",
    )

    # Типы уведомлений о заказах
    notify_new_orders = models.BooleanField(
        _("Новые заказы"),
        default=False,
        help_text="Уведомления о новых заказах",
    )
    notify_order_cancelled = models.BooleanField(
        _("Отмена заказов"),
        default=False,
        help_text="Уведомления об отмене заказов",
    )

    # Типы уведомлений о пользователях
    notify_user_verification = models.BooleanField(
        _("Верификация B2B"),
        default=False,
        help_text="Уведомления о новых заявках на верификацию B2B партнёров",
    )
    notify_pending_queue = models.BooleanField(
        _("Alert очереди"),
        default=False,
        help_text="Уведомления о превышении очереди pending верификаций",
    )

    # Типы уведомлений о товарах и отчётах
    notify_low_stock = models.BooleanField(
        _("Малый остаток"),
        default=False,
        help_text="Уведомления о малом остатке товаров",
    )
    notify_daily_summary = models.BooleanField(
        _("Ежедневный отчёт"),
        default=False,
        help_text="Ежедневные сводные отчёты",
    )

    class Meta:
        verbose_name = _("Получатель уведомлений")
        verbose_name_plural = _("Получатели уведомлений")
        ordering = ["email"]
        indexes = [
            models.Index(fields=["is_active", "notify_new_orders"]),
            models.Index(fields=["is_active", "notify_user_verification"]),
        ]

    def __str__(self) -> str:
        if self.name:
            return f"{self.name} <{self.email}>"
        return self.email

    def clean(self):
        """Валидация email адреса."""
        super().clean()
        if self.email:
            self.email = self.email.lower().strip()
