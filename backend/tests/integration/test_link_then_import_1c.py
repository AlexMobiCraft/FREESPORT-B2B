"""
Регрессионный тест стыка подсистем: привязка → повторный импорт из 1С.

Ради этого сценария существует вся фича. До привязки экспорт заказа подставлял
псевдо-идентификатор SHA256(email), в 1С заводился новый контрагент, и дубль
воспроизводился при каждом импорте. Тест доказывает, что после привязки
повторный импорт того же контрагента обновляет аккаунт заявителя, а не создаёт
запись рядом.

Используются реальные XML из data/import_1c/contragents/ — синтетические
выгрузки для тестов импорта 1С запрещены.
"""

from __future__ import annotations

import itertools
import os
import time
from pathlib import Path

import pytest

from apps.products.models import ImportSession
from apps.users.models import User
from apps.users.services.link_1c_customer import find_link_candidates, link_1c_customer
from apps.users.services.parser import CustomerDataParser
from apps.users.services.processor import CustomerDataProcessor

pytestmark = [pytest.mark.integration, pytest.mark.data_dependent, pytest.mark.django_db]

_counter = itertools.count()

CONTRAGENTS_FILE = "contragents_1_564750cd-8a00-4926-a2a4-7a1c995605c0.xml"


@pytest.fixture
def real_xml_file() -> str:
    """Путь к реальной выгрузке контрагентов (Docker или локальный запуск)."""
    if os.path.exists("/app/data"):
        xml_path = Path("/app/data/import_1c/contragents") / CONTRAGENTS_FILE
    else:
        # backend/tests/integration/test_link_then_import_1c.py → parents[2] = backend/
        xml_path = Path(__file__).resolve().parents[2] / "data" / "import_1c" / "contragents" / CONTRAGENTS_FILE
    if not xml_path.exists():
        pytest.skip(f"Реальный dataset 1С не найден: {xml_path}")
    return str(xml_path)


@pytest.fixture
def processor() -> CustomerDataProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CUSTOMERS,
        status=ImportSession.ImportStatus.STARTED,
    )
    return CustomerDataProcessor(session_id=session.pk)


@pytest.fixture
def customer_data(real_xml_file, processor) -> dict:
    """Первый контрагент-покупатель с ИНН из реальной выгрузки."""
    for candidate in CustomerDataParser().parse(real_xml_file):
        if processor.is_buyer(candidate) and (candidate.get("tax_id") or "").strip():
            return candidate
    pytest.skip("В реальной выгрузке нет контрагента-покупателя с ИНН")


def test_link_then_reimport_updates_applicant_without_duplicate(processor, customer_data):
    imported = processor.process_customer(customer_data)
    assert imported is not None, "Реальный контрагент не импортировался"
    assert imported.is_unlinked_1c_record is True

    applicant = User.objects.create_user(
        email=f"applicant_{time.time_ns()}_{next(_counter)}@example.com",
        password="StrongPassword123!",
        first_name="Заявитель",
        last_name="Портальный",
        role="wholesale_level1",
        company_name="Форма Компани",
        tax_id=imported.tax_id,
        verification_status="pending",
    )

    assert find_link_candidates(applicant) == [imported]

    linked = link_1c_customer(
        target_id=applicant.pk,
        source_id=imported.pk,
        expected_onec_id=imported.onec_id,
    )
    assert linked.onec_id == customer_data["onec_id"]

    users_before = User.objects.count()
    applicant_email, applicant_role = linked.email, linked.role

    # Повторный прогон того же XML — как при ближайшей синхронизации.
    reimported = processor.process_customer(customer_data)

    assert reimported is not None
    assert reimported.pk == applicant.pk, "Импорт нашёл заявителя по перенесённому onec_id"
    assert User.objects.count() == users_before, "Импорт создал дубль вместо обновления"

    applicant.refresh_from_db()
    assert applicant.email == applicant_email, "Импорт перезаписал логин заявителя"
    # Роль сохраняется потому, что в старом снимке contragents/ блока
    # <ЗначенияРеквизитов> нет ни у кого: резолвер отвечает no_data.
    # С 40.4 импорт роль привязанного аккаунта меняет — но только когда
    # 1С отдала вид цен (см. tests/integration/test_import_role_from_1c.py).
    assert applicant.role == applicant_role, "Импорт изменил роль, хотя вида цен в выгрузке нет"
    assert applicant.onec_id == customer_data["onec_id"]

    imported.refresh_from_db()
    assert imported.onec_id is None
    assert imported.is_active is False
