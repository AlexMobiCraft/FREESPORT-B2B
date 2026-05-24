"""
Celery tasks для отправки email уведомлений при регистрации B2B пользователей.

Story 29.4: Email Notification System
- Уведомление админов о новых заявках на верификацию
- Уведомление пользователей о принятии заявки
- Мониторинг очереди pending верификаций
"""

import logging
from datetime import timedelta
from smtplib import SMTPException
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from apps.users.models import User

logger = logging.getLogger(__name__)


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,  # 10 минут максимум
)
def send_admin_verification_email(self: Any, user_id: int) -> bool:
    """
    Отправить email администраторам о новой заявке на верификацию.

    Args:
        user_id: ID пользователя, подавшего заявку

    Returns:
        True если email отправлен успешно
    """
    try:
        user = User.objects.get(id=user_id)

        # Получаем email администраторов из NotificationRecipient
        from apps.common.models import NotificationRecipient

        admin_emails = list(
            NotificationRecipient.objects.filter(
                is_active=True,
                notify_user_verification=True,
            ).values_list("email", flat=True)
        )

        if not admin_emails:
            logger.warning(
                "No recipients configured for verification notifications. " "Skipping notification for user %s",
                user_id,
                extra={
                    "user_id": user_id,
                    "action": "skip_admin_email",
                    "reason": "no_verification_recipients_configured",
                },
            )
            return False

        # Рендерим template
        context = {
            "user": user,
            "role_display": user.get_role_display(),
            "company_name": user.company_name,
            "tax_id": user.tax_id,
            "registration_date": user.created_at,
            "admin_url": f"{settings.SITE_URL}/admin/users/user/{user.id}/change/",
        }

        html_message = render_to_string("emails/admin_new_verification_request.html", context)
        plain_message = render_to_string("emails/admin_new_verification_request.txt", context)

        # Отправляем email
        send_mail(
            subject=(f"[FREESPORT] Новая заявка: {user.get_role_display()} - " f"{user.company_name}"),
            message=plain_message,
            from_email=None,  # Uses DEFAULT_FROM_EMAIL
            recipient_list=admin_emails,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Admin verification email sent successfully",
            extra={
                "user_id": user_id,
                "user_email": str(user.email or ""),
                "role": user.role,
                "admin_emails": admin_emails,
                "template": "admin_new_verification_request",
                "timestamp": timezone.now().isoformat(),
            },
        )
        return True

    except User.DoesNotExist:
        logger.error(
            "User not found for verification email",
            extra={"user_id": user_id, "action": "admin_verification_email"},
        )
        return False

    except SMTPException as exc:
        logger.error(
            "Failed to send admin verification email",
            extra={
                "user_id": user_id,
                "exception": str(exc),
                "retry_count": self.request.retries,
                "action": "admin_verification_email",
            },
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_user_pending_email(self: Any, user_id: int) -> bool:
    """
    Отправить email пользователю о том, что его заявка на рассмотрении.

    Args:
        user_id: ID пользователя

    Returns:
        True если email отправлен успешно
    """
    try:
        user = User.objects.get(id=user_id)

        context = {
            "user": user,
            "first_name": user.first_name,
            "role_display": user.get_role_display(),
            "company_name": user.company_name,
        }

        html_message = render_to_string("emails/user_registration_pending.html", context)
        plain_message = render_to_string("emails/user_registration_pending.txt", context)

        send_mail(
            subject="[FREESPORT] Ваша заявка принята",
            message=plain_message,
            from_email=None,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Pending email sent to user",
            extra={
                "user_id": user_id,
                "user_email": str(user.email or ""),
                "template": "user_registration_pending",
                "timestamp": timezone.now().isoformat(),
            },
        )
        return True

    except User.DoesNotExist:
        logger.error(
            "User not found for pending email",
            extra={"user_id": user_id, "action": "user_pending_email"},
        )
        return False

    except SMTPException as exc:
        logger.error(
            "Failed to send pending email to user",
            extra={
                "user_id": user_id,
                "exception": str(exc),
                "retry_count": self.request.retries,
                "action": "user_pending_email",
            },
        )
        raise self.retry(exc=exc)


@shared_task
def monitor_pending_verification_queue() -> dict:
    """
    Мониторинг очереди pending верификаций.
    Отправляет alert если слишком много заявок в очереди за последние 24 часа.

    Returns:
        Словарь с информацией о количестве pending заявок и статусе alert
    """
    threshold = 10
    time_window = timezone.now() - timedelta(hours=24)

    pending_count = User.objects.filter(verification_status="pending", created_at__gte=time_window).count()

    alert_sent = False

    if pending_count > threshold:
        logger.warning(
            "High pending verification queue detected",
            extra={
                "pending_count": pending_count,
                "threshold": threshold,
                "time_window_hours": 24,
            },
        )

        # Отправить alert получателям с флагом notify_pending_queue
        from apps.common.models import NotificationRecipient

        admin_emails = list(
            NotificationRecipient.objects.filter(
                is_active=True,
                notify_pending_queue=True,
            ).values_list("email", flat=True)
        )

        if admin_emails:
            send_mail(
                subject=(f"⚠️ [FREESPORT] Alert: {pending_count} заявок ожидают верификации"),
                message=f"За последние 24 часа поступило {pending_count} заявок "
                f"на верификацию B2B партнеров.\n\n"
                f"Пороговое значение: {threshold}\n\n"
                f"Пожалуйста, проверьте очередь в админ-панели.",
                from_email=None,
                recipient_list=admin_emails,
            )
            alert_sent = True

            logger.info(
                "Pending queue alert sent to admins",
                extra={
                    "pending_count": pending_count,
                    "admin_emails": admin_emails,
                },
            )

    return {"pending_count": pending_count, "alert_sent": alert_sent}


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_password_reset_email(self: Any, user_id: int, reset_url: str) -> bool:
    """
    Отправить email для сброса пароля.

    Args:
        user_id: ID пользователя
        reset_url: Ссылка для сброса пароля

    Returns:
        True если email отправлен успешно
    """
    try:
        user = User.objects.get(id=user_id)

        context = {
            "reset_url": reset_url,
        }

        html_message = render_to_string("emails/password_reset.html", context)
        plain_message = render_to_string("emails/password_reset.txt", context)

        send_mail(
            subject="[FREESPORT] Сброс пароля",
            message=plain_message,
            from_email=None,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Password reset email sent",
            extra={
                "user_id": user_id,
                "user_email": user.email,
                "template": "password_reset",
                "timestamp": timezone.now().isoformat(),
            },
        )
        return True

    except User.DoesNotExist:
        logger.error(
            "User not found for password reset email",
            extra={"user_id": user_id, "action": "password_reset_email"},
        )
        return False

    except SMTPException as exc:
        logger.error(
            "Failed to send password reset email",
            extra={
                "user_id": user_id,
                "exception": str(exc),
                "retry_count": self.request.retries,
                "action": "password_reset_email",
            },
        )
        raise self.retry(exc=exc)


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_user_verified_email(self: Any, user_id: int) -> bool:
    """
    Отправить email пользователю о том, что его аккаунт верифицирован.

    Args:
        user_id: ID пользователя

    Returns:
        True если email отправлен успешно
    """
    try:
        user = User.objects.get(id=user_id)

        context = {
            "first_name": user.first_name,
            "role_display": user.get_role_display(),
            "site_url": settings.SITE_URL,
        }

        html_message = render_to_string("emails/account_verified.html", context)
        plain_message = render_to_string("emails/account_verified.txt", context)

        send_mail(
            subject="[FREESPORT] Ваша заявка одобрена! Аккаунт верифицирован",
            message=plain_message,
            from_email=None,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(
            "Account verified email sent",
            extra={
                "user_id": user_id,
                "user_email": user.email,
                "template": "account_verified",
                "timestamp": timezone.now().isoformat(),
            },
        )
        return True

    except User.DoesNotExist:
        logger.error(
            "User not found for verified email",
            extra={"user_id": user_id, "action": "user_verified_email"},
        )
        return False

    except SMTPException as exc:
        logger.error(
            "Failed to send verified email",
            extra={
                "user_id": user_id,
                "exception": str(exc),
                "retry_count": self.request.retries,
                "action": "user_verified_email",
            },
        )
        raise self.retry(exc=exc)
