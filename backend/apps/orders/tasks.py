"""
Celery tasks для отправки email-уведомлений о заказах.

Реализует асинхронную отправку уведомлений при создании/отмене заказов
получателям, настроенным через NotificationRecipient в Django Admin.
"""

import logging
from datetime import datetime, timedelta
from smtplib import SMTPException
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from apps.common.models import NotificationRecipient
from apps.orders.models import Order, OrderItem
from apps.users.staff_roles import responsible_manager_candidates, split_by_manager_section

logger = logging.getLogger(__name__)


def _get_order_display_items(order: Order) -> Any:
    """Возвращает позиции для отображения в email/admin.

    Для master-заказа агрегирует items из всех субзаказов.
    Для legacy-заказов (без субзаказов) — прямые items.
    """
    if order.is_master and order.sub_orders.exists():
        return OrderItem.objects.filter(order__parent_order=order).select_related("product", "variant")
    return order.items.select_related("product", "variant").all()


def _render_new_order_email(order: Order, context: dict[str, Any]) -> tuple[str | None, str]:
    """Возвращает `(html, текст)` письма о новом заказе; при сбое шаблона — простой текст без HTML."""
    try:
        html_message = render_to_string("emails/admin_new_order.html", context)
        plain_message = str(render_to_string("emails/admin_new_order.txt", context))
    except Exception as e:
        logger.error(
            "Failed to render order notification template",
            extra={
                "order_id": order.id,
                "exception": str(e),
            },
        )
        # Fallback на простое сообщение
        plain_message = (
            f"Новый заказ #{order.order_number}\n\n"
            f"Клиент: {context['customer_name']}\n"
            f"Email: {context['customer_email']}\n"
            f"Сумма: {order.total_amount} ₽\n\n"
            f"Откройте заказ по ссылке: {context['admin_url']}"
        )
        return None, plain_message
    return html_message, plain_message


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,
)
def send_order_confirmation_to_customer(self: Any, order_id: int) -> bool:
    """
    Асинхронная отправка email-подтверждения клиенту при создании заказа.

    Args:
        order_id: ID заказа

    Returns:
        True если email отправлен успешно
    """
    try:
        order = Order.objects.prefetch_related("items", "sub_orders__items").get(id=order_id)
    except Order.DoesNotExist:
        logger.error(
            "Order not found for customer confirmation",
            extra={"order_id": order_id},
        )
        return False

    customer_email = None
    if order.user and hasattr(order.user, "email"):
        customer_email = str(order.user.email or "")
    elif order.customer_email:
        customer_email = order.customer_email

    if not customer_email:
        logger.warning(f"Не удалось отправить email для заказа {order.order_number}: " "email клиента не указан")
        return False

    subject = f"Заказ #{order.order_number_display} успешно оформлен - OPTISPORT"
    message = _build_order_email_text(order)

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[customer_email],
            fail_silently=False,
        )
        logger.info(f"Email-уведомление о заказе {order.order_number} " f"отправлено на {customer_email}")
        return True
    except SMTPException as exc:
        logger.error(f"Ошибка отправки email для заказа {order.order_number}: {exc}")
        raise self.retry(exc=exc)


def _build_order_email_text(order):
    """Формирование текста email-уведомления о заказе."""
    customer_name = order.customer_display_name or "Уважаемый клиент"
    display_number = order.order_number_display

    delivery_methods = {
        "pickup": "Самовывоз",
        "courier": "Курьерская доставка",
        "post": "Почтовая доставка",
        "transport": "Транспортная компания",
        "transport_company": "Транспортная компания",
        "transport_schedule": "Доставка по расписанию",
    }
    delivery_method_name = delivery_methods.get(order.delivery_method, order.delivery_method)

    items_text = ""
    for item in _get_order_display_items(order):
        items_text += f"  - {item.product_name} × {item.quantity}: {item.total_price} ₽\n"

    message = f"""
Здравствуйте, {customer_name}!

Ваш заказ #{display_number} успешно оформлен.

ДЕТАЛИ ЗАКАЗА:
{items_text}
Итого: {order.total_amount} ₽

ДОСТАВКА:
Способ: {delivery_method_name}
Адрес: {order.delivery_address}

ЧТО ДАЛЬШЕ?
Администратор свяжется с вами в течение 24 часов для уточнения:
- Способа оплаты
- Точной стоимости доставки
- Времени доставки

Спасибо за заказ!

С уважением,
Команда OPTISPORT
"""
    return message.strip()


