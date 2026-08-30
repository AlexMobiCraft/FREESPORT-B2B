"""Изоляция каталога обмена 1С по сессии (стори `onec-exchange-dir-isolation`).

Каталог обмена был общий для всех сессий: 1С шлёт `mode=import` на каждый файл и
`mode=complete` следом, задачи сериализуются локом каталога, и прогон без
обещанного имени (`mode=complete`) успевал собрать по маске чужой свежий файл,
прочитать его и законно удалить как обработанный. Сегмент, отстоявший очередь за
локом, обещанного файла не находил и падал в FAILED.

Замер прода 28.08.2026, окно 7 дней: 110 упавших сессий, 85 из них с «файл не
найден в каталоге обмена», и все 85 — ровно те, что ждали лока.

`session_key` уникален для каждого файла (1С не держит cookie-сессию между
запросами), поэтому каталог на сессию = каталог на файл: пересечься физически
невозможно.

XML берутся из закоммиченного среза реальной выгрузки 1С
(`backend/tests/fixtures/1c-data/`) — синтетику проект запрещает.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from django.core.cache import cache
from django.core.management import call_command

from apps.integrations.onec_exchange.file_service import FileStreamService
from apps.integrations.onec_exchange.routing_service import SHARED_ROOT_NAMES, FileRoutingService
from apps.products.factories import ProductFactory
from apps.products.management.commands.import_products_from_1c import Command
from apps.products.models import ImportSession, Product, ProductVariant
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor
from apps.products.tasks import (
    SESSION_HAS_NO_OWN_FILES,
    _import_lock_key,
    cleanup_stale_exchange_dirs,
    process_1c_import_task,
)

ONEC_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "1c-data"

# Восемь реальных сегментов остатков с исходными именами 1С (`rests_1_<N>_<guid>.xml`).
# Порядок — числовой по номеру сегмента, а не лексикографический.
REAL_SEGMENTS = sorted(
    (ONEC_FIXTURES / "rests" / "segments").glob("rests_1_*.xml"),
    key=lambda p: int(p.name.split("_")[2]),
)

# Реальная выгрузка товаров вместе с настоящими картинками: пути внутри XML
# имеют вид `import_files/<xx>/<file>.jpg`.
GOODS_SOURCE_DIR = ONEC_FIXTURES / "goods" / "import_files"
GOODS_XML = GOODS_SOURCE_DIR / "goods.xml"
# Товар из этой выгрузки, у которого есть <Картинка> в каталоге `01/`.
GOODS_PRODUCT_WITH_IMAGES = "018d777d-9094-11ec-a2ff-04421a23d8e8"

# Реальная выгрузка торговых предложений. Изображений она не несёт: во всём
# корпусе `data/import_1c/offers/` (31 файл) ноль тегов <Картинка> — 1С отдаёт
# состав фото только в goods.xml. Поэтому тест AC2 для варианта берёт из XML
# настоящее предложение, а ссылку на картинку подставляет ровно в той форме
# `import_files/<xx>/<file>.jpg`, в какой её пишет 1С: выдумывать XML проект
# запрещает, а разрешение исходника проверить надо.
OFFERS_XML = ONEC_FIXTURES / "offers" / "offers.xml"


def _segment_path(index: int) -> Path:
    """Реальный сегмент остатков по порядковому номеру (1-based)."""
    return REAL_SEGMENTS[index - 1]


def _segment_name(index: int) -> str:
    """Имя сегмента ровно в том виде, в котором его присылает 1С."""
    return _segment_path(index).name


@pytest.fixture
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def exchange(tmp_path, settings):
    """Приватные каталоги обмена 1С, переведённые в tmp_path.

    Оба каталога подменяются целиком: изоляция считает сессионным ровно тот
    каталог, чей родитель — `ONEC_EXCHANGE["IMPORT_DIR"]`, и без подмены правило
    смотрело бы на боевой путь.
    """
    temp_dir = tmp_path / "1c_temp"
    import_dir = tmp_path / "1c_import"
    temp_dir.mkdir()
    import_dir.mkdir()
    settings.ONEC_EXCHANGE = {
        **settings.ONEC_EXCHANGE,
        "TEMP_DIR": temp_dir,
        "IMPORT_DIR": import_dir,
    }
    return SimpleNamespace(temp=temp_dir, imports=import_dir)


def _upload(sessid: str, source: Path, filename: str | None = None) -> Path:
    """Провести файл штатным путём 1С: temp сессии → каталог обмена.

    Именно так файл попадает в каталог на проде (`handle_file_upload` +
    `_transfer_files`), поэтому тест не выкладывает файлы руками.
    """
    name = filename or source.name
    stream = FileStreamService(sessid)
    stream._ensure_session_dir()
    shutil.copyfile(source, stream.get_file_path(name))
    return FileRoutingService(sessid).move_to_import(name)


def _session(sessid: str, status: str) -> ImportSession:
    return ImportSession.objects.create(session_key=sessid, status=status)


def _import_dir(sessid: str) -> Path:
    return FileRoutingService(sessid).import_dir


def _run_task(session: ImportSession, sessid: str, source_filename: str | None, task_id: str) -> str:
    """Прогон задачи импорта по каталогу своей сессии."""
    return process_1c_import_task.apply(
        args=(session.pk,),
        kwargs={"data_dir": str(_import_dir(sessid)), "source_filename": source_filename},
        task_id=task_id,
    ).get()


@pytest.mark.django_db
class TestSessionDirIsolation:
    """AC1 — сессионная раскладка каталога обмена."""

    def test_import_dir_is_session_scoped(self, exchange):
        """Каталог обмена сессии — подкаталог общего корня с именем сессии."""
        router = FileRoutingService("sess-a")

        assert router.import_dir == exchange.imports / "sess-a"
        assert FileRoutingService("sess-b").import_dir != router.import_dir

    def test_uploaded_segment_lands_in_own_dir(self, exchange):
        """Файл сессии виден только в её каталоге."""
        target = _upload("sess-a", _segment_path(1))

        assert target == exchange.imports / "sess-a" / "rests" / _segment_name(1)
        assert not (exchange.imports / "sess-b" / "rests" / _segment_name(1)).exists()

    def test_neighbour_segment_survives_promiseless_run(self, exchange, clean_cache):
        """Ядро дефекта: прогон без обещания не имеет права съесть чужой сегмент.

        Воспроизводится прод-механика сессий 66453/66454: сессия A (`mode=complete`)
        держит лок и работает, файл сессии B уже лежит в каталоге обмена (окно
        между `_transfer_files` и `_dispatch_import`, где B ещё PENDING), поэтому
        guard `defer_to_active_sessions` его не видит. На общем каталоге A
        собирает файл B по маске, читает и удаляет — B, дождавшись лока, падает.
        """
        session_a = _session("sess-a", ImportSession.ImportStatus.PENDING)
        session_b = _session("sess-b", ImportSession.ImportStatus.PENDING)

        own = _upload("sess-a", _segment_path(1))
        neighbour = _upload("sess-b", _segment_path(2))

        # `mode=complete` идёт с file_type=all — бэкап БД к изоляции отношения не имеет.
        with patch.object(Command, "_backup_before_import"):
            assert _run_task(session_a, "sess-a", "complete", "task-iso-a") == "success"

        assert not own.exists(), "Свой сегмент прогон обязан прочитать и убрать"
        assert neighbour.exists(), "Чужой сегмент прогон без обещания читать не вправе"

        # Очередь за локом отстояла — теперь работает B со своим обещанным файлом.
        session_b.status = ImportSession.ImportStatus.IN_PROGRESS
        session_b.save(update_fields=["status"])
        assert _run_task(session_b, "sess-b", _segment_name(2), "task-iso-b") == "success"

        session_a.refresh_from_db()
        session_b.refresh_from_db()
        assert session_a.status == ImportSession.ImportStatus.COMPLETED
        assert session_b.status == ImportSession.ImportStatus.COMPLETED
        assert not neighbour.exists(), "Свой сегмент сессия B обязана прочитать сама"

    def test_locked_dir_defers_neighbour_and_both_sessions_complete(self, exchange, clean_cache):
        """AC1 целиком: занятый общий лок → Retry соседа → обе сессии COMPLETED.

        Приёмка стори требует одного прогона от начала до конца, а не двух
        разрозненных проверок: изоляция считается работающей только если очередь
        за локом сохранилась (AC6), а обе задачи, отстояв её, прочитали ровно
        свой сегмент. На проде рвалась именно эта связка (сессии 66453/66454).

        Держателем лока выступает сессия A: её задача берёт лок первой, а B в
        этот момент уже стоит в очереди. Лок ставится тестом напрямую, потому
        что задача A снимает его в `finally` — иначе окно «B пришла, пока A
        работает» одним потоком не воспроизвести.
        """
        session_a = _session("sess-a", ImportSession.ImportStatus.PENDING)
        session_b = _session("sess-b", ImportSession.ImportStatus.PENDING)

        own_a = _upload("sess-a", _segment_path(1))
        own_b = _upload("sess-b", _segment_path(2))

        lock_key = _import_lock_key(str(_import_dir("sess-a")))
        assert lock_key == _import_lock_key(str(_import_dir("sess-b"))), "Лок обязан остаться общим"

        cache.add(lock_key, "task-ac1-a", 60)

        with patch.object(process_1c_import_task, "retry", side_effect=Retry()) as mock_retry:
            process_1c_import_task.apply(
                args=(session_b.pk,),
                kwargs={"data_dir": str(_import_dir("sess-b")), "source_filename": _segment_name(2)},
                task_id="task-ac1-b-deferred",
            )

        mock_retry.assert_called_once()
        session_b.refresh_from_db()
        assert "Каталог обмена занят другим импортом, задача отложена" in session_b.report
        assert own_b.exists(), "Отложенный сегмент обязан дождаться своей задачи"

        # Держатель лока отработал и освободил каталог обмена.
        cache.delete(lock_key)
        with patch.object(Command, "_backup_before_import"):
            assert _run_task(session_a, "sess-a", "complete", "task-ac1-a") == "success"

        assert not own_a.exists(), "Свой сегмент прогон A обязан прочитать"
        assert own_b.exists(), "Прогон без обещания не вправе трогать сегмент соседа"

        session_b.status = ImportSession.ImportStatus.IN_PROGRESS
        session_b.save(update_fields=["status"])
        assert _run_task(session_b, "sess-b", _segment_name(2), "task-ac1-b") == "success"

        assert not own_b.exists(), "Свой сегмент сессия B обязана прочитать сама"
        session_a.refresh_from_db()
        session_b.refresh_from_db()
        assert session_a.status == ImportSession.ImportStatus.COMPLETED
        assert session_b.status == ImportSession.ImportStatus.COMPLETED

    def test_session_id_must_be_single_path_segment(self, exchange):
        """`sessid` приходит из query-параметра и становится сегментом пути под rmtree."""
        for evil in ("../escape", "a/b", "a\\b", "..", ""):
            with pytest.raises(ValueError):
                FileRoutingService(evil)

    def test_session_id_must_not_collide_with_shared_dirs(self, exchange):
        """`sessid`, совпавший с общим каталогом, отдал бы его под уборку сессии.

        `sessid=import_files` даёт каталог сессии `IMPORT_DIR/import_files` —
        то есть общий каталог картинок целиком, вместе с `cleanup_import_dir` и
        `remove_session_dirs` этой сессии. `sessid=goods` уносит легаси-раскладку,
        на которую опирается фолбэк переходного окна.
        """
        for shared in sorted(SHARED_ROOT_NAMES):
            with pytest.raises(ValueError):
                FileRoutingService(shared)

        # Регистр файловая система не различает — проверка тоже не должна.
        with pytest.raises(ValueError):
            FileRoutingService("Import_Files")


@pytest.mark.django_db
class TestSharedImages:
    """AC2 — картинки остаются общими и доступны XML любой сессии."""

    def test_images_are_routed_to_shared_dir(self, exchange):
        """Картинка ложится в общий `import_files`, а не в каталог своей сессии."""
        image = next((GOODS_SOURCE_DIR / "01").glob("*.jpg"))
        target = _upload("sess-images", image)

        assert target == exchange.imports / "import_files" / image.name
        assert not (exchange.imports / "sess-images" / "import_files").exists()

    def test_xml_from_session_dir_resolves_shared_images(self, exchange, tmp_path, settings):
        """goods.xml изолированной сессии находит картинки чужого обмена."""
        settings.MEDIA_ROOT = str(tmp_path / "media")

        data_dir = _import_dir("sess-goods")
        (data_dir / "goods").mkdir(parents=True)
        shutil.copyfile(GOODS_XML, data_dir / "goods" / "goods.xml")

        # Картинки приехали отдельным обменом с другим sessid — они в общем каталоге.
        shared_images = exchange.imports / "import_files"
        for sub in ("01", "03", "06"):
            shutil.copytree(GOODS_SOURCE_DIR / sub, shared_images / sub)

        session = _session("sess-goods", ImportSession.ImportStatus.IN_PROGRESS)
        call_command(
            "import_products_from_1c",
            data_dir=str(data_dir),
            file_type="goods",
            import_session_id=session.pk,
        )

        product = Product.objects.get(onec_id=GOODS_PRODUCT_WITH_IMAGES)
        assert product.base_images, "Картинки из общего каталога обязаны разрешиться"
        assert shared_images.exists(), "Общий каталог картинок чистит не сессия"

    def test_offers_variant_binds_image_from_shared_dir(self, exchange, tmp_path, settings):
        """AC2 для ProductVariant: шаг offers тоже смотрит в общий `import_files`.

        `_images_base_dir` вызывается ДВАЖДЫ — с `xml_subdir="goods"` и с
        `xml_subdir="offers"`, — и проверки `Product.base_images` мало: ветка
        вариантов могла бы остаться на сессионном каталоге и молча потерять фото.

        XML здесь настоящий. Изображений реальный offers.xml не несёт (их состав
        1С отдаёт только в goods.xml), поэтому ссылка на картинку добавляется к
        уже распарсенному предложению — в той же форме `import_files/<xx>/<file>`,
        какую пишет 1С. Родительский товар создан фабрикой: в фикстурном
        goods.xml родителей этих предложений нет, а выдумывать XML нельзя.
        """
        settings.MEDIA_ROOT = str(tmp_path / "media")

        data_dir = _import_dir("sess-offers")
        (data_dir / "offers").mkdir(parents=True)
        shutil.copyfile(OFFERS_XML, data_dir / "offers" / "offers.xml")

        # Картинки приехали отдельным обменом со своим sessid — общий каталог.
        shared_images = exchange.imports / "import_files"
        shutil.copytree(GOODS_SOURCE_DIR / "01", shared_images / "01")

        session = _session("sess-offers", ImportSession.ImportStatus.IN_PROGRESS)
        processor = VariantImportProcessor(session_id=session.pk)
        base_dir = Command()._images_base_dir(str(data_dir), "offers", processor)

        assert Path(base_dir) == shared_images, "Шаг offers обязан брать картинки из общего каталога"

        offer = XMLDataParser().parse_offers_xml(str(data_dir / "offers" / "offers.xml"))[0]
        parent_onec_id = str(offer["id"]).split("#")[0]
        parent = ProductFactory(create_variant=False)
        Product.objects.filter(pk=parent.pk).update(onec_id=parent_onec_id)

        # Самый крупный файл каталога: порог `MIN_IMAGE_SIZE_BYTES` — 100 КБ,
        # и на превью тест проверял бы резервную ветку, а не разрешение пути.
        image = max((shared_images / "01").glob("*.jpg"), key=lambda f: f.stat().st_size)
        offer["images"] = [f"import_files/01/{image.name}"]

        variant = processor.process_variant_from_offer(dict(offer), base_dir=base_dir, skip_images=False)

        assert variant is not None, "Вариант реального предложения обязан создаться"
        assert variant.main_image, "Картинка общего каталога обязана привязаться к варианту"
        assert ProductVariant.objects.get(pk=variant.pk).main_image
        assert (Path(settings.MEDIA_ROOT) / str(variant.main_image)).exists()
        assert image.exists(), "Общий каталог картинок остаётся нетронутым"

    def test_legacy_image_layout_still_resolves(self, exchange, tmp_path, settings):
        """Переходное окно выката: картинки лежат в старой раскладке `goods/import_files`.

        Частичное разрешение картинок обрезало бы состав фото товара
        (`_import_base_images(mirror_composition=True)`), поэтому фолбэк на
        легаси-раскладку обязателен, пока прод не перешёл на новую.
        """
        settings.MEDIA_ROOT = str(tmp_path / "media")

        data_dir = _import_dir("sess-legacy")
        (data_dir / "goods").mkdir(parents=True)
        shutil.copyfile(GOODS_XML, data_dir / "goods" / "goods.xml")

        legacy_images = exchange.imports / "goods" / "import_files"
        for sub in ("01", "03", "06"):
            shutil.copytree(GOODS_SOURCE_DIR / sub, legacy_images / sub)

        session = _session("sess-legacy", ImportSession.ImportStatus.IN_PROGRESS)
        call_command(
            "import_products_from_1c",
            data_dir=str(data_dir),
            file_type="goods",
            import_session_id=session.pk,
        )

        product = Product.objects.get(onec_id=GOODS_PRODUCT_WITH_IMAGES)
        assert product.base_images, "Легаси-раскладка картинок обязана разрешаться фолбэком"


@pytest.mark.django_db
class TestConsumedImagesAreReclaimed:
    """Tech-debt п. 27 — общий `import_files` не растёт без ограничения.

    До изоляции каталог картинок вычищался `cleanup_import_dir` вместе со всем
    каталогом обмена. После изоляции его не чистит ни одна сессия, а полная
    выгрузка с картинками кладёт туда практически весь каталог исходных JPEG
    (на проде 28.08.2026 сохранённых копий 4,9 ГБ при 20 ГБ свободного диска).
    Критерий уборки строго ссылочный: копия подтверждена в хранилище.
    """

    def test_command_deletes_sources_it_stored(self, exchange, tmp_path, settings):
        """Потреблённый исходник убирается сразу прогоном, который его перенёс."""
        settings.MEDIA_ROOT = str(tmp_path / "media")

        data_dir = _import_dir("sess-consumed")
        (data_dir / "goods").mkdir(parents=True)
        shutil.copyfile(GOODS_XML, data_dir / "goods" / "goods.xml")

        shared_images = exchange.imports / "import_files"
        for sub in ("01", "03", "06"):
            shutil.copytree(GOODS_SOURCE_DIR / sub, shared_images / sub)
        before = {f for f in shared_images.rglob("*") if f.is_file()}

        session = _session("sess-consumed", ImportSession.ImportStatus.IN_PROGRESS)
        call_command(
            "import_products_from_1c",
            data_dir=str(data_dir),
            file_type="goods",
            import_session_id=session.pk,
        )

        product = Product.objects.get(onec_id=GOODS_PRODUCT_WITH_IMAGES)
        assert product.base_images, "Картинки обязаны разрешиться до всякой уборки"

        after = {f for f in shared_images.rglob("*") if f.is_file()}
        assert after < before, "Перенесённые исходники обязаны быть убраны"

        media = Path(settings.MEDIA_ROOT)
        for stored in product.base_images:
            assert (media / str(stored)).exists(), "Копия в хранилище обязана пережить уборку"

    def test_reimport_after_cleanup_keeps_composition(self, exchange, tmp_path, settings):
        """Повторный goods.xml без исходников не обрезает состав фото.

        Ровно тот сценарий, ради которого ревью запретило уборку по возрасту.
        Здесь он безопасен: `_save_image_if_not_exists` берёт подтверждённую
        копию из хранилища, и `mirror_composition=True` зеркалирует полный состав.
        """
        settings.MEDIA_ROOT = str(tmp_path / "media")

        data_dir = _import_dir("sess-twice")
        (data_dir / "goods").mkdir(parents=True)
        shared_images = exchange.imports / "import_files"
        for sub in ("01", "03", "06"):
            shutil.copytree(GOODS_SOURCE_DIR / sub, shared_images / sub)

        session = _session("sess-twice", ImportSession.ImportStatus.IN_PROGRESS)
        for run in ("first", "second"):
            shutil.copyfile(GOODS_XML, data_dir / "goods" / "goods.xml")
            call_command(
                "import_products_from_1c",
                data_dir=str(data_dir),
                file_type="goods",
                import_session_id=session.pk,
            )
            if run == "first":
                first_composition = list(Product.objects.get(onec_id=GOODS_PRODUCT_WITH_IMAGES).base_images)

        second_composition = list(Product.objects.get(onec_id=GOODS_PRODUCT_WITH_IMAGES).base_images)
        assert second_composition == first_composition, "Состав фото обязан пережить исчезновение исходников"

    def test_manual_corpus_is_never_touched(self, exchange, tmp_path, settings):
        """Ручной корпус `ONEC_DATA_DIR` уборке не подлежит — это входные данные.

        Прогон по каталогу вне обмена (`data/import_1c/`) читает те же картинки,
        но удалять их нельзя: на них работают тесты и повторные прогоны.
        """
        settings.MEDIA_ROOT = str(tmp_path / "media")

        manual = tmp_path / "manual_corpus"
        (manual / "goods").mkdir(parents=True)
        shutil.copyfile(GOODS_XML, manual / "goods" / "goods.xml")
        manual_images = manual / "goods" / "import_files"
        for sub in ("01", "03", "06"):
            shutil.copytree(GOODS_SOURCE_DIR / sub, manual_images / sub)
        before = {f for f in manual_images.rglob("*") if f.is_file()}

        session = _session("sess-manual", ImportSession.ImportStatus.IN_PROGRESS)
        call_command(
            "import_products_from_1c",
            data_dir=str(manual),
            file_type="goods",
            import_session_id=session.pk,
        )

        after = {f for f in manual_images.rglob("*") if f.is_file()}
        assert after == before, "Картинки ручного корпуса удалять нельзя"

    def test_periodic_prune_removes_only_stored_copies(self, exchange, tmp_path, settings):
        """Страховка: убирается то, что в хранилище, паркуется то, чего там нет."""
        settings.MEDIA_ROOT = str(tmp_path / "media")

        shared_images = exchange.imports / "import_files"
        shutil.copytree(GOODS_SOURCE_DIR / "01", shared_images / "01")
        stored, parked = sorted((shared_images / "01").glob("*.jpg"))[:2]

        # Копия в хранилище есть только у первого файла.
        destination = Path(settings.MEDIA_ROOT) / "products" / "base" / "01" / stored.name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(stored, destination)

        assert cleanup_stale_exchange_dirs() >= 1
        assert not stored.exists(), "Перенесённый исходник обязан уйти"
        assert parked.exists(), "Без копии в хранилище файл трогать нельзя"


@pytest.mark.django_db
class TestPromiselessRunKeepsHandsOff:
    """AC3 — `mode=complete` не сгребает каталог."""

    def test_complete_without_own_files_completes_with_note(self, exchange, clean_cache):
        """Своих файлов нет: COMPLETED с пометкой, соседи целы и не прочитаны."""
        session_a = _session("sess-empty", ImportSession.ImportStatus.PENDING)
        _session("sess-owner", ImportSession.ImportStatus.PENDING)

        neighbours = [_upload("sess-owner", _segment_path(i)) for i in (3, 4)]

        with patch.object(Command, "_backup_before_import"):
            assert _run_task(session_a, "sess-empty", "complete", "task-empty") == "success"

        session_a.refresh_from_db()
        assert session_a.status == ImportSession.ImportStatus.COMPLETED
        assert SESSION_HAS_NO_OWN_FILES in session_a.report
        assert all(path.exists() for path in neighbours), "Файлы соседей обязаны остаться на диске"

    def test_complete_with_own_files_still_imports(self, exchange, clean_cache):
        """Свои файлы есть — прогон работает как раньше."""
        session = _session("sess-own", ImportSession.ImportStatus.PENDING)
        own = _upload("sess-own", _segment_path(5))

        with patch.object(Command, "_backup_before_import"):
            assert _run_task(session, "sess-own", "complete", "task-own") == "success"

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert SESSION_HAS_NO_OWN_FILES not in session.report
        assert not own.exists(), "Свой сегмент прогон обязан прочитать"

    def test_own_files_are_imported_despite_active_neighbour(self, exchange, clean_cache):
        """Чужая активная сессия изолированный `mode=complete` больше не тормозит.

        Guard `defer_to_active_sessions` писался под ОБЩИЙ каталог, где сбор без
        обещания забирал чужие сегменты. В сессионной раскладке чужого в папке
        нет по построению, а активная соседка есть практически всегда: 1С шлёт
        `mode=import` на каждый файл и `mode=complete` следом каждые пару секунд.
        Оставить guard включённым — значит не импортировать собственный XML почти
        никогда.
        """
        session = _session("sess-own-busy", ImportSession.ImportStatus.PENDING)
        _session("sess-neighbour", ImportSession.ImportStatus.IN_PROGRESS)
        own = _upload("sess-own-busy", _segment_path(6))

        with patch.object(Command, "_backup_before_import"):
            assert _run_task(session, "sess-own-busy", "complete", "task-own-busy") == "success"

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert "Импорт каталога пропущен" not in session.report
        assert not own.exists(), "Свой сегмент прогон обязан прочитать"


@pytest.mark.django_db
class TestCleanupStaysInOwnDir:
    """AC4 — уборка ограничена каталогом своей сессии."""

    def test_cleanup_does_not_touch_neighbour(self, exchange):
        own = _upload("sess-a", _segment_path(1))
        neighbour = _upload("sess-b", _segment_path(2))

        deleted = FileRoutingService("sess-a").cleanup_import_dir()

        assert deleted >= 1
        assert not own.exists()
        assert neighbour.exists(), "Каталог соседней сессии уборке не подлежит"

    def test_force_cleanup_does_not_touch_shared_images(self, exchange):
        image = next((GOODS_SOURCE_DIR / "01").glob("*.jpg"))
        shared = _upload("sess-a", image)
        _upload("sess-a", _segment_path(1))

        FileRoutingService("sess-a").cleanup_import_dir(force=True)

        assert shared.exists(), "Общие картинки нужны XML соседних сессий"

    def test_remove_session_dirs_clears_both_roots(self, exchange):
        _upload("sess-a", _segment_path(1))
        router = FileRoutingService("sess-a")

        router.cleanup_import_dir()
        router.remove_session_dirs()

        assert not (exchange.imports / "sess-a").exists()
        assert not (exchange.temp / "sess-a").exists()

    def test_session_dir_removed_even_with_active_neighbour(self, exchange, clean_cache):
        """Свой каталог удаляется независимо от чужих `IN_PROGRESS`-сессий.

        Историческому guard-у здесь держать нечего: каталог принадлежит завершённой
        сессии целиком. Пока guard действовал и на изолированную раскладку, папки
        не удалялись почти никогда — на проде их накопилось 32 276.
        """
        session = _session("sess-done", ImportSession.ImportStatus.PENDING)
        _session("sess-neighbour", ImportSession.ImportStatus.IN_PROGRESS)
        _upload("sess-done", _segment_path(7))
        neighbour = _upload("sess-neighbour", _segment_path(8))

        assert _run_task(session, "sess-done", _segment_name(7), "task-done") == "success"

        assert not (exchange.imports / "sess-done").exists(), "Каталог завершённой сессии обязан уйти"
        assert not (exchange.temp / "sess-done").exists()
        assert neighbour.exists(), "Каталог активной соседки уборке не подлежит"


@pytest.mark.django_db
class TestStaleExchangeDirCleanup:
    """AC5 — каталоги обмена не накапливаются."""

    @staticmethod
    def _age(path: Path, hours: float) -> None:
        """Состарить каталог ЦЕЛИКОМ, вместе с содержимым.

        Возраст одного корня ничего не значит: уборка смотрит на самую свежую
        метку в дереве, потому что свежий XML внутри — признак живой сессии,
        стоящей в очереди за локом.
        """
        old = time.time() - hours * 3600
        targets = [path, *path.rglob("*")] if path.is_dir() else [path]
        for target in sorted(targets, reverse=True):
            os.utime(target, (old, old))

    def test_stale_dirs_removed_fresh_kept(self, exchange):
        _upload("sess-old", _segment_path(1))
        _upload("sess-new", _segment_path(2))
        self._age(exchange.imports / "sess-old", 25)
        self._age(exchange.temp / "sess-old", 25)

        removed = cleanup_stale_exchange_dirs()

        assert removed >= 2
        assert not (exchange.imports / "sess-old").exists()
        assert not (exchange.temp / "sess-old").exists()
        assert (exchange.imports / "sess-new").exists()

    def test_threshold_is_24_hours(self, exchange):
        """Порог зафиксирован контрактом: 23 часа — ещё свежий каталог."""
        _upload("sess-young", _segment_path(1))
        self._age(exchange.imports / "sess-young", 23)
        self._age(exchange.temp / "sess-young", 23)

        assert cleanup_stale_exchange_dirs() == 0
        assert (exchange.imports / "sess-young").exists()

    def test_fresh_file_inside_old_dir_keeps_it(self, exchange):
        """Свежий файл внутри старого каталога — это сессия, ждущая лока.

        `shutil.move` кладёт XML внутрь, не обязательно трогая mtime родителя.
        Удаление по возрасту одного корня унесло бы уже принятый файл, и сессия
        упала бы «не найден в каталоге обмена» — тем самым дефектом, ради
        которого делалась изоляция.
        """
        segment = _upload("sess-waiting", _segment_path(1))
        self._age(exchange.imports / "sess-waiting", 48)
        os.utime(segment, None)

        assert cleanup_stale_exchange_dirs() == 0
        assert segment.exists(), "Файл ждущей сессии уборке не подлежит"

    def test_active_session_dir_is_kept(self, exchange):
        """Каталог живой сессии не удаляется, каким бы старым ни был его mtime.

        Задача может стоять в очереди за локом сколько угодно долго: соседние
        сегменты идут каждые ~6,5 с, а лимит ожидания задан ретраями, а не
        порогом уборки.
        """
        _session("sess-waiting", ImportSession.ImportStatus.PENDING)
        _upload("sess-waiting", _segment_path(1))
        self._age(exchange.imports / "sess-waiting", 48)
        self._age(exchange.temp / "sess-waiting", 48)

        assert cleanup_stale_exchange_dirs() == 0
        assert (exchange.imports / "sess-waiting").exists()

    def test_shared_dirs_are_protected(self, exchange):
        """Общий каталог картинок и легаси-раскладка каталогами сессий не являются."""
        image = next((GOODS_SOURCE_DIR / "01").glob("*.jpg"))
        shared = _upload("sess-a", image)
        legacy = exchange.imports / "goods" / "import_files"
        legacy.mkdir(parents=True)
        (legacy / "keep.jpg").write_bytes(b"legacy")
        self._age(exchange.imports / "import_files", 48)
        self._age(exchange.imports / "goods", 48)

        cleanup_stale_exchange_dirs()

        assert shared.exists(), "Каталог общих картинок сносить нельзя"
        assert (legacy / "keep.jpg").exists(), "Легаси-раскладка нужна фолбэку картинок"

    def test_old_shared_images_are_never_pruned(self, exchange):
        """Картинка старше суток — законный источник для XML, который приедет завтра.

        Контракт связи «обмен изображениями ↔ будущий XML» не задаёт, и 1С её не
        передаёт. Подрезка общего каталога по возрасту прямо ломала бы AC2: у
        товара, чей goods.xml приехал позже, состав фото обрезался бы
        `mirror_composition=True` по частично разрешённому набору.
        """
        old_image = _upload("sess-a", next((GOODS_SOURCE_DIR / "01").glob("*.jpg")))
        self._age(old_image, 240)

        assert cleanup_stale_exchange_dirs() == 0
        assert old_image.exists(), "Общие картинки по возрасту не удаляются"

    def test_task_is_registered_in_beat_schedule(self):
        """Проверяется ЭФФЕКТИВНОЕ расписание, а не источник объявления.

        Расписание объявлено дважды — в `settings/base.py` и в `celery.py`, — и
        замер в контейнере 28.08.2026 показал, что побеждает `CELERY_BEAT_SCHEDULE`
        из настроек: `app.conf` ленив, присваивание в `celery.py` выполняется до
        финализации конфига. Отсюда и форма теста: он смотрит в `app.conf`, а
        значит останется верным при любой перестановке этих двух мест.
        """
        from freesport.celery import app

        entries = [e for e in app.conf.beat_schedule.values() if e["task"] == cleanup_stale_exchange_dirs.name]
        assert entries, "Задача уборки обязана попасть в app.conf.beat_schedule"


@pytest.mark.django_db
class TestLockKeepsSerialization:
    """AC6 — очередь за локом каталога обмена сохраняется.

    Non-goal спеки: «не устранять само ожидание лока». Наивная изоляция даёт
    каждой сессии собственный ключ лока и молча снимает сериализацию задач.
    """

    def test_sessions_share_one_lock_key(self, exchange):
        assert _import_lock_key(str(_import_dir("sess-a"))) == _import_lock_key(str(_import_dir("sess-b")))

    def test_manual_dir_keeps_its_own_key(self, tmp_path):
        """Ручной прогон вне каталога обмена ключуется по себе, как и раньше."""
        manual = str(tmp_path / "manual")
        assert _import_lock_key(manual) == f"onec:import:lock:{manual}"

    @patch("apps.products.tasks.call_command")
    def test_second_session_waits_for_the_lock(self, mock_call_command, exchange, clean_cache, settings):
        """Вторая сессия получает Retry с той же формулировкой, потом отрабатывает."""
        session_b = _session("sess-b", ImportSession.ImportStatus.IN_PROGRESS)
        data_dir_b = str(_import_dir("sess-b"))
        Path(data_dir_b).mkdir(parents=True, exist_ok=True)

        cache.add(_import_lock_key(str(_import_dir("sess-a"))), "task-holder", 60)

        with patch.object(process_1c_import_task, "retry", side_effect=Retry()) as mock_retry:
            process_1c_import_task.apply(
                args=(session_b.pk,),
                kwargs={"data_dir": data_dir_b, "source_filename": _segment_name(2)},
                task_id="task-wait",
            )

        mock_retry.assert_called_once()
        mock_call_command.assert_not_called()
        session_b.refresh_from_db()
        assert "Каталог обмена занят другим импортом, задача отложена" in session_b.report

        cache.clear()
        assert (
            process_1c_import_task.apply(
                args=(session_b.pk,),
                kwargs={"data_dir": data_dir_b, "source_filename": _segment_name(2)},
                task_id="task-wait-2",
            ).get()
            == "success"
        )
