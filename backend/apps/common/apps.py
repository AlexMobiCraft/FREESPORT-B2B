from django.apps import AppConfig
from django.conf import settings
from django.core.checks import Error, Tags, register

SIGNED_COOKIE_SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"


@register(Tags.security)
def check_session_engine_for_subscribe_consent(app_configs, **kwargs):
    """Проверить, что anonymous subscribe consent может получить session_key."""
    errors = []

    if settings.SESSION_ENGINE == SIGNED_COOKIE_SESSION_ENGINE:
        errors.append(
            Error(
                "Подписка на рассылку требует server-side session_key для anonymous UserConsent.",
                hint=(
                    "Используйте django.contrib.sessions.backends.db или другой server-side "
                    "SESSION_ENGINE; signed_cookies не создаёт request.session.session_key."
                ),
                id="common.E001",
            )
        )

    rest_framework_settings = getattr(settings, "REST_FRAMEWORK", {})
    throttle_rates = rest_framework_settings.get("DEFAULT_THROTTLE_RATES", {})
    if "subscribe" not in throttle_rates:
        errors.append(
            Error(
                "Для /subscribe/ должен быть задан отдельный throttle scope 'subscribe'.",
                hint="Добавьте REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['subscribe'] в настройки окружения.",
                id="common.E002",
            )
        )

    if "unsubscribe" not in throttle_rates:
        errors.append(
            Error(
                "Для /unsubscribe/ должен быть задан отдельный throttle scope 'unsubscribe'.",
                hint="Добавьте REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['unsubscribe'] в настройки окружения.",
                id="common.E003",
            )
        )

    return errors


class CommonConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    verbose_name = "Общие утилиты"
