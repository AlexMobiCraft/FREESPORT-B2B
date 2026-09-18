"""
Интеграционные тесты детектора регресса выгрузки контрагентов (стори 40.1).

Блок <ЗначенияРеквизитов> формирует патч тиражного расширения БУС и
теряется при обновлении модуля: файлы продолжают приходить, вида цен в
них больше нет. Отказ тихий, поэтому импорт обязан считать контрагентов
с блоком и без него и громко сообщать, если блока нет ни у кого.

Данные — только реальные выгрузки из backend/data/import_1c/
(NFR-3940-01): contragents_pricetype/ — снимок со второй редакцией патча,
contragents/ — снимок 11.04.2026 без блока.
"""

from __future__ import annotations

import shutil
from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.core.management import call_command

from apps.products.models import ImportSession
from apps.users.services.parser import CustomerDataParser


def _import_1c_dir() -> Path:
    """Каталог реальных выгрузок 1С (работает и локально, и в контейнере)."""
    return Path(settings.BASE_DIR) / "data" / "import_1c"


def _snapshot_files(subdir: str) -> list[Path]:
    """Файлы снимка по глобу.

    Имена задаёт 1С: contragents_<пакет>_<GUID>.xml, где GUID новый при
    каждой выгрузке, — зашивать имя нельзя.
    """
    files = sorted((_import_1c_dir() / subdir).glob("contragents*.xml"))
    if not files:
        pytest.skip(f"Реальный dataset 1С не найден: {subdir}")
    return files


def _single_file_data_dir(tmp_path: Path, subdir: str) -> str:
    """
    Готовит каталог вида <tmp>/contragents/<один файл снимка>.

    Команда жёстко требует подкаталог contragents/, а каталог
    contragents_pricetype/ напрямую не читает. Одного файла достаточно:
    счётчики линейны, а инвариант present + missing == total не зависит
    от объёма — прогон всего снимка создал бы 4735 пользователей.
    """
    files = _snapshot_files(subdir)
    smallest = min(files, key=lambda path: path.stat().st_size)

    data_dir = tmp_path / "import_1c"
    (data_dir / "contragents").mkdir(parents=True)
    shutil.copy(smallest, data_dir / "contragents" / smallest.name)
    return str(data_dir)


@pytest.mark.data_dependent
class TestPriceTypeSnapshotInvariants:
    """Инварианты снимка выгрузки — проверяются на нём целиком (AC7)."""

    def test_snapshot_satisfies_price_type_invariants(self):
        """
        AC7: у каждого контрагента ровно один вид цен либо явный статус.

        Абсолютные числа не проверяются намеренно: снимок обновляемый, и
        зашитая константа правилась бы не глядя при каждом переснятии.
        """
        parser = CustomerDataParser()
        customers: list[dict] = []
        for file_path in _snapshot_files("contragents_pricetype"):
            customers.extend(parser.parse(str(file_path)))

        assert customers, "Снимок разобран, но контрагентов в нём нет"

        ambiguous = [c for c in customers if len(c["price_type_ids"]) > 1]
        assert ambiguous == [], f"У {len(ambiguous)} контрагентов более одного различного ТипЦенId"

        uncovered = [c for c in customers if not c["price_type_ids"] and c["agreement_status"] != "НетСоглашения"]
        assert uncovered == [], (
            f"{len(uncovered)} контрагентов без вида цен и без статуса НетСоглашения — "
            "снимок первой редакции патча либо смешение редакций в каталоге"
        )


@pytest.mark.django_db
@pytest.mark.data_dependent
class TestAttributesBlockAnomalyDetector:
    """Детектор регресса выгрузки в команде import_customers_from_1c."""

    def test_block_present_no_anomaly(self, tmp_path):
        """AC9, AC10: блок есть — аномалии нет, счётчики сходятся с total."""
        data_dir = _single_file_data_dir(tmp_path, "contragents_pricetype")
        out = StringIO()

        call_command("import_customers_from_1c", data_dir=data_dir, stdout=out)

        session = ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS).latest("started_at")
        report = session.report_details

        assert report["attributes_block_anomaly"] is False
        assert report["attributes_block_present"] > 0
        assert report["attributes_block_present"] + report["attributes_block_missing"] == report["total"]

        output = out.getvalue()
        assert "Контрагентов с видом цен из 1С" in output
        assert "Аномалия выгрузки: нет" in output
        assert "ЗначенияРеквизитов" not in output

    def test_block_missing_everywhere_triggers_anomaly(self, tmp_path):
        """AC8: блока нет ни у кого — аномалия в отчёте и предупреждение в выводе."""
        data_dir = _single_file_data_dir(tmp_path, "contragents")
        out = StringIO()

        call_command("import_customers_from_1c", data_dir=data_dir, stdout=out)

        session = ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS).latest("started_at")
        report = session.report_details

        assert report["attributes_block_anomaly"] is True
        assert report["attributes_block_present"] == 0
        assert report["attributes_block_missing"] == report["total"] > 0

        output = out.getvalue()
        assert "ЗначенияРеквизитов" in output
        assert "ОбменСБитриксУправлениеСайтомУТ" in output
        assert "Аномалия выгрузки: ДА" in output

    def test_anomaly_warning_printed_in_dry_run(self, tmp_path):
        """
        AC8: предупреждение печатается и в dry-run.

        Итоговый блок в dry-run не выводится, поэтому предупреждение живёт
        отдельно от него: иначе прогон «на посмотреть» перед импортом на
        проде промолчал бы о поломке.
        """
        data_dir = _single_file_data_dir(tmp_path, "contragents")
        out = StringIO()

        call_command("import_customers_from_1c", data_dir=data_dir, dry_run=True, stdout=out)

        output = out.getvalue()
        assert "DRY-RUN" in output
        assert "ЗначенияРеквизитов" in output
