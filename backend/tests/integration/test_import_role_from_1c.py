"""
Интеграционные тесты применения роли из 1С при импорте (стори 40.4).

Импорт перестал быть «слепым» к уровню цен: роль привязанного аккаунта
приезжает из соглашения 1С (FR-40-07, FR-40-12), смена пишется в AuditLog
(FR-40-08), а отчёт сессии объясняет каждое решение (FR-40-09).

Ключевой предохранитель выката: непривязанная запись 1С роли не получает
никогда. Смена её роли выбила бы запись из unlinked_1c_record_q(), то есть
из всех путей привязки разом — вернулся бы баг, чинившийся миграцией 0018.
Отсюда критерий приёмки #4 (роли записей 1С остаются unregistered) и #5
(критические пути привязки не сломаны).

Данные — только реальная выгрузка из backend/data/import_1c/
(NFR-3940-01): contragents_pricetype/ — снимок второй редакции патча
расширения БУС.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import AuditLog
from apps.products.models import ImportSession, PriceType
from apps.users.services.parser import CustomerDataParser
from apps.users.services.processor import ROLE_STATS_KEYS

User = get_user_model()

pytestmark = [pytest.mark.django_db, pytest.mark.data_dependent]

REGISTER_URL = "/api/v1/auth/register/"


def _snapshot_files(onec_data_dir: Path) -> list[Path]:
    """
    Файлы снимка второй редакции патча.

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
def snapshot_data_dir(tmp_path, onec_data_dir):
    """
    Каталог вида <tmp>/contragents/<один файл снимка> плюс его разбор.

    Команда жёстко требует подкаталог contragents/ внутри --data-dir и
    каталог contragents_pricetype/ напрямую не читает.
    """
    file_path, customers = _pick_representative_file(Path(onec_data_dir))

    data_dir = tmp_path / "import_1c"
    (data_dir / "contragents").mkdir(parents=True)
    shutil.copy(file_path, data_dir / "contragents" / file_path.name)

    return str(data_dir), customers


def _buyer_with_single_price_type(customers: list[dict]) -> dict:
    """Первый покупатель снимка ровно с одним видом цен."""
    for data in customers:
        if "Покупатель" in str(data.get("role") or "") and len(set(data.get("price_type_ids") or [])) == 1:
            return data
    pytest.skip("В выбранном файле снимка нет покупателя с одним ТипЦенId")


def _imported_record_with_valid_tax_id() -> User:
    """
    Импортированная запись 1С с ИНН, который принимает форма регистрации.

    ИНН выбирается по факту из БД, а не по позиции в файле: у физлиц он
    пуст, а у зарубежных контрагентов — 9-значный УНП, и оба варианта
    сделали бы тест недетерминированным.
    """
    for record in User.objects.unlinked_1c_records().exclude(tax_id=""):
        tax_id = record.tax_id.strip()
        if tax_id.isdigit() and len(tax_id) in (10, 12):
            return record
    pytest.skip("В выбранном файле снимка нет записи 1С с 10- или 12-значным ИНН")


def _last_report_details() -> dict:
    """report_details последней завершённой сессии импорта контрагентов."""
    session = (
        ImportSession.objects.filter(
            import_type=ImportSession.ImportType.CUSTOMERS,
            status=ImportSession.ImportStatus.COMPLETED,
        )
        .order_by("-finished_at", "-pk")
        .first()
    )
    assert session is not None, "Команда не завершила сессию импорта"
    return session.report_details or {}


class TestImportKeepsUnlinkedRecordsUnregistered:
    """Критерий приёмки #4: записи 1С без портального аккаунта не меняют роль."""

    def test_all_1c_records_stay_unregistered(self, snapshot_data_dir):
        """
        AC15: ORM-эквивалент контрольного SQL из задания.

        SELECT role, COUNT(*) FROM users
        WHERE created_in_1c AND onec_id IS NOT NULL AND password = ''
        GROUP BY role  →  только unregistered.
        """
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)
        # Повторный прогон: на нём записи уже существуют и идут веткой
        # обновления — именно там роль и могла бы поменяться.
        call_command("import_customers_from_1c", data_dir=data_dir)

        roles = set(
            User.objects.filter(created_in_1c=True, onec_id__isnull=False, password="").values_list("role", flat=True)
        )
        assert roles == {User.ROLE_UNREGISTERED}


