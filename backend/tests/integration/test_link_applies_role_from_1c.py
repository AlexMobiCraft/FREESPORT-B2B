"""
Привязка реальной записи 1С выдаёт роль сразу, без повторного импорта (стори 40.5).

До 40.5 тот же результат достигался только следующим обменом: менеджер связывал
заявку, импорт находил аккаунт по перенесённому onec_id и применял роль
(`test_link_then_import_1c.py`). Между двумя событиями клиент видел чужой уровень
цен. Здесь проверяется закрытие этого разрыва — импорт после привязки не
запускается вовсе.

Данные — только реальная выгрузка backend/data/import_1c/contragents_pricetype/
(NFR-3940-01): снимок второй редакции патча расширения БУС, где блок
<ЗначенияРеквизитов> приходит у каждого контрагента.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from apps.common.models import AuditLog
from apps.products.models import ImportSession, PriceType
from apps.users.models import User
from apps.users.services.link_1c_customer import find_link_candidates, link_1c_customer
from apps.users.services.parser import CustomerDataParser
from apps.users.services.processor import CustomerDataProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.data_dependent]

# Роль, которую сценарий назначает виду цен из снимка. Выбрана так, чтобы
# отличаться от исходной роли заявителя (wholesale_level1) и оставаться в
# User.B2B_ROLES: только тогда смена роли доказывает работу сервиса.
EXPECTED_ROLE = "wholesale_level2"


def _snapshot_files(onec_data_dir: Path) -> list[Path]:
    """Файлы снимка второй редакции патча.

    Имена задаёт 1С (contragents_<пакет>_<GUID>.xml, GUID новый при каждой
    выгрузке) — зашивать имя нельзя.
    """
    files = sorted((onec_data_dir / "contragents_pricetype").glob("contragents*.xml"))
    if not files:
        pytest.skip("Реальный dataset 1С не найден: contragents_pricetype")
    return files


def _pick_representative_file(onec_data_dir: Path) -> tuple[Path, list[dict]]:
    """
    Наименьший файл снимка, где есть обе интересующие ветки.

    Прогон всех 10 файлов — это 4735 создаваемых User и столько же записей
    журнала, десятки минут. Одного файла достаточно: проверяемые инварианты
    от объёма не зависят. Файл выбирается по содержимому, а не по имени:
    состав пакетов меняется при каждом переснятии снимка.
    """
    parser = CustomerDataParser()
    candidates: list[tuple[int, Path, list[dict]]] = []

    for file_path in _snapshot_files(onec_data_dir):
        customers = parser.parse(str(file_path))
        buyers = [c for c in customers if "Покупатель" in str(c.get("role") or "")]
        has_price_type = any(len(set(c["price_type_ids"])) == 1 for c in buyers)
        has_no_agreement = any(c["agreement_status"] == "НетСоглашения" for c in buyers)
        if has_price_type and has_no_agreement:
            candidates.append((file_path.stat().st_size, file_path, customers))

    if not candidates:
        pytest.skip("В снимке нет файла сразу с видом цен и со статусом НетСоглашения")

    _, file_path, customers = min(candidates, key=lambda item: item[0])
    return file_path, customers


@pytest.fixture
def processor() -> CustomerDataProcessor:
    return CustomerDataProcessor(
        session_id=ImportSession.objects.create(
            import_type=ImportSession.ImportType.CUSTOMERS,
            status=ImportSession.ImportStatus.STARTED,
        ).pk
    )


@pytest.fixture
def customer_with_price_type(onec_data_dir, processor) -> dict:
    """
    Разбор одного файла снимка вместо прогона команды импорта.

    Команде нужен весь файл (4735 User и столько же записей журнала —
    десятки минут), а стори проверяет привязку одной записи: импортируется
    ровно один контрагент через process_customer.
    """
    _, customers = _pick_representative_file(Path(onec_data_dir))
    for candidate in customers:
        if not processor.is_buyer(candidate):
            continue
        if not (candidate.get("tax_id") or "").strip():
            continue
        if len(set(candidate["price_type_ids"])) != 1:
            continue
        if candidate["agreement_status"] == "НетСоглашения":
            continue
        return candidate
    pytest.skip("В выбранном файле снимка нет покупателя с ИНН и однозначным видом цен")


def test_link_applies_role_from_agreement_without_reimport(processor, customer_with_price_type):
    """
    Роль применяется в момент привязки — повторный прогон импорта не нужен.

    Конкретный GUID не зашивается: состав видов цен внутри файла снимка не
    зафиксирован (замер стори 40.3), и поиск по литералу дал бы
    недетерминированный skip. Ожидаемая роль берётся из созданной записи
    справочника, а не из литерала.
    """
    imported = processor.process_customer(customer_with_price_type)
    assert imported is not None, "Реальный контрагент не импортировался"
    assert imported.onec_price_type_id, "У импортированной записи нет вида цен из соглашения"
    assert imported.role == User.ROLE_UNREGISTERED, "У записи 1С роль всегда unregistered"

    price_type, _ = PriceType.objects.get_or_create(
        onec_id=imported.onec_price_type_id,
        defaults={
            "onec_name": "Опт 2 (150-300 тыс.руб в квартал)",
            "product_field": "opt2_price",
            "user_role": EXPECTED_ROLE,
            "is_active": True,
        },
    )
    # defaults срабатывают только при создании: у уже существующей записи
    # справочника (GUID снимка может быть засеян миграцией) роль и признак
    # активности задаются принудительно. Довзводить роль только из пустой
    # недостаточно: у засеянной записи там может стоять retail (сервис по AC6
    # такую роль намеренно не применяет) или wholesale_level1 (совпадает с
    # исходной ролью заявителя) — в обоих случаях тест упал бы ложно, проверяя
    # состояние справочника, а не поведение привязки. resolve_role_from_price_types
    # читает только активные записи, поэтому is_active довзводится наравне.
    stale_fields = []
    if price_type.user_role != EXPECTED_ROLE:
        price_type.user_role = EXPECTED_ROLE
        stale_fields.append("user_role")
    if not price_type.is_active:
        price_type.is_active = True
        stale_fields.append("is_active")
    if stale_fields:
        price_type.save(update_fields=stale_fields)
    expected_role = price_type.user_role

    applicant = User.objects.create_user(
        email=f"applicant_{time.time_ns()}@example.com",
        password="StrongPassword123!",
        first_name="Заявитель",
        last_name="Портальный",
        role="wholesale_level1",
        company_name="Форма Компани",
        tax_id=imported.tax_id,
        verification_status="pending",
    )
    assert expected_role != applicant.role, "Ожидаемая роль обязана отличаться от исходной"
    assert find_link_candidates(applicant) == [imported]

    linked = link_1c_customer(
        target_id=applicant.pk,
        source_id=imported.pk,
        expected_onec_id=imported.onec_id,
    )

    applicant.refresh_from_db()
    assert applicant.onec_price_type_id == imported.onec_price_type_id, "Вид цен не перенесён"
    assert applicant.role == expected_role, "Роль не применена в момент привязки"
    assert linked.role == expected_role

    entry = AuditLog.objects.get(action="link_1c_customer", resource_id=str(applicant.pk))
    assert "role" in entry.changes["transferred_fields"]
    assert "onec_price_type_id" in entry.changes["transferred_fields"]
    assert entry.changes["previous_values"]["role"] == "wholesale_level1"
