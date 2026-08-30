"""
Синхронизация состава изображений товара с 1С (стори onec-image-composition-sync).

Проверяются четыре метода состава в VariantImportProcessor:
- _save_image_if_not_exists — уже перенесённая копия не считается потерей (AC1);
- _import_base_images — зеркалирование состава Product.base_images (AC2-AC4, AC7);
- _import_variant_images — переназначение ProductVariant.main_image (AC5, AC8);
- _get_effective_min_size — порог размера по фактически доступному файлу (AC6).

XML здесь не участвует: тестируются сами методы состава, поэтому вместо реальных
выгрузок 1С используются временные файлы-заглушки нужного размера. Размер заглушек
строго больше MIN_IMAGE_SIZE_BYTES (100 КБ) — иначе картинка отсеется порогом
и сработает защита AC3.
"""

from decimal import Decimal
from pathlib import Path

import pytest
from django.test import override_settings

from apps.products.models import Brand, Category, ImportSession, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor

# Заглушка крупнее основного порога 100 КБ
BIG_IMAGE_BYTES = b"x" * (150 * 1024)
# Заглушка меньше основного порога, но крупнее резервного (8 КБ)
SMALL_IMAGE_BYTES = b"x" * (20 * 1024)


@pytest.fixture
def brand(db):
    return Brand.objects.create(name="Composition Brand", slug="composition-brand", is_active=True)


@pytest.fixture
def category(db):
    return Category.objects.create(name="Composition Category", slug="composition-category", is_active=True)


@pytest.fixture
def import_session(db):
    return ImportSession.objects.create(import_type="full", status="in_progress")


@pytest.fixture
def product(db, brand, category):
    return Product.objects.create(
        name="Composition Product",
        slug="composition-product",
        onec_id="composition-parent-id",
        parent_onec_id="composition-parent-id",
        brand=brand,
        category=category,
        is_active=True,
        base_images=[],
    )


@pytest.fixture
def variant(db, product):
    return ProductVariant.objects.create(
        product=product,
        sku="COMPOSITION-SKU-001",
        onec_id="composition-parent-id#variant-id",
        retail_price=Decimal("1000.00"),
        is_active=True,
    )


@pytest.fixture
def processor(import_session):
    return VariantImportProcessor(session_id=import_session.id)


@pytest.fixture
def media_root(tmp_path):
    """Изолированный MEDIA_ROOT — методы состава пишут в default_storage."""
    path = tmp_path / "media"
    path.mkdir()
    return path


@pytest.fixture
def import_dir(tmp_path):
    """Каталог выгрузки 1С (аналог data/import_1c/goods/import_files)."""
    path = tmp_path / "import"
    (path / "xx").mkdir(parents=True)
    return path


def write_source(import_dir: Path, name: str, payload: bytes = BIG_IMAGE_BYTES) -> Path:
    """Кладёт файл-заглушку в каталог выгрузки."""
    source = import_dir / "xx" / name
    source.write_bytes(payload)
    return source


def write_copy(media_root: Path, prefix: str, name: str, payload: bytes = BIG_IMAGE_BYTES) -> str:
    """Кладёт уже перенесённую копию в media и возвращает её относительный путь."""
    destination = media_root / "products" / prefix / "xx" / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(payload)
    return f"products/{prefix}/xx/{name}"


@pytest.mark.django_db
class TestCopyResolvesMissingSource:
    """AC1: перенесённая копия в хранилище — не потеря файла."""

    def test_copy_in_storage_resolves_image(self, processor, media_root, import_dir):
        """Исходник подчищен 1С, копия в media есть → путь возвращён, ошибки нет."""
        copy_path = write_copy(media_root, "base", "photo1.jpg")
        missing_source = import_dir / "xx" / "photo1.jpg"

        with override_settings(MEDIA_ROOT=str(media_root)):
            result = processor._save_image_if_not_exists(
                missing_source,
                "xx/photo1.jpg",
                "base",
            )

        assert result == copy_path
        assert processor.stats["images_skipped"] == 1
        assert processor.stats["images_errors"] == 0

    def test_small_copy_does_not_pass_threshold(self, processor, media_root, import_dir):
        """Копия мельче порога в состав не возвращается (связка с AC6)."""
        write_copy(media_root, "base", "tiny.jpg", payload=SMALL_IMAGE_BYTES)
        missing_source = import_dir / "xx" / "tiny.jpg"

        with override_settings(MEDIA_ROOT=str(media_root)):
            result = processor._save_image_if_not_exists(
                missing_source,
                "xx/tiny.jpg",
                "base",
            )

        assert result is None
        assert processor.stats["images_errors"] == 0

    def test_no_source_and_no_copy_counts_error(self, processor, media_root, import_dir):
        """Регрессия: нет ни исходника, ни копии → это по-прежнему ошибка."""
        missing_source = import_dir / "xx" / "nowhere.jpg"

        with override_settings(MEDIA_ROOT=str(media_root)):
            result = processor._save_image_if_not_exists(
                missing_source,
                "xx/nowhere.jpg",
                "base",
            )

        assert result is None
        assert processor.stats["images_errors"] == 1


