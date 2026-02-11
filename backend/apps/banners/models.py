"""
Модели баннеров для платформы FREESPORT
Управление героическими баннерами на главной странице с таргетингом по пользователям
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, cast

from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


class Banner(models.Model):
    """
    Модель баннера для главной страницы
    Поддерживает таргетинг по группам пользователей и планирование показов
    """

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
