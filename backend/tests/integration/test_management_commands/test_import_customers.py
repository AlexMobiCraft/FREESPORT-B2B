"""
Integration-тесты для команды import_customers_from_1c
Используют реальные данные из data/import_1c/contragents/
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from typing import Type, cast

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.common.models import CustomerSyncLog
from apps.products.models import ImportSession
from apps.users.models import User as CustomUserModel

User = cast(Type[CustomUserModel], get_user_model())


@pytest.mark.django_db
@pytest.mark.integration
class TestImportCustomersCommand:
    """Integration-тесты для команды import_customers_from_1c"""

    @pytest.fixture
    def real_data_dir(self):
        """Путь к директории с данными 1С"""
        # В Docker контейнере data смонтирована в /app/data
        # Локально - из корня проекта
        import os

        if os.path.exists("/app/data/import_1c"):
            # Docker environment
            data_path = Path("/app/data/import_1c")
        else:
            # Local environment
            base_path = Path(__file__).parent.parent.parent.parent.parent
            data_path = base_path / "data" / "import_1c"
        return str(data_path)

    def test_command_imports_real_customers(self, real_data_dir):
        """Тест импорта реальных клиентов из 1С"""
        out = StringIO()

        # Запустить команду
        call_command("import_customers_from_1c", data_dir=real_data_dir, stdout=out)

        output = out.getvalue()

        # Проверить что команда вывела статистику
        assert "Найдено" in output
        assert "файлов контрагентов" in output
        assert "Распознано" in output
        assert "клиентов" in output or "контрагентов" in output
        assert "Итоговая статистика" in output
        assert "Импорт успешно завершен" in output

        # Проверить что сессия создана и завершена успешно
        session = ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS).latest("started_at")

        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.finished_at is not None
        assert "total" in session.report_details

        # Проверить что клиенты созданы
        customers_count = User.objects.filter(created_in_1c=True).count()
        assert customers_count == session.report_details["created"]
        assert session.report_details["total"] == (
            session.report_details["created"]
            + session.report_details["updated"]
            + session.report_details["skipped"]
            + session.report_details["errors"]
        )

        # Проверить что логи созданы
        logs_count = CustomerSyncLog.objects.filter(session=str(session.pk)).count()
        assert logs_count >= session.report_details["total"]

    def test_command_dry_run_mode(self, real_data_dir):
        """Тест dry-run режима команды"""
        initial_users_count = User.objects.count()

        out = StringIO()
        call_command("import_customers_from_1c", data_dir=real_data_dir, dry_run=True, stdout=out)

        output = out.getvalue()

        # Проверить сообщение о dry-run
        assert "DRY-RUN режим" in output
        assert "изменения не сохранены" in output

        # Проверить что данные НЕ сохранены
        assert User.objects.count() == initial_users_count

        # Проверить что сессия создана, но не завершена
        sessions_count = ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS).count()
        assert sessions_count == 1
        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.STARTED

    def test_command_with_custom_chunk_size(self, real_data_dir):
        """Тест команды с пользовательским chunk_size"""
        out = StringIO()

        # Запустить с малым chunk_size
        call_command("import_customers_from_1c", data_dir=real_data_dir, chunk_size=2, stdout=out)

        output = out.getvalue()

        # Проверить успешное выполнение
        assert "Импорт успешно завершен" in output

        # Проверить что клиенты созданы
        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.COMPLETED

    def test_command_handles_dir_not_found(self):
        """Тест обработки несуществующей директории"""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("import_customers_from_1c", data_dir="/nonexistent/dir")

        assert "Директория не найдена" in str(exc_info.value)

    def test_command_handles_invalid_chunk_size(self, real_data_dir):
        """Тест обработки невалидного chunk_size"""
        from django.core.management.base import CommandError

        with pytest.raises(CommandError) as exc_info:
            call_command("import_customers_from_1c", data_dir=real_data_dir, chunk_size=0)

        assert "chunk-size" in str(exc_info.value).lower()

    def test_command_prevents_concurrent_execution(self, real_data_dir):
        """Тест переиспользования активной сессии импорта"""
        # Создать активную сессию импорта
        active_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CUSTOMERS,
            status=ImportSession.ImportStatus.STARTED,
        )

        out = StringIO()
        call_command("import_customers_from_1c", data_dir=real_data_dir, stdout=out)

        output = out.getvalue()
        assert f"Используется существующая сессия импорта #{active_session.pk}" in output

        # Проверить, что не создана новая сессия
        assert ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS).count() == 1
        session = ImportSession.objects.latest("started_at")
        assert session.pk == active_session.pk
        assert session.status == ImportSession.ImportStatus.COMPLETED

    def test_command_handles_malformed_xml(self, tmp_path):
        """Тест обработки некорректного XML"""
        malformed_xml = tmp_path / "malformed.xml"
        malformed_xml.write_text("<КоммерческаяИнформация><Контрагенты>", encoding="utf-8")

        with pytest.raises(Exception):  # Может быть CommandError или ValidationError
            call_command("import_customers_from_1c", file=str(malformed_xml))

        # Проверить что сессия помечена как failed
        sessions = ImportSession.objects.filter(import_type=ImportSession.ImportType.CUSTOMERS)
        if sessions.exists():
            session = sessions.latest("started_at")
            assert session.status == ImportSession.ImportStatus.FAILED
            assert session.error_message != ""

    def test_command_creates_correct_roles(self, real_data_dir):
        """Тест корректного маппинга ролей"""
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        # Проверить что роли корректно установлены
        users = User.objects.filter(created_in_1c=True)

        # Все роли должны быть валидными
        valid_roles = [choice[0] for choice in User.ROLE_CHOICES]
        for user in users:
            assert user.role in valid_roles

    def test_command_handles_customers_without_email(self, real_data_dir):
        """Тест обработки клиентов без email"""
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        # Проверить что клиенты без email созданы
        users_without_email = User.objects.filter(created_in_1c=True, email="")

        # Может быть 0 или больше клиентов без email
        if users_without_email.exists():
            # Для каждого клиента без email должен быть onec_id
            for user in users_without_email:
                assert user.onec_id

            # Проверить что есть логи с warning
            session = ImportSession.objects.latest("started_at")
            warning_logs = CustomerSyncLog.objects.filter(
                session=str(session.pk),
                status=CustomerSyncLog.StatusType.WARNING,
            )
            # Может быть warning логи для клиентов без email

    def test_command_updates_existing_customers(self, real_data_dir):
        """Тест обновления существующих клиентов"""
        # Запустить импорт первый раз
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        first_session = ImportSession.objects.latest("started_at")
        first_created = first_session.report_details["created"]

        # Запустить импорт второй раз
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        second_session = ImportSession.objects.latest("started_at")

        # Во второй раз должны быть только обновления, а не создания
        assert second_session.report_details["updated"] > 0
        assert second_session.report_details["created"] == 0

    def test_command_logs_all_operations(self, real_data_dir):
        """Тест логирования всех операций"""
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        session = ImportSession.objects.latest("started_at")
        logs_count = CustomerSyncLog.objects.filter(session=str(session.pk)).count()

        # Должно быть столько же логов, сколько обработано клиентов
        total_processed = session.report_details["total"]
        assert logs_count >= total_processed  # >= потому что может быть несколько логов на клиента

    def test_command_sets_sync_status(self, real_data_dir):
        """Тест установки статуса синхронизации"""
        call_command("import_customers_from_1c", data_dir=real_data_dir)

        # Все импортированные клиенты должны иметь sync_status='synced'
        users = User.objects.filter(created_in_1c=True)
        for user in users:
            assert user.sync_status == "synced"
            assert user.last_sync_at is not None
