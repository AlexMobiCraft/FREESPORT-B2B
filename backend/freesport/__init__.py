# Это гарантирует, что приложение Celery будет загружено при запуске Django.
import os

if os.environ.get("FREESPORT_DISABLE_CELERY") != "1":
    from .celery import app as celery_app

    __all__ = ("celery_app",)