class TestImportRoleReport:
    """Критерий приёмки #6: отчёт объясняет каждое решение."""

    def test_report_details_contain_all_role_counters(self, snapshot_data_dir):
        """AC7/AC9: все девять ролевых счётчиков попадают в report_details."""
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)

        report = _last_report_details()
        for key in ROLE_STATS_KEYS:
            assert key in report, f"В report_details нет ключа {key}"

    def test_first_run_reports_no_role_activity(self, snapshot_data_dir):
        """
        AC9: прогон «с нуля» — все записи создаются, ролевые счётчики нулевые.

        Именно так выглядит день выката на проде: обновлять нечего.
        """
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)

        report = _last_report_details()
        assert report["created"] > 0
        assert report["updated"] == 0
        assert report["roles_updated"] == 0
        assert report["roles_skipped_unlinked_record"] == 0

    def test_second_run_reports_unlinked_records(self, snapshot_data_dir):
        """
        AC9: повторный прогон даёт roles_skipped_unlinked_record > 0.

        Это наблюдаемая норма прода: roles_updated = 0 объясняется тем, что
        живых привязанных аккаунтов ещё нет, а не поломкой импорта.
        """
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)
        call_command("import_customers_from_1c", data_dir=data_dir)

        report = _last_report_details()
        assert report["updated"] > 0
        assert report["roles_updated"] == 0
        assert report["roles_skipped_unlinked_record"] > 0

    def test_role_counters_sum_to_updated(self, snapshot_data_dir):
        """AC10: исходы взаимно исключающие и покрывают все обновления."""
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)
        call_command("import_customers_from_1c", data_dir=data_dir)

        report = _last_report_details()
        role_outcomes = sum(
            report[key]
            for key in (
                "roles_updated",
                "roles_already_actual",
                "roles_skipped_unlinked_record",
                "roles_skipped_no_data",
                "roles_skipped_no_agreement",
                "roles_skipped_unknown_price_type",
                "roles_skipped_ambiguous",
            )
        )
        assert role_outcomes == report["updated"]
        assert report["roles_updated"] == (
            report["roles_updated_from_unregistered"] + report["roles_updated_from_assigned"]
        )


class TestImportAppliesRoleToLinkedAccount:
    """Критерии приёмки #1–#3: живой аккаунт получает роль из соглашения."""

    def test_linked_account_role_comes_from_price_type_reference(self, snapshot_data_dir):
        """
        AC2/AC5/AC8: роль приезжает из справочника, смена уходит в AuditLog.

        Конкретный GUID не зашивается: состав видов цен внутри файла снимка
        не зафиксирован. Берём вид цен у первого подходящего контрагента и
        заводим для него запись справочника через get_or_create — GUID может
        оказаться «Опт 4», уже засеянным миграцией products/0053.
        """
        data_dir, customers = snapshot_data_dir
        customer = _buyer_with_single_price_type(customers)
        guid = customer["price_type_ids"][0]

        price_type, _ = PriceType.objects.get_or_create(
            onec_id=guid,
            defaults={
                "onec_name": "Опт 2 (150-300 тыс.руб в квартал)",
                "product_field": "opt2_price",
                "user_role": "wholesale_level2",
                "is_active": True,
            },
        )
        if not price_type.user_role:
            price_type.user_role = "wholesale_level2"
            price_type.save(update_fields=["user_role"])
        expected_role = price_type.user_role

        linked = User.objects.create(
            email=f"linked_{time.time_ns()}@example.com",
            onec_id=customer["onec_id"],
            role="wholesale_level1",
            created_in_1c=False,
            verification_status="verified",
        )
        linked.set_password("StrongPassword123!")
        linked.save(update_fields=["password"])
        assert linked.is_unlinked_1c_record is False
        assert expected_role != "wholesale_level1", "Ожидаемая роль обязана отличаться от исходной"

        call_command("import_customers_from_1c", data_dir=data_dir)

        linked.refresh_from_db()
        assert linked.role == expected_role

        logs = AuditLog.objects.filter(action="role_from_1c", resource_id=str(linked.pk))
        assert logs.count() == 1
        log = logs.first()
        assert log.user is None
        assert log.changes["previous_role"] == "wholesale_level1"
        assert log.changes["new_role"] == expected_role
        assert log.changes["price_type_id"] == guid

        report = _last_report_details()
        assert report["roles_updated"] == 1
        assert report["roles_updated_from_assigned"] == 1


class TestLinkPathsSurviveImport:
    """Критерий приёмки #5 (NFR-3940-05): пути привязки не сломаны."""

    def test_unlinked_records_and_candidates_are_still_found(self, snapshot_data_dir):
        """AC16: выборка кандидатов и аннотация админки остаются непустыми."""
        from apps.users.admin import has_1c_candidate_expression
        from apps.users.services.link_1c_customer import find_link_candidates

        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)

        assert User.objects.unlinked_1c_records().exists()

        record = _imported_record_with_valid_tax_id()

        applicant = User.objects.create(
            email=f"applicant_{time.time_ns()}@example.com",
            first_name="Заявка",
            last_name="Оптовик",
            role="wholesale_level1",
            tax_id=record.tax_id,
            verification_status="pending",
        )
        applicant.set_password("StrongPassword123!")
        applicant.save(update_fields=["password"])

        assert find_link_candidates(applicant), "После импорта кандидаты на привязку исчезли"
        assert (
            User.objects.annotate(_has_1c_candidate=has_1c_candidate_expression())
            .filter(_has_1c_candidate=True)
            .exists()
        )

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_registration_with_known_tax_id_still_returns_201(self, mock_admin_email, snapshot_data_dir):
        """AC16: регистрация по ИНН, известному 1С, создаёт заявку, а не отказ."""
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)

        record = _imported_record_with_valid_tax_id()

        client = APIClient()
        response = client.post(
            REGISTER_URL,
            {
                "email": f"portal_link_{time.time_ns()}@example.com",
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "first_name": "Форма",
                "last_name": "Регистрации",
                "role": "wholesale_level1",
                "company_name": "Форма Компани",
                "tax_id": record.tax_id,
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
