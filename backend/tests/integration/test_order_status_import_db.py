"""
Интеграционные тесты для OrderStatusImportService с реальной БД.

Story 5.1: [AI-Review][Medium] Test Quality — проверка save(update_fields=...)
с реальной базой данных для исключения опечаток в именах полей.
"""

from datetime import datetime, timedelta
from typing import Any, cast

import pytest
from django.db import OperationalError
from django.test import TestCase
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.services.order_status_import import MAX_ERRORS, ORDER_ID_PREFIX, OrderStatusImportService
from tests.conftest import get_unique_suffix


def build_test_xml(
    order_id: str = "order-123",
    order_number: str = "FS-TEST-001",
    status: str = "Отгружен",
    paid_date: str | None = None,
    shipped_date: str | None = None,
) -> str:
    """Генерирует тестовый XML в формате CommerceML 3.1."""
    requisites = f"""
        <ЗначениеРеквизита>
            <Наименование>СтатусЗаказа</Наименование>
            <Значение>{status}</Значение>
        </ЗначениеРеквизита>
    """
    if paid_date:
        requisites += f"""
        <ЗначениеРеквизита>
            <Наименование>ДатаОплаты</Наименование>
            <Значение>{paid_date}</Значение>
        </ЗначениеРеквизита>
        """
    if shipped_date:
        requisites += f"""
        <ЗначениеРеквизита>
            <Наименование>ДатаОтгрузки</Наименование>
            <Значение>{shipped_date}</Значение>
        </ЗначениеРеквизита>
        """

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-02T12:00:00">
    <Контейнер>
        <Документ>
            <Ид>{order_id}</Ид>
            <Номер>{order_number}</Номер>
            <Дата>2026-02-02</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                {requisites}
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""


