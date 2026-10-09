"""
Сайт основной Django-админки FREESPORT (`/admin/`).

Эпик 42: флаг `is_staff` теперь означает «сотрудник» (менеджер, маркетинг,
руководитель), а не «администратор». Сотрудникам `is_staff` нужен для входа
в их собственные разделы, поэтому основная `/admin/` с логами синхронизации,
привязками к 1С и служебными полями открыта только суперпользователю.
"""

from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest


class SuperuserAdminSite(admin.AdminSite):
    """
    Сайт `/admin/`, доступный только активному суперпользователю.

    Отказ — штатное поведение `AdminSite.admin_view`: 302 на страницу входа
    `/admin/login/?next=…`. Подключается как сайт по умолчанию через
    `freesport.apps.FreesportAdminConfig`, поэтому `admin.site` и все
    `@admin.register(...)` продолжают работать с экземпляром этого класса.
    """

    def has_permission(self, request: HttpRequest) -> bool:
        """Пускает только активного суперпользователя, `is_staff` доступа не даёт."""
        user = request.user
        return bool(user.is_active and user.is_superuser)
