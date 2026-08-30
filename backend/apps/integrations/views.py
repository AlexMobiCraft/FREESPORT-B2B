"""
Views для страницы импорта данных из 1С.

Отдельная standalone страница для запуска нового импорта без необходимости
выбирать существующую сессию импорта.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django_redis import get_redis_connection

from apps.products.models import ImportSession, Product

from .tasks import run_selective_import_task

logger = logging.getLogger(__name__)


@staff_member_required
def import_from_1c_view(request: HttpRequest) -> HttpResponse:
    """
    Страница импорта данных из 1С.

    GET: Отображает форму выбора типа импорта с radio buttons
    POST: Обрабатывает запуск импорта и перенаправляет на страницу сессий

    Args:
        request: HTTP запрос

    Returns:
        TemplateResponse с формой или HttpResponse редирект
    """
    # POST запрос - запуск импорта
    if request.method == "POST":
        return _handle_import_request(request)

    # GET запрос - отображение формы
    from django.contrib.admin import site as admin_site

    context = {
        **admin_site.each_context(request),
        "title": "Импорт данных из 1С",
        "site_header": admin_site.site_header,
        "site_title": admin_site.site_title,
        "import_types": [
            {
                "value": "catalog",
                "label": "Полный каталог",
                "description": (
                    "Импорт всех данных: товары, категории, бренды, цены, " "остатки, свойства, справочники"
                ),
                "files": (
                    "goods_*.xml, offers_*.xml, prices_*.xml, rests_*.xml, " "groups.xml, units.xml, storages.xml"
                ),
                "requires_catalog": False,
            },
            {
                "value": "variants",
                "label": "Варианты товаров (ProductVariant)",
                "description": (
                    "Импорт SKU-вариантов товаров из offers.xml. "
                    "Создаёт ProductVariant с ценами, остатками, цветом и размером. "
                    "Требует предварительного импорта каталога товаров."
                ),
                "files": "offers_*.xml, prices_*.xml, rests_*.xml",
                "requires_catalog": True,
            },
            {
                "value": "attributes",
                "label": "Загрузить атрибуты (справочники)",
                "description": (
                    "Импорт атрибутов товаров и их значений. "
                    "Дубликаты объединяются автоматически по нормализованному имени. "
                    "Новые атрибуты импортируются как неактивные (is_active=False). "
                    "После импорта активируйте нужные атрибуты в разделе "
                    "Товары → Атрибуты."
                ),
                "files": "propertiesGoods/*.xml, propertiesOffers/*.xml",
                "requires_catalog": False,
            },
            {
                "value": "images",
                "label": "Только изображения товаров",
                "description": ("Обновление изображений товаров из директории 1С " "(main_image и gallery_images)"),
                "files": "data/import_1c/goods/import_files/**/*.jpg, **/*.png",
                "requires_catalog": True,
            },
            {
                "value": "stocks",
                "label": "Только остатки",
                "description": "Обновление остатков товаров на складах",
                "files": "rests_*.xml",
                "requires_catalog": True,
            },
            {
                "value": "prices",
                "label": "Только цены",
                "description": "Обновление цен товаров",
                "files": "prices_*.xml",
                "requires_catalog": True,
            },
            {
                "value": "customers",
                "label": "Клиенты",
                "description": "Импорт контрагентов из 1С",
                "files": "contragents.xml",
                "requires_catalog": False,
            },
        ],
    }
    return TemplateResponse(request, "admin/integrations/import_1c.html", context)


def _handle_import_request(request: HttpRequest) -> HttpResponse:
    """
    Обработка POST запроса на запуск импорта.

    Args:
        request: HTTP запрос с данными формы

    Returns:
        HttpResponse редирект на страницу сессий или обратно на форму
    """
    import_type = request.POST.get("import_type")

    if not import_type:
        messages.warning(request, "⚠️ Не выбран тип импорта.")
        return redirect("admin:integrations_import_from_1c")

    # Валидация зависимостей
    is_valid, error_message = _validate_dependencies([import_type])
    if not is_valid:
        messages.error(request, error_message)
        return redirect("admin:integrations_import_from_1c")

    # Проверка Redis lock
    redis_conn = get_redis_connection("default")
    lock_key = "import_catalog_lock"
    lock = redis_conn.lock(lock_key, timeout=3600)  # 1 час TTL

    if not lock.acquire(blocking=False):
        logger.warning("Импорт уже запущен, блокировка активна")
        messages.warning(
            request,
            "⚠️ Импорт уже запущен! Дождитесь завершения текущего импорта.",
        )
        return redirect("admin:integrations_import_from_1c")

    try:
        # Запуск импорта
        session = _create_and_run_import(import_type)

        messages.success(
            request,
            f"✅ Импорт запущен (Task ID: {session.celery_task_id}, "
            f"Session ID: {session.pk}). "
            f"Вы будете перенаправлены на страницу сессий для отслеживания прогресса.",
        )

        # Редирект на страницу сессий (обновлен после переименования модели)
        return redirect("admin:integrations_session_changelist")

    except Exception as e:
        logger.error(f"Ошибка запуска импорта: {e}", exc_info=True)
        messages.error(request, f"❌ Ошибка запуска импорта: {e}")
        return redirect("admin:integrations_import_from_1c")
    finally:
        lock.release()


def _validate_dependencies(selected_types: list[str]) -> tuple[bool, str]:
    """
    Проверка зависимостей между типами импорта.

    Args:
        selected_types: Список выбранных типов импорта

    Returns:
        Tuple[bool, str]: (is_valid, error_message)
    """
    # Типы, требующие наличия товаров в БД
    catalog_dependent_types = ["stocks", "prices", "images", "variants"]

    if any(t in selected_types for t in catalog_dependent_types):
        if not Product.objects.exists():
            # Определяем какой тип был выбран для более точного сообщения
            if "images" in selected_types:
                return (
                    False,
                    "⚠️ Невозможно загрузить изображения: "
                    "каталог товаров пуст. Сначала импортируйте полный каталог.",
                )
            else:
                return (
                    False,
                    "⚠️ Невозможно загрузить остатки/цены/варианты: "
                    "каталог товаров пуст. Сначала импортируйте полный каталог.",
                )
    return True, ""


def _create_and_run_import(import_type: str) -> ImportSession:
    """
    Создание сессии импорта и запуск Celery задачи.

    Args:
        import_type: Тип импорта (catalog, images, stocks, prices, customers)

    Returns:
        ImportSession: Созданная сессия импорта

    Raises:
        ValueError: Если ONEC_DATA_DIR не настроен
    """
    request_id = str(uuid.uuid4())[:8]
    logger.info(f"[Request {request_id}] Запуск импорта типа: {import_type}")

    # Проверяем наличие настройки ONEC_DATA_DIR
    data_dir = getattr(settings, "ONEC_DATA_DIR", None)
    if not data_dir:
        raise ValueError("Настройка ONEC_DATA_DIR не найдена в settings. " "Убедитесь, что путь к данным 1С настроен.")

    # Проверяем существование директории данных
    data_path = Path(data_dir)
    if not data_path.exists():
        raise FileNotFoundError(
            f"Директория данных 1С не найдена: {data_dir}. " f"Убедитесь, что данные выгружены из 1С."
        )

    # Проверяем наличие необходимых поддиректорий в зависимости от типа импорта
    if import_type == "catalog":
        required_subdirs = ["goods", "offers", "prices", "rests"]
        missing_subdirs = [subdir for subdir in required_subdirs if not (data_path / subdir).exists()]
        if missing_subdirs:
            raise FileNotFoundError(
                f"Отсутствуют обязательные поддиректории в {data_dir}: "
                f"{', '.join(missing_subdirs)}. "
                f"Убедитесь, что данные выгружены из 1С в правильной структуре."
            )
    elif import_type == "stocks":
        if not (data_path / "rests").exists():
            raise FileNotFoundError(
                f"Директория остатков не найдена: {data_path / 'rests'}. " f"Убедитесь, что данные выгружены из 1С."
            )
    elif import_type == "prices":
        if not (data_path / "prices").exists():
            raise FileNotFoundError(
                f"Директория цен не найдена: {data_path / 'prices'}. " f"Убедитесь, что данные выгружены из 1С."
            )
    elif import_type == "customers":
        if not (data_path / "contragents").exists():
            raise FileNotFoundError(
                f"Директория контрагентов не найдена: {data_path / 'contragents'}. "
                f"Убедитесь, что данные выгружены из 1С."
            )
    elif import_type == "images":
        import_files_dir = data_path / "goods" / "import_files"
        if not import_files_dir.exists():
            raise FileNotFoundError(
                f"Директория изображений не найдена: {import_files_dir}. "
                f"Убедитесь, что данные выгружены из 1С с изображениями товаров."
            )
    elif import_type == "variants":
        required_subdirs = ["offers", "prices", "rests"]
        missing_subdirs = [subdir for subdir in required_subdirs if not (data_path / subdir).exists()]
        if missing_subdirs:
            raise FileNotFoundError(
                f"Отсутствуют обязательные поддиректории в {data_dir}: "
                f"{', '.join(missing_subdirs)}. "
                f"Убедитесь, что данные выгружены из 1С в правильной структуре."
            )

    # Маппинг типов импорта на типы сессий
    session_type_map = {
        "catalog": ImportSession.ImportType.CATALOG,
        "variants": ImportSession.ImportType.VARIANTS,
        "images": ImportSession.ImportType.IMAGES,
        "stocks": ImportSession.ImportType.STOCKS,
        "prices": ImportSession.ImportType.PRICES,
        "customers": ImportSession.ImportType.CUSTOMERS,
    }

    session_import_type = session_type_map.get(import_type, ImportSession.ImportType.CATALOG)

    # Запускаем Celery задачу
    task = run_selective_import_task.delay([import_type])

    # Создаем сессию импорта для отслеживания
    # Команда import_customers_from_1c создаст свою внутреннюю сессию
    # но мы создаем сессию здесь для единообразия и отображения в UI
    session = ImportSession.objects.create(
        import_type=session_import_type,
        status=ImportSession.ImportStatus.STARTED,
        celery_task_id=task.id,
    )

    logger.info(f"[Request {request_id}] Импорт запущен. " f"Session ID: {session.pk}, Task ID: {task.id}")

    return session
