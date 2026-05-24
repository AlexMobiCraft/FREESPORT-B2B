"""Конфигурация Celery для проекта FREESPORT.

Этот файл настраивает приложение Celery, определяет периодические задачи
и обеспечивает интеграцию с Django.
"""

import os

from celery import Celery
from celery.schedules import crontab

# Устанавливаем переменную окружения для настроек Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freesport.settings.development")

app = Celery("freesport")

# Используем конфигурацию из настроек Django
# Неймспейс 'CELERY' означает, что все настройки Celery
# должны начинаться с CELERY_ в файле настроек.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Автоматически обнаруживаем и регистрируем задачи из всех приложений Django
app.autodiscover_tasks()

# Настройка периодических задач (Celery Beat)
app.conf.beat_schedule = {
    # Задача для очистки "брошенных" корзин
    "clear-abandoned-carts-every-hour": {
        "task": "apps.cart.tasks.clear_abandoned_carts_task",
        "schedule": crontab(minute="0", hour="*"),  # Запускать каждый час
        "args": (24,),  # Передаем аргумент `hours=24` в задачу
        "options": {
            "expires": 3500,  # Задача должна выполниться в течение часа
        },
    },
    # Задача для очистки зависших сессий импорта 1С
    "cleanup-stale-import-sessions-every-hour": {
        "task": "apps.products.tasks.cleanup_stale_import_sessions",
        "schedule": crontab(minute="30", hour="*"),  # Запускать каждые полчаса (в :30)
        "options": {
            "expires": 3500,
        },
    },
}


@app.task(bind=True)
def debug_task(self):
    """Отладочная задача для вывода информации о запросе.

    Args:
        self: Экземпляр задачи, передаваемый Celery.
    """
    print(f"Request: {self.request!r}")
