"""
Интеграционные тесты для OrderStatusImportService с реальной БД.

Story 5.1: [AI-Review][Medium] Test Quality — проверка save(update_fields=...)
с реальной базой данных для исключения опечаток в именах полей.
"""

from datetime import datetime, timedelta
from typing import Any, cast

import pytest
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
        """Создать тестовый заказ в БД."""
        from decimal import Decimal

        self.order_number = f"FS-INT-{get_unique_suffix()}"
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

        # ARRANGE — создаём ещё 2 заказа
        order2_number = f"FS-INT2-{get_unique_suffix()}"
        order3_number = f"FS-INT3-{get_unique_suffix()}"

        order2 = Order.objects.create(
            order_number=order2_number,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("200.00"),
        )
        order3 = Order.objects.create(
            order_number=order3_number,
            status="pending",
            delivery_address="Тестовый адрес",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("300.00"),
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
        # Query count breakdown (6 total):
        # 1. SAVEPOINT — transaction.atomic() start
        # 2. SELECT ... FOR UPDATE — bulk fetch all 3 orders in one query
        # 3. UPDATE order 1 — save() with update_fields
        # 4. UPDATE order 2 — save() with update_fields
        # 5. UPDATE order 3 — save() with update_fields
        # 6. RELEASE SAVEPOINT — transaction.atomic() commit
        with cast(Any, self).assertNumQueries(6):
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