@pytest.mark.integration
@pytest.mark.django_db
class TestOrderStatusImportDBIntegration(TestCase):
    """
    Интеграционные тесты с реальной БД.

    Проверяют, что save(update_fields=...) работает корректно
    и нет опечаток в именах полей модели Order.
    """

    def setUp(self):
        """Создать master + sub-order в БД (Story 34-5).

        self.order — субзаказ (is_master=False), получает статус из 1С.
        self.master — мастер-заказ, агрегирует статус от sub_orders.
        """
        from decimal import Decimal

        self.order_number = f"FS-INT-{get_unique_suffix()}"
        self.master = Order.objects.create(
            order_number=f"FS-INT-M-{get_unique_suffix()}",
            is_master=True,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        self.order = Order.objects.create(
            order_number=self.order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            sent_to_1c_at=None,
            paid_at=None,
            shipped_at=None,
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
            is_master=False,
            parent_order=self.master,
        )
        self.service = OrderStatusImportService()

    def test_update_fields_status_persisted_to_db(self):
        """Проверка: status и status_1c сохраняются в БД."""
        # ARRANGE
        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Отгружен",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — перезагружаем из БД
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertEqual(self.order.status, "shipped")
        self.assertEqual(self.order.status_1c, "Отгружен")

    def test_update_fields_dates_persisted_to_db(self):
        """Проверка: paid_at и shipped_at сохраняются в БД."""
        # ARRANGE
        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Доставлен",
            paid_date="2026-02-01T10:30:00",
            shipped_date="2026-02-02T14:00:00",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — перезагружаем из БД
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertIsNotNone(self.order.paid_at)
        self.assertIsNotNone(self.order.shipped_at)
        paid_at = cast(datetime, self.order.paid_at)
        shipped_at = cast(datetime, self.order.shipped_at)
        self.assertEqual(paid_at.day, 1)
        self.assertEqual(shipped_at.day, 2)

    def test_update_fields_sent_to_1c_persisted_to_db(self):
        """Проверка: sent_to_1c и sent_to_1c_at сохраняются в БД."""
        # ARRANGE — заказ ещё не синхронизирован
        self.assertFalse(self.order.sent_to_1c)
        self.assertIsNone(self.order.sent_to_1c_at)

        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Подтвержден",
        )

        # ACT
        before_process = timezone.now()
        result = self.service.process(xml_data)
        after_process = timezone.now()

        # ASSERT — перезагружаем из БД
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertTrue(self.order.sent_to_1c)
        self.assertIsNotNone(self.order.sent_to_1c_at)
        sent_to_1c_at = cast(datetime, self.order.sent_to_1c_at)
        # sent_to_1c_at должен быть между before и after
        self.assertGreaterEqual(sent_to_1c_at, before_process)
        self.assertLessEqual(sent_to_1c_at, after_process)

    def test_idempotent_no_update_when_status_matches(self):
        """Идемпотентность: статус не меняется, sent_to_1c_at обновляется."""
        # ARRANGE — установим статус вручную
        self.order.status = "shipped"
        self.order.status_1c = "Отгружен"
        self.order.sent_to_1c = True
        previous_sent_to_1c_at = timezone.now() - timedelta(days=1)
        self.order.sent_to_1c_at = previous_sent_to_1c_at
        self.order.save()

        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Отгружен",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — заказ не должен быть обновлён
        self.order.refresh_from_db()
        self.assertEqual(result.skipped_up_to_date, 1)
        self.assertEqual(result.skipped_unknown_status, 0)
        self.assertEqual(result.updated, 0)
        self.assertNotEqual(self.order.sent_to_1c_at, previous_sent_to_1c_at)

    def test_find_order_by_pk_from_order_id(self):
        """Проверка поиска заказа по order-{pk} формату."""
        # ARRANGE — используем pk заказа
        order_id = f"{ORDER_ID_PREFIX}{self.order.pk}"
        xml_data = build_test_xml(
            order_id=order_id,
            order_number="",  # Пустой номер — поиск по ID
            status="Отменен",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 1)
        self.assertEqual(self.order.status, "cancelled")

    def test_bulk_fetch_orders_optimization(self):
        """Проверка bulk fetch: несколько заказов загружаются одним запросом."""
        from decimal import Decimal

        # ARRANGE — создаём ещё 2 субзаказа того же мастера
        order2_number = f"FS-INT2-{get_unique_suffix()}"
        order3_number = f"FS-INT3-{get_unique_suffix()}"

        order2 = Order.objects.create(
            order_number=order2_number,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("200.00"),
            is_master=False,
            parent_order=self.master,
        )
        order3 = Order.objects.create(
            order_number=order3_number,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("300.00"),
            is_master=False,
            parent_order=self.master,
        )

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    <Контейнер>
        <Документ>
            <Номер>{self.order_number}</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Отгружен</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
    <Контейнер>
        <Документ>
            <Номер>{order2_number}</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Доставлен</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
    <Контейнер>
        <Документ>
            <Номер>{order3_number}</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Подтвержден</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""

        # ACT
        # Query count breakdown (11 total) после Story 34-5 (master+sub):
        # 1. SAVEPOINT — transaction.atomic() start
        # 2. SELECT ... FOR UPDATE — bulk fetch all 3 sub-orders in one query
        # (no EXISTS: is_master=False short-circuits master-guard)
        # 3. UPDATE sub1 — save() with update_fields
        # 4. UPDATE sub2 — save() with update_fields
        # 5. UPDATE sub3 — save() with update_fields
        # [Master aggregation — 1 shared master]
        # 6. SELECT FOR UPDATE master — get master by pk
        # 7. SELECT sub_orders.status — _aggregate_master_status
        # 8. SELECT sub_orders.payment_status — _aggregate_master_payment_status
        # 9. SELECT sub_orders.sent_to_1c_at — _aggregate_master_sent_to_1c_at
        # 10. UPDATE master — save() with update_fields
        # 11. RELEASE SAVEPOINT — transaction.atomic() commit
        with cast(Any, self).assertNumQueries(11):
            result = self.service.process(xml_data)

        # ASSERT — все 3 заказа обновлены
        self.assertEqual(result.processed, 3)
        self.assertEqual(result.updated, 3)

        self.order.refresh_from_db()
        order2.refresh_from_db()
        order3.refresh_from_db()

        self.assertEqual(self.order.status, "shipped")
        self.assertEqual(order2.status, "delivered")
        self.assertEqual(order3.status, "confirmed")


