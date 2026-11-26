"""
Сайты Django-админки OPTISPORT: основная `/admin/`, раздел менеджера `/manager/`,
раздел маркетинга `/marketing/` и раздел руководителя `/supervisor/`.

Эпик 42: флаг `is_staff` теперь означает «сотрудник» (менеджер, маркетинг,
руководитель), а не «администратор». Сотрудникам `is_staff` нужен для входа
в их собственные разделы, поэтому основная `/admin/` с логами синхронизации,
привязками к 1С и служебными полями открыта только суперпользователю.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.contrib import admin
from django.http import Http404, HttpRequest
from django.template.response import TemplateResponse
from django.urls import URLPattern, URLResolver, path, reverse

from apps.users.staff_instructions import STAFF_INSTRUCTIONS, get_instruction
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP, is_supervisor

# Период сводки руководителя в его сессии: строка `?date_from=…&date_to=…`, собранная
# из двух проверенных дат. По ней ссылка «← Раздел руководителя» возвращает в сводку.
SUMMARY_PERIOD_SESSION_KEY = "supervisor_summary_period"


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


class StaffSectionAdminSite(admin.AdminSite):
    """
    Общая проверка входа в раздел сотрудника.

    Пускает активного сотрудника (`is_staff`) из групп `section_groups`.
    Суперпользователя раздел не пускает, даже если он состоит в группе:
    у него есть `/admin/` с тем же и большим, а членство в группе не должно
    превращать его в сотрудника с урезанным видом. Отказ — штатный 302 на
    страницу входа раздела.
    """

    section_groups: tuple[str, ...] = ()

    def has_permission(self, request: HttpRequest) -> bool:
        user = request.user
        if not (user.is_active and user.is_staff) or user.is_superuser:
            return False
        # admin_view и each_context зовут has_permission по нескольку раз за
        # запрос — членство в группах читается из БД один раз. Кэш — словарь по
        # имени сайта: один запрос проверяют разные разделы, и общий атрибут
        # отдал бы одному разделу ответ другого.
        access = getattr(request, "_staff_section_access", None)
        if access is None:
            access = {}
            request._staff_section_access = access  # type: ignore[attr-defined]
        if self.name not in access:
            access[self.name] = user.groups.filter(name__in=self.section_groups).exists()
        return bool(access[self.name])

    def each_context(self, request: HttpRequest) -> dict[str, Any]:
        # Руководитель входит в разделы менеджера и маркетинга, а их боковое меню
        # строится из моделей своего сайта: без блока разделов он не вернулся бы
        # в /supervisor/. Блок «Разделы» рисует admin/nav_sidebar.html по ключу
        # supervisor_sections, ссылки в шапке — admin/base_site.html по
        # supervisor_home_url (в /manager/, /marketing/) и supervisor_header_links
        # (в /supervisor/): боковое меню на узких экранах скрыто.
        context = super().each_context(request)
        # В /supervisor/ пускает только группа «Руководители»: is_supervisor не нужен.
        if context["has_permission"] and (self.name == "supervisor" or is_supervisor(request)):
            context["supervisor_sections"] = self._supervisor_sections(request)
            if self.name == "supervisor":
                # Шапка видна на узких экранах и при свёрнутом боковом меню, где блока
                # «Разделы» нет: туда выносятся пункты, кроме текущего выделенного.
                context["supervisor_header_links"] = [s for s in context["supervisor_sections"] if not s["current"]]
            else:
                # Руководитель смотрел сводку за выбранный период и вернётся в неё же.
                period_query = getattr(request, "session", {}).get(SUMMARY_PERIOD_SESSION_KEY, "")
                context["supervisor_home_url"] = reverse("supervisor:index") + period_query
        return context

    def _supervisor_sections(self, request: HttpRequest) -> list[dict[str, Any]]:
        """
        Разделы руководителя для бокового меню; `current` — раздел, в котором сидит запрос.

        Флаг считается по сайту и точному пути, а не по вхождению пути в шаблоне:
        `/supervisor/` — префикс каждого URL раздела, и «Сводка» горела бы везде.
        На страницах моделей /supervisor/ не выделен ни один пункт.
        """
        in_supervisor = self.name == "supervisor"
        index_url = reverse("supervisor:index")
        journal_url = reverse("supervisor:journal")
        summary_urls = (index_url, reverse("supervisor:summary"))
        return [
            {"url": index_url, "name": "Сводка", "current": in_supervisor and request.path in summary_urls},
            {"url": journal_url, "name": "Журнал действий", "current": in_supervisor and request.path == journal_url},
            {"url": reverse("manager:index"), "name": "Клиенты и заказы", "current": self.name == "manager"},
            {"url": reverse("marketing:index"), "name": "Маркетинг", "current": self.name == "marketing"},
        ]


class ManagerAdminSite(StaffSectionAdminSite):
    """
    Раздел менеджера `/manager/`: клиенты, за которых отвечает сотрудник (стори 42.4),
    их заказы и очередь главной (стори 42.5).

    Пускает активного сотрудника (`is_staff`) из группы «Менеджеры» или
    «Руководители» — ровно критерий `RESPONSIBLE_MANAGER_CHOICES` плюс
    `is_active`: в раздел входит тот, кого можно назначить ответственным.
    Суперпользователя раздел не пускает, даже если он состоит в группе:
    у него есть `/admin/` с тем же и большим, а членство в группе не должно
    превращать его в «менеджера» с урезанной видимостью. Отказ — штатный
    302 на `/manager/login/`.
    """

    site_header = "OPTISPORT — Менеджер"
    site_title = "OPTISPORT — Менеджер"
    index_title = "Раздел менеджера"
    # Без блока «Последние действия»: его ссылки строит LogEntry.get_admin_url()
    # через reverse("admin:…") без current_app, то есть в закрытую /admin/.
    index_template = "admin/manager/index.html"
    section_groups = (MANAGERS_GROUP, SUPERVISORS_GROUP)

    def get_urls(self) -> list[URLResolver | URLPattern]:
        # Свои пути — до родительских: AdminSite.get_urls() заканчивается
        # catch-all, и путь после него отвечал бы 404.
        return [
            path("instructions/", self.admin_view(self.instructions_view), name="instructions"),
            path("instructions/<slug:slug>/", self.admin_view(self.instruction_view), name="instruction"),
            *super().get_urls(),
        ]

    def instructions_view(self, request: HttpRequest) -> TemplateResponse:
        # current_app — для reverse() и {% url 'admin:…' %}: без него ссылки шапки
        # и хлебных крошек вели бы в закрытую /admin/.
        request.current_app = self.name
        context = {**self.each_context(request), "title": "Инструкции", "instructions": STAFF_INSTRUCTIONS}
        return TemplateResponse(request, "admin/instructions/index.html", context)

    def instruction_view(self, request: HttpRequest, slug: str) -> TemplateResponse:
        instruction = get_instruction(slug)
        if instruction is None:
            raise Http404("Инструкция не найдена")
        request.current_app = self.name
        context = {
            **self.each_context(request),
            "title": instruction.title,
            "instruction": instruction,
            "other_instructions": [other for other in STAFF_INSTRUCTIONS if other.slug != instruction.slug],
        }
        return TemplateResponse(request, "admin/instructions/detail.html", context)

    def index(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> TemplateResponse:
        # Очередь главной (стори 42.5). Импорт внутри метода: модуль заказов
        # раздела сам импортирует manager_site, импорт на уровне модуля дал бы цикл.
        from apps.orders.manager_admin import manager_queue

        extra_context = {
            **(extra_context or {}),
            "manager_queue": manager_queue(request, self),
            "staff_instructions": STAFF_INSTRUCTIONS,
        }
        return super().index(request, extra_context)

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


class MarketingAdminSite(StaffSectionAdminSite):
    """
    Раздел маркетинга `/marketing/` (стори 42.6): баннеры, новости и блог,
    рубрики, метки товаров, бренды и категории главной.

    Пускает активного сотрудника из группы «Маркетинг» или «Руководители»;
    суперпользователя — нет (см. `StaffSectionAdminSite`). Фильтра по региону
    у маркетинга нет, руководитель видит раздел целиком.
    """

    site_header = "OPTISPORT — Маркетинг"
    site_title = "OPTISPORT — Маркетинг"
    index_title = "Раздел маркетинга"
    # Без блока «Последние действия» — по той же причине, что у раздела менеджера.
    index_template = "admin/marketing/index.html"
    section_groups = (MARKETING_GROUP, SUPERVISORS_GROUP)

    def index(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> TemplateResponse:
        # Плашка подписчиков. Импорт внутри метода: модуль раздела сам
        # импортирует marketing_site, импорт на уровне модуля дал бы цикл.
        from apps.common.marketing_admin import newsletter_stats

        extra_context = {**(extra_context or {}), "newsletter_stats": newsletter_stats()}
        return super().index(request, extra_context)

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[dict[str, Any]]:
        # «Общие утилиты» в разделе — это новости и блог; их «Категории» —
        # рубрики, иначе рядом с «Категориями для главной» две похожие «Категории».
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            if app["app_label"] != "common":
                continue
            app["name"] = "Новости и блог"
            for model in app["models"]:
                if model["object_name"] == "Category":
                    model["name"] = "Рубрики"
        return app_list


marketing_site = MarketingAdminSite(name="marketing")


class SupervisorAdminSite(StaffSectionAdminSite):
    """
    Раздел руководителя `/supervisor/` (стори 42.7): сотрудники, правила
    регионов, получатели уведомлений и бонусная программа. Главная `/supervisor/`
    — сводка (стори 42.8): заявки, заказы и выручка отдела; путь
    `/supervisor/summary/` отдаёт её же.
    Журнал действий `/supervisor/journal/` (стори 42.9) — лента того, что
    сделали сотрудники.

    Пускает активного сотрудника из группы «Руководители»; суперпользователя —
    нет (см. `StaffSectionAdminSite`). Клиентов и заказы руководитель смотрит
    в `/manager/` — там для него снят фильтр по ответственному, — а витрину
    в `/marketing/`: оба раздела пускают «Руководителей».
    """

    site_header = "OPTISPORT — Руководитель"
    site_title = "OPTISPORT — Руководитель"
    index_title = "Раздел руководителя"
    section_groups = (SUPERVISORS_GROUP,)

    def get_urls(self) -> list[URLResolver | URLPattern]:
        # Свои пути — до родительских: AdminSite.get_urls() заканчивается
        # catch-all, и путь после него отвечал бы 404.
        return [
            path("summary/", self.admin_view(self.summary_view), name="summary"),
            path("journal/", self.admin_view(self.journal_view), name="journal"),
            *super().get_urls(),
        ]

    def summary_view(self, request: HttpRequest) -> TemplateResponse:
        return self._summary_response(request)

    def journal_view(self, request: HttpRequest) -> TemplateResponse:
        # Как summary_view: current_app — для reverse() и {% url 'admin:…' %}.
        request.current_app = self.name
        # Импорт внутри метода: модуль ленты через apps.orders.manager_admin
        # импортирует этот модуль, импорт на уровне модуля дал бы цикл.
        from apps.common.staff_journal import build_journal

        context = {**self.each_context(request), "title": "Журнал действий", **build_journal(request)}
        return TemplateResponse(request, "admin/supervisor/journal.html", context)

    def index(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> TemplateResponse:
        # Главная — сразу сводка, а не витрина разделов: разделы руководителя
        # лежат в боковом меню (supervisor_sections из each_context).
        return self._summary_response(request, extra_context)

    def _summary_response(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> TemplateResponse:
        # Как AdminSite.index: reverse() в Python без current_app вёл бы в /admin/.
        request.current_app = self.name
        # Импорт внутри метода: модуль сводки через apps.orders.manager_admin
        # импортирует этот модуль, импорт на уровне модуля дал бы цикл.
        from apps.orders.supervisor_summary import build_summary

        base = self.each_context(request)
        summary = build_summary(request)
        self._remember_period(request, summary["period_form"], summary["period"])
        # Ключ главной AdminSite.index: список приложений уже собран в each_context,
        # второй get_app_list не нужен. extra_context идёт последним, как у index().
        context = {
            **base,
            "title": "Сводка",
            "app_list": base["available_apps"],
            **summary,
            **(extra_context or {}),
        }
        return TemplateResponse(request, "admin/supervisor/summary.html", context)

    @staticmethod
    def _remember_period(request: HttpRequest, form: forms.Form, period: Any) -> None:
        """
        Запоминает период, за который руководитель смотрит сводку.

        Вход без параметров сбрасывает запомненное (вернётся период по умолчанию),
        неверный период сессию не трогает. Сессия пишется только при изменении
        значения: повторный заход лишнего запроса не стоит.
        """
        if form.is_bound and not form.is_valid():
            return
        session = request.session
        if not form.is_bound:
            session.pop(SUMMARY_PERIOD_SESSION_KEY, None)
        elif session.get(SUMMARY_PERIOD_SESSION_KEY) != period.query:
            session[SUMMARY_PERIOD_SESSION_KEY] = period.query

    def get_app_list(self, request: HttpRequest, app_label: str | None = None) -> list[dict[str, Any]]:
        # Пользователи раздела — сотрудники; «Общие утилиты» — регионы и
        # получатели уведомлений.
        app_list = super().get_app_list(request, app_label)
        for app in app_list:
            if app["app_label"] == "users":
                app["name"] = "Сотрудники"
                for model in app["models"]:
                    if model["object_name"] == "User":
                        model["name"] = "Сотрудники"
            elif app["app_label"] == "common":
                app["name"] = "Регионы и уведомления"
                for model in app["models"]:
                    if model["object_name"] == "ManagerRoutingRule":
                        model["name"] = "Правила регионов"
        return app_list


supervisor_site = SupervisorAdminSite(name="supervisor")
