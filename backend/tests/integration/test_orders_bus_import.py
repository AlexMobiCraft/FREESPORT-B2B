"""
Интеграционные тесты маршрута выгрузки заказов БУС.

Спека `spec-1c-order-statuses-import.md`: 1С проходит
`checkauth → init → file → import` с `type=sale` и `filename=orders_*.xml`,
сайт применяет статусы через `OrderStatusImportService(bus_format=True)`
и не запускает импорт каталога.

XML собран по раскладке `БУС_ВыгрузкаСервер.СформироватьЗаказ`; разбор
реальной выгрузки с test_base — в `test_bus_orders_real_export` (`data_dependent`).
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import cast
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.conf import settings
from django.contrib.auth.models import Permission
from django.db import OperationalError
from django.http import HttpResponse
from rest_framework.test import APIClient

from apps.orders.models import Order
from apps.products.models import ImportSession
from tests.conftest import UserFactory, get_unique_suffix
from tests.unit.test_order_status_import import build_bus_document, build_bus_xml
from tests.utils import EXCHANGE_URL, ONEC_PASSWORD, perform_1c_checkauth

# `ДатаФормирования` в `build_bus_xml` — 2026-11-23T12:00:00; часы стоят
# на десять минут позже, чтобы проверка устаревания XML не зависела от даты прогона.
FROZEN_NOW = datetime(2026, 11, 23, 12, 10, tzinfo=ZoneInfo(settings.TIME_ZONE))


@pytest.fixture
def exchange_dirs(tmp_path, monkeypatch):
    temp_dir = tmp_path / "1c_temp"
    import_dir = tmp_path / "1c_import"
    temp_dir.mkdir()
    import_dir.mkdir()
    monkeypatch.setitem(settings.ONEC_EXCHANGE, "TEMP_DIR", temp_dir)
    monkeypatch.setitem(settings.ONEC_EXCHANGE, "IMPORT_DIR", import_dir)
    monkeypatch.setattr(settings, "EXCHANGE_LOG_DIR", str(tmp_path / "logs"), raising=False)
    return {"temp": temp_dir, "import": import_dir, "logs": tmp_path / "logs"}


@pytest.fixture
def frozen_now():
    with patch("django.utils.timezone.now", return_value=FROZEN_NOW):
        yield FROZEN_NOW


def _create_master_with_subs(*statuses: str) -> tuple[Order, list[Order]]:
    master = Order.objects.create(
        order_number=f"BUS-M-{get_unique_suffix()}",
        is_master=True,
        status=statuses[0],
        delivery_address="Test",
        delivery_method="courier",
        payment_method="card",
        total_amount=Decimal("200.00"),
    )
    subs = [
        Order.objects.create(
            order_number=f"BUS-S{index}-{get_unique_suffix()}",
            is_master=False,
            parent_order=master,
            status=status,
            status_1c="К выполнению",
            sent_to_1c=True,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        for index, status in enumerate(statuses, start=1)
    ]
    return master, subs


def _document_for(order: Order, **kwargs) -> str:
    return build_bus_document(order_id=f"order-{order.pk}", order_number=order.order_number, **kwargs)


def _zip(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.usefixtures("frozen_now")
class TestBusOrdersImport:
    """HTTP-цепочка БУС: `checkauth → init → file → import`."""

    @pytest.fixture(autouse=True)
    def _setup(self, exchange_dirs):
        self.dirs = exchange_dirs
        self.client = APIClient()
        user = UserFactory.create(password=ONEC_PASSWORD)
        user.user_permissions.add(
            Permission.objects.get(content_type__app_label="integrations", codename="can_exchange_1c")
        )
        perform_1c_checkauth(self.client, user.email, ONEC_PASSWORD)
        init = cast(HttpResponse, self.client.get(EXCHANGE_URL, {"type": "sale", "mode": "init"}))
        assert init.status_code == 200
        self.sessid = self.client.cookies[settings.SESSION_COOKIE_NAME].value

    @property
    def session_temp(self) -> Path:
        return self.dirs["temp"] / self.sessid

    def _upload(self, filename: str, body: bytes) -> str:
        response = cast(
            HttpResponse,
            self.client.post(
                f"{EXCHANGE_URL}?type=sale&mode=file&filename={filename}",
                data=body,
                content_type="application/octet-stream",
            ),
        )
        return response.content.decode("utf-8")

    def _import(self, filename: str) -> str:
        response = cast(
            HttpResponse,
            self.client.get(EXCHANGE_URL, {"type": "sale", "mode": "import", "filename": filename}),
        )
        assert response.status_code == 200
        return response.content.decode("utf-8")

    # ------------------------------------------------------------------ маршрут

    def test_open_xml_updates_sub_orders_and_master(self):
        master, (sub1, sub2) = _create_master_with_subs("processing", "processing")
        xml = build_bus_xml(
            _document_for(sub1, status="Передан на склад"),
            _document_for(sub2, status="Передан на склад"),
        ).encode("utf-8")

        assert self._upload("orders_1_a1b2.xml", xml) == "success"
        body = self._import("orders_1_a1b2.xml")

        assert body == "success"
        sub1.refresh_from_db()
        sub2.refresh_from_db()
        master.refresh_from_db()
        assert (sub1.status, sub1.status_1c) == ("at_warehouse", "Передан на склад")
        assert sub2.status == "at_warehouse"
        assert master.status == "at_warehouse"
        assert not ImportSession.objects.exists(), "импорт каталога не должен запускаться"
        assert not (self.session_temp / "orders_1_a1b2.xml").exists()
        assert list(self.dirs["logs"].glob("*orders_1_a1b2.xml")), "копия файла до разбора"

    def test_zip_archive_is_read_and_removed(self):
        master, (sub,) = _create_master_with_subs("processing")
        archive = _zip({"orders_1_c3d4.xml": build_bus_xml(_document_for(sub, status="Закрыт")).encode("utf-8")})

        assert self._upload("v8_C3D4.zip", archive) == "success"
        body = self._import("orders_1_c3d4.xml")

        assert body == "success"
        sub.refresh_from_db()
        master.refresh_from_db()
        assert sub.status == "delivered"
        assert master.status == "delivered"
        assert not (self.session_temp / "v8_C3D4.zip").exists()
        assert not ImportSession.objects.exists()

    def test_mixed_archive_keeps_archive_for_other_files(self):
        _, (sub,) = _create_master_with_subs("processing")
        archive = _zip(
            {
                "orders_1_e5f6.xml": build_bus_xml(_document_for(sub, status="Передан на склад")).encode("utf-8"),
                "contragents_1_e5f6.xml": b"<?xml version='1.0'?><root/>",
            }
        )

        self._upload("v8_E5F6.zip", archive)
        body = self._import("orders_1_e5f6.xml")

        assert body == "success"
        sub.refresh_from_db()
        assert sub.status == "at_warehouse"
        assert (self.session_temp / "v8_E5F6.zip").exists(), "contragents_*.xml заберёт свой mode=import"
        assert not ImportSession.objects.exists()

    def test_all_orders_files_of_session_are_processed(self):
        _, (sub1, sub2) = _create_master_with_subs("processing", "processing")
        self._upload("orders_1_aaaa.xml", build_bus_xml(_document_for(sub1, status="Передан на склад")).encode())
        self._upload(
            "v8_BBBB.zip",
            _zip({"orders_2_bbbb.xml": build_bus_xml(_document_for(sub2, status="Закрыт")).encode()}),
        )

        body = self._import("orders_1_aaaa.xml")

        assert body == "success"
        sub1.refresh_from_db()
        sub2.refresh_from_db()
        assert sub1.status == "at_warehouse"
        assert sub2.status == "delivered"
        assert list(self.session_temp.glob("orders*")) == []
        assert list(self.session_temp.glob("*.zip")) == []

    def test_file_already_routed_by_orchestrator_is_processed(self):
        """`mode=import` другого файла раньше распаковал архив в `IMPORT_DIR/<sessid>/orders/`."""
        _, (sub,) = _create_master_with_subs("processing")
        orders_dir = self.dirs["import"] / self.sessid / "orders"
        orders_dir.mkdir(parents=True)
        routed = orders_dir / "orders_1_c0de.xml"
        routed.write_bytes(build_bus_xml(_document_for(sub, status="Передан на склад")).encode("utf-8"))

        body = self._import("orders_1_c0de.xml")

        assert body == "success"
        sub.refresh_from_db()
        assert sub.status == "at_warehouse"
        assert not routed.exists()

    def test_orders_processed_while_catalog_import_in_progress(self):
        ImportSession.objects.create(
            session_key=f"catalog-{get_unique_suffix()}",
            status=ImportSession.ImportStatus.IN_PROGRESS,
            import_type=ImportSession.ImportType.CATALOG,
        )
        _, (sub,) = _create_master_with_subs("processing")
        self._upload("orders_1_busy.xml", build_bus_xml(_document_for(sub, status="Передан на склад")).encode())

        body = self._import("orders_1_busy.xml")

        assert body == "success"
        sub.refresh_from_db()
        assert sub.status == "at_warehouse"
        assert ImportSession.objects.count() == 1

    # ------------------------------------------------------------------ отмена

    def test_cancel_and_false_cancel(self):
        master, (cancelled_sub, live_sub) = _create_master_with_subs("processing", "shipped")
        xml = build_bus_xml(
            _document_for(cancelled_sub, status=None, cancelled=True, lines=()),
            _document_for(live_sub, status="Закрыт", cancelled=True),
        ).encode("utf-8")
        self._upload("orders_1_cancel.xml", xml)

        body = self._import("orders_1_cancel.xml")

        assert body == "success"
        cancelled_sub.refresh_from_db()
        live_sub.refresh_from_db()
        master.refresh_from_db()
        assert (cancelled_sub.status, cancelled_sub.status_1c) == ("cancelled", "Отменен")
        assert (live_sub.status, live_sub.status_1c) == ("shipped", "Закрыт")
        assert master.status == "shipped"

    # ------------------------------------------------------------------ success, хоть и без изменений

    def test_foreign_and_statusless_documents_answer_success(self):
        _, (sub,) = _create_master_with_subs("processing")
        xml = build_bus_xml(
            build_bus_document(order_id="1c-guid-foreign", order_number="УТ-00042", status="Закрыт"),
            _document_for(sub, status=None),
            _document_for(sub, operation="Выплата безналичных денег"),
        ).encode("utf-8")
        self._upload("orders_1_noop.xml", xml)

        body = self._import("orders_1_noop.xml")

        assert body == "success"
        sub.refresh_from_db()
        assert sub.status == "processing"

    # ------------------------------------------------------------------ failure

    def test_no_xml_is_failure(self):
        body = self._import("orders_1_missing.xml")

        assert body.startswith("failure")
        assert "not found" in body

    def test_malformed_xml_is_failure(self):
        self._upload("orders_1_bad.xml", "<КоммерческаяИнформация><Контейнер>".encode("utf-8"))

        body = self._import("orders_1_bad.xml")

        assert body == "failure\nMalformed XML"

    def test_stale_xml_is_failure(self):
        _, (sub,) = _create_master_with_subs("processing")
        xml = build_bus_xml(_document_for(sub, status="Передан на склад")).replace(
            'ДатаФормирования="2026-11-23T12:00:00"', 'ДатаФормирования="2026-11-20T12:00:00"'
        )
        self._upload("orders_1_old.xml", xml.encode("utf-8"))

        body = self._import("orders_1_old.xml")

        assert body == "failure\nXML timestamp too old"
        sub.refresh_from_db()
        assert sub.status == "processing"

    def test_database_down_after_retries_is_failure(self):
        _, (sub,) = _create_master_with_subs("processing")
        self._upload("orders_1_db.xml", build_bus_xml(_document_for(sub, status="Передан на склад")).encode())

        with (
            patch(
                "apps.integrations.onec_exchange.views.OrderStatusImportService.process",
                side_effect=OperationalError("db down"),
            ) as process,
            patch("apps.integrations.onec_exchange.views.time.sleep"),
        ):
            body = self._import("orders_1_db.xml")

        assert body == "failure\nInternal error"
        assert process.call_count == 3

    def test_database_error_inside_process_is_failure(self):
        """`process` гасит `OperationalError` пакета в `errors` — маршрут всё равно обязан ответить `failure`."""
        _, (sub,) = _create_master_with_subs("processing")
        self._upload("orders_1_dbin.xml", build_bus_xml(_document_for(sub, status="Передан на склад")).encode())

        with patch(
            "apps.orders.services.order_status_import.OrderStatusImportService._bulk_fetch_orders",
            side_effect=OperationalError("db down"),
        ):
            body = self._import("orders_1_dbin.xml")

        assert body == "failure\nInternal error"
        sub.refresh_from_db()
        assert sub.status == "processing"

    # ------------------------------------------------------------------ прежний путь не задет

    def test_exact_orders_xml_import_still_goes_to_orchestrator(self):
        with patch("apps.integrations.onec_exchange.views.ImportOrchestratorService") as orchestrator:
            orchestrator.return_value.execute.return_value = (True, "success")
            body = self._import("orders.xml")

        assert body == "success"
        orchestrator.assert_called_once()

    def test_orders_file_without_sale_type_goes_to_orchestrator(self):
        with patch("apps.integrations.onec_exchange.views.ImportOrchestratorService") as orchestrator:
            orchestrator.return_value.execute.return_value = (True, "success")
            response = cast(
                HttpResponse,
                self.client.get(EXCHANGE_URL, {"type": "catalog", "mode": "import", "filename": "orders_1_x.xml"}),
            )

        assert response.content == b"success"
        orchestrator.assert_called_once()


# ---------------------------------------------------------------------------
# Реальная выгрузка БУС с test_base (backend/data/import_1c/orders/)
# ---------------------------------------------------------------------------

REAL_EXPORT_DIR = Path(settings.BASE_DIR) / "data" / "import_1c" / "orders"


def _strip(root) -> None:
    for elem in root.iter():
        if isinstance(elem.tag, str) and "}" in elem.tag:
            elem.tag = elem.tag.split("}", 1)[1]


def _expected_status(document) -> str | None:
    """Статус сайта по правилам спеки; None — документ пропускается."""
    requisites = {
        (item.findtext("Наименование") or "").strip(): (item.findtext("Значение") or "").strip()
        for item in document.findall("ЗначенияРеквизитов/ЗначениеРеквизита")
    }
    cancelled = requisites.get("Отменен", "").lower() == "true"
    lines = [line.findtext("Ид") for line in document.findall("Товары/Товар")]
    marked = (document.findtext("ПометкаУдаления") or "").strip().lower() == "true"
    if cancelled and (marked or all(line_id == "ORDER_DELIVERY" for line_id in lines)):
        return "cancelled"
    status_id = requisites.get("Статуса заказа ИД")
    if not status_id:
        return None
    from apps.orders.constants import FINAL_STATUSES, STATUS_MAPPING, STATUS_PRIORITY

    mapped = STATUS_MAPPING[status_id]
    if cancelled and mapped in FINAL_STATUSES:
        return None
    if STATUS_PRIORITY[mapped] and STATUS_PRIORITY[mapped] < STATUS_PRIORITY["processing"]:
        return None
    return mapped


@pytest.mark.django_db
@pytest.mark.integration
@pytest.mark.data_dependent
def test_bus_orders_real_export(exchange_dirs):
    """Реальный `orders_*.xml` БУС проходит `checkauth → init → file → import`."""
    import defusedxml.ElementTree as ET
    from django.core.management.color import no_style
    from django.db import connection

    files = sorted(REAL_EXPORT_DIR.glob("orders*.xml"))
    if not files:
        pytest.skip("Реальная выгрузка заказов БУС не найдена: data/import_1c/orders")
    raw = files[0].read_bytes()
    root = ET.fromstring(raw)
    _strip(root)

    expected: dict[int, str] = {}
    for document in root.iter("Документ"):
        if (document.findtext("ХозОперация") or "").strip() != "Заказ товара":
            continue
        order_id = (document.findtext("Ид") or "").strip()
        if not order_id.startswith("order-"):
            continue
        pk = int(order_id.removeprefix("order-"))
        Order.objects.create(
            pk=pk,
            order_number=(document.findtext("Номер") or "").strip(),
            is_master=False,
            status="processing",
            status_1c="К выполнению",
            sent_to_1c=True,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        status = _expected_status(document)
        if status is not None:
            expected[pk] = status
    with connection.cursor() as cursor:
        for sql in connection.ops.sequence_reset_sql(no_style(), [Order]):
            cursor.execute(sql)
    assert expected, "в выгрузке нет заказов сайта со статусом"
    assert {"at_warehouse", "delivered", "cancelled"} <= set(expected.values())

    formed_at = datetime.fromisoformat(root.get("ДатаФормирования")).replace(tzinfo=ZoneInfo(settings.TIME_ZONE))
    client = APIClient()
    user = UserFactory.create(password=ONEC_PASSWORD)
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="integrations", codename="can_exchange_1c")
    )
    perform_1c_checkauth(client, user.email, ONEC_PASSWORD)
    with patch("django.utils.timezone.now", return_value=formed_at):
        client.get(EXCHANGE_URL, {"type": "sale", "mode": "init"})
        upload = client.post(
            f"{EXCHANGE_URL}?type=sale&mode=file&filename={files[0].name}",
            data=raw,
            content_type="application/octet-stream",
        )
        assert upload.content == b"success"
        response = client.get(EXCHANGE_URL, {"type": "sale", "mode": "import", "filename": files[0].name})

    assert response.content == b"success"
    assert not ImportSession.objects.exists()
    actual = dict(Order.objects.filter(pk__in=expected).values_list("pk", "status"))
    assert actual == expected
