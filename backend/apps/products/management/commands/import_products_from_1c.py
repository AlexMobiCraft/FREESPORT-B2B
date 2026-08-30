"""
Management команда для импорта каталога товаров из 1С с поддержкой ProductVariant

Story 13.2: Рефакторинг импорта из 1С для ProductVariant

Новый workflow импорта:
1. goods.xml → Product (базовая информация, base_images)
2. offers.xml → ProductVariant (SKU, характеристики)
3. Default variants → ProductVariant для товаров без вариантов
4. prices.xml → ProductVariant (цены)
5. rests.xml → ProductVariant (остатки)

Strategy: Batch-Level Atomicity
-------------------------------
Due to the potentially large size of XML files (hundreds of megabytes) and memory constraints,
we explicitly avoid wrapping the entire import process in a single atomic transaction.
Instead, we use batch-level processing where each batch (default 500 items) is processed
within its own transaction (via VariantImportProcessor).

Trade-offs:
- Pros: Significantly lower memory usage, resilient to timeouts, partial progress is saved.
- Cons: Failure mid-import requires a re-run or manual cleanup (ImportSession tracks state).
- Recovery: ImportSession.report logs progress, allowing analysis of where failure occurred.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from tqdm import tqdm

from apps.products.models import Brand, Category, ImportSession, Product, ProductVariant
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor

logger = logging.getLogger("import_tasks")


class Command(BaseCommand):
    """
    Импорт каталога товаров из XML файлов 1С (CommerceML 3.1) с поддержкой
    ProductVariant

    Использование:
        python manage.py import_products_from_1c --data-dir /path/to/1c/data
        python manage.py import_products_from_1c --data-dir /path --dry-run
        python manage.py import_products_from_1c --data-dir /path --batch-size=500
        python manage.py import_products_from_1c --data-dir /path --file-type=goods
        python manage.py import_products_from_1c --data-dir /path --clear-existing
        python manage.py import_products_from_1c --data-dir /path --variants-only
    """

    help = "Импорт каталога товаров из файлов 1С (CommerceML 3.1) " "с поддержкой ProductVariant"

    # Отметка «бэкап в этом окне уже делался». Ключ общий для всех прогонов:
    # защищаемся мы от лавины бэкапов внутри одной выгрузки 1С.
    BACKUP_MARKER_KEY = "onec:import:backup:last"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Пути, которые этот прогон действительно распарсил. Основа точечного
        # cleanup: каталог обмена общий для всех сессий, и удалять по маске
        # нельзя — снесём файлы соседних задач.
        self._processed_files: list[str] = []
        # Файлы, исчезнувшие из каталога между сбором списка и парсингом.
        self._missing_files: list[str] = []
        # Отпечаток файла на момент парсинга — см. `_file_signature`.
        # Значение None означает «снять отпечаток не удалось»: такой файл
        # cleanup не трогает, иначе удалял бы вслепую (см. `_cleanup_files`).
        self._file_signatures: dict[str, tuple[int, int, int, int] | None] = {}
        # Имена файлов (в нижнем регистре), которые 1С обещала этому прогону.
        # None означает «конкретных файлов не обещали»: ручной общий импорт
        # или mode=complete. Обычно это один сегмент (`rests_1_12_….xml`), но
        # задача архива обещает весь XML, который сама из него распаковала.
        self._expected_filenames: set[str] | None = None
        # Текст о неудавшемся бэкапе — переносится в отчёт сессии, когда она
        # появится: шаг бэкапа выполняется до её создания.
        self._backup_note: str | None = None

    @staticmethod
    def _file_signature(file_path: str) -> tuple[int, int, int, int] | None:
        """Отпечаток файла: устройство, inode, mtime и размер.

        Каталог обмена общий, и путь сам по себе не доказывает, что на диске
        лежит тот же файл: сосед мог снести наш и положить свой под тем же
        именем (1С переиспользует имена, когда не сегментирует выгрузку).
        """
        try:
            st = os.stat(file_path)
        except OSError:
            return None
        return (st.st_dev, st.st_ino, st.st_mtime_ns, st.st_size)

    def _parse_or_skip(self, file_path: str, parse: Callable[[str], Any]) -> Any | None:
        """Распарсить файл, пережив его исчезновение из общего каталога обмена.

        Сосед может удалить файл между `_collect_xml_files` и парсингом.
        Пропавший файл — предупреждение и пропуск, а не падение всего импорта.
        """
        signature = self._file_signature(file_path)
        try:
            data = parse(file_path)
        except FileNotFoundError as exc:
            self._missing_files.append(file_path)
            self.stdout.write(
                self.style.WARNING(f"   ⚠️ Файл исчез до парсинга, пропуск: {Path(file_path).name} ({exc})")
            )
            return None

        self._processed_files.append(file_path)
        # Отпечаток пишется всегда, включая None: «отпечатка нет» — это факт,
        # который cleanup обязан увидеть, а не отсутствие записи в словаре.
        self._file_signatures[file_path] = signature
        return data

    def _restrict_to_expected(self, collected: list[str]) -> list[str]:
        """Оставить из собранного только файлы, обещанные этому прогону.

        Каталог обмена общий, и один присланный файл обязан обрабатывать ровно
        одна задача — та, которой его обещали. Лок сериализовал задачи, но не
        убрал следствие гонки: пока одна держит лок, 1С успевает положить в
        каталог следующие файлы, а сбор по маске (`rests_*.xml`) забирал весь
        накопившийся backlog. Прогон читал и удалял чужое, их собственные задачи
        затем падали `FAILED` («сегмент не найден») — данные доезжали, но
        выгрузка отчитывалась провалом.

        Сужение действует на **все** шаги прогона, а не только на шаг своего
        типа: сегмент `offers_….xml` запускает ещё и шаги цен и остатков
        (`file_type in ["all", "prices", "offers"]`), и без сужения съедал бы
        уже ожидающие `prices_*`/`rests_*`. Справочники (`groups.xml`,
        `propertiesGoods.xml`, `priceLists.xml`) приходят своими файлами и
        обрабатываются своими сессиями.

        Ручной общий импорт и `mode=complete` конкретных файлов не обещают
        (`_expected_filenames is None`) — там список не сужается вовсе.

        Raises:
            CommandError: если одному обещанному имени соответствует несколько
                физических файлов. `_collect_xml_files` ищет регистронезависимо
                (`rests_*.xml`, `Rests_*.xml`), и на регистрозависимой ФС в
                каталоге могут лежать оба. Какой из них прислала 1С — неизвестно,
                а взять оба значит съесть и удалить файл соседней сессии.
        """
        expected = self._expected_filenames
        if expected is None or not collected:
            return collected

        own: list[str] = []
        skipped: list[str] = []
        by_name: dict[str, list[str]] = {}
        for path in collected:
            name = Path(path).name.lower()
            if name in expected:
                own.append(path)
                by_name.setdefault(name, []).append(path)
            else:
                skipped.append(path)

        duplicated = {name: paths for name, paths in by_name.items() if len(paths) > 1}
        if duplicated:
            details = "; ".join(
                f"{name} → {', '.join(sorted(Path(p).name for p in paths))}"
                for name, paths in sorted(duplicated.items())
            )
            raise CommandError(
                "В каталоге обмена нескольким физическим файлам соответствует одно обещанное имя "
                f"(различаются только регистром): {details}. Какой из них прислала 1С — неизвестно, "
                "а обработать оба значит удалить файл соседней сессии, поэтому импорт остановлен."
            )

        if skipped:
            names = ", ".join(sorted(Path(path).name for path in skipped))
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠️ Пропущены файлы соседних сессий ({len(skipped)}): {names} — "
                    f"их обработают собственные задачи"
                )
            )
        return own

    def add_arguments(self, parser):
        """Добавление аргументов команды"""
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help=("Путь к директории с XML файлами из 1С. " "Если не указан, используется ONEC_DATA_DIR из settings."),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без записи в БД",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Размер пакета для bulk операций (default: 500, NFR4)",
        )
        parser.add_argument(
            "--skip-validation",
            action="store_true",
            help="Пропустить валидацию данных для ускорения импорта",
        )
        parser.add_argument(
            "--file-type",
            type=str,
            choices=["goods", "offers", "prices", "rests", "all"],
            default="all",
            help="Выборочный импорт конкретного типа файлов (default: all)",
        )
        parser.add_argument(
            "--clear-existing",
            action="store_true",
            help=("Очистить существующие данные перед импортом " "(ВНИМАНИЕ: удалит все товары и варианты)"),
        )
        parser.add_argument(
            "--skip-backup",
            action="store_true",
            help="Пропустить создание backup перед импортом",
        )
        parser.add_argument(
            "--skip-images",
            action="store_true",
            help="Пропустить импорт изображений товаров (только метаданные)",
        )
        parser.add_argument(
            "--skip-default-variants",
            action="store_true",
            help="Пропустить создание default variants для товаров без вариантов",
        )
        parser.add_argument(
            "--variants-only",
            action="store_true",
            help=(
                "Импортировать только варианты (offers.xml, prices.xml, rests.xml) "
                "без пересоздания базовых товаров (goods.xml). "
                "Требует предварительно импортированного каталога товаров."
            ),
        )
        parser.add_argument(
            "--celery-task-id",
            type=str,
            default=None,
            help=(
                "ID Celery задачи для связи с существующей сессией импорта. "
                "Если указан, команда использует существующую сессию вместо "
                "создания новой."
            ),
        )
        parser.add_argument(
            "--keep-files",
            action="store_true",
            help="Не удалять файлы после успешного импорта (для отладки)",
        )
        parser.add_argument(
            "--import-session-id",
            type=int,
            default=None,
            help="ID существующей сессии ImportSession для консолидации логов.",
        )
        parser.add_argument(
            "--source-filename",
            type=str,
            action="append",
            default=None,
            help=(
                "Имя файла, который 1С прислала этому прогону (`rests_1_12_….xml`). "
                "Можно указать несколько раз: задача архива обещает весь XML, "
                "который сама из него распаковала. Если обещанный файл не будет "
                "обработан — импорт завершится ошибкой, а не тихим успехом с нулём "
                "записей. Не указывать для ручного общего импорта."
            ),
        )

    def _backup_before_import(self) -> None:
        """Бэкап БД перед полным импортом каталога.

        Три вещи, которых здесь раньше не было.

        **Путь.** Умолчание было относительным (`backend/backup_db`), а команда
        исполняется с рабочим каталогом `/app` — получался `/app/backend/backup_db`,
        каталог uid 999 при процессе под 1000:1000. `Permission denied` на каждом
        полном импорте, ошибка глоталась в WARNING, прод жил без бэкапов.

        **Частота.** Бэкап нельзя дёргать на каждом прогоне с `file_type="all"`:
        на прод-выгрузке 27.08.2026 из 172 сессий 37 пришли с этим типом
        (`mode=complete`, забирающий остатки каталога). Тридцать семь полных
        `pg_dump` базы подряд во время обмена — это нагрузка, а не защита.
        Отметка в кэше (Redis) пропускает повторы внутри
        `BACKUP_MIN_INTERVAL_SECONDS`; ставится она на **попытку**, а не на успех,
        иначе сломанный бэкап писал бы ошибку по десятку раз за выгрузку.

        **Громкость.** Провал больше не тонет в WARNING: он идёт в лог как ERROR
        и попадает в отчёт сессии (`self._backup_note`), видимый в админке.
        Импорт при этом продолжается осознанно: 1С сегмент не повторит, и
        остановка обмена из-за неудавшегося бэкапа стоила бы дороже, чем импорт
        без него. Совсем выключить шаг можно настройкой `BACKUP_BEFORE_IMPORT`.
        """
        from django.conf import settings
        from django.core.cache import cache
        from django.utils import timezone

        if not getattr(settings, "BACKUP_BEFORE_IMPORT", True):
            self.stdout.write(self.style.WARNING("\n💾 Бэкап перед импортом отключён настройкой BACKUP_BEFORE_IMPORT"))
            return

        interval = getattr(settings, "BACKUP_MIN_INTERVAL_SECONDS", 3600)
        try:
            first_in_window = cache.add(self.BACKUP_MARKER_KEY, timezone.now().isoformat(), interval)
        except Exception as exc:  # pragma: no cover - кэш недоступен, бэкап важнее отметки
            logger.warning(f"Не удалось проверить отметку бэкапа: {exc}")
            first_in_window = True

        if not first_in_window:
            self.stdout.write(f"\n💾 Бэкап пропущен: уже делался в последние {interval} с")
            return

        self.stdout.write(self.style.WARNING("\n💾 Создание backup перед импортом..."))
        try:
            call_command("backup_db")
            self.stdout.write(self.style.SUCCESS("✅ Backup создан успешно"))
        except Exception as exc:
            note = f"Бэкап перед импортом НЕ создан: {exc}. Импорт продолжен без него — " "откатить его будет нечем."
            logger.error(note)
            self._backup_note = note
            self.stdout.write(self.style.ERROR(f"❌ {note}"))

    def handle(self, *args, **options):
        """Основная логика команды"""
        from django.conf import settings

        data_dir = options["data_dir"]
        if not data_dir:
            data_dir = settings.ONEC_DATA_DIR

        # Команда может переиспользоваться в одном процессе (тесты, call_command
        # подряд) — состояние прогона обязано начинаться пустым.
        self._processed_files = []
        self._missing_files = []
        self._file_signatures = {}
        self._expected_filenames = None
        self._backup_note = None

        # Конкретные файлы от 1С обещаны только при вызове из задачи обмена.
        # Ручной прогон и mode=complete имён не передают — там пустой каталог
        # по-прежнему штатная ситуация.
        #
        # call_command передаёт значение как есть, минуя action="append":
        # строка от одиночного сегмента и список от задачи архива одинаково
        # допустимы, поэтому нормализуем оба вида на входе.
        source_filenames = options.get("source_filename") or []
        if isinstance(source_filenames, str):
            source_filenames = [source_filenames]
        expected_filenames = {os.path.basename(name).lower() for name in source_filenames if name}
        self._expected_filenames = expected_filenames or None

        dry_run = options.get("dry_run", False)
        batch_size = options.get("batch_size", 500)
        skip_validation = options.get("skip_validation", False)
        file_type = options.get("file_type", "all")
        clear_existing = options.get("clear_existing", False)
        skip_backup = options.get("skip_backup", False)
        skip_images = options.get("skip_images", False)
        skip_default_variants = options.get("skip_default_variants", False)
        variants_only = options.get("variants_only", False)
        celery_task_id = options.get("celery_task_id", None)
        import_session_id = options.get("import_session_id", None)

        # --variants-only переопределяет file_type
        if variants_only:
            file_type = "offers"  # Импортировать только offers + prices + rests

        # Валидация директории
        if not os.path.exists(data_dir):
            raise CommandError(f"Директория не найдена: {data_dir}")

        if not os.path.isdir(data_dir):
            raise CommandError(f"Путь не является директорией: {data_dir}")

        # Валидация структуры директории
        if file_type == "all":
            required_subdirs = ["goods", "offers", "prices", "rests", "priceLists"]
            for subdir in required_subdirs:
                subdir_path = os.path.join(data_dir, subdir)
                if not os.path.exists(subdir_path):
                    raise CommandError(f"Отсутствует обязательная поддиректория: {subdir}")
        elif file_type == "offers" or variants_only:
            # Для --variants-only нужны только offers, prices, rests
            required_subdirs = ["offers", "prices", "rests"]
            for subdir in required_subdirs:
                subdir_path = os.path.join(data_dir, subdir)
                if not os.path.exists(subdir_path):
                    raise CommandError(f"Отсутствует обязательная поддиректория для " f"импорта вариантов: {subdir}")

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 DRY RUN MODE: Изменения не будут сохранены в БД"))
            return self._dry_run_import(data_dir)

        # Автоматический backup перед полным импортом
        if not dry_run and file_type == "all" and not skip_backup:
            self._backup_before_import()

        # Очистка существующих данных
        if clear_existing:
            self._clear_existing_data()

        # Вывод параметров импорта
        self.stdout.write("\n" + "=" * 60)
        if variants_only:
            self.stdout.write("📊 ПАРАМЕТРЫ ИМПОРТА (Только варианты):")
        else:
            self.stdout.write("📊 ПАРАМЕТРЫ ИМПОРТА (ProductVariant mode):")
        self.stdout.write(f"   Директория: {data_dir}")
        self.stdout.write(f"   Тип файлов: {file_type}")
        self.stdout.write(f"   Variants only: {variants_only}")
        self.stdout.write(f"   Batch size: {batch_size}")
        self.stdout.write(f"   Skip validation: {skip_validation}")
        self.stdout.write(f"   Skip backup: {skip_backup}")
        self.stdout.write(f"   Skip images: {skip_images}")
        self.stdout.write(f"   Skip default variants: {skip_default_variants}")
        if import_session_id:
            self.stdout.write(f"   Import session ID: {import_session_id}")
        self.stdout.write("=" * 60)

        # Создание или получение существующей сессии импорта
        session_type = ImportSession.ImportType.VARIANTS if variants_only else ImportSession.ImportType.CATALOG

        session = None

        # 1. Сначала пробуем по import_session_id (приоритет для консолидации)
        if import_session_id:
            try:
                session = ImportSession.objects.get(pk=import_session_id)
                session.status = ImportSession.ImportStatus.IN_PROGRESS
                if celery_task_id:
                    session.celery_task_id = celery_task_id
                session.save(update_fields=["status", "celery_task_id", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"\n✅ Используется существующая сессия импорта ID: {session.pk}"))
            except ImportSession.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"\n⚠️ Сессия с id={import_session_id} не найдена."))

        # 2. Если не нашли, пробуем по celery_task_id
        if session is None and celery_task_id:
            try:
                session = ImportSession.objects.get(celery_task_id=celery_task_id)
                session.status = ImportSession.ImportStatus.IN_PROGRESS
                session.save(update_fields=["status", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"\n✅ Найдена сессия по Celery Task ID: {session.pk}"))
            except ImportSession.DoesNotExist:
                pass

        # 3. Если всё еще нет - создаем новую
        if session is None:
            session = ImportSession.objects.create(
                import_type=session_type,
                status=ImportSession.ImportStatus.IN_PROGRESS,
                celery_task_id=celery_task_id,
            )
            self.stdout.write(self.style.SUCCESS(f"\n✅ Создана НОВАЯ сессия импорта ID: {session.pk}"))

        session_id = session.pk

        try:
            # Инициализация парсера и процессора
            parser = XMLDataParser()

            # VariantImportProcessor для Product + ProductVariant
            # + Categories + Brands + PriceTypes
            # (методы process_categories, process_brands, process_price_types
            # мигрированы в Story 27.1)
            variant_processor = VariantImportProcessor(
                session_id=session_id,
                batch_size=batch_size,
                skip_validation=skip_validation,
            )

            # Провал бэкапа обязан быть виден там же, где смотрят результат
            # импорта, а не только в логах воркера. Сам шаг выполняется до
            # создания сессии, поэтому текст едет сюда через `_backup_note`.
            if self._backup_note:
                variant_processor.log_progress(self._backup_note)

            # ШАГ 0.5: Загрузка категорий из groups.xml
            if file_type in ["all", "goods"]:
                variant_processor.log_progress("Начало импорта категорий...")
                self._import_categories(data_dir, parser, variant_processor)

            # ШАГ 0.6: Загрузка брендов из propertiesGoods.xml
            if file_type in ["all", "goods"]:
                variant_processor.log_progress("Начало импорта брендов...")
                self._import_brands(data_dir, parser, variant_processor)

            # ШАГ 1: Загрузка типов цен из priceLists*.xml
            if file_type in ["all", "prices"]:
                variant_processor.log_progress("Начало импорта типов цен...")
                self._import_price_types(data_dir, parser, variant_processor)

            # ШАГ 2: Парсинг goods.xml → Product (базовая информация)
            if file_type in ["all", "goods"]:
                variant_processor.log_progress("Начало импорта товаров (goods.xml)...")
                self._import_products_from_goods(data_dir, parser, variant_processor, skip_images)

            # ШАГ 3: Парсинг offers.xml → ProductVariant
            if file_type in ["all", "offers"]:
                variant_processor.log_progress("Начало импорта вариантов (offers.xml)...")
                self._import_variants_from_offers(data_dir, parser, variant_processor, skip_images)

            # ШАГ 3.5: Создание default variants для товаров без вариантов
            if file_type in ["all", "offers"] and not skip_default_variants:
                variant_processor.log_progress("Создание дефолтных вариантов...")
                self._create_default_variants(variant_processor)

            # ШАГ 4: Парсинг prices.xml → ProductVariant (цены)
            if file_type in ["all", "prices", "offers"]:
                variant_processor.log_progress("Обновление цен из prices.xml...")
                self._import_variant_prices(data_dir, parser, variant_processor)

            # ШАГ 5: Парсинг rests.xml → ProductVariant (остатки)
            if file_type in ["all", "rests", "offers"]:
                variant_processor.log_progress("Обновление остатков из rests.xml...")
                self._import_variant_stocks(data_dir, parser, variant_processor)

            # Статус по факту, а не по факту дохода до конца метода.
            # Раньше сессия, чей файл увёл сосед, отчитывалась COMPLETED
            # с нулём записей — успех в отчёте, дырка в данных.
            if self._missing_files:
                missing_names = ", ".join(Path(p).name for p in self._missing_files)
                variant_processor.log_progress(
                    f"Файлы исчезли из каталога обмена до парсинга ({len(self._missing_files)}): {missing_names}"
                )
                if not self._processed_files:
                    raise CommandError(f"Все файлы импорта исчезли из каталога обмена до парсинга: {missing_names}")

            # Обещанный сегмент обязан быть прочитан. Именно здесь на проде
            # 25.08.2026 рождалась тихая потеря: файл увёл сосед, команда
            # написала «Файлы rests.xml не найдены» и отчиталась COMPLETED
            # с нулём записей (сессии 62672, 62674). 1С такой сегмент не
            # повторит, поэтому единственный честный статус — FAILED.
            self._assert_expected_file_processed(variant_processor)

            # Финализация сессии
            variant_processor.finalize_session(status=ImportSession.ImportStatus.COMPLETED)

            # Очистка файлов после успешного импорта
            if not dry_run and not options.get("keep_files", False):
                self._cleanup_files(self._processed_files, variant_processor)

            # Вывод статистики
            self._print_stats(variant_processor.get_stats())

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ ОШИБКА ИМПОРТА: {e}"))
            session.status = ImportSession.ImportStatus.FAILED
            session.error_message = str(e)
            # ТОЛЬКО эти поля. Объект `session` загружен в начале прогона, а
            # `VariantImportProcessor.log_progress` всё это время дописывал
            # `report` прямо в БД через F-выражение — в памяти он остался
            # пустым. Полный `save()` записывал строку целиком и стирал весь
            # прогресс упавшей сессии: именно поэтому у пяти failed-сессий
            # инцидента 25.08.2026 в отчёте не видно, что они успели сделать.
            session.save(update_fields=["status", "error_message", "updated_at"])
            raise CommandError(f"Импорт завершился с ошибкой: {e}")

    def _import_categories(self, data_dir: str, parser: XMLDataParser, processor: VariantImportProcessor) -> None:
        """Импорт категорий из groups.xml"""
        self.stdout.write("\n📁 Шаг 0.5: Загрузка категорий...")
        groups_files = self._collect_xml_files(data_dir, "groups", "groups.xml")

        if groups_files:
            total_categories = 0
            for file_path in groups_files:
                categories_data = self._parse_or_skip(file_path, parser.parse_groups_xml)
                if categories_data is None:
                    continue
                result = processor.process_categories(categories_data)
                total_categories += result["created"] + result["updated"]
                self.stdout.write(f"   • {Path(file_path).name}: категорий {len(categories_data)}")

                if result["cycles_detected"] > 0:
                    self.stdout.write(
                        self.style.WARNING(f"   ⚠️ Обнаружено циклических ссылок: " f"{result['cycles_detected']}")
                    )

            self.stdout.write(self.style.SUCCESS(f"   ✅ Загружено категорий (всего): {total_categories}"))
        else:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы groups.xml не найдены"))

    def _import_brands(self, data_dir: str, parser: XMLDataParser, processor: VariantImportProcessor) -> None:
        """Импорт брендов из propertiesGoods.xml"""
        self.stdout.write("\n🏷️  Шаг 0.6: Загрузка брендов...")
        properties_files = self._collect_xml_files(data_dir, "propertiesGoods", "propertiesGoods.xml")

        if properties_files:
            total_brands = 0
            total_mappings = 0
            for file_path in properties_files:
                brands_data = self._parse_or_skip(file_path, parser.parse_properties_goods_xml)
                if brands_data is None:
                    continue
                result = processor.process_brands(brands_data)
                total_brands += result["brands_created"]
                total_mappings += result["mappings_created"]
                self.stdout.write(f"   • {Path(file_path).name}: брендов {len(brands_data)}")

            self.stdout.write(self.style.SUCCESS(f"   ✅ Создано брендов: {total_brands}, маппингов: {total_mappings}"))
        else:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы propertiesGoods*.xml не найдены"))

    def _import_price_types(self, data_dir: str, parser: XMLDataParser, processor: VariantImportProcessor) -> None:
        """Импорт типов цен из priceLists.xml"""
        self.stdout.write("\n📋 Шаг 1: Загрузка типов цен...")
        price_list_files = self._collect_xml_files(data_dir, "priceLists", "priceLists.xml")

        if price_list_files:
            total_price_types = 0
            for file_path in price_list_files:
                price_types_data = self._parse_or_skip(file_path, parser.parse_price_lists_xml)
                if price_types_data is None:
                    continue
                for price_type in price_types_data:
                    processor.process_price_types([price_type])
                total_price_types += len(price_types_data)
                self.stdout.write(f"   • {Path(file_path).name}: типов цен {len(price_types_data)}")

            self.stdout.write(self.style.SUCCESS(f"   ✅ Загружено типов цен (всего): {total_price_types}"))
        else:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы priceLists*.xml не найдены"))

    def _images_base_dir(self, data_dir: str, xml_subdir: str, processor: VariantImportProcessor) -> str:
        """Каталог изображений для этого прогона.

        Правило детерминированное, без эвристик: если `data_dir` — каталог
        обмена конкретной сессии (`IMPORT_DIR/<sessid>`), картинки берутся из
        ОБЩЕГО `IMPORT_DIR/import_files`. Их присылает отдельный обмен со своим
        `sessid`, и связи «архив картинок ↔ XML-сессия» протокол 1С не даёт —
        изолируй картинки, и goods.xml перестанет их находить.

        Во всех прочих случаях (ручной прогон по `ONEC_DATA_DIR`, тесты)
        поведение прежнее: `<data_dir>/<xml_subdir>/import_files` с фолбэком на
        `goods/import_files`, куда роутер складывал картинки исторически.

        Побочно ставит процессору фолбэк на легаси-раскладку: на время
        переходного окна выката картинка может лежать ещё в старом месте, а
        ЧАСТИЧНОЕ разрешение состава обрезает фото товара
        (`_import_base_images(mirror_composition=True)`).
        """
        from apps.integrations.onec_exchange.routing_service import (
            images_dir_for,
            is_session_import_dir,
            legacy_images_dir_for,
        )

        if is_session_import_dir(data_dir):
            legacy = legacy_images_dir_for(data_dir)
            processor.image_fallback_dirs = [str(legacy)] if legacy else []
            return str(images_dir_for(data_dir))

        processor.image_fallback_dirs = []
        base_dir = os.path.join(data_dir, xml_subdir, "import_files")
        # Fallback: если папка <xml_subdir>/import_files не существует, пробуем
        # goods/import_files — историческое место всех картинок обмена.
        if not os.path.exists(base_dir):
            alt_dir = os.path.join(data_dir, "goods", "import_files")
            if os.path.exists(alt_dir):
                base_dir = alt_dir
                self.stdout.write(f"   ℹ️ Изображения будут загружаться из: {Path(base_dir).relative_to(data_dir)}")
        return base_dir

    def _import_products_from_goods(
        self,
        data_dir: str,
        parser: XMLDataParser,
        processor: VariantImportProcessor,
        skip_images: bool,
    ) -> None:
        """Импорт Product из goods.xml (AC1)"""
        self.stdout.write("\n📦 Шаг 2: Создание Product из goods.xml...")
        goods_files = self._collect_xml_files(data_dir, "goods", "goods.xml")

        if not goods_files:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы товаров (goods_*.xml) не найдены. Пропуск шага."))
            return

        for file_path in goods_files:
            goods_data = self._parse_or_skip(file_path, parser.parse_goods_xml)
            if goods_data is None:
                continue
            base_dir = self._images_base_dir(data_dir, "goods", processor)

            for i, goods_item in enumerate(tqdm(goods_data, desc=f"   Обработка {Path(file_path).name}")):
                processor.process_product_from_goods(
                    cast("dict[str, Any]", goods_item),
                    base_dir=base_dir,
                    skip_images=skip_images,
                )
                if (i + 1) % 20 == 0:
                    processor.log_progress(
                        f"Обработка товаров ({Path(file_path).name}): " f"{i + 1} из {len(goods_data)}"
                    )

            self.stdout.write(f"   • {Path(file_path).name}: товаров {len(goods_data)}")

        stats = processor.get_stats()
        self.stdout.write(
            self.style.SUCCESS(f"   ✅ Создано: {stats['products_created']}, " f"обновлено: {stats['products_updated']}")
        )

    def _import_variants_from_offers(
        self,
        data_dir: str,
        parser: XMLDataParser,
        processor: VariantImportProcessor,
        skip_images: bool,
    ) -> None:
        """Импорт ProductVariant из offers.xml (AC2, AC3, AC4)"""
        self.stdout.write("\n🎁 Шаг 3: Создание ProductVariant из offers.xml...")
        offers_files = self._collect_xml_files(data_dir, "offers", "offers.xml")

        if not offers_files:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы вариантов (offers_*.xml) не найдены. Пропуск шага."))
            return

        for file_path in offers_files:
            offers_data = self._parse_or_skip(file_path, parser.parse_offers_xml)
            if offers_data is None:
                continue
            base_dir = self._images_base_dir(data_dir, "offers", processor)

            for i, offer_item in enumerate(tqdm(offers_data, desc=f"   Обработка {Path(file_path).name}")):
                processor.process_variant_from_offer(
                    cast("dict[str, Any]", offer_item),
                    base_dir=base_dir,
                    skip_images=skip_images,
                )
                if (i + 1) % 20 == 0:
                    processor.log_progress(
                        f"Обработка вариантов ({Path(file_path).name}): " f"{i + 1} из {len(offers_data)}"
                    )

            self.stdout.write(f"   • {Path(file_path).name}: предложений {len(offers_data)}")

        stats = processor.get_stats()
        self.stdout.write(
            self.style.SUCCESS(
                f"   ✅ Создано вариантов: {stats['variants_created']}, "
                f"обновлено: {stats['variants_updated']}, "
                f"пропущено: {stats['skipped']}"
            )
        )

    def _create_default_variants(self, processor: VariantImportProcessor) -> None:
        """Создание default variants для товаров без вариантов (AC5)"""
        self.stdout.write("\n🔄 Шаг 3.5: Создание default variants...")
        count = processor.create_default_variants()
        self.stdout.write(self.style.SUCCESS(f"   ✅ Создано default variants: {count}"))

    def _import_variant_prices(
        self,
        data_dir: str,
        parser: XMLDataParser,
        processor: VariantImportProcessor,
    ) -> None:
        """Импорт цен в ProductVariant из prices.xml (AC7)"""
        self.stdout.write("\n💰 Шаг 4: Обновление цен ProductVariant из prices.xml...")
        prices_files = self._collect_xml_files(data_dir, "prices", "prices.xml")

        if not prices_files:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы prices.xml не найдены"))
            return

        for file_path in prices_files:
            prices_data = self._parse_or_skip(file_path, parser.parse_prices_xml)
            if prices_data is None:
                continue

            for i, price_item in enumerate(tqdm(prices_data, desc=f"   Обработка {Path(file_path).name}")):
                processor.update_variant_prices(cast("dict[str, Any]", price_item))
                if (i + 1) % 20 == 0:
                    processor.log_progress(
                        f"Обновление цен ({Path(file_path).name}): " f"{i + 1} из {len(prices_data)}"
                    )

            self.stdout.write(f"   • {Path(file_path).name}: записей цен {len(prices_data)}")

        stats = processor.get_stats()
        self.stdout.write(self.style.SUCCESS(f"   ✅ Обновлено цен: {stats['prices_updated']}"))

    def _import_variant_stocks(
        self,
        data_dir: str,
        parser: XMLDataParser,
        processor: VariantImportProcessor,
    ) -> None:
        """Импорт остатков в ProductVariant из rests.xml (AC8)"""
        self.stdout.write("\n📊 Шаг 5: Обновление остатков ProductVariant из rests.xml...")
        rests_files = self._collect_xml_files(data_dir, "rests", "rests.xml")

        if not rests_files:
            self.stdout.write(self.style.WARNING("   ⚠️ Файлы rests.xml не найдены"))
            return

        for file_path in rests_files:
            rests_data = self._parse_or_skip(file_path, parser.parse_rests_xml)
            if rests_data is None:
                continue

            for i, rest_item in enumerate(tqdm(rests_data, desc=f"   Обработка {Path(file_path).name}")):
                processor.update_variant_stock(cast("dict[str, Any]", rest_item))
                if (i + 1) % 20 == 0:
                    processor.log_progress(
                        f"Обновление остатков ({Path(file_path).name}): " f"{i + 1} из {len(rests_data)}"
                    )

            self.stdout.write(f"   • {Path(file_path).name}: записей остатков {len(rests_data)}")

        stats = processor.get_stats()
        self.stdout.write(self.style.SUCCESS(f"   ✅ Обновлено остатков: {stats['stocks_updated']}"))

    def _assert_expected_file_processed(self, processor: VariantImportProcessor) -> None:
        """Проверить, что файлы, обещанные 1С этому прогону, действительно прочитаны.

        Проверка включается только когда имена переданы (`--source-filename`),
        то есть при вызове из задачи обмена. Ручной общий импорт и `mode=complete`
        конкретных файлов не обещают — там пустой каталог остаётся успехом.
        """
        expected = self._expected_filenames
        if not expected:
            return

        processed_names = {Path(p).name.lower() for p in self._processed_files}
        unread = sorted(expected - processed_names)
        if not unread:
            return

        missing_names = {Path(p).name.lower() for p in self._missing_files}
        details = "; ".join(
            f"{name} — "
            + ("исчез из каталога обмена до парсинга" if name in missing_names else "не найден в каталоге обмена")
            for name in unread
        )
        consequence = "данные не попали в БД, а 1С их не повторит"
        message = f"Файлы, присланные 1С этому прогону, не прочитаны ({details}): {consequence}."
        processor.log_progress(message)
        raise CommandError(message)

    def _cleanup_files(
        self,
        processed_files: list[str] | None = None,
        processor: VariantImportProcessor | None = None,
    ) -> None:
        """
        Удаление обработанных файлов после успешного импорта.

        Удаляются ТОЛЬКО те XML, которые этот прогон реально распарсил
        (`processed_files`). Маска glob как приём удаления не используется:
        каталог обмена общий для всех сессий, и `glob("rests/rests*.xml")`
        сносил файлы соседних задач раньше, чем те успевали их прочитать
        (инцидент выгрузки 25.08.2026). Файлы, которых этот прогон не читал, —
        не его дело: их уберёт `FileRoutingService.cleanup_import_dir`, когда
        активных сессий не останется.

        Перед удалением сверяется отпечаток файла (`_file_signature`): путь сам
        по себе не доказывает, что на диске всё ещё лежит распарсенный файл —
        сосед мог снести наш и положить свой под тем же именем. Микроскопическое
        окно между `stat` и `unlink` остаётся (TOCTOU неустраним без работы по
        дескриптору), но вместо секунд обработки это доли миллисекунды. Если
        отпечаток снять не удалось вовсе (`os.stat` упал, а парсер файл всё же
        открыл), сверять нечего — такой файл не удаляется: fail-open здесь снова
        означал бы удаление чужого файла под тем же именем.

        Картинки удаляются ПОФАЙЛОВО и только те, что этот прогон реально
        потребил (`processor.consumed_image_sources` — копия подтверждена в
        хранилище). Раньше здесь чистились каталоги `<data_dir>/goods/import_files`
        и `<data_dir>/offers/import_files`; после изоляции каталога обмена
        картинки лежат в ОБЩЕМ `IMPORT_DIR/import_files`, и та уборка потеряла
        цель — общий каталог перестал чиститься вовсе. Каталогом его убирать и
        нельзя: он общий, и в нём лежат картинки, ещё не забранные goods.xml
        соседних сессий.

        Превью ниже порога размера не удаляются: копии в хранилище у них не
        появляется, и признака «потреблено» для них не существует.
        """
        self.stdout.write(self.style.WARNING("\n🧹 Очистка обработанных файлов..."))

        # 1. Удаление XML файлов, распарсенных этим прогоном
        deleted_xml_count = 0
        for raw_path in processed_files or []:
            file_path = Path(raw_path)
            expected_signature = self._file_signatures.get(raw_path)
            if expected_signature is None:
                # Отпечаток снять не удалось — сверить нечего. Удалять вслепую
                # нельзя: под этим именем уже может лежать файл соседа.
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⚠️ Отпечаток {file_path.name} на момент парсинга неизвестен — "
                        "удаление пропущено, файл уберёт cleanup каталога обмена"
                    )
                )
                continue
            if self._file_signature(raw_path) != expected_signature:
                self.stdout.write(
                    self.style.WARNING(
                        f"   ⚠️ {file_path.name} подменён после парсинга — удаление пропущено, "
                        "файл принадлежит другому прогону"
                    )
                )
                continue
            try:
                file_path.unlink(missing_ok=True)
                deleted_xml_count += 1
            except OSError as e:
                self.stdout.write(self.style.ERROR(f"   ❌ Ошибка удаления {file_path.name}: {e}"))

        self.stdout.write(f"   ✅ Удалено XML файлов: {deleted_xml_count}")

        # 2. Удаление потреблённых исходников картинок
        self._cleanup_consumed_images(processor)

    def _cleanup_consumed_images(self, processor: VariantImportProcessor | None) -> None:
        """Удалить исходники картинок, копии которых уже лежат в хранилище.

        Область строго ограничена каталогом обмена (`ONEC_EXCHANGE["IMPORT_DIR"]`).
        Ручной корпус `ONEC_DATA_DIR` (`data/import_1c/`) не трогается никогда:
        это исходные выгрузки, на которых работают тесты и повторные прогоны,
        и удалять их — значит уничтожать входные данные разработчика.

        Удаление безопасно по построению: в `consumed_image_sources` попадают
        только те файлы, для которых копия в хранилище подтверждена, а
        `_save_image_if_not_exists` при отсутствии исходника берёт копию оттуда
        и состав фото не обрезает.
        """
        if processor is None:
            return

        sources = getattr(processor, "consumed_image_sources", None)
        if not sources:
            return

        from apps.integrations.onec_exchange.routing_service import get_import_base

        try:
            exchange_base = get_import_base().resolve()
        except OSError:  # pragma: no cover - защита от битого пути в настройках
            return

        deleted = 0
        skipped_outside = 0
        for raw_source in sorted(sources):
            source = Path(raw_source)
            try:
                if not source.resolve().is_relative_to(exchange_base):
                    skipped_outside += 1
                    continue
            except OSError:  # pragma: no cover - файл исчез между прогоном и уборкой
                continue

            try:
                source.unlink(missing_ok=True)
                deleted += 1
            except OSError as e:
                self.stdout.write(self.style.WARNING(f"   ⚠️ Не удалось удалить {source.name}: {e}"))

        if deleted:
            self.stdout.write(f"   ✅ Удалено перенесённых изображений: {deleted}")
        if skipped_outside:
            self.stdout.write(
                f"   ℹ️ Вне каталога обмена, не тронуто: {skipped_outside} "
                f"(ручной корпус ONEC_DATA_DIR не чистится)"
            )

    def _clear_existing_data(self) -> None:
        """Очистка существующих данных"""
        self.stdout.write(
            self.style.WARNING(
                "\n⚠️ ВНИМАНИЕ: Удаление всех существующих товаров, вариантов, " "категорий и брендов..."
            )
        )
        confirm = input("Вы уверены? Введите 'yes' для подтверждения: ")

        if confirm.lower() == "yes":
            ProductVariant.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            Brand.objects.all().delete()
            self.stdout.write(self.style.SUCCESS("✅ Данные очищены"))
        else:
            self.stdout.write(self.style.ERROR("❌ Очистка отменена"))
            raise CommandError("Очистка данных отменена пользователем")

    def _print_stats(self, stats: dict) -> None:
        """Вывод статистики импорта"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ ИМПОРТ ЗАВЕРШЕН УСПЕШНО"))
        self.stdout.write("=" * 60)
        self.stdout.write("\n📊 СТАТИСТИКА:")
        self.stdout.write(f"   Products создано:        {stats.get('products_created', 0)}")
        self.stdout.write(f"   Products обновлено:      {stats.get('products_updated', 0)}")
        self.stdout.write(f"   Variants создано:        {stats.get('variants_created', 0)}")
        self.stdout.write(f"   Variants обновлено:      {stats.get('variants_updated', 0)}")
        self.stdout.write(f"   Default variants:        {stats.get('default_variants_created', 0)}")
        self.stdout.write(f"   Цен обновлено:           {stats.get('prices_updated', 0)}")
        self.stdout.write(f"   Остатков обновлено:      {stats.get('stocks_updated', 0)}")
        self.stdout.write(f"   Пропущено:               {stats.get('skipped', 0)}")
        self.stdout.write(f"   Предупреждений:          {stats.get('warnings', 0)}")
        self.stdout.write(f"   Ошибок:                  {stats.get('errors', 0)}")

        self.stdout.write("\n📸 ИЗОБРАЖЕНИЯ:")
        self.stdout.write(f"   Скопировано:             {stats.get('images_copied', 0)}")
        self.stdout.write(f"   Заменено (новое содержимое): {stats.get('images_replaced', 0)}")
        # Раньше здесь стояла одна строка «Пропущено (существуют)» на сумму трёх
        # исходов — и она врала: мелкое превью не «существует», а отброшено, а
        # «узнано по копии» вообще означает разрешённую картинку, а не пропуск.
        self.stdout.write(f"   Уже в хранилище:         {stats.get('images_skipped_existing', 0)}")
        self.stdout.write(f"   Отсеяно по размеру:      {stats.get('images_skipped_small', 0)}")
        self.stdout.write(f"   Узнано по копии:         {stats.get('images_resolved_from_copy', 0)}")
        self.stdout.write(f"   Ошибок:                  {stats.get('images_errors', 0)}")
        self.stdout.write("=" * 60)

    def _collect_xml_files(self, base_dir: str, subdir: str, filename: str) -> list[str]:
        """
        Сбор XML файлов из директории с поддержкой альтернативных имен и папок.

        1C часто присылает 'import.xml' вместо 'goods.xml', и файлы могут
        находиться в разных подпапках в зависимости от модуля выгрузки.
        """
        base_path = Path(base_dir) / subdir
        collected: list[Path] = []

        # Список имен для поиска (переданное имя + стандартные имена 1С)
        search_filenames = [filename]
        if filename == "goods.xml" or filename == "groups.xml":
            search_filenames.append("import.xml")

        # Список директорий для поиска (переданная + логические альтернативы)
        search_paths = [base_path]
        if subdir == "groups":
            search_paths.append(Path(base_dir) / "goods")

        for p in search_paths:
            if not p.exists():
                continue

            for fname in search_filenames:
                prefix = fname.replace(".xml", "")

                # 1. Прямое совпадение имени
                for f_case in [fname, fname.capitalize(), fname.lower()]:
                    direct_file = p / f_case
                    if direct_file.exists() and direct_file not in collected:
                        collected.append(direct_file)

                # 2. Сегментированные файлы (prefix_*.xml) - ищем регистронезависимо
                # На Linux glob('*.xml') чувствителен к регистру
                for pattern in [
                    f"{prefix}_*.xml",
                    f"{prefix.capitalize()}_*.xml",
                    f"{prefix.lower()}_*.xml",
                ]:
                    for segmented_file in sorted(p.glob(pattern)):
                        if segmented_file not in collected:
                            collected.append(segmented_file)

                # 3. Legacy путь (подпапка import_files - иногда 1С кладет туда)
                legacy_file = p / "import_files" / fname
                if legacy_file.exists() and legacy_file not in collected:
                    collected.append(legacy_file)

        return self._restrict_to_expected([str(path) for path in collected])

    def _dry_run_import(self, data_dir: str) -> None:
        """Тестовый запуск импорта без записи в БД"""
        parser = XMLDataParser()

        self.stdout.write("\n📋 Проверка priceLists.xml...")
        price_list_files = self._collect_xml_files(data_dir, "priceLists", "priceLists.xml")
        if price_list_files:
            total = sum(len(parser.parse_price_lists_xml(f)) for f in price_list_files)
            self.stdout.write(f"   ✅ Найдено типов цен: {total}")
        else:
            self.stdout.write("   ⚠️ Файлы не найдены")

        self.stdout.write("\n📦 Проверка goods.xml...")
        goods_files = self._collect_xml_files(data_dir, "goods", "goods.xml")
        if goods_files:
            total = sum(len(parser.parse_goods_xml(f)) for f in goods_files)
            self.stdout.write(f"   ✅ Найдено товаров (Product): {total}")
        else:
            self.stdout.write("   ❌ Файлы не найдены")

        self.stdout.write("\n🎁 Проверка offers.xml...")
        offers_files = self._collect_xml_files(data_dir, "offers", "offers.xml")
        if offers_files:
            total = sum(len(parser.parse_offers_xml(f)) for f in offers_files)
            self.stdout.write(f"   ✅ Найдено предложений (ProductVariant): {total}")
        else:
            self.stdout.write("   ❌ Файлы не найдены")

        self.stdout.write("\n💰 Проверка prices.xml...")
        prices_files = self._collect_xml_files(data_dir, "prices", "prices.xml")
        if prices_files:
            total = sum(len(parser.parse_prices_xml(f)) for f in prices_files)
            self.stdout.write(f"   ✅ Найдено записей цен: {total}")
        else:
            self.stdout.write("   ⚠️ Файлы не найдены")

        self.stdout.write("\n📊 Проверка rests.xml...")
        rests_files = self._collect_xml_files(data_dir, "rests", "rests.xml")
        if rests_files:
            total = sum(len(parser.parse_rests_xml(f)) for f in rests_files)
            self.stdout.write(f"   ✅ Найдено записей остатков: {total}")
        else:
            self.stdout.write("   ⚠️ Файлы не найдены")

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS("✅ DRY RUN ЗАВЕРШЕН: Структура файлов корректна"))
        self.stdout.write("=" * 60)