@pytest.mark.django_db
class TestBaseImagesMirroring:
    """AC2-AC4: Product.base_images зеркалит goods.xml."""

    def test_dropped_image_leaves_composition(self, processor, product, media_root, import_dir):
        """Снятая в 1С картинка уходит из base_images, порядок берётся из выгрузки."""
        product.base_images = [
            write_copy(media_root, "base", "dropped.jpg"),
            write_copy(media_root, "base", "keep.jpg"),
        ]
        product.save(update_fields=["base_images"])
        write_source(import_dir, "second.jpg")
        write_source(import_dir, "keep.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_base_images(
                product,
                ["xx/second.jpg", "xx/keep.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        product.refresh_from_db()
        assert product.base_images == [
            "products/base/xx/second.jpg",
            "products/base/xx/keep.jpg",
        ]

    def test_import_files_prefix_resolves_to_same_copy(self, processor, product, media_root, import_dir):
        """Сырой путь из XML нормализуется — копия находится, дубль не плодится."""
        copy_path = write_copy(media_root, "base", "photo1.jpg")
        product.base_images = [copy_path]
        product.save(update_fields=["base_images"])

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_base_images(
                product,
                ["import_files/xx/photo1.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        product.refresh_from_db()
        assert product.base_images == [copy_path]

    def test_zero_resolved_keeps_composition(self, processor, product, media_root, import_dir):
        """AC3: не разрешилась ни одна картинка → состав не трогаем."""
        existing = [write_copy(media_root, "base", "existing.jpg")]
        product.base_images = list(existing)
        product.save(update_fields=["base_images"])

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_base_images(
                product,
                ["xx/missing-1.jpg", "xx/missing-2.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        product.refresh_from_db()
        assert product.base_images == existing
        assert processor.stats["images_errors"] == 2

    def test_missing_images_key_keeps_composition(self, processor, product, media_root, import_dir):
        """AC4: у товара нет ключа images в goods_data → состав не трогается."""
        existing = [write_copy(media_root, "base", "existing.jpg")]
        product.base_images = list(existing)
        product.save(update_fields=["base_images"])

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor.process_product_from_goods(
                {"id": product.onec_id, "name": product.name},
                base_dir=str(import_dir),
            )

        product.refresh_from_db()
        assert product.base_images == existing


@pytest.mark.django_db
class TestVariantImagesMirroring:
    """AC5, AC8: ProductVariant.main_image переназначается по offers.xml."""

    def test_main_image_is_reassigned(self, processor, variant, media_root, import_dir):
        """Первая картинка выгрузки становится главной, прежняя уходит из главного."""
        variant.main_image = write_copy(media_root, "variants", "old.jpg")
        variant.save(update_fields=["main_image"])
        write_source(import_dir, "new1.jpg")
        write_source(import_dir, "new2.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_variant_images(
                variant,
                ["xx/new1.jpg", "xx/new2.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        variant.refresh_from_db()
        assert variant.main_image.name == "products/variants/xx/new1.jpg"
        assert variant.gallery_images == ["products/variants/xx/new2.jpg"]

    def test_zero_resolved_keeps_variant_composition(self, processor, variant, media_root, import_dir):
        """AC3 для варианта: пустое разрешение состав варианта не меняет."""
        old_path = write_copy(media_root, "variants", "old.jpg")
        variant.main_image = old_path
        variant.gallery_images = ["products/variants/xx/gallery.jpg"]
        variant.save(update_fields=["main_image", "gallery_images"])

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_variant_images(
                variant,
                ["xx/missing.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        variant.refresh_from_db()
        assert variant.main_image.name == old_path
        assert variant.gallery_images == ["products/variants/xx/gallery.jpg"]

    def test_filled_main_image_does_not_raise(self, processor, variant, media_root, import_dir):
        """AC8: аддитивный режим на заполненном main_image не падает TypeError."""
        old_path = write_copy(media_root, "variants", "old.jpg")
        variant.main_image = old_path
        variant.save(update_fields=["main_image"])
        write_source(import_dir, "new.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_variant_images(
                variant,
                ["xx/new.jpg"],
                str(import_dir),
            )

        variant.refresh_from_db()
        # AC7: аддитивный режим главное изображение не переназначает
        assert variant.main_image.name == old_path
        assert variant.gallery_images == ["products/variants/xx/new.jpg"]


@pytest.mark.django_db
class TestEffectiveMinSize:
    """AC6: порог размера считается и по копиям в media."""

    def test_threshold_uses_copy_when_source_is_gone(self, processor, media_root, import_dir):
        """Исходников нет, крупная копия есть → порог остаётся основным (100 КБ)."""
        write_copy(media_root, "base", "big.jpg")
        write_copy(media_root, "base", "tiny.jpg", payload=SMALL_IMAGE_BYTES)

        with override_settings(MEDIA_ROOT=str(media_root)):
            effective_min = processor._get_effective_min_size(
                ["xx/big.jpg", "xx/tiny.jpg"],
                str(import_dir),
                "base",
            )

        assert effective_min == processor.MIN_IMAGE_SIZE_BYTES

    def test_small_copy_not_returned_to_composition(self, processor, product, media_root, import_dir):
        """Мелкое превью не возвращается в состав после подчистки исходников."""
        big_copy = write_copy(media_root, "base", "big.jpg")
        write_copy(media_root, "base", "tiny.jpg", payload=SMALL_IMAGE_BYTES)

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_base_images(
                product,
                ["xx/big.jpg", "xx/tiny.jpg"],
                str(import_dir),
                mirror_composition=True,
            )

        product.refresh_from_db()
        assert product.base_images == [big_copy]


@pytest.mark.django_db
class TestScanningModeStaysAdditive:
    """AC7: режим сканирования каталога состав не режет и порядок не переставляет."""

    def test_additive_mode_appends_to_tail(self, processor, product, media_root, import_dir):
        """Прогон сканирования только дописывает в хвост существующего состава."""
        existing = [write_copy(media_root, "base", "existing.jpg")]
        product.base_images = list(existing)
        product.save(update_fields=["base_images"])
        write_source(import_dir, "scanned.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._import_base_images(
                product=product,
                image_paths=["xx/scanned.jpg"],
                base_dir=str(import_dir),
            )

        product.refresh_from_db()
        assert product.base_images == existing + ["products/base/xx/scanned.jpg"]


# Две заглушки крупнее порога, но РАЗНОГО размера: подмена содержимого под тем же
# именем различима только размером — на этом и стоит CAP-5.
REPLACED_IMAGE_BYTES = b"y" * (200 * 1024)


@pytest.mark.django_db
class TestContentReplacementReachesSite:
    """CAP-5: замена содержимого фото под тем же GUID доезжает до сайта.

    Имя копии детерминировано парой GUID товара и картинки. Пока решение
    «копировать или пропустить» принималось по одному существованию файла,
    заменённый в 1С снимок оставался на сайте старым — молча, без ошибок и без
    следов в отчёте. Дефект латентный: обычно 1С заводит новый GUID.
    """

    def test_changed_content_overwrites_stored_copy(self, processor, media_root, import_dir):
        """Другой размер под тем же именем → копия перезаписана содержимым выгрузки."""
        copy_path = write_copy(media_root, "base", "photo1.jpg")
        source = write_source(import_dir, "photo1.jpg", payload=REPLACED_IMAGE_BYTES)

        with override_settings(MEDIA_ROOT=str(media_root)):
            result = processor._save_image_if_not_exists(source, "xx/photo1.jpg", "base")

        assert result == copy_path, "Путь карточки меняться не должен — меняется содержимое"
        assert (media_root / copy_path).read_bytes() == REPLACED_IMAGE_BYTES
        assert processor.stats["images_replaced"] == 1
        assert processor.stats["images_skipped_existing"] == 0

    def test_same_size_copy_is_left_alone(self, processor, media_root, import_dir):
        """Совпал размер — копия считается актуальной, лишней записи нет.

        Побайтовое сравнение стоило бы чтения всего каталога на каждом прогоне
        (6,4 ГБ на проде 28.08.2026) ради случая, когда подменённый снимок весит
        ровно столько же.
        """
        copy_path = write_copy(media_root, "base", "photo1.jpg")
        source = write_source(import_dir, "photo1.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            result = processor._save_image_if_not_exists(source, "xx/photo1.jpg", "base")

        assert result == copy_path
        assert (media_root / copy_path).read_bytes() == BIG_IMAGE_BYTES
        assert processor.stats["images_replaced"] == 0
        assert processor.stats["images_skipped_existing"] == 1


@pytest.mark.django_db
class TestImageOutcomesAreDistinguishable:
    """Расщепление `images_skipped` (tech-debt п. 24).

    Три исхода сливались в один счётчик — на проде 11 186 в одной куче, — хотя
    смысл у них разный вплоть до противоположного: «узнано по копии» означает,
    что картинка РАЗРЕШЕНА, а не отброшена.
    """

    def test_three_outcomes_counted_separately(self, processor, media_root, import_dir):
        """Каждый исход попадает в свой счётчик, а сумма сходится со старым."""
        write_copy(media_root, "base", "existing.jpg")
        existing_source = write_source(import_dir, "existing.jpg")
        small_source = write_source(import_dir, "small.jpg", payload=SMALL_IMAGE_BYTES)
        write_copy(media_root, "base", "from_copy.jpg")
        missing_source = import_dir / "xx" / "from_copy.jpg"

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._save_image_if_not_exists(existing_source, "xx/existing.jpg", "base")
            processor._save_image_if_not_exists(small_source, "xx/small.jpg", "base")
            processor._save_image_if_not_exists(missing_source, "xx/from_copy.jpg", "base")

        assert processor.stats["images_skipped_existing"] == 1
        assert processor.stats["images_skipped_small"] == 1
        assert processor.stats["images_resolved_from_copy"] == 1
        # `images_skipped` остаётся суммой: значение читает админка и оно уже
        # лежит в report_details прошлых сессий.
        assert processor.stats["images_skipped"] == 3

    def test_report_line_names_every_outcome(self, processor, media_root, import_dir):
        """Строка отчёта перечисляет исходы поимённо, а не одной кучей."""
        assert processor.image_report_line() == "", "Прогон без картинок строку не получает"

        write_copy(media_root, "base", "existing.jpg")
        source = write_source(import_dir, "existing.jpg")
        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._save_image_if_not_exists(source, "xx/existing.jpg", "base")

        line = processor.image_report_line()
        for label in ("скопировано", "заменено", "уже в хранилище", "отсеяно по размеру", "узнано по копии", "ошибок"):
            assert label in line, f"В строке отчёта нет исхода «{label}»"
        assert "уже в хранилище 1" in line

    def test_session_report_carries_image_line(self, processor, import_session, media_root, import_dir):
        """Числа видны в ТЕКСТОВОМ отчёте сессии, а не только в JSONB report_details."""
        write_copy(media_root, "base", "existing.jpg")
        source = write_source(import_dir, "existing.jpg")

        with override_settings(MEDIA_ROOT=str(media_root)):
            processor._save_image_if_not_exists(source, "xx/existing.jpg", "base")
            processor.finalize_session(status=ImportSession.ImportStatus.COMPLETED)

        import_session.refresh_from_db()
        assert "Изображения:" in import_session.report
        assert "уже в хранилище 1" in import_session.report

    def test_run_without_images_keeps_report_clean(self, processor, import_session):
        """Сегменты остатков и цен шумную строку про картинки не получают."""
        processor.finalize_session(status=ImportSession.ImportStatus.COMPLETED)

        import_session.refresh_from_db()
        assert "Изображения:" not in import_session.report