@pytest.mark.integration
@pytest.mark.django_db
class TestMaxErrorsLimit(TestCase):
    """Тест ограничения списка ошибок."""

    def test_errors_limited_to_max_errors(self):
        """Проверка: список ошибок ограничен MAX_ERRORS."""
        # ARRANGE — создаём XML со 150 несуществующими заказами
        orders_xml = ""
        for i in range(150):
            orders_xml += f"""
            <Контейнер>
                <Документ>
                    <Номер>NOT-EXISTS-{i}</Номер>
                    <ЗначенияРеквизитов>
                        <ЗначениеРеквизита>
                            <Наименование>СтатусЗаказа</Наименование>
                            <Значение>Отгружен</Значение>
                        </ЗначениеРеквизита>
                    </ЗначенияРеквизитов>
                </Документ>
            </Контейнер>
            """

        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    {orders_xml}
</КоммерческаяИнформация>
"""

        service = OrderStatusImportService()

        # ACT
        result = service.process(xml_data)

        # ASSERT
        self.assertEqual(result.processed, 150)
        self.assertEqual(result.not_found, 150)
        # Ошибки ограничены MAX_ERRORS
        self.assertEqual(len(result.errors), MAX_ERRORS)

    def test_detect_data_conflict_when_order_found_by_id(self):
        """Проверка обнаружения конфликта данных при поиске по ID."""
        # ARRANGE
        from decimal import Decimal

        service = OrderStatusImportService()

        # Создаем заказ с одним номером
        order_number = f"FS-CONFLICT-{get_unique_suffix()}"
        order = Order.objects.create(
            order_number=order_number,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )

        # Данные XML с другим номером но тем же ID
        xml_data = build_test_xml(
            order_id=f"order-{order.id}",
            order_number="FS-CONFLICT-999",  # Другой номер
            status="Отгружен",
        )

        # ACT
        result = service.process(xml_data)

        # ASSERT
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.not_found, 0)
        self.assertEqual(result.skipped_data_conflict, 1)  # Пропущен из-за конфликта
        self.assertEqual(len(result.errors), 1)  # Ошибка конфликта должна быть записана


@pytest.mark.integration
@pytest.mark.django_db
class TestFinalStatusTransitionsDB(TestCase):
    """[AI-Review][Medium] Интеграционные тесты блокировки переходов между финальными статусами."""

    def setUp(self):
        """Создать тестовый заказ в БД."""
        from decimal import Decimal

        self.order_number = f"FS-FINAL-{get_unique_suffix()}"
        self.order = Order.objects.create(
            order_number=self.order_number,
            status="delivered",  # Финальный статус
            status_1c="Доставлен",
            sent_to_1c=True,
            sent_to_1c_at=timezone.now(),
            paid_at=None,
            shipped_at=None,
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        self.service = OrderStatusImportService()

    def test_transition_between_final_statuses_blocked_in_db(self):
        """Переход delivered → cancelled блокируется и не сохраняется в БД."""
        # ARRANGE
        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Отменен",  # cancelled — другой финальный статус
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — переход не выполнен
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped_status_regression, 1)
        # Статус в БД не изменился
        self.assertEqual(self.order.status, "delivered")
        self.assertEqual(self.order.status_1c, "Доставлен")

    def test_transition_cancelled_to_refunded_blocked_in_db(self):
        """Переход cancelled → refunded блокируется."""
        # ARRANGE — меняем статус на cancelled
        self.order.status = "cancelled"
        self.order.status_1c = "Отменен"
        self.order.save()

        # [AI-Review][Medium] Data Integrity:
        # order_id должен соответствовать реальному pk
        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.order.pk}",
            order_number=self.order_number,
            status="Возвращен",  # refunded — другой финальный статус
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — переход не выполнен
        self.order.refresh_from_db()
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped_status_regression, 1)
        self.assertEqual(self.order.status, "cancelled")


# =============================================================================
# Story 34-4: Master Aggregation Integration Tests
# =============================================================================


def _build_multi_sub_xml(subs_data: list[dict]) -> str:
    """Генерирует XML с несколькими документами (для субзаказов)."""
    containers = []
    for sd in subs_data:
        containers.append(
            f"""
        <Контейнер>
            <Документ>
                <Ид>{sd['order_id']}</Ид>
                <Номер>{sd['order_number']}</Номер>
                <Дата>2026-02-02</Дата>
                <ХозОперация>Заказ товара</ХозОперация>
                <ЗначенияРеквизитов>
                    <ЗначениеРеквизита>
                        <Наименование>СтатусЗаказа</Наименование>
                        <Значение>{sd['status']}</Значение>
                    </ЗначениеРеквизита>
                </ЗначенияРеквизитов>
            </Документ>
        </Контейнер>
        """
        )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-02T12:00:00">
    {''.join(containers)}
</КоммерческаяИнформация>
"""