def _responsible_manager_email(order: Order) -> str | None:
    """Email ответственного менеджера клиента заказа или `None`, если письмо ему слать нельзя.

    Источник — `User.responsible_manager`: он уже учитывает правило региона и ручное
    назначение. Менеджер годится, только если проходит `responsible_manager_candidates()`
    (активный сотрудник из групп «Менеджеры»/«Руководители») и у него есть email:
    иначе раздел `/manager/` не откроет ему заказ, и ссылка из письма была бы мёртвой.
    """
    if order.user_id is None:
        return None

    manager_id = order.user.responsible_manager_id
    if manager_id is not None:
        manager_email = responsible_manager_candidates().filter(pk=manager_id).values_list("email", flat=True).first()
        if manager_email:
            return str(manager_email)

    logger.warning(
        f"У заказа {order.order_number} нет подходящего ответственного менеджера клиента: "
        f"письмо уйдёт только общему списку получателей"
    )
    return None


def _collect_new_order_recipients(order: Order) -> list[str]:
    """Получатели письма о новом заказе: общий список и ответственный менеджер без дублей.

    Флаг `notify_new_orders` управляет только общим списком; менеджер клиента
    добавляется независимо от него. Дубли убираются по `email.lower()`, порядок
    сохраняется: сначала общий список, затем менеджер.
    """
    emails = list(
        NotificationRecipient.objects.filter(is_active=True, notify_new_orders=True).values_list("email", flat=True)
    )
    manager_email = _responsible_manager_email(order)
    if manager_email:
        emails.append(manager_email)

    unique: dict[str, str] = {}
    for email in emails:
        unique.setdefault(email.lower(), email)
    return list(unique.values())


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,  # 10 минут максимум
)
def send_order_notification_email(self: Any, order_id: int) -> bool:
    """
    Отправить email-уведомление о новом заказе.

    Получатели: все активные с флагом notify_new_orders=True и ответственный менеджер
    клиента (независимо от флага, если он может войти в раздел `/manager/`).

    Args:
        order_id: ID заказа

    Returns:
        True если хотя бы один email отправлен успешно
    """
    try:
        order = Order.objects.prefetch_related("items", "sub_orders__items").get(id=order_id)
    except Order.DoesNotExist:
        logger.error(
            "Order not found for notification",
            extra={"order_id": order_id, "action": "order_notification_email"},
        )
        return False

    # Общий список + ответственный менеджер клиента (независимо от флага)
    recipients = _collect_new_order_recipients(order)

    if not recipients:
        logger.info(
            "No recipients configured for new order notifications",
            extra={"order_id": order_id, "action": "skip_order_notification"},
        )
        return False

    # Подготавливаем контекст для шаблона
    customer_email = ""
    customer_phone = ""
    customer_name = ""

    if order.user:
        customer_email = getattr(order.user, "email", "") or ""
        customer_phone = getattr(order.user, "phone", "") or ""
        customer_name = order.customer_display_name
    else:
        customer_email = order.customer_email
        customer_phone = order.customer_phone
        customer_name = order.customer_name or order.customer_email

    delivery_methods = {
        "pickup": "Самовывоз",
        "courier": "Курьерская доставка",
        "post": "Почтовая доставка",
        "transport_company": "Транспортная компания",
    }

    context = {
        "order": order,
        "items": _get_order_display_items(order),
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "delivery_method": delivery_methods.get(order.delivery_method, order.delivery_method),
    }

    # Менеджер или руководитель среди получателей в /admin/ не войдёт —
    # ему уходит отдельное письмо со ссылкой на заказ в разделе менеджера.
    site_url = getattr(settings, "SITE_URL", "http://localhost:8001")
    admin_part, manager_part = split_by_manager_section(recipients)
    change_paths = (
        (admin_part, f"/admin/orders/order/{order.id}/change/"),
        (manager_part, reverse("manager:orders_order_change", args=[order.id])),
    )

    # Отправляем email
    try:
        for recipient_list, change_path in change_paths:
            if not recipient_list:
                continue
            html_message, plain_message = _render_new_order_email(
                order, {**context, "admin_url": f"{site_url}{change_path}"}
            )
            send_mail(
                subject=f"[OPTISPORT] Новый заказ #{order.order_number}",
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                html_message=html_message,
                fail_silently=False,
            )

        logger.info(
            "Order notification email sent successfully",
            extra={
                "order_id": order_id,
                "order_number": order.order_number,
                "recipients_count": len(recipients),
                "total_amount": str(order.total_amount),
            },
        )
        return True

    except SMTPException as exc:
        logger.error(
            "Failed to send order notification email",
            extra={
                "order_id": order_id,
                "exception": str(exc),
                "retry_count": self.request.retries,
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
def send_order_cancelled_notification_email(self: Any, order_id: int) -> bool:
    """
    Отправить email-уведомление об отмене заказа.

    Отправляет уведомление всем получателям с флагом notify_order_cancelled=True.

    Args:
        order_id: ID заказа

    Returns:
        True если хотя бы один email отправлен успешно
    """
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        logger.error(
            "Order not found for cancellation notification",
            extra={"order_id": order_id},
        )
        return False

    recipients = NotificationRecipient.objects.filter(
        is_active=True,
        notify_order_cancelled=True,
    ).values_list("email", flat=True)

    if not recipients:
        logger.info(
            "No recipients configured for order cancellation notifications",
            extra={"order_id": order_id},
        )
        return False

    customer_name = order.customer_display_name or order.customer_email

    site_url = getattr(settings, "SITE_URL", "http://localhost:8001")
    message = (
        f"Заказ #{order.order_number} был отменён.\n\n"
        f"Клиент: {customer_name}\n"
        f"Сумма: {order.total_amount} ₽\n\n"
        f"Подробности в Django Admin: {site_url}/admin/orders/order/{order.id}/change/"
    )

    try:
        send_mail(
            subject=f"[OPTISPORT] Заказ #{order.order_number} отменён",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=list(recipients),
            fail_silently=False,
        )

        logger.info(
            "Order cancellation notification sent",
            extra={
                "order_id": order_id,
                "order_number": order.order_number,
                "recipients_count": len(recipients),
            },
        )
        return True

    except SMTPException as exc:
        logger.error(
            "Failed to send order cancellation notification",
            extra={
                "order_id": order_id,
                "exception": str(exc),
            },
        )
        raise self.retry(exc=exc)


# Ключ кэша: какие заказы уже попали в письмо и когда оно ушло.
_STUCK_ALERT_CACHE_KEY = "orders:stuck_in_1c_alert_state"
_STUCK_ALERT_STATE_TTL = 7 * 24 * 60 * 60
_STUCK_ALERT_MAX_LISTED = 50


def _stuck_alert_recipients() -> list[str]:
    """Получатели алерта: активные с флагом `notify_exchange_alerts`, иначе `settings.ADMINS`."""
    emails = list(
        NotificationRecipient.objects.filter(is_active=True, notify_exchange_alerts=True).values_list(
            "email", flat=True
        )
    )
    if not emails:
        emails = [email for _name, email in getattr(settings, "ADMINS", []) if email]
    unique: dict[str, str] = {}
    for email in emails:
        unique.setdefault(email.lower(), email)
    return list(unique.values())


def _format_age(delta: timedelta) -> str:
    """Возраст заказа в виде «1 ч 05 мин» или «45 мин»."""
    minutes = max(int(delta.total_seconds() // 60), 0)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} ч {minutes:02d} мин"
    return f"{minutes} мин"


@shared_task(
    bind=True,
    max_retries=3,
    autoretry_for=(SMTPException, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=600,  # 10 минут максимум
)
def alert_orders_stuck_in_1c(self: Any) -> dict[str, Any]:
    """Письмо администратору, если 1С не забирает субзаказы дольше порога.

    Зависшим считается субзаказ (`is_master=False`) с `sent_to_1c=False`,
    `export_skipped=False`, созданный раньше `ORDERS_STUCK_ALERT_THRESHOLD_MINUTES`.
    Письмо уходит, когда в наборе появился новый заказ или с прошлого письма прошло
    `ORDERS_STUCK_ALERT_REPEAT_HOURS`. Состояние лежит в кэше и пишется только после
    успешной отправки, поэтому сбой SMTP повторяет задачу, а не теряет алерт.
    """
    now = timezone.now()
    threshold_minutes = settings.ORDERS_STUCK_ALERT_THRESHOLD_MINUTES
    repeat = timedelta(hours=settings.ORDERS_STUCK_ALERT_REPEAT_HOURS)

    stuck = list(
        Order.objects.filter(
            is_master=False,
            parent_order__isnull=False,
            sent_to_1c=False,
            export_skipped=False,
            created_at__lte=now - timedelta(minutes=threshold_minutes),
        )
        .order_by("created_at")
        .values_list("id", "order_number", "created_at")
    )

    if not stuck:
        cache.delete(_STUCK_ALERT_CACHE_KEY)
        return {"stuck": 0, "sent": False}

    ids = sorted(row[0] for row in stuck)
    state = cache.get(_STUCK_ALERT_CACHE_KEY) or {}
    known_ids = set(state.get("ids", []))
    sent_at = state.get("sent_at")
    last_sent = datetime.fromisoformat(sent_at) if sent_at else None

    has_new = bool(set(ids) - known_ids)
    reminder_due = last_sent is None or now - last_sent >= repeat

    if not has_new and not reminder_due:
        if known_ids != set(ids):
            # Часть заказов забрали: запоминаем остаток, чтобы не считать их новыми.
            cache.set(_STUCK_ALERT_CACHE_KEY, {"ids": ids, "sent_at": sent_at}, _STUCK_ALERT_STATE_TTL)
        return {"stuck": len(ids), "sent": False}

    recipients = _stuck_alert_recipients()
    if not recipients:
        logger.error(
            "Заказы не забраны 1С, но получателей алерта нет: отметьте «Сбои обмена с 1С» "
            "в получателях уведомлений или задайте ADMIN_EMAILS",
            extra={"stuck_count": len(ids), "action": "stuck_orders_alert_no_recipients"},
        )
        return {"stuck": len(ids), "sent": False}

    lines = [
        f"{number} — {_format_age(now - created_at)}" for _id, number, created_at in stuck[:_STUCK_ALERT_MAX_LISTED]
    ]
    if len(stuck) > _STUCK_ALERT_MAX_LISTED:
        lines.append(f"…и ещё {len(stuck) - _STUCK_ALERT_MAX_LISTED}")
    message = (
        f"1С не забрала заказы с сайта дольше {threshold_minutes} мин: {len(stuck)} шт.\n\n"
        + "\n".join(lines)
        + "\n\nПроверьте обмен с 1С: настройку БУС «По расписанию» для загрузки заказов, "
        "доступность базы 1С и запросы mode=query в логе nginx."
    )

    send_mail(
        subject=f"[OPTISPORT] 1С не забирает заказы: {len(stuck)} шт.",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=recipients,
        fail_silently=False,
    )
    cache.set(_STUCK_ALERT_CACHE_KEY, {"ids": ids, "sent_at": now.isoformat()}, _STUCK_ALERT_STATE_TTL)
    logger.info(
        "Алерт о зависших в 1С заказах отправлен",
        extra={"stuck_count": len(ids), "recipients": recipients, "action": "stuck_orders_alert_sent"},
    )
    return {"stuck": len(ids), "sent": True}
