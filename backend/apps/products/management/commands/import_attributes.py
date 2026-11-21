"""
Management команда для импорта атрибутов товаров из 1С

Story 14.2: Import Attributes from 1C (Reference Data) & Admin UI

Импортирует атрибуты (свойства) товаров и их значения из XML файлов:
- propertiesGoods/*.xml - свойства для товаров (goods)
- propertiesOffers/*.xml - свойства для предложений (offers/SKU)

Использование:
    python manage.py import_attributes
    python manage.py import_attributes --data-dir /path/to/1c/data
    python manage.py import_attributes --file-type=goods
    python manage.py import_attributes --file-type=offers
    python manage.py import_attributes --dry-run
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.products.services.attribute_import import AttributeImportService


class Command(BaseCommand):
    """
    Импорт атрибутов товаров из XML файлов 1С (CommerceML 3.1)

    Обрабатывает файлы propertiesGoods/*.xml и propertiesOffers/*.xml,
    создает/обновляет записи Attribute и AttributeValue с дедупликацией по onec_id.
    """

    help = "Импорт атрибутов товаров из файлов 1С (propertiesGoods, propertiesOffers)"

    def add_arguments(self, parser: Any) -> None:
        """Добавление аргументов команды"""
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help=("Путь к директории с XML файлами из 1С. " "Если не указан, используется ONEC_DATA_DIR из settings."),
        )
        parser.add_argument(
            "--file-type",
            type=str,
            choices=["goods", "offers", "all"],
            default="all",
            help=(
                "Выборочный импорт конкретного типа файлов:\n"
                "  goods - только propertiesGoods/*.xml\n"
                "  offers - только propertiesOffers/*.xml\n"
                "  all - все типы (default)"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без записи в БД (только парсинг и валидация)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод (уровень логирования DEBUG)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основная логика команды"""
        # Настройка уровня логирования
        if options["verbose"]:
            import logging

            logging.getLogger("apps.products.services.attribute_import").setLevel(logging.DEBUG)

        # Определение корневой директории с данными
        data_dir = options.get("data_dir") or getattr(settings, "ONEC_DATA_DIR", None)

        if not data_dir:
            raise CommandError(
                "Не указана директория с данными. " "Используйте --data-dir или установите ONEC_DATA_DIR в settings."
            )

        data_dir_path = Path(data_dir)
        if not data_dir_path.exists():
            raise CommandError(f"Директория не найдена: {data_dir}")

        if not data_dir_path.is_dir():
            raise CommandError(f"Путь не является директорией: {data_dir}")

        # Определение типов файлов для импорта
        file_type = options["file_type"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠️  DRY-RUN MODE: Данные не будут записаны в БД\n"))

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 70}\n" f"📦 Импорт атрибутов товаров из 1С\n" f"{'=' * 70}\n"))
        self.stdout.write(f"📁 Директория данных: {data_dir}\n")
        self.stdout.write(f"📋 Тип файлов: {file_type}\n")

        try:
            # Суммарная статистика для всех импортов
            total_stats = {
                "attributes_created": 0,
                "mappings_created": 0,
                "attributes_deduplicated": 0,
                "values_created": 0,
                "value_mappings_created": 0,
                "values_deduplicated": 0,
                "errors": 0,
            }

            # Импорт propertiesGoods
            if file_type in ["goods", "all"]:
                goods_stats = self._import_properties_goods(data_dir_path, dry_run)
                for key in total_stats:
                    total_stats[key] += goods_stats.get(key, 0)

            # Импорт propertiesOffers
            if file_type in ["offers", "all"]:
                offers_stats = self._import_properties_offers(data_dir_path, dry_run)
                for key in total_stats:
                    total_stats[key] += offers_stats.get(key, 0)

            # Вывод итоговой статистики
            self._print_stats(total_stats, dry_run)

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Ошибка импорта: {e}\n"))
            raise CommandError(f"Импорт прерван: {e}")

    def _import_properties_goods(self, data_dir: Path, dry_run: bool) -> dict[str, int]:
        """Импорт свойств товаров (propertiesGoods)"""
        properties_goods_dir = data_dir / "propertiesGoods"

        if not properties_goods_dir.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Директория не найдена: {properties_goods_dir}\n" "   Пропуск propertiesGoods\n"
                )
            )
            return {
                "attributes_created": 0,
                "mappings_created": 0,
                "attributes_deduplicated": 0,
                "values_created": 0,
                "value_mappings_created": 0,
                "values_deduplicated": 0,
                "errors": 0,
            }

        self.stdout.write(self.style.SUCCESS(f"\n{'─' * 70}\n" f"📄 Обработка propertiesGoods/*.xml\n" f"{'─' * 70}\n"))

        # Создаем отдельный сервис для goods с source="goods"
        service = AttributeImportService(source="goods", dry_run=dry_run)

        if dry_run:
            # В dry-run режиме только парсим без сохранения
            self._dry_run_import(service, str(properties_goods_dir))
        else:
            service.import_from_directory(str(properties_goods_dir))

        self.stdout.write(self.style.SUCCESS("✅ propertiesGoods обработаны\n"))
        return service.get_stats()

    def _import_properties_offers(self, data_dir: Path, dry_run: bool) -> dict[str, int]:
        """Импорт свойств предложений (propertiesOffers)"""
        properties_offers_dir = data_dir / "propertiesOffers"

        if not properties_offers_dir.exists():
            self.stdout.write(
                self.style.WARNING(
                    f"\n⚠️  Директория не найдена: {properties_offers_dir}\n" "   Пропуск propertiesOffers\n"
                )
            )
            return {
                "attributes_created": 0,
                "mappings_created": 0,
                "attributes_deduplicated": 0,
                "values_created": 0,
                "value_mappings_created": 0,
                "values_deduplicated": 0,
                "errors": 0,
            }

        self.stdout.write(self.style.SUCCESS(f"\n{'─' * 70}\n" f"📄 Обработка propertiesOffers/*.xml\n" f"{'─' * 70}\n"))

        # Создаем отдельный сервис для offers с source="offers"
        service = AttributeImportService(source="offers", dry_run=dry_run)

        if dry_run:
            # В dry-run режиме только парсим без сохранения
            self._dry_run_import(service, str(properties_offers_dir))
        else:
            service.import_from_directory(str(properties_offers_dir))

        self.stdout.write(self.style.SUCCESS("✅ propertiesOffers обработаны\n"))
        return service.get_stats()

    def _dry_run_import(self, service: AttributeImportService, directory: str) -> None:
        """Тестовый импорт без записи в БД (только парсинг)"""
        import defusedxml.ElementTree as ET

        xml_files = [f for f in os.listdir(directory) if f.endswith(".xml")]

        self.stdout.write(f"   Найдено файлов: {len(xml_files)}\n")

        for filename in xml_files:
            file_path = os.path.join(directory, filename)
            try:
                # Только парсинг без сохранения
                tree = ET.parse(file_path)
                root = tree.getroot()
                properties = service._parse_properties(root)

                self.stdout.write(f"   ✓ {filename}: {len(properties)} свойств\n")

                # Подсчет значений
                total_values = sum(len(p.get("values", [])) for p in properties)
                if total_values > 0:
                    self.stdout.write(f"     └─ Значений: {total_values}\n")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"   ✗ {filename}: {e}\n"))

    def _print_stats(self, stats: dict[str, int], dry_run: bool) -> None:
        """Вывод итоговой статистики импорта с дедупликацией"""
        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 70}\n" f"📊 Итоговая статистика импорта\n" f"{'=' * 70}\n"))

        if dry_run:
            self.stdout.write(self.style.WARNING("⚠️  DRY-RUN: Данные не были сохранены в БД\n\n"))
        else:
            self.stdout.write(
                f"✨ Атрибуты:\n"
                f"   • Создано новых: {stats['attributes_created']}\n"
                f"   • Дедуплицировано (объединено): "
                f"{stats['attributes_deduplicated']}\n"
                f"   • Создано маппингов 1С: {stats['mappings_created']}\n"
                f"\n"
                f"🎯 Значения атрибутов:\n"
                f"   • Создано новых: {stats['values_created']}\n"
                f"   • Дедуплицировано (объединено): {stats['values_deduplicated']}\n"
                f"   • Создано маппингов 1С: {stats['value_mappings_created']}\n"
                f"\n"
            )

            # Вывод эффективности дедупликации
            total_attrs = stats["attributes_created"] + stats["attributes_deduplicated"]
            total_values = stats["values_created"] + stats["values_deduplicated"]

            if total_attrs > 0:
                dedup_rate = stats["attributes_deduplicated"] / total_attrs * 100
                self.stdout.write(
                    f"📈 Эффективность дедупликации атрибутов: "
                    f"{dedup_rate:.1f}% ({stats['attributes_deduplicated']}/"
                    f"{total_attrs})\n"
                )

            if total_values > 0:
                value_dedup_rate = stats["values_deduplicated"] / total_values * 100
                self.stdout.write(
                    f"📈 Эффективность дедупликации значений: "
                    f"{value_dedup_rate:.1f}% ({stats['values_deduplicated']}/"
                    f"{total_values})\n"
                )

            self.stdout.write("\n")

            if stats["errors"] > 0:
                self.stdout.write(self.style.ERROR(f"❌ Ошибок: {stats['errors']}\n"))
            else:
                self.stdout.write(self.style.SUCCESS("✅ Ошибок нет\n"))

            # Напоминание об активации атрибутов
            if stats["attributes_created"] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        "\n⚠️  Новые атрибуты созданы с is_active=False\n"
                        "   Для отображения в каталоге активируйте их в Django Admin\n"
                    )
                )

        self.stdout.write(self.style.SUCCESS(f"{'=' * 70}\n"))
