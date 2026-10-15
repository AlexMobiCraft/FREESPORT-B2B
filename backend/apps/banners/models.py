"""
Модели баннеров для платформы FREESPORT
Управление героическими баннерами на главной странице с таргетингом по пользователям
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, cast
from urllib.parse import urlsplit

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import models
from django.db.models import Q, QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from apps.users.models import User


UNSAFE_CTA_SCHEMES = ("javascript:", "data:", "vbscript:")

# ИНН: 10 цифр у юрлиц, 12 — у ИП и физлиц. Контрольная сумма не проверяется намеренно:
# реквизиты вводит менеджер вручную, ложное отклонение валидного ИНН дороже опечатки.
#
# Класс задан как [0-9], а не \d: в Python \d для str-паттернов Unicode-aware и матчит
# арабо-индийские и деванагари-цифры, из-за чего "١٢٣٤٥٦٧٨٩٠" прошёл бы как валидный ИНН.
# По той же причине здесь не переиспользован CustomerIdentityResolver._validate_inn —
# он опирается на str.isdigit(), у которого ровно тот же дефект.
INN_PATTERN = re.compile(r"^[0-9]{10}$|^[0-9]{12}$")


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
    mobile_image = cast(
        models.ImageField,
        models.ImageField(
            "Мобильное изображение",
            upload_to="promos/%Y/%m/",
            blank=True,
            help_text=(
                "Изображение для мобильных устройств (21:9, рекомендуемый размер: 1260×540px). "
                "Если не загружено — используется основное."
            ),
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

    # Поля маркировки рекламы (ФЗ «О рекламе»)
    is_advertisement = cast(
        bool,
        models.BooleanField(
            "Является рекламой",
            default=False,
            help_text="Показывать на баннере метку «Реклама» с реквизитами рекламодателя",
        ),
    )
    advertiser_name = cast(
        str,
        models.CharField(
            "Наименование рекламодателя",
            max_length=255,
            blank=True,
            help_text='Например: ООО "Прайм Спорт Рус". Обязательно, если баннер помечен как реклама',
        ),
    )
    advertiser_inn = cast(
        str,
        models.CharField(
            "ИНН рекламодателя",
            max_length=12,
            blank=True,
            help_text="10 цифр для юрлиц, 12 — для ИП и физлиц. Обязательно, если баннер помечен как реклама",
        ),
    )
    erid = cast(
        str,
        models.CharField(
            "Токен ERID",
            max_length=64,
            blank=True,
            help_text="Идентификатор рекламного креатива из ОРД. Необязателен",
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
        - При is_advertisement=True обязательны реквизиты рекламодателя
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

        self._clean_advertisement_fields()

    def clean_fields(self, exclude: Any = None) -> None:
        """
        Нормализует рекламные реквизиты до проверки полей.

        Обрезка пробелов обязана происходить именно здесь: full_clean() вызывает
        clean_fields() раньше clean(), и ИНН вида "  7718933790  " иначе отбивается
        по max_length=12 ещё до того, как clean() успеет его нормализовать.
        """
        self._normalize_advertisement_fields()
        # ModelForm._update_errors роняет ValueError, если clean() положит ошибку на поле,
        # которого в форме нет. Запоминаем exclude, чтобы перенаправить такие ошибки.
        self._validation_exclude = set(exclude or ())
        super().clean_fields(exclude=exclude)

    def _normalize_advertisement_fields(self) -> None:
        """Обрезает пробелы по краям рекламных реквизитов. Идемпотентна."""
        self.advertiser_name = self.advertiser_name.strip() if isinstance(self.advertiser_name, str) else ""
        self.advertiser_inn = self.advertiser_inn.strip() if isinstance(self.advertiser_inn, str) else ""
        self.erid = self.erid.strip() if isinstance(self.erid, str) else ""

    def _clean_advertisement_fields(self) -> None:
        """
        Валидирует блок рекламной маркировки.

        Обязательность реквизитов проверяется только при is_advertisement=True —
        чтобы обычные баннеры не ломались от пустых полей.
        """
        self._normalize_advertisement_fields()

        if not self.is_advertisement:
            return

        errors: dict[str, str] = {}

        # Метка «Реклама» рисуется только в маркетинговой карусели. Молча принятый флаг
        # на hero-баннере означал бы рекламу без обязательной по закону маркировки,
        # поэтому лучше отказать менеджеру в момент сохранения.
        if self.type != self.BannerType.MARKETING:
            errors["is_advertisement"] = (
                "Маркировка рекламы поддерживается только для маркетинговых баннеров: "
                "на баннерах других типов метка «Реклама» не отображается."
            )

        if not self.advertiser_name:
            errors["advertiser_name"] = "Наименование рекламодателя обязательно для рекламного баннера."

        if not self.advertiser_inn:
            errors["advertiser_inn"] = "ИНН рекламодателя обязателен для рекламного баннера."
        elif not INN_PATTERN.match(self.advertiser_inn):
            errors["advertiser_inn"] = "ИНН должен состоять из 10 цифр (юрлицо) или 12 цифр (ИП, физлицо)."

        if errors:
            raise ValidationError(self._route_errors_around_exclude(errors))

    def _route_errors_around_exclude(self, errors: dict[str, str]) -> dict[str, list[str]] | dict[str, str]:
        """
        Перенаправляет ошибки исключённых полей в NON_FIELD_ERRORS.

        Без этого частичная ModelForm (inline, list_editable, кастомная форма без
        рекламных полей) получала бы ValueError вместо ошибки валидации.
        """
        excluded = getattr(self, "_validation_exclude", None)
        if not excluded:
            return errors

        routed: dict[str, list[str]] = {}
        for field, message in errors.items():
            key = NON_FIELD_ERRORS if field in excluded else field
            routed.setdefault(key, []).append(message)
        return routed

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
