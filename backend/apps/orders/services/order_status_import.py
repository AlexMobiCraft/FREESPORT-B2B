"""
Сервис импорта статусов заказов из 1С в формате CommerceML 3.1.

Реализует Service Layer паттерн с разделением Parser/Processor:
- _parse_orders_xml() — чистый парсинг XML, возврат dataclass
- _process_order_update() — бизнес-логика обновления Order
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from xml.etree.ElementTree import Element
from zoneinfo import ZoneInfo

import defusedxml.ElementTree as ET
from defusedxml.common import DefusedXmlException
from django.conf import settings
from django.db import OperationalError, transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.orders.constants import (
    ACTIVE_STATUSES,
    ALLOWED_REQUISITES,
    FINAL_STATUSES,
    MAX_CONSECUTIVE_ERRORS,
    MAX_ERRORS,
    ORDER_ID_PREFIX,
    STATUS_MAPPING,
    STATUS_MAPPING_LOWER,
    STATUS_PRIORITY,
    ProcessingStatus,
)
from apps.orders.models import Order

logger = logging.getLogger(__name__)

# [AI-Review][Low] Regex вынесен на уровень модуля для оптимизации
REQUISITE_NAME_WHITESPACE_RE = re.compile(r"\s+")


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class OrderUpdateData:
    """Данные для обновления заказа, извлечённые из XML."""

    order_id: str  # Значение <Ид>, формат: 'order-{id}'
    order_number: str  # Значение <Номер>
    status_1c: str  # Оригинальный статус из 1С (СтатусЗаказа)
    paid_at: datetime | None = None  # Дата оплаты (ДатаОплаты)
    shipped_at: datetime | None = None  # Дата отгрузки (ДатаОтгрузки)
    # Флаги наличия тегов дат в XML (для корректного сброса)
    paid_at_present: bool = False  # True если тег <ДатаОплаты> присутствует в XML
    shipped_at_present: bool = False  # True если тег <ДатаОтгрузки> присутствует в XML
    # [AI-Review][Medium] Observability: ошибки парсинга дат для ImportResult.errors
    parse_warnings: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    """Результат импорта статусов заказов."""

    processed: int = 0  # Всего обработано документов
    updated: int = 0  # Успешно обновлено заказов
    skipped_up_to_date: int = 0  # Пропущено: данные уже актуальны
    skipped_unknown_status: int = 0  # Пропущено: неизвестный статус 1С
    skipped_data_conflict: int = 0  # Пропущено: конфликт данных (номер/ID)
    skipped_status_regression: int = 0  # Пропущено: попытка регрессии статуса
    skipped_invalid: int = 0  # Пропущено: некорректные документы
    not_found: int = 0  # Заказ не найден в БД
    errors: list[str] = field(default_factory=list)  # Ошибки парсинга/обработки

    @property
    def skipped(self) -> int:
        """
        [AI-Review][Low] AC Deviation: суммарное количество пропущенных заказов.

        Обеспечивает совместимость с AC9, где указан `skipped_count`.
        Гранулярные метрики (skipped_up_to_date, skipped_unknown_status, etc.)
        доступны для детального мониторинга.
        """
        return (
            self.skipped_up_to_date
            + self.skipped_unknown_status
            + self.skipped_data_conflict
            + self.skipped_status_regression
            + self.skipped_invalid
        )


class DocumentParseError(Exception):
    """Ошибка парсинга одного документа orders.xml."""


# =============================================================================
# Service
# =============================================================================


class OrderStatusImportService:
    """
    Сервис импорта статусов заказов из XML 1С (CommerceML 3.1).

    Реализует Service Layer паттерн — вся бизнес-логика обновления статусов
    инкапсулирована в этом классе.

    Usage:
        service = OrderStatusImportService()
        result = service.process(xml_data)
        print(
            f"Updated: {result.updated}, "
            f"Skipped up-to-date: {result.skipped_up_to_date}, "
            f"Skipped unknown status: {result.skipped_unknown_status}, "
            f"Skipped invalid: {result.skipped_invalid}"
        )
    """

    def process(self, xml_data: str | bytes) -> ImportResult:
        """
        Основная точка входа: парсить XML и обновить статусы заказов.

        Args:
            xml_data: XML-строка или bytes в формате CommerceML 3.1.

        Returns:
            ImportResult с подробной статистикой обработки.
        """
        result = ImportResult()

        # PARSE: извлечь данные из XML
        try:
            order_updates, total_documents, parse_errors = self._parse_orders_xml(xml_data)
        except DefusedXmlException as e:
            logger.error(f"XML security error: {e}")
            result.errors.append(f"XML security error: {e}")
            return result
        except ET.ParseError as e:
            logger.error(f"XML parse error: {e}")
            result.errors.append(f"XML parse error: {e}")
            return result

        # [AI-Review][Low] Учитываем все найденные <Документ>, включая некорректные
        result.processed = total_documents

        if parse_errors:
            result.skipped_invalid = len(parse_errors)
            for error_msg in parse_errors:
                if len(result.errors) >= MAX_ERRORS:
                    break
                result.errors.append(error_msg)

        # [AI-Review][Medium] Observability: собираем ошибки парсинга дат из OrderUpdateData
        for order_data in order_updates:
            for warning in order_data.parse_warnings:
                if len(result.errors) >= MAX_ERRORS:
                    break
                result.errors.append(warning)

        # PROCESS: обновить каждый заказ
        # [AI-Review][High] Изоляция ошибок — одна ошибка не останавливает весь процесс
        # [AI-Review][Medium] Rate-limited logging: остановка логирования после N последовательных ошибок
        consecutive_errors = 0
        log_suppressed = False

        # [AI-Review][Medium] Batch processing — сокращаем длительные блокировки
        batch_size = self._get_batch_size()

        # [AI-Review][High] Защита от race condition — блокировки в bulk fetch
        for start in range(0, len(order_updates), batch_size):
            batch = order_updates[start : start + batch_size]
            try:
                with transaction.atomic():
                    # BULK FETCH: загрузить заказы для пакета (оптимизация N+1)
                    orders_cache = self._bulk_fetch_orders(batch)

                    for order_data in batch:
                        try:
                            status, update_error = self._process_order_update(order_data, orders_cache)
                            # [AI-Review][Medium] Используем Enum вместо magic strings
                            if status == ProcessingStatus.UPDATED:
                                result.updated += 1
                                consecutive_errors = 0  # Сброс счётчика при успехе
                            elif status == ProcessingStatus.SKIPPED_UP_TO_DATE:
                                result.skipped_up_to_date += 1
                            elif status == ProcessingStatus.SKIPPED_UNKNOWN_STATUS:
                                result.skipped_unknown_status += 1
                            elif status == ProcessingStatus.SKIPPED_DATA_CONFLICT:
                                result.skipped_data_conflict += 1
                            elif status == ProcessingStatus.SKIPPED_STATUS_REGRESSION:
                                result.skipped_status_regression += 1
                            elif status == ProcessingStatus.NOT_FOUND:
                                result.not_found += 1
                                consecutive_errors += 1

                            # Сбор ошибок из _process_order_update
                            if update_error and len(result.errors) < MAX_ERRORS:
                                result.errors.append(update_error)

                        except Exception as e:
                            consecutive_errors += 1
                            order_ref = order_data.order_number or order_data.order_id
                            update_error = f"Error processing order {order_ref}: {e}"

                            # Rate-limited logging: предотвращаем флуд логов
                            if consecutive_errors <= MAX_CONSECUTIVE_ERRORS:
                                logger.exception(update_error)
                            elif not log_suppressed:
                                logger.warning(
                                    f"Suppressing further error logs after "
                                    f"{MAX_CONSECUTIVE_ERRORS} consecutive errors"
                                )
                                log_suppressed = True

                            if len(result.errors) < MAX_ERRORS:
                                result.errors.append(update_error)
            except OperationalError as e:
                consecutive_errors += 1
                update_error = f"Database error during bulk fetch: {e}"
                if consecutive_errors <= MAX_CONSECUTIVE_ERRORS:
                    logger.exception(update_error)
                elif not log_suppressed:
                    logger.warning(
                        f"Suppressing further error logs after " f"{MAX_CONSECUTIVE_ERRORS} consecutive errors"
                    )
                    log_suppressed = True
                if len(result.errors) < MAX_ERRORS:
                    result.errors.append(update_error)
                continue

        # Итоговое сообщение, если логи были подавлены
        if log_suppressed:
            logger.info(
                f"Processing complete. Total errors suppressed: " f"{consecutive_errors - MAX_CONSECUTIVE_ERRORS}"
            )

        return result

    # =========================================================================
    # Parser Methods
    # =========================================================================

    def _parse_orders_xml(self, xml_data: str | bytes) -> tuple[list[OrderUpdateData], int, list[str]]:
        """
        Парсинг XML orders.xml в формате CommerceML 3.1.

        XML структура (ожидаемая)::

            <КоммерческаяИнформация>
                <Контейнер>
                    <Документ>
                        <Ид>order-123</Ид>
                        <Номер>FS-20260202-001</Номер>
                        <ЗначенияРеквизитов>
                            <ЗначениеРеквизита>
                                <Наименование>СтатусЗаказа</Наименование>
                                <Значение>Отгружен</Значение>
                            </ЗначениеРеквизита>
                            ...
                        </ЗначенияРеквизитов>
                    </Документ>
                </Контейнер>
            </КоммерческаяИнформация>

        Args:
            xml_data: XML-строка или bytes.

        Returns:
            tuple: (список OrderUpdateData, общее число найденных <Документ>,
            список ошибок парсинга документов).

        Raises:
            ET.ParseError: при невалидном XML.
        """
        # defusedxml.ElementTree handles encoding automatically

        root = ET.fromstring(xml_data)
        order_updates: list[OrderUpdateData] = []
        parse_errors: list[str] = []

        # [AI-Review][High] Гибкий поиск <Документ>:
        # 1. Сначала ищем .//Документ везде в дереве (наиболее гибко)
        # 2. Это покрывает: <Контейнер><Документ>, <Документ> напрямую, вложенные структуры
        documents = root.findall(".//Документ")

        total_documents = len(documents)
        for document in documents:
            try:
                order_data = self._parse_document(document)
            except DocumentParseError as exc:
                parse_errors.append(str(exc))
                continue

            order_updates.append(order_data)

        return order_updates, total_documents, parse_errors

    def _parse_document(self, document: Element) -> OrderUpdateData:
        """
        Парсинг одного элемента <Документ>.

        Args:
            document: XML элемент <Документ>.

        Returns:
            OrderUpdateData.

        Raises:
            DocumentParseError: если документ некорректен и должен быть пропущен.
        """
        order_id_elem = document.find("Ид")
        order_number_elem = document.find("Номер")

        order_id = order_id_elem.text if order_id_elem is not None else ""
        order_number = order_number_elem.text if order_number_elem is not None else ""

        if not order_id and not order_number:
            raise DocumentParseError("Document without <Ид> and <Номер>, skipping")

        # [AI-Review][Low] Оптимизация: собрать все реквизиты в dict один раз
        # [AI-Review][High] Нормализация имен: поддержка "Статус Заказа" и "СтатусЗаказа"
        requisites = self._extract_all_requisites(document)

        # Извлечь статус из реквизитов (нормализация уже в _extract_all_requisites)
        status_1c = requisites.get("статусзаказа")
        if not status_1c:
            error_msg = f"Document {order_id or order_number}: no СтатусЗаказа requisite"
            logger.warning(error_msg)
            raise DocumentParseError(error_msg)

        # Извлечь даты из реквизитов (AC5, нормализация уже в _extract_all_requisites)
        # [AI-Review][Medium] Logic/Data Consistency: различаем "тег отсутствует" от "тег пустой"
        paid_at_value = requisites.get("датаоплаты")
        shipped_at_value = requisites.get("датаотгрузки")
        paid_at_present = "датаоплаты" in requisites
        shipped_at_present = "датаотгрузки" in requisites
        paid_at = self._parse_date_value(paid_at_value)
        shipped_at = self._parse_date_value(shipped_at_value)

        # [AI-Review][Medium] Observability: собираем ошибки парсинга дат
        parse_warnings: list[str] = []
        order_ref = order_number or order_id

        if paid_at_value is not None and paid_at_value.strip() and paid_at is None:
            paid_at_present = False
            parse_warnings.append(f"Order {order_ref}: invalid paid_at date format: '{paid_at_value}'")
        if shipped_at_value is not None and shipped_at_value.strip() and shipped_at is None:
            shipped_at_present = False
            parse_warnings.append(f"Order {order_ref}: invalid shipped_at date format: '{shipped_at_value}'")

        return OrderUpdateData(
            order_id=order_id or "",
            order_number=order_number or "",
            status_1c=status_1c,
            paid_at=paid_at,
            shipped_at=shipped_at,
            paid_at_present=paid_at_present,
            shipped_at_present=shipped_at_present,
            parse_warnings=parse_warnings,
        )

    def _extract_all_requisites(self, document: Element) -> dict[str, str]:
        """
        Извлечь все реквизиты документа в словарь (один проход).

        Нормализация имен: удаляем все whitespace-символы и приводим к lowercase
        для поддержки разных вариантов написания ("СтатусЗаказа", "Статус Заказа").

        Args:
            document: XML элемент <Документ>.

        Returns:
            dict: {normalized_name: value}, где normalized_name = lowercase.
        """
        result: dict[str, str] = {}
        requisites = document.find("ЗначенияРеквизитов")
        if requisites is None:
            return result

        # Pre-compute normalized whitelist for O(1) lookup
        _allowed_normalized = {REQUISITE_NAME_WHITESPACE_RE.sub("", r).lower() for r in ALLOWED_REQUISITES}

        for req in requisites.findall("ЗначениеРеквизита"):
            name_elem = req.find("Наименование")
            value_elem = req.find("Значение")
            if name_elem is not None and name_elem.text:
                # Нормализуем имя: удаляем все whitespace, приводим к lowercase
                normalized_name = REQUISITE_NAME_WHITESPACE_RE.sub("", name_elem.text).lower()
                if not normalized_name:
                    continue
                # [Story 5.2, AC14] Field whitelist — skip unknown requisites
                if normalized_name not in _allowed_normalized:
                    logger.debug("Skipping unknown requisite: '%s'", name_elem.text)
                    continue
                value = (value_elem.text or "") if value_elem is not None else ""
                result[normalized_name] = value

        return result

    def _get_source_timezone(self) -> ZoneInfo:
        """
        Получить timezone источника дат из настроек ONEC_EXCHANGE.

        Используется для явного назначения timezone при разборе дат из 1С,
        чтобы избежать неявного использования серверного времени.
        """
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        tz_name = exchange_cfg.get("SOURCE_TIME_ZONE") or settings.TIME_ZONE
        try:
            return ZoneInfo(str(tz_name))
        except Exception as exc:
            fallback_tz = ZoneInfo(str(settings.TIME_ZONE))
            logger.warning(
                "Invalid ONEC_EXCHANGE SOURCE_TIME_ZONE '%s', falling back to '%s': %s",
                tz_name,
                settings.TIME_ZONE,
                exc,
            )
            return fallback_tz

    def _get_batch_size(self) -> int:
        """
        Получить размер batch для обработки заказов.

        Настройка берётся из ONEC_EXCHANGE.ORDER_STATUS_IMPORT_BATCH_SIZE.
        """
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        raw_value = exchange_cfg.get("ORDER_STATUS_IMPORT_BATCH_SIZE", 500)
        try:
            batch_size = int(raw_value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid ORDER_STATUS_IMPORT_BATCH_SIZE '%s', using default 500",
                raw_value,
            )
            return 500
        if batch_size <= 0:
            logger.warning("ORDER_STATUS_IMPORT_BATCH_SIZE must be > 0, using default 500")
            return 500
        return batch_size

    def _parse_date_value(self, date_str: str | None) -> datetime | None:
        """
        Распарсить строку даты/времени.

        Поддерживаемые форматы:
        - YYYY-MM-DDTHH:MM:SS (ISO datetime)
        - YYYY-MM-DD (только дата, время = 00:00:00)

        Args:
            date_str: Строка с датой или None.

        Returns:
            datetime с timezone или None.
        """
        if not date_str:
            return None

        source_tz = self._get_source_timezone()

        # 1. Попытка парсинга как datetime (YYYY-MM-DDTHH:MM:SS)
        try:
            parsed_datetime = parse_datetime(date_str)
        except ValueError as exc:
            logger.warning("Could not parse datetime: %s (%s)", date_str, exc)
            return None
        if parsed_datetime:
            if timezone.is_naive(parsed_datetime):
                return timezone.make_aware(parsed_datetime, timezone=source_tz)
            return parsed_datetime

        # 2. Fallback: парсинг только даты (YYYY-MM-DD)
        try:
            parsed_date = parse_date(date_str)
        except ValueError as exc:
            logger.warning("Could not parse date: %s (%s)", date_str, exc)
            return None
        if parsed_date:
            # Конвертируем date в datetime с началом дня
            return timezone.make_aware(
                datetime.combine(parsed_date, datetime.min.time()),
                timezone=source_tz,
            )

        logger.warning(f"Could not parse date: {date_str}")
        return None

    # =========================================================================
    # Bulk Fetch Methods (N+1 Optimization)
    # =========================================================================

    def _parse_order_id_to_pk(self, order_id: str, log_invalid: bool = True) -> int | None:
        """
        Парсинг order-{id} формата для извлечения pk.

        Args:
            order_id: Строка вида 'order-123'.
            log_invalid: Логировать ли некорректный формат.

        Returns:
            int | None: pk или None если некорректный формат.
        """
        # [AI-Review][Low] Используем константу ORDER_ID_PREFIX
        if not order_id or not order_id.startswith(ORDER_ID_PREFIX):
            return None
        try:
            return int(order_id[len(ORDER_ID_PREFIX) :])
        except ValueError:
            if log_invalid:
                logger.warning(f"Invalid order_id format: '{order_id}'")
            return None

    def _bulk_fetch_orders(self, order_updates: list[OrderUpdateData]) -> dict[str, Order]:
        """
        Загрузить все заказы одним запросом для оптимизации N+1.

        Создаёт кэш заказов с префиксами для избежания коллизий:
        - 'num:{order_number}' для поиска по номеру заказа
        - 'pk:{id}' для поиска по первичному ключу

        Note:
            Bulk fetch использует select_for_update() для защиты от race condition.
            Вызывайте внутри transaction.atomic() для корректной блокировки.

        Args:
            order_updates: Список данных для обновления.

        Returns:
            Словарь {ключ: Order}, где ключ — 'num:{order_number}' или 'pk:{id}'.
        """
        from django.db.models import Q

        if not order_updates:
            return {}

        # [AI-Review][Low] Используем set() для избежания дубликатов в SQL IN-запросе
        order_numbers: set[str] = set()
        order_pks: set[int] = set()

        for data in order_updates:
            if data.order_number:
                order_numbers.add(data.order_number)
            pk = self._parse_order_id_to_pk(data.order_id, log_invalid=False)
            if pk is not None:
                order_pks.add(pk)

        # Один запрос с OR условиями
        query = Q()
        if order_numbers:
            query.add(Q(order_number__in=list(order_numbers)), Q.OR)
        if order_pks:
            query.add(Q(pk__in=list(order_pks)), Q.OR)

        if not query:
            return {}

        # [AI-Review][Low] Performance: загружаем только необходимые поля
        orders = (
            Order.objects.select_for_update()
            .filter(query)
            # [AI-Review][Medium] Deadlock Risk: стабилизируем порядок блокировок
            .order_by("pk")
            .only(
                "pk",
                "order_number",
                "status",
                "status_1c",
                "payment_status",
                "paid_at",
                "shipped_at",
                "sent_to_1c",
                "sent_to_1c_at",
                "updated_at",
            )
        )

        # [AI-Review][High] Строим кэш с префиксами для избежания коллизий:
        # num:{order_number} и pk:{id} — разные namespace
        cache: dict[str, Order] = {}
        for order in orders:
            if order.order_number:
                cache[f"num:{order.order_number}"] = order
            cache[f"pk:{order.pk}"] = order

        logger.debug(f"Bulk fetched {len(cache)} orders for {len(order_updates)} updates")
        return cache

    # =========================================================================
    # Processor Methods
    # =========================================================================

    def _process_order_update(
        self,
        order_data: OrderUpdateData,
        orders_cache: dict[str, Order] | None = None,
    ) -> tuple[ProcessingStatus, str | None]:
        """
        Обработка обновления одного заказа.

        Поиск заказа:
        1. По <Номер> (order_number) — приоритет
        2. По <Ид> в формате 'order-{id}' — fallback

        Args:
            order_data: Данные для обновления.
            orders_cache: Кэш заказов из bulk fetch (опционально).

        Returns:
            tuple: (ProcessingStatus, ошибка или None).
        """
        order, conflict_msg = self._find_order(order_data, orders_cache)
        if conflict_msg:
            return ProcessingStatus.SKIPPED_DATA_CONFLICT, conflict_msg

        if order is None:
            error_msg = f"Order not found: number='{order_data.order_number}', " f"id='{order_data.order_id}'"
            logger.error(error_msg)
            return ProcessingStatus.NOT_FOUND, error_msg

        # [AI-Review][Low] Code Style: оптимизированный регистронезависимый маппинг
        # Используем pre-computed STATUS_MAPPING_LOWER вместо цикла
        normalized_status = order_data.status_1c.strip()
        # Сначала точный поиск (оптимизация для частого случая)
        new_status = STATUS_MAPPING.get(normalized_status)
        # Fallback: поиск в lowercase-словаре (O(1) вместо O(n) цикла)
        if new_status is None:
            new_status = STATUS_MAPPING_LOWER.get(normalized_status.lower())

        if new_status is None:
            error_msg = f"Order {order.order_number}: unknown 1C status " f"'{order_data.status_1c}', skipping update"
            logger.warning(error_msg)
            return ProcessingStatus.SKIPPED_UNKNOWN_STATUS, error_msg

        # [Story 5.2, AC8] Status regression protection
        # 1. Block ALL transitions FROM final statuses (except same→same)
        if order.status in FINAL_STATUSES and new_status != order.status:
            error_msg = (
                f"Order {order.order_number}: transition from final status "
                f"'{order.status}' to '{new_status}' blocked"
            )
            logger.warning(error_msg)
            return ProcessingStatus.SKIPPED_STATUS_REGRESSION, error_msg

        # 2. Priority-based regression for non-final statuses
        # cancelled/refunded (priority 0) are always allowed as target.
        current_priority = STATUS_PRIORITY.get(order.status, 0)
        new_priority = STATUS_PRIORITY.get(new_status, 0)

        if new_priority > 0 and current_priority > 0 and new_priority < current_priority:
            error_msg = (
                f"Order {order.order_number}: status regression from "
                f"'{order.status}' (p={current_priority}) to "
                f"'{new_status}' (p={new_priority}) blocked"
            )
            logger.warning(error_msg)
            return ProcessingStatus.SKIPPED_STATUS_REGRESSION, error_msg

        # Проверяем, нужно ли обновление (идемпотентность AC8)
        status_changed = order.status != new_status or order.status_1c != order_data.status_1c
        # [AI-Review][Medium] Logic/Data Consistency: учитываем флаги наличия тегов
        # Если тег присутствует в XML — сравниваем значения (включая сброс на None)
        # Если тег отсутствует — не трогаем существующее значение
        dates_changed = (order_data.paid_at_present and order.paid_at != order_data.paid_at) or (
            order_data.shipped_at_present and order.shipped_at != order_data.shipped_at
        )
        sent_to_1c_changed = not order.sent_to_1c
        payment_status_needs_update = (
            order_data.paid_at_present
            and order_data.paid_at is not None
            and order.payment_status not in {"paid", "refunded"}
        )
        sync_time = timezone.now()

        if not status_changed and not dates_changed and not sent_to_1c_changed and not payment_status_needs_update:
            logger.debug(f"Order {order.order_number}: up-to-date, updating sync timestamp")
            order.sent_to_1c_at = sync_time
            order.save(update_fields=["sent_to_1c_at", "updated_at"])
            return ProcessingStatus.SKIPPED_UP_TO_DATE, None

        # Обновление заказа
        update_fields = ["updated_at"]

        if status_changed:
            order.status = new_status
            # [AI-Review][Low] Truncate status_1c to 255 chars to prevent DB errors
            order.status_1c = order_data.status_1c[:255]  # AC4
            update_fields.extend(["status", "status_1c"])

        # Обновление дат (AC5) — обновляем если тег присутствует и значение изменилось
        # [AI-Review][Medium] Logic/Data Consistency: поддержка сброса дат (None)
        if order_data.paid_at_present and order.paid_at != order_data.paid_at:
            order.paid_at = order_data.paid_at  # может быть None (сброс даты)
            update_fields.append("paid_at")
        if order_data.shipped_at_present and order.shipped_at != order_data.shipped_at:
            order.shipped_at = order_data.shipped_at  # может быть None (сброс даты)
            update_fields.append("shipped_at")

        # [AI-Review][Medium] Sync payment_status с paid_at из 1С
        if payment_status_needs_update:
            order.payment_status = "paid"
            update_fields.append("payment_status")

        # [AI-Review][Medium] Устанавливаем sent_to_1c=True при получении статуса из 1С
        if sent_to_1c_changed:
            order.sent_to_1c = True
            if "sent_to_1c" not in update_fields:
                update_fields.append("sent_to_1c")

        # [AI-Review][Low] Обновляем sent_to_1c_at на каждый успешный sync из 1С
        order.sent_to_1c_at = sync_time
        if "sent_to_1c_at" not in update_fields:
            update_fields.append("sent_to_1c_at")

        order.save(update_fields=update_fields)

        logger.debug(f"Order {order.order_number}: status updated to " f"'{new_status}' (1C: '{order_data.status_1c}')")
        return ProcessingStatus.UPDATED, None

    def _find_order(
        self,
        order_data: OrderUpdateData,
        orders_cache: dict[str, Order] | None = None,
    ) -> tuple[Order | None, str | None]:
        """
        Поиск заказа по номеру или ID (AC2).

        Стратегия:
        1. Поиск в кэше (если доступен) — быстрый путь
        2. Fallback на БД запрос с select_for_update() для предотвращения race condition

        Args:
            order_data: Данные с order_number и order_id.
            orders_cache: Кэш заказов из bulk fetch (опционально).

        Returns:
            tuple: (Order или None, сообщение о конфликте или None).
        """
        # Быстрый путь через кэш (None = нет кэша, {} = пустой кэш)
        if orders_cache is not None:
            # [AI-Review][High] Используем num: префикс для избежания коллизий
            # 1. Поиск по order_number в кэше
            if order_data.order_number:
                cache_key = f"num:{order_data.order_number}"
                if cache_key in orders_cache:
                    order = orders_cache[cache_key]

                    # [AI-Review][Medium] Data Integrity check: verify order_id matches if present
                    if order_data.order_id:
                        pk_from_xml = self._parse_order_id_to_pk(order_data.order_id, log_invalid=False)
                        if pk_from_xml is not None and order.pk != pk_from_xml:
                            conflict_msg = (
                                f"Data conflict: found order by number '{order_data.order_number}' "
                                f"(pk={order.pk}), but XML ID '{order_data.order_id}' (pk={pk_from_xml}) mismatches"
                            )
                            logger.warning(conflict_msg)
                            return None, conflict_msg

                    return order, None

            # 2. Поиск по pk в кэше [AI-Review][Medium] DRY — используем _parse_order_id_to_pk
            pk = self._parse_order_id_to_pk(order_data.order_id, log_invalid=False)
            if pk is not None:
                cache_key = f"pk:{pk}"
                if cache_key in orders_cache:
                    order = orders_cache[cache_key]
                    # [AI-Review][Medium] Data Integrity: Validate ID match
                    if order.pk != pk:
                        # This should theoretically be impossible with cache_key=f"pk:{pk}",
                        # but good for sanity.
                        pass

                    if order_data.order_number and order.order_number != order_data.order_number:
                        conflict_msg = (
                            f"Data conflict: found order by ID {order_data.order_id} (pk={pk}) "
                            f"but order numbers don't match: "
                            f"DB='{order.order_number}' vs XML='{order_data.order_number}'"
                        )
                        logger.warning(conflict_msg)
                        return None, conflict_msg

                    # [AI-Review][Medium] Data Integrity: Even if found by order_number in cache (above),
                    # we should ideally check if order_id matches if provided.
                    # However, the logic above (step 1) has already returned a result.
                    # We are here only if not found by number.

                    return order, None

            return None, None

        # [AI-Review][Medium] Fallback на БД с select_for_update() для предотвращения race condition
        # Используется когда кэш не передан или при критичных concurrent-сценариях
        # 1. Поиск по order_number с блокировкой
        if order_data.order_number:
            db_order: Order | None = (
                Order.objects.select_for_update().filter(order_number=order_data.order_number).first()
            )
            if db_order:
                # [AI-Review][Medium] Data Integrity check: verify order_id matches if present
                if order_data.order_id:
                    pk_from_xml = self._parse_order_id_to_pk(order_data.order_id, log_invalid=False)
                    if pk_from_xml is not None and db_order.pk != pk_from_xml:
                        conflict_msg = (
                            f"Data conflict: found order by number '{order_data.order_number}' "
                            f"(pk={db_order.pk}), but XML ID '{order_data.order_id}' (pk={pk_from_xml}) mismatches"
                        )
                        logger.warning(conflict_msg)
                        return None, conflict_msg

                return db_order, None

        # 2. Поиск по order_id формата 'order-{id}' [AI-Review][Medium] DRY
        pk = self._parse_order_id_to_pk(order_data.order_id)
        if pk is not None:
            db_order_by_id: Order | None = Order.objects.select_for_update().filter(pk=pk).first()
            if db_order_by_id:
                # [AI-Review][Medium] Detect data conflict when finding order by ID
                if order_data.order_number and db_order_by_id.order_number != order_data.order_number:
                    conflict_msg = (
                        f"Data conflict: found order by ID {order_data.order_id} (pk={pk}) "
                        f"but order numbers don't match: "
                        f"DB='{db_order_by_id.order_number}' vs XML='{order_data.order_number}'"
                    )
                    logger.warning(conflict_msg)
                    return None, conflict_msg
                return db_order_by_id, None

        return None, None
