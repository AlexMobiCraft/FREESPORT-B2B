"""
Интеграционные тесты накопления вида цен из 1С (стори 40.3).

Портал начинает хранить GUID вида цен из соглашения (реквизит ТипЦенId),
но роль по нему не выдаёт — её применение заводит стори 40.4. Отсюда
главный тест выката: после прогона импорта роли всех записей обязаны
остаться прежними.

Данные — только реальная выгрузка из backend/data/import_1c/
(NFR-3940-01): contragents_pricetype/ — снимок второй редакции патча
расширения БУС, где блок <ЗначенияРеквизитов> приходит у каждого
контрагента.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.users.services.parser import CustomerDataParser

User = get_user_model()

pytestmark = [pytest.mark.django_db, pytest.mark.data_dependent]


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


class TestImportStoresPriceType:
    """Заполнение User.onec_price_type_id прогоном реальной выгрузки."""

    def test_price_type_is_populated_from_real_export(self, snapshot_data_dir):
        """
        AC3, AC11: поле реально заполняется, значения нормализованы.

        Нижний регистр и отсутствие пробелов проверяются потому, что стори
        40.5 сравнивает сохранённый GUID со справочником: расползание
        формата всплыло бы там, а не здесь.
        """
        data_dir, customers = snapshot_data_dir
        expected = {
            customer["onec_id"]: customer["price_type_ids"][0]
            for customer in customers
            if "Покупатель" in str(customer.get("role") or "") and len(set(customer["price_type_ids"])) == 1
        }
        assert expected, "В выбранном файле снимка нет контрагента с одним ТипЦенId"

        call_command("import_customers_from_1c", data_dir=data_dir)

        stored = dict(User.objects.filter(onec_id__in=expected.keys()).values_list("onec_id", "onec_price_type_id"))
        assert stored == expected

        for guid in User.objects.exclude(onec_price_type_id="").values_list("onec_price_type_id", flat=True):
            assert guid == guid.strip().lower(), f"GUID вида цен не нормализован: {guid!r}"

    def test_no_agreement_customers_have_empty_price_type(self, snapshot_data_dir):
        """AC4: у контрагентов со снятым соглашением поле пусто."""
        data_dir, customers = snapshot_data_dir
        no_agreement_ids = [
            customer["onec_id"]
            for customer in customers
            if "Покупатель" in str(customer.get("role") or "") and customer["agreement_status"] == "НетСоглашения"
        ]
        assert no_agreement_ids, "В выбранном файле снимка нет статуса НетСоглашения"

        call_command("import_customers_from_1c", data_dir=data_dir)

        stored = set(User.objects.filter(onec_id__in=no_agreement_ids).values_list("onec_price_type_id", flat=True))
        assert stored == {""}

    def test_roles_unchanged_after_import(self, snapshot_data_dir):
        """
        AC10, предохранитель выката: прогон импорта роли не меняет.

        Стори выкатывается самостоятельно, до включения автоприменения роли
        (40.4), и поведение портала для пользователей менять не должна.
        Снимок ролей снимается после первого прогона и сверяется после
        второго — так проверяется и повторный импорт той же выгрузки.
        """
        data_dir, _ = snapshot_data_dir

        call_command("import_customers_from_1c", data_dir=data_dir)
        roles_before = dict(User.objects.exclude(onec_id=None).values_list("onec_id", "role"))
        price_types_before = dict(User.objects.exclude(onec_id=None).values_list("onec_id", "onec_price_type_id"))
        assert roles_before, "Импорт не создал ни одной записи 1С"

        call_command("import_customers_from_1c", data_dir=data_dir)
        roles_after = dict(User.objects.exclude(onec_id=None).values_list("onec_id", "role"))
        price_types_after = dict(User.objects.exclude(onec_id=None).values_list("onec_id", "onec_price_type_id"))

        assert roles_after == roles_before
        # AC9: повторный прогон той же выгрузки не меняет и вид цен
        assert price_types_after == price_types_before

    def test_imported_records_keep_unregistered_role(self, snapshot_data_dir):
        """AC2: контрагент с видом цен всё равно получает роль unregistered."""
        data_dir, customers = snapshot_data_dir
        with_price_type = [
            customer["onec_id"]
            for customer in customers
            if "Покупатель" in str(customer.get("role") or "") and len(set(customer["price_type_ids"])) == 1
        ]

        call_command("import_customers_from_1c", data_dir=data_dir)

        roles = set(User.objects.filter(onec_id__in=with_price_type).values_list("role", flat=True))
        assert roles == {User.ROLE_UNREGISTERED}
