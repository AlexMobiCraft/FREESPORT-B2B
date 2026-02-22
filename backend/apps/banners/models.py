"""
Модели баннеров для платформы FREESPORT
Управление героическими баннерами на главной странице с таргетингом по пользователям
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


UNSAFE_CTA_SCHEMES = ("javascript:", "data:", "vbscript:")


def is_safe_internal_cta_link(link: str) -> bool:
    """Проверяет, что cta_link является безопасным внутренним относительным путём."""
    trimmed = link.strip()
    if not trimmed:
        return False

    lowered = trimmed.lower()
    if lowered.startswith(UNSAFE_CTA_SCHEMES):
        return False

    # Блокируем protocol-relative URL: //evil.com
    if trimmed.startswith("//"):
        return False

    # Блокируем обратные слеши — могут использоваться для обфускации путей
    if "\\" in trimmed:
        return False

    # Разрешаем только внутренние ссылки вида /catalog и /catalog?x=1
    if not trimmed.startswith("/"):
        return False

    parsed = urlsplit(trimmed)
    return parsed.scheme == "" and parsed.netloc == ""


class Banner(models.Model):
    """
    Модель баннера для главной страницы
    Поддерживает таргетинг по группам пользователей и планирование показов
    """

    class BannerType(models.TextChoices):
        HERO = "hero", "Геройский (Hero)"
        MARKETING = "marketing", "Маркетинговый"

    # Поля контента
    title = cast(
        str,
        models.CharField("Заголовок", max_length=200, help_text="Основной заголовок баннера"),
    )
    subtitle = cast(
        str,
        models.CharField(
            "Подзаголовок",
            max_length=500,
            blank=True,
            help_text="Дополнительный текст под заголовком",
        ),
    )
    image = cast(
        models.ImageField,
        models.ImageField(
            "Изображение",
            upload_to="promos/%Y/%m/",
            blank=True,
            help_text="Рекомендуемый размер: 1920×600px",
        ),
    )
    image_alt = cast(
        str,
        models.CharField(
            "Alt-текст изображения",
            max_length=200,
            blank=True,
            help_text="Alt-текст для accessibility",
        ),
    )
    cta_text = cast(
        str,
        models.CharField(
            "Текст кнопки",
            max_length=50,
            blank=True,
            help_text="Текст call-to-action кнопки",
        ),
    )
    cta_link = cast(
        str,
        models.CharField("Ссылка кнопки", max_length=200, help_text="URL для перехода по клику"),
    )

    # Поля таргетинга
    show_to_guests = cast(
        bool,
        models.BooleanField(
            "Показывать гостям",
            default=False,
            help_text="Показывать неавторизованным пользователям",
        ),
    )
    show_to_authenticated = cast(
        bool,
        models.BooleanField(
            "Показывать авторизованным",
            default=False,
            help_text="Показывать авторизованным пользователям (роль retail)",
        ),
    )
    show_to_trainers = cast(
        bool,
        models.BooleanField(
            "Показывать тренерам",
            default=False,
            help_text="Показывать пользователям с ролью trainer",
        ),
    )
    show_to_wholesale = cast(
        bool,
        models.BooleanField(
            "Показывать оптовикам",
            default=False,
            help_text="Показывать пользователям с ролями wholesale_level1-3",
        ),
    )
    show_to_federation = cast(
        bool,
        models.BooleanField(
            "Показывать представителям федераций",
            default=False,
            help_text="Показывать пользователям с ролью federation_rep",
        ),
    )

    # Поля управления
    type = cast(
        str,
        models.CharField(
            "Тип баннера",
            max_length=20,
            choices=BannerType.choices,
            default=BannerType.HERO,
            help_text="Тип определяет место и способ отображения баннера",
        ),
    )
    is_active = cast(
        bool,
        models.BooleanField(
            "Активен",
            default=True,
            help_text="Отключить/включить баннер",
        ),
    )
    priority = cast(
        int,
        models.IntegerField(
            "Приоритет",
            default=0,
            help_text="Баннеры с большим приоритетом показываются первыми",
        ),
    )
    start_date = cast(
        Optional[datetime],
        models.DateTimeField(
            "Дата начала показа",
            null=True,
            blank=True,
            help_text="Баннер начнёт показываться с этой даты",
        ),
    )
    end_date = cast(
        Optional[datetime],
        models.DateTimeField(
            "Дата окончания показа",
            null=True,
            blank=True,
            help_text="Баннер перестанет показываться после этой даты",
        ),
    )

    # Метаданные
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Баннер"
        verbose_name_plural = "Баннеры"
        db_table = "banners"
        ordering = ["-priority", "-created_at"]

    def __str__(self) -> str:
        """Строковое представление баннера"""
        return f"{self.title} (priority: {self.priority})"

    def clean(self) -> None:
        """
        Валидация модели:
        - Image обязательна для Marketing баннеров (AC2)
        - CTA ссылка должна быть безопасным внутренним относительным путём
        """
        super().clean()

        cleaned_cta_link = self.cta_link.strip() if isinstance(self.cta_link, str) else ""
        if not cleaned_cta_link:
            raise ValidationError({"cta_link": "Ссылка кнопки обязательна и не может быть пустой."})
        if not is_safe_internal_cta_link(cleaned_cta_link):
            raise ValidationError(
                {
                    "cta_link": (
                        "Ссылка кнопки должна быть внутренним относительным путём "
                        "(например, /catalog) без небезопасных протоколов."
                    )
                }
            )
        self.cta_link = cleaned_cta_link

        if self.type == self.BannerType.MARKETING and not self.image:
            raise ValidationError({"image": "Изображение обязательно для маркетинговых баннеров."})

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Вызывает full_clean() перед сохранением для обеспечения валидации."""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_scheduled_active(self) -> bool:
        """
        Проверяет активность баннера с учётом дат начала и окончания показа

        Returns:
            True если баннер активен и находится в интервале дат показа
        """
        if not self.is_active:
            return False

        now = timezone.now()

        # Проверка даты начала
        if self.start_date and now < self.start_date:
            return False

        # Проверка даты окончания
        if self.end_date and now > self.end_date:
            return False

        return True

    @classmethod
    def get_for_user(cls, user: Optional[User] = None) -> QuerySet[Banner]:
        """
        Получить баннеры, подходящие для конкретного пользователя

        Args:
            user: Пользователь или None для гостей

        Returns:
            QuerySet с отфильтрованными баннерами
        """
        now = timezone.now()

        # Базовая фильтрация: только активные и в рамках дат
        queryset = cls.objects.filter(is_active=True)

        # Фильтрация по датам
        queryset = queryset.filter(Q(start_date__isnull=True) | Q(start_date__lte=now)).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )

        # Фильтрация по роли пользователя
        if user is None or not user.is_authenticated:
            # Гость - показываем только баннеры для гостей
            queryset = queryset.filter(show_to_guests=True)
        else:
            # Авторизованный пользователь - фильтруем по роли
            role_filters = Q(show_to_authenticated=True)  # Базовая роль retail

            if hasattr(user, "role"):
                if user.role == "trainer":
                    role_filters |= Q(show_to_trainers=True)
                elif user.role and user.role.startswith("wholesale"):
                    role_filters |= Q(show_to_wholesale=True)
                elif user.role == "federation_rep":
                    role_filters |= Q(show_to_federation=True)

            queryset = queryset.filter(role_filters)

        return queryset