@pytest.mark.integration
@pytest.mark.django_db
class TestMasterAggregationDB(TestCase):
    """Интеграционные тесты агрегации мастера (Story 34-4, AC3, AC9, AC10, AC11, AC12)."""

    def setUp(self):
        from decimal import Decimal

        self.master = Order.objects.create(
            order_number=f"FS-AGG-M-{get_unique_suffix()}",
            is_master=True,
            parent_order=None,
            status="pending",
            payment_status="pending",
            sent_to_1c=False,
            sent_to_1c_at=None,
            total_amount=Decimal("2000.00"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )
        self.sub5 = Order.objects.create(
            order_number=f"FS-AGG-S5-{get_unique_suffix()}",
            is_master=False,
            parent_order=self.master,
            status="pending",
            payment_status="pending",
            sent_to_1c=False,
            sent_to_1c_at=None,
            total_amount=Decimal("1000.00"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )
        self.sub22 = Order.objects.create(
            order_number=f"FS-AGG-S22-{get_unique_suffix()}",
            is_master=False,
            parent_order=self.master,
            status="pending",
            payment_status="pending",
            sent_to_1c=False,
            sent_to_1c_at=None,
            total_amount=Decimal("1000.00"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )
        self.service = OrderStatusImportService()

    def test_batch_both_subs_confirmed_aggregates_master(self):
        """AC3+AC10: оба sub→confirmed, одна агрегация мастера."""
        # ARRANGE
        xml_data = _build_multi_sub_xml(
            [
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub5.pk}",
                    "order_number": self.sub5.order_number,
                    "status": "Подтвержден",
                },
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub22.pk}",
                    "order_number": self.sub22.order_number,
                    "status": "Подтвержден",
                },
            ]
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT
        self.assertEqual(result.updated, 2)
        self.assertEqual(result.aggregated_master_count, 1)
        self.master.refresh_from_db()
        self.assertEqual(self.master.status, "confirmed")

    def test_batch_mixed_statuses_aggregates_to_pending(self):
        """Только один sub обновлён — master остаётся pending."""
        # ARRANGE — master в confirmed, чтобы увидеть изменение
        self.master.status = "confirmed"
        self.master.save(update_fields=["status"])

        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.sub5.pk}",
            order_number=self.sub5.order_number,
            status="Отгружен",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.aggregated_master_count, 1)
        self.master.refresh_from_db()
        self.assertEqual(self.master.status, "pending")
        self.sub5.refresh_from_db()
        self.assertEqual(self.sub5.status, "shipped")

    def test_signal_master_order_ids_emitted(self):
        """AC11: сигнал содержит master_order_ids."""
        # ARRANGE
        from apps.orders.signals import orders_bulk_updated

        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            xml_data = _build_multi_sub_xml(
                [
                    {
                        "order_id": f"{ORDER_ID_PREFIX}{self.sub5.pk}",
                        "order_number": self.sub5.order_number,
                        "status": "Подтвержден",
                    },
                    {
                        "order_id": f"{ORDER_ID_PREFIX}{self.sub22.pk}",
                        "order_number": self.sub22.order_number,
                        "status": "Подтвержден",
                    },
                ]
            )

            # ACT
            result = self.service.process(xml_data)

            # ASSERT
            self.assertEqual(result.updated, 2)
            self.assertIn("master_order_ids", received_kwargs)
            self.assertIn(self.master.pk, received_kwargs["master_order_ids"])
            self.assertIn(self.sub5.pk, received_kwargs["order_ids"])
            self.assertIn(self.sub22.pk, received_kwargs["order_ids"])
        finally:
            orders_bulk_updated.disconnect(handler)

    def test_idempotent_repeat_import_no_master_save(self):
        """AC12: повторный импорт — aggregated_master_count=0."""
        # ARRANGE
        xml_data = _build_multi_sub_xml(
            [
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub5.pk}",
                    "order_number": self.sub5.order_number,
                    "status": "Подтвержден",
                },
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub22.pk}",
                    "order_number": self.sub22.order_number,
                    "status": "Подтвержден",
                },
            ]
        )

        # ACT — первый импорт
        result1 = self.service.process(xml_data)
        # ACT — второй импорт (тот же XML)
        result2 = self.service.process(xml_data)

        # ASSERT
        self.assertEqual(result1.aggregated_master_count, 1)
        self.assertEqual(result2.aggregated_master_count, 0)
        self.master.refresh_from_db()
        self.assertEqual(self.master.status, "confirmed")

    def test_master_regression_from_delivered_blocked(self):
        """AC5: регрессия delivered→shipped на мастере блокируется, sub обновляется."""
        # ARRANGE
        self.master.status = "delivered"
        self.master.save(update_fields=["status"])

        xml_data = build_test_xml(
            order_id=f"{ORDER_ID_PREFIX}{self.sub5.pk}",
            order_number=self.sub5.order_number,
            status="Отгружен",
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — sub обновлён, мастер нет
        self.assertEqual(result.updated, 1)
        self.assertEqual(result.skipped_master_regression, 1)
        self.sub5.refresh_from_db()
        self.assertEqual(self.sub5.status, "shipped")
        self.master.refresh_from_db()
        self.assertEqual(self.master.status, "delivered")

    def test_vat_group_none_sub_included_in_xml_import_aggregation(self):
        """AC13: sub с vat_group=None участвует в агрегации через XML-импорт."""
        from decimal import Decimal

        # ARRANGE — sub с vat_group=None
        sub_none = Order.objects.create(
            order_number=f"FS-AGG-SN-{get_unique_suffix()}",
            is_master=False,
            parent_order=self.master,
            vat_group=None,
            status="pending",
            payment_status="pending",
            sent_to_1c=False,
            sent_to_1c_at=None,
            total_amount=Decimal("500.00"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )

        # Все три sub → confirmed через XML
        xml_data = _build_multi_sub_xml(
            [
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub5.pk}",
                    "order_number": self.sub5.order_number,
                    "status": "Подтвержден",
                },
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub22.pk}",
                    "order_number": self.sub22.order_number,
                    "status": "Подтвержден",
                },
                {
                    "order_id": f"{ORDER_ID_PREFIX}{sub_none.pk}",
                    "order_number": sub_none.order_number,
                    "status": "Подтвержден",
                },
            ]
        )

        # ACT
        result = self.service.process(xml_data)

        # ASSERT — все 3 sub обновлены, master агрегирован
        self.assertEqual(result.updated, 3)
        self.assertEqual(result.aggregated_master_count, 1)
        self.master.refresh_from_db()
        self.assertEqual(self.master.status, "confirmed")
        sub_none.refresh_from_db()
        self.assertEqual(sub_none.status, "confirmed")

    def test_aggregation_rollback_on_error(self):
        """AC9: rollback при ошибке агрегации."""
        # ARRANGE
        from unittest.mock import patch

        xml_data = _build_multi_sub_xml(
            [
                {
                    "order_id": f"{ORDER_ID_PREFIX}{self.sub5.pk}",
                    "order_number": self.sub5.order_number,
                    "status": "Подтвержден",
                },
            ]
        )

        with patch("apps.orders.models.Order.save", side_effect=OperationalError("DB error")):
            # ACT
            result = self.service.process(xml_data)

        # ASSERT — rollback: sub и master не изменились
        self.sub5.refresh_from_db()
        self.master.refresh_from_db()
        self.assertEqual(self.sub5.status, "pending")
        self.assertEqual(self.master.status, "pending")
