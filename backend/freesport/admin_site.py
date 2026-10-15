"""
Сайты Django-админки FREESPORT: основная `/admin/` и раздел менеджера `/manager/`.

Эпик 42: флаг `is_staff` теперь означает «сотрудник» (менеджер, маркетинг,
руководитель), а не «администратор». Сотрудникам `is_staff` нужен для входа
в их собственные разделы, поэтому основная `/admin/` с логами синхронизации,
привязками к 1С и служебными полями открыта только суперпользователю.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.users.staff_roles import MANAGERS_GROUP, SUPERVISORS_GROUP


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


class ManagerAdminSite(admin.AdminSite):
    """
    Раздел менеджера `/manager/` (стори 42.4): клиенты, за которых отвечает сотрудник.

    Пускает активного сотрудника (`is_staff`) из группы «Менеджеры» или
    «Руководители» — ровно критерий `RESPONSIBLE_MANAGER_CHOICES` плюс
    `is_active`: в раздел входит тот, кого можно назначить ответственным.
    Суперпользователя раздел не пускает, даже если он состоит в группе:
    у него есть `/admin/` с тем же и большим, а членство в группе не должно
    превращать его в «менеджера» с урезанной видимостью. Отказ — штатный
    302 на `/manager/login/`.
    """

    site_header = "FREESPORT — Менеджер"
    site_title = "FREESPORT — Менеджер"
    index_title = "Раздел менеджера"
    # Без блока «Последние действия»: его ссылки строит LogEntry.get_admin_url()
    # через reverse("admin:…") без current_app, то есть в закрытую /admin/.
    index_template = "admin/manager/index.html"

    def has_permission(self, request: HttpRequest) -> bool:
        user = request.user
        if not (user.is_active and user.is_staff) or user.is_superuser:
            return False
        # admin_view и each_context зовут has_permission по нескольку раз за
        # запрос — членство в группах читается из БД один раз.
        cached = getattr(request, "_manager_site_access", None)
        if cached is None:
            cached = user.groups.filter(name__in=(MANAGERS_GROUP, SUPERVISORS_GROUP)).exists()
            request._manager_site_access = cached  # type: ignore[attr-defined]
        return bool(cached)

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[dict[str, Any]]:
        # Пользователи раздела — клиенты: так называются и блок, и модель.
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            if app["app_label"] != "users":
                continue
            for model in app["models"]:
                if model["object_name"] == "User":
                    model["name"] = "Клиенты"
                    app["name"] = "Клиенты"
        return app_list


manager_site = ManagerAdminSite(name="manager")
