"""
Интеграционные тесты для команды load_product_stocks

Story 3.1.5: Команда для обновления остатков товаров
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.products.models import ImportSession, ProductVariant

if TYPE_CHECKING:
    from _pytest.tmpdir import TempPathFactory


@pytest.mark.django_db
@pytest.mark.integration
class TestImportStocksIntegration:
    """Интеграционные тесты для импорта остатков"""

    @pytest.fixture
    def test_rests_xml(self, tmp_path: Path) -> str:
        """Создание тестового rests.xml"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Ид>product-1-uuid#sku-1-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>150</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
    <Предложение>
      <Ид>product-2-uuid#sku-2-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>75</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests.xml"
        xml_file.write_text(xml_content, encoding="utf-8")
        return str(xml_file)

    @pytest.fixture
    def test_products(self) -> list[ProductVariant]:
        """Создание тестовых вариантов товаров"""
        from apps.products.factories import ProductVariantFactory

        variants = [
            ProductVariantFactory.create(
                product__name="Product 1",
                onec_id="product-1-uuid#sku-1-uuid",
                stock_quantity=0,
            ),
            ProductVariantFactory.create(
                product__name="Product 2",
                onec_id="product-2-uuid#sku-2-uuid",
                stock_quantity=0,
            ),
        ]
        return variants

    def test_full_import_cycle(self, test_rests_xml: str, test_products: list[ProductVariant]) -> None:
        """Тест полного цикла импорта остатков"""
        # Запускаем команду
        call_command("load_product_stocks", file=test_rests_xml)

        # Проверяем обновление вариантов
        test_products[0].refresh_from_db()
        test_products[1].refresh_from_db()

        assert test_products[0].stock_quantity == 150
        assert test_products[1].stock_quantity == 75
        assert test_products[0].last_sync_at is not None
        assert test_products[1].last_sync_at is not None

        # Проверяем сессию импорта
        session = ImportSession.objects.latest("started_at")
        assert session.import_type == ImportSession.ImportType.STOCKS
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.report_details["total_records"] == 2
        assert session.report_details["updated_count"] == 2
        assert session.report_details["not_found_count"] == 0
        assert session.finished_at is not None

    def test_transaction_rollback_on_error(self, test_rests_xml: str, test_products: list[ProductVariant]) -> None:
        """Тест отката транзакции при ошибке"""
        initial_quantity = test_products[0].stock_quantity

        # Мокируем ошибку в процессе обновления
        with patch(
            "apps.products.management.commands.load_product_stocks." "ProductVariant.objects.bulk_update",
            side_effect=Exception("Database error"),
        ):
            with pytest.raises(Exception, match="Database error"):
                call_command("load_product_stocks", file=test_rests_xml)

        # Проверяем что данные не изменились
        test_products[0].refresh_from_db()
        assert test_products[0].stock_quantity == initial_quantity

        # Проверяем что сессия отмечена как failed
        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.FAILED

    def test_mixed_scenario_with_missing_products(self, tmp_path: Path, test_products: list[ProductVariant]) -> None:
        """Тест со смешанным сценарием: существующие и отсутствующие товары"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Ид>product-1-uuid#sku-1-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>100</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
    <Предложение>
      <Ид>nonexistent-product-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>50</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests_mixed.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        call_command("load_product_stocks", file=str(xml_file))

        # Проверяем что существующий вариант обновлен
        test_products[0].refresh_from_db()
        assert test_products[0].stock_quantity == 100

        # Проверяем статистику сессии
        session = ImportSession.objects.latest("started_at")
        assert session.report_details["updated_count"] == 1
        assert session.report_details["not_found_count"] == 1
        assert "nonexistent-product-uuid" in session.report_details["not_found_skus"]

    def test_invalid_data_handling(self, tmp_path: Path) -> None:
        """Тест обработки некорректных данных"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>100</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
    <Предложение>
      <Ид>test-product-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>
            <Ид>warehouse-1-uuid</Ид>
          </Склад>
          <Количество>-50</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests_invalid.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        call_command("load_product_stocks", file=str(xml_file))

        session = ImportSession.objects.latest("started_at")
        # Первая запись без ID пропускается парсером (не попадает в данные)
        # Вторая запись с отрицательным количеством пропускается командой
        assert session.report_details["skipped_count"] == 1

    def test_batch_processing_integration(self, tmp_path: Path) -> None:
        """Тест batch processing с реальными данными"""
        from apps.products.factories import ProductVariantFactory

        # Создаем 50 вариантов для теста
        variants = ProductVariantFactory.create_batch(50, stock_quantity=0)

        # Создаем XML с данными для всех товаров
        offers = "\n".join(
            [
                f"""
        <Предложение>
          <Ид>{product.onec_id}</Ид>
          <Остатки>
            <Остаток>
              <Склад>
                <Ид>warehouse-1</Ид>
              </Склад>
              <Количество>{i * 10}</Количество>
            </Остаток>
          </Остатки>
        </Предложение>"""
                for i, product in enumerate(variants, 1)
            ]
        )

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    {offers}
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests_batch.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        # Запускаем с batch_size=20
        call_command("load_product_stocks", file=str(xml_file), batch_size=20)

        # Проверяем что все товары обновлены
        session = ImportSession.objects.latest("started_at")
        assert session.report_details["updated_count"] == 50
        assert session.report_details["batch_size"] == 20

        # Проверяем несколько вариантов
        variants[0].refresh_from_db()
        variants[49].refresh_from_db()
        assert variants[0].stock_quantity == 10
        assert variants[49].stock_quantity == 500

    def test_dry_run_integration(self, test_rests_xml: str, test_products: list[ProductVariant]) -> None:
        """Интеграционный тест режима dry-run"""
        initial_quantities = [p.stock_quantity for p in test_products]

        # Запускаем в dry-run режиме
        call_command("load_product_stocks", file=test_rests_xml, dry_run=True)

        # Проверяем что данные НЕ изменились
        for i, product in enumerate(test_products):
            product.refresh_from_db()
            assert product.stock_quantity == initial_quantities[i]

        # Проверяем что сессия записана с флагом dry_run
        session = ImportSession.objects.latest("started_at")
        assert session.report_details["dry_run"] is True
        assert session.report_details["updated_count"] == 2  # Посчитаны, но не сохранены

    def test_concurrent_updates_handling(self, test_rests_xml: str, test_products: list[ProductVariant]) -> None:
        """Тест обработки параллельных обновлений"""
        # Запускаем команду дважды подряд
        call_command("load_product_stocks", file=test_rests_xml)
        call_command("load_product_stocks", file=test_rests_xml)

        # Проверяем что создано 2 сессии
        sessions = ImportSession.objects.filter(import_type=ImportSession.ImportType.STOCKS).order_by("-started_at")

        assert sessions.count() == 2
        assert all(s.status == ImportSession.ImportStatus.COMPLETED for s in sessions)

        # Проверяем что данные корректны
        test_products[0].refresh_from_db()
        assert test_products[0].stock_quantity == 150

    def test_empty_file_integration(self, tmp_path: Path) -> None:
        """Тест пустого файла"""
        xml_content = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests_empty.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        call_command("load_product_stocks", file=str(xml_file))

        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.report_details["total_records"] == 0
        assert "warning" in session.report_details

    def test_large_not_found_list_truncation(self, tmp_path: Path) -> None:
        """Тест усечения большого списка not_found_skus"""
        # Создаем XML со 150 несуществующими товарами
        offers = "\n".join(
            [
                f"""
        <Предложение>
          <Ид>nonexistent-{i}</Ид>
          <Остатки>
            <Остаток>
              <Склад>
                <Ид>warehouse-1</Ид>
              </Склад>
              <Количество>10</Количество>
            </Остаток>
          </Остатки>
        </Предложение>"""
                for i in range(150)
            ]
        )

        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    {offers}
  </Предложения>
</ПакетПредложений>"""

        xml_file = tmp_path / "rests_large.xml"
        xml_file.write_text(xml_content, encoding="utf-8")

        call_command("load_product_stocks", file=str(xml_file))

        session = ImportSession.objects.latest("started_at")
        assert session.report_details["not_found_count"] == 150
        # Проверяем усечение до 100 элементов
        assert len(session.report_details["not_found_skus"]) == 100
