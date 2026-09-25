"""
Celery задачи для асинхронного импорта данных из 1С
"""

import logging
from pathlib import Path
from typing import Any

from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

from apps.products.models import ImportSession, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor

logger = logging.getLogger(__name__)


@shared_task(
    name="apps.integrations.tasks.run_selective_import_task",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def run_selective_import_task(
    self: Any,
    selected_types: list[str],
    data_dir: (
        str
        | None
        # Этот аргумент больше не используется, но оставлен для обратной совместимости
    ) = None,
) -> dict[str, Any]:
    """
    Асинхронная задача для выборочного импорта данных из 1С.

    Args:
        selected_types: Список типов импорта (catalog, stocks, prices, customers)
        data_dir: Директория с данными 1С (если None, берется из settings)

    Returns:
        Dict с результатами импорта

    Raises:
        Exception: При критических ошибках импорта
    """
    task_id = self.request.id
    logger.info(f"[Task {task_id}] Запуск выборочного импорта: {selected_types}")

    # Получаем директорию с данными
    if data_dir is None:
        data_dir = getattr(settings, "ONEC_DATA_DIR", None)
        if not data_dir:
            error_msg = "Настройка ONEC_DATA_DIR не найдена в settings"
            logger.error(f"[Task {task_id}] {error_msg}")
            raise ValueError(error_msg)

    results: list[dict[str, str]] = []
    import_order = [
        "catalog",
        "attributes",
        "variants",
        "stocks",
        "prices",
        "customers",
        "images",
    ]

    try:
        for import_type in import_order:
            if import_type not in selected_types:
                continue

            logger.info(f"[Task {task_id}] Начало импорта: {import_type}")

            try:
                result = _execute_import_type(import_type, task_id)
                results.append(result)
                logger.info(f"[Task {task_id}] Импорт {import_type} завершен: " f"{result['message']}")
            except Exception as e:
                error_msg = f"Ошибка импорта {import_type}: {e}"
                logger.error(f"[Task {task_id}] {error_msg}", exc_info=True)
                # При ошибке прерываем цепочку
                raise Exception(error_msg) from e

        # Формируем итоговый результат
        summary = {
            "status": "success",
            "task_id": task_id,
            "completed_imports": [r["type"] for r in results],
            "messages": [r["message"] for r in results],
        }
        logger.info(f"[Task {task_id}] Импорт завершен успешно: {summary}")
        return summary

    except Exception as e:
        logger.error(
            f"[Task {task_id}] Критическая ошибка импорта: {e}",
            exc_info=True,
        )
        # Повторная попытка при ошибке (до max_retries раз)
        raise self.retry(exc=e)


def _execute_import_type(import_type: str, task_id: str) -> dict[str, str]:
    """
    Выполнение импорта конкретного типа данных.

    Args:
        import_type: (
            "Тип импорта (catalog, attributes, stocks, prices, customers, images)"
        )
        task_id: ID задачи Celery для логирования и связи с сессией

    Returns:
        Dict с результатом импорта

    Raises:
        FileNotFoundError: Если файл не найден
        Exception: При ошибках выполнения команды
    """
    if import_type == "catalog":
        logger.info(f"[Task {task_id}] Запуск import_products_from_1c --file-type=all")
        call_command(
            "import_products_from_1c",
            "--file-type",
            "all",
            "--celery-task-id",
            task_id,
        )
        return {"type": "catalog", "message": "Каталог импортирован"}

    elif import_type == "attributes":
        logger.info(f"[Task {task_id}] Запуск import_attributes --file-type=all")
        call_command("import_attributes", "--file-type", "all")
        return {
            "type": "attributes",
            "message": "Атрибуты и справочники импортированы",
        }

    elif import_type == "stocks":
        logger.info(f"[Task {task_id}] Запуск import_products_from_1c --file-type=rests")
        call_command(
            "import_products_from_1c",
            "--file-type",
            "rests",
            "--celery-task-id",
            task_id,
        )
        return {"type": "stocks", "message": "Остатки обновлены"}

    elif import_type == "prices":
        logger.info(f"[Task {task_id}] Запуск import_products_from_1c --file-type=prices")
        call_command(
            "import_products_from_1c",
            "--file-type",
            "prices",
            "--celery-task-id",
            task_id,
        )
        return {"type": "prices", "message": "Цены обновлены"}

    elif import_type == "customers":
        # Получаем директорию из settings для команды import_customers_from_1c
        onec_data_dir = getattr(settings, "ONEC_DATA_DIR", None)
        if not onec_data_dir:
            raise ValueError("Настройка ONEC_DATA_DIR не найдена в settings")
        logger.info(f"[Task {task_id}] Запуск import_customers_from_1c " f"--data-dir={onec_data_dir}")
        call_command("import_customers_from_1c", "--data-dir", onec_data_dir)
        return {"type": "customers", "message": "Клиенты импортированы"}

    elif import_type == "images":
        logger.info(f"[Task {task_id}] Запуск импорта изображений товаров")
        result = _run_image_import(task_id)
        return {"type": "images", "message": "Изображения обновлены"}

    elif import_type == "variants":
        logger.info(f"[Task {task_id}] Запуск импорта вариантов товаров")
        call_command(
            "import_products_from_1c",
            "--variants-only",
            "--celery-task-id",
            task_id,
        )
        return {"type": "variants", "message": "Варианты товаров импортированы"}

    else:
        raise ValueError(f"Неизвестный тип импорта: {import_type}")


def _get_product_images(product: Product, base_dir: Path) -> list[str]:
    """
    Получить список изображений для товара из директории 1С.

    Args:
        product: Product instance с onec_id
        base_dir: Путь к goods/import_files/

    Returns:
        Список относительных путей (например, ["00/001a16a4_image.jpg"])
    """
    if not product.onec_id:
        return []

    # Первые 2 символа onec_id определяют поддиректорию
    onec_id = product.onec_id
    subdir = onec_id[:2] if len(onec_id) >= 2 else "00"

    images_dir = base_dir / subdir

    if not images_dir.exists():
        return []

    # Поиск файлов начинающихся с onec_id
    image_paths = []
    for ext in ["*.jpg", "*.jpeg", "*.png"]:
        for img_file in images_dir.glob(f"{onec_id}*"):
            if img_file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                # Относительный путь от base_dir
                relative_path = f"{subdir}/{img_file.name}"
                image_paths.append(relative_path)

    return image_paths


def _run_image_import(task_id: str) -> dict[str, str]:
    """
    Импорт изображений товаров из директории 1С.

    Args:
        task_id: ID задачи Celery

    Returns:
        Dict с результатом импорта

    Raises:
        FileNotFoundError: Если директория import_files не найдена
        Exception: При критических ошибках импорта
    """
    logger.info(f"[Task {task_id}] Начало импорта изображений")

    # Найти сессию по task_id
    session = None
    try:
        session = ImportSession.objects.get(celery_task_id=task_id)
    except ImportSession.DoesNotExist:
        logger.warning(f"ImportSession не найдена для task_id: {task_id}")

    # Обновить статус на IN_PROGRESS
    if session:
        session.status = ImportSession.ImportStatus.IN_PROGRESS
        session.save(update_fields=["status"])
        logger.info(f"[Task {task_id}] ImportSession {session.id} установлена в IN_PROGRESS")

    try:
        # Получить директорию с данными 1С
        onec_data_dir = getattr(settings, "ONEC_DATA_DIR", None)
        if not onec_data_dir:
            raise ValueError("Настройка ONEC_DATA_DIR не найдена в settings")

        # Построить путь к директории изображений
        base_dir = Path(onec_data_dir) / "goods" / "import_files"

        # Проверить существование директории
        if not base_dir.exists():
            raise FileNotFoundError(
                f"Директория изображений не найдена: {base_dir}. " f"Убедитесь что данные из 1С синхронизированы."
            )

        logger.info(f"[Task {task_id}] Директория изображений: {base_dir}")

        # Получить все активные товары с onec_id
        products_qs = Product.objects.filter(is_active=True, onec_id__isnull=False).exclude(onec_id="")

        total_products = products_qs.count()
        processed = 0
        total_copied = 0
        total_skipped = 0
        total_errors = 0

        logger.info(f"[Task {task_id}] Найдено {total_products} активных товаров с onec_id")

        # Создать экземпляр процессора, используя ID текущей сессии (если найдена)
        processor_session_id = session.id if session else 0
        processor = VariantImportProcessor(session_id=processor_session_id)

        # Chunked processing для экономии памяти
        for product in products_qs.iterator(chunk_size=100):
            try:
                # Получить список изображений для товара
                image_paths = _get_product_images(product, base_dir)

                if not image_paths:
                    total_skipped += 1
                    processed += 1
                    continue

                # Epic 13/14: Импорт изображений в Product.base_images (Hybrid подход)
                # Это fallback для вариантов без собственных изображений
                processor._import_base_images(
                    product=product,
                    image_paths=image_paths,
                    base_dir=str(base_dir),
                )

                # Импортируем изображения в первый ProductVariant (если есть)
                # Это обеспечивает отображение изображений в карточках товаров
                first_variant = product.variants.first()
                if first_variant:
                    processor._import_variant_images(
                        variant=first_variant,
                        image_paths=image_paths,
                        base_dir=str(base_dir),
                    )
                    total_copied += len(image_paths)
                else:
                    # Если нет вариантов, считаем как base_images
                    total_copied += len(image_paths)

                processed += 1

                # Обновление прогресса каждые 50 товаров
                if processed % 50 == 0:
                    logger.info(
                        f"[Task {task_id}] Прогресс: {processed}/{total_products} "
                        f"товаров. Copied: {total_copied}, Skipped: {total_skipped}, "
                        f"Errors: {total_errors}"
                    )

                    if session:
                        session.report_details = {
                            "total_products": total_products,
                            "processed": processed,
                            "copied": total_copied,
                            "skipped": total_skipped,
                            "errors": total_errors,
                            "last_updated": timezone.now().isoformat(),
                        }
                        session.save(update_fields=["report_details"])

            except Exception as e:
                logger.error(
                    f"[Task {task_id}] Ошибка обработки товара {product.id} " f"(onec_id: {product.onec_id}): {e}"
                )
                total_errors += 1
                processed += 1
                # Продолжаем обработку остальных товаров

        # Финализация сессии
        if session:
            session.status = ImportSession.ImportStatus.COMPLETED
            session.finished_at = timezone.now()
            session.report_details = {
                "total_products": total_products,
                "processed": processed,
                "copied": total_copied,
                "skipped": total_skipped,
                "errors": total_errors,
                "completed_at": timezone.now().isoformat(),
            }
            session.save(update_fields=["status", "finished_at", "report_details"])
            logger.info(f"[Task {task_id}] ImportSession {session.id} завершена успешно")

        logger.info(
            f"[Task {task_id}] Импорт изображений завершен. "
            f"Обработано {processed} товаров. "
            f"Copied: {total_copied}, Skipped: {total_skipped}, Errors: {total_errors}"
        )

        return {
            "type": "images",
            "message": f"Обработано {processed} товаров. "
            f"Скопировано: {total_copied}, Пропущено: {total_skipped}, "
            f"Ошибок: {total_errors}",
        }

    except Exception as e:
        logger.error(
            f"[Task {task_id}] Критическая ошибка импорта изображений: {e}",
            exc_info=True,
        )

        # Обновить сессию как FAILED
        if session:
            session.status = ImportSession.ImportStatus.FAILED
            session.finished_at = timezone.now()
            session.error_message = str(e)
            session.save(update_fields=["status", "finished_at", "error_message"])
            logger.info(f"[Task {task_id}] ImportSession {session.id} помечена как FAILED")

        # Поднять исключение для retry механизма Celery
        raise
