"""
Management command для тестирования email конфигурации.
Story 29.3: Email Server Configuration

Использование:
    python manage.py test_email --to admin@freesport.ru
    python manage.py test_email --to admin@freesport.ru --verbose
"""

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """Команда для тестирования email конфигурации."""

    help = "Отправляет тестовое письмо для проверки email конфигурации"

    def add_arguments(self, parser):
        """Определяет аргументы командной строки."""
        parser.add_argument(
            "--to",
            type=str,
            required=True,
            help="Email адрес получателя тестового письма",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Показать подробную информацию о конфигурации",
        )

    def handle(self, *args, **options):
        """Выполняет отправку тестового письма."""
        to_email = options["to"]
        verbose = options["verbose"]

        # Показываем текущую конфигурацию
        self.stdout.write(self.style.NOTICE("=== Email Configuration ==="))
        self.stdout.write(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        self.stdout.write(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        self.stdout.write(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

        if verbose:
            self.stdout.write(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
            if settings.EMAIL_HOST_PASSWORD:
                masked_password = "*" * len(settings.EMAIL_HOST_PASSWORD)
            else:
                masked_password = "(not set)"
            self.stdout.write(f"EMAIL_HOST_PASSWORD: {masked_password}")
            self.stdout.write(f"ADMINS: {settings.ADMINS}")

        self.stdout.write(self.style.NOTICE("==========================="))
        self.stdout.write(f"\nОтправка тестового письма на {to_email}...")

        try:
            result = send_mail(
                subject="[FREESPORT] Тестовое письмо",
                message=self._get_test_message(),
                from_email=None,  # Использует DEFAULT_FROM_EMAIL
                recipient_list=[to_email],
                fail_silently=False,
            )

            if result:
                self.stdout.write(self.style.SUCCESS(f"\n✅ Письмо успешно отправлено на {to_email}"))
                self.stdout.write(self.style.SUCCESS("Проверьте входящие (и папку спам) для подтверждения доставки."))
            else:
                self.stdout.write(self.style.WARNING("\n⚠️ send_mail вернул 0 - письмо возможно не отправлено"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Ошибка отправки: {e}"))
            self.stdout.write(self.style.NOTICE("\nВозможные причины:"))
            self.stdout.write("  - Неверные EMAIL_HOST_USER или EMAIL_HOST_PASSWORD")
            self.stdout.write("  - EMAIL_HOST или EMAIL_PORT недоступны")
            self.stdout.write("  - Для Gmail: нужен App Password вместо обычного пароля")
            self.stdout.write("  - Firewall блокирует исходящие соединения на порт 587")
            raise

    def _get_test_message(self):
        """Возвращает текст тестового письма."""
        return """Это тестовое письмо от платформы FREESPORT.

Если вы получили это письмо, значит email конфигурация работает корректно.

Настройки:
- EMAIL_HOST: {host}
- EMAIL_PORT: {port}
- DEFAULT_FROM_EMAIL: {from_email}

--
FREESPORT Platform
https://freesport.ru
""".format(
            host=settings.EMAIL_HOST,
            port=settings.EMAIL_PORT,
            from_email=settings.DEFAULT_FROM_EMAIL,
        )
