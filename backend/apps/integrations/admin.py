from __future__ import annotations

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from .models import Session

admin.site.site_header = "Администрирование портала OPTISPORT"
admin.site.site_title = "Администрирование портала OPTISPORT"  # опционально
admin.site.index_title = "Панель управления"  # опционально


@admin.register(Session)
class ImportSessionAdmin(admin.ModelAdmin):
    """
    Read-only Admin для журнала сессий импорта.

    Предоставляет доступ только для просмотра истории импортов
    с мониторингом Celery задач и автообновлением статусов.

    Запуск новых импортов осуществляется через отдельную страницу
    /admin/integrations/import_1c/
    """

    list_display = (
        "id",
        "import_type",
        "colored_status",
        "celery_task_status",
        "started_at",
        "finished_at",
        "duration",
    )
    list_filter = ("status", "import_type", "started_at")
    search_fields = ("id", "error_message")
    readonly_fields = (
        "id",
        "started_at",
        "finished_at",
        "report_details",
        "celery_task_id",
    )
    actions = []  # Удалены все admin actions - только просмотр

    class Media:
        """Добавляем JavaScript для автообновления страницы"""

        js = ("admin/js/import_session_auto_refresh.js",)

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": ("id", "import_type", "status", "celery_task_id"),
            },
        ),
        (
            "Детали",
            {
                "fields": (
                    "report_details",
                    "error_message",
                ),
            },
        ),
        (
            "Временные метки",
            {
                "fields": ("started_at", "finished_at"),
            },
        ),
    )

    # ========================================================================
    # Permission methods - Read-only режим
    # ========================================================================

    def has_add_permission(self, request: HttpRequest) -> bool:
        """
        Запрещаем создание новых сессий через admin.

        Сессии импорта создаются автоматически при запуске импорта
        через отдельную страницу /admin/integrations/import_1c/
        """
        return False

    def has_change_permission(self, request: HttpRequest, obj: Session | None = None) -> bool:
        """
        Запрещаем редактирование существующих сессий.

        Это журнал истории импортов, изменение записей не допускается
        для сохранения целостности данных аудита.
        """
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Session | None = None) -> bool:
        """
        Разрешаем удаление сессий для периодического cleanup.

        Причины:
        - Удаление тестовых/ошибочных сессий при разработке
        - Периодический cleanup старых данных (>6 месяцев)
        - Предотвращение бесконечного роста БД
        - Django Admin требует подтверждения перед удалением
        """
        return True

    @admin.display(description="Статус")
    def colored_status(self, obj: Session) -> str:
        """
        Отображение статуса с цветовой индикацией и иконками.

        - 🟢 Зеленый: completed
        - 🟡 Желтый: in_progress
        - 🔴 Красный: failed
        - ⚪ Серый: started
        """
        colors = {
            "completed": "green",
            "in_progress": "orange",
            "failed": "red",
            "started": "gray",
        }
        icons = {
            "completed": "✅",
            "in_progress": "⏳",
            "failed": "❌",
            "started": "⏸️",
        }
        color = colors.get(obj.status, "black")
        icon = icons.get(obj.status, "❓")
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.get_status_display(),
        )

    @admin.display(description="Celery Task")
    def celery_task_status(self, obj: Session) -> str:
        """
        Отображение статуса Celery задачи в реальном времени.

        Проверяет статус задачи через Celery API и показывает:
        - PENDING: задача в очереди
        - STARTED: задача выполняется
        - SUCCESS: задача завершена успешно
        - FAILURE: задача завершена с ошибкой
        - RETRY: задача ожидает повторной попытки
        """
        if not obj.celery_task_id:
            return format_html('<span style="color: gray;">{}</span>', "-")

        try:
            from celery.result import AsyncResult

            task_result: AsyncResult = AsyncResult(obj.celery_task_id)
            state = task_result.state

            # Маппинг статусов на иконки и цвета
            status_map = {
                "PENDING": ("⏳", "gray", "В очереди"),
                "STARTED": ("▶️", "blue", "Выполняется"),
                "SUCCESS": ("✅", "green", "Завершено"),
                "FAILURE": ("❌", "red", "Ошибка"),
                "RETRY": ("🔄", "orange", "Повтор"),
            }

            icon, color, label = status_map.get(state, ("❓", "black", state))

            return format_html(
                '<span style="color: {}; font-weight: bold;" title="Task ID: {}">' "{} {}</span>",
                color,
                obj.celery_task_id,
                icon,
                label,
            )
        except Exception:
            return format_html(
                '<span style="color: gray;" title="{}">⚠️ Недоступно</span>',
                obj.celery_task_id,
            )

    @admin.display(description="Длительность")
    def duration(self, obj: Session) -> str:
        """
        Расчет длительности импорта.

        Показывает время в минутах если импорт завершен,
        или "В процессе..." если еще выполняется.
        """
        if obj.finished_at and obj.started_at:
            delta = obj.finished_at - obj.started_at
            minutes = delta.total_seconds() / 60
            if minutes < 1:
                seconds = delta.total_seconds()
                return f"{seconds:.0f} сек"
            return f"{minutes:.1f} мин"
        elif obj.started_at:
            return "В процессе..."
        return "-"

    @admin.display(description="Прогресс")
    def progress_display(self, obj: Session) -> str:
        """
        Отображение прогресс-бара для импортов в процессе выполнения.

        Показывает HTML5 progress bar с процентами, если:
        - Статус: in_progress
        - Есть данные о прогрессе в report_details

        Поддерживает разные форматы report_details:
        - total_items/processed_items (catalog, stocks, prices)
        - total_products/processed (images)
        - total_customers/... (customers)
        """
        if obj.status == "in_progress" and obj.report_details:
            # Попытка получить данные в разных форматах
            total = (
                obj.report_details.get("total_items")
                or obj.report_details.get("total_products")
                or obj.report_details.get("total_customers")
                or 0
            )
            processed = obj.report_details.get("processed_items") or obj.report_details.get("processed") or 0

            if total > 0:
                progress = (processed / total) * 100
                progress_percent = f"{progress:.0f}"
                progress_bar = (
                    '<progress value="{}" max="100" '
                    'style="width: 150px; height: 20px;"></progress> '
                    '<span style="font-weight: bold;">{}%</span> ({}/{})'
                )
                return format_html(
                    progress_bar,
                    progress,
                    progress_percent,
                    processed,
                    total,
                )
        return "-"
