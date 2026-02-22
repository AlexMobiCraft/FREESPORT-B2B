"""
Factory классы для создания тестовых баннеров

КРИТИЧНО: Использует LazyFunction с get_unique_suffix() для полной изоляции тестов
"""

import time
import uuid
from datetime import timedelta
from io import BytesIO

import factory
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image

from apps.banners.models import Banner

# Глобальный счетчик для обеспечения уникальности
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс"""
    global _unique_counter
    _unique_counter += 1
    return f"{int(time.time() * 1000)}-{_unique_counter}-{uuid.uuid4().hex[:6]}"


def generate_test_image():
    """Генерирует тестовое изображение для ImageField"""
    # Создаем простое изображение 100x100 красного цвета
    img = Image.new("RGB", (100, 100), color="red")
    img_io = BytesIO()
    img.save(img_io, format="PNG")
    img_io.seek(0)
    return ContentFile(img_io.read(), name=f"test_banner_{get_unique_suffix()}.png")


class BannerFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых баннеров"""

    class Meta:
        model = Banner

    # Поля контента
    title = factory.LazyFunction(lambda: f"Баннер {get_unique_suffix()}")
    subtitle = factory.Faker("text", max_nb_chars=100)
    image = factory.LazyFunction(generate_test_image)
    image_alt = factory.Faker("text", max_nb_chars=50)
    cta_text = "Подробнее"
    cta_link = factory.LazyFunction(lambda: f"/promo/{get_unique_suffix()}")

    # Поля таргетинга - по умолчанию все False
    show_to_guests = False
    show_to_authenticated = False
    show_to_trainers = False
    show_to_wholesale = False
    show_to_federation = False

    # Поля управления
    is_active = True
    priority = 0
    start_date = None
    end_date = None


class ActiveGuestBannerFactory(BannerFactory):
    """Factory для активных баннеров для гостей"""

    show_to_guests = True
    is_active = True


class ActiveAuthenticatedBannerFactory(BannerFactory):
    """Factory для активных баннеров для авторизованных пользователей"""

    show_to_authenticated = True
    is_active = True


class ActiveTrainerBannerFactory(BannerFactory):
    """Factory для активных баннеров для тренеров"""

    show_to_trainers = True
    is_active = True


class ActiveWholesaleBannerFactory(BannerFactory):
    """Factory для активных баннеров для оптовиков"""

    show_to_wholesale = True
    is_active = True


class ActiveFederationBannerFactory(BannerFactory):
    """Factory для активных баннеров для представителей федераций"""

    show_to_federation = True
    is_active = True


class ScheduledBannerFactory(BannerFactory):
    """Factory для баннеров с запланированными датами показа"""

    start_date = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    end_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    is_active = True


class ExpiredBannerFactory(BannerFactory):
    """Factory для просроченных баннеров"""

    start_date = factory.LazyFunction(lambda: timezone.now() - timedelta(days=30))
    end_date = factory.LazyFunction(lambda: timezone.now() - timedelta(days=1))
    is_active = True


class FutureBannerFactory(BannerFactory):
    """Factory для будущих баннеров"""

    start_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))
    end_date = factory.LazyFunction(lambda: timezone.now() + timedelta(days=7))
    is_active = True


class InactiveBannerFactory(BannerFactory):
    """Factory для неактивных баннеров"""

    is_active = False
    show_to_guests = True
