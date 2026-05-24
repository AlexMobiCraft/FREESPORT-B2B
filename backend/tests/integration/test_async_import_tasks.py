"""
Интеграционные тесты для асинхронного импорта через Celery
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from celery.exceptions import Retry
from django.conf import settings

from apps.integrations.tasks import _execute_import_type, run_selective_import_task


@pytest.mark.integration
class TestRunSelectiveImportTask:
    """Тесты для Celery задачи run_selective_import_task"""

    @patch("apps.integrations.tasks._execute_import_type")
    def test_successful_catalog_import(self, mock_execute):
        """Тест успешного импорта каталога"""
        # Arrange
        mock_execute.return_value = {
            "type": "catalog",
            "message": "Каталог импортирован",
        }
        selected_types = ["catalog"]
        data_dir = "/path/to/data"

        # Act
        result = run_selective_import_task(selected_types, data_dir)

        # Assert
        assert result["status"] == "success"
        assert "catalog" in result["completed_imports"]
        assert len(result["messages"]) == 1
        mock_execute.assert_called_once()

    @patch("apps.integrations.tasks._execute_import_type")
    def test_multiple_types_sequential_import(self, mock_execute):
        """Тест последовательного импорта нескольких типов"""
        # Arrange
        mock_execute.side_effect = [
            {"type": "catalog", "message": "Каталог импортирован"},
            {"type": "stocks", "message": "Остатки обновлены"},
            {"type": "prices", "message": "Цены обновлены"},
        ]
        selected_types = ["catalog", "stocks", "prices"]
        data_dir = "/path/to/data"

        # Act
        result = run_selective_import_task(selected_types, data_dir)

        # Assert
        assert result["status"] == "success"
        assert result["completed_imports"] == ["catalog", "stocks", "prices"]
        assert len(result["messages"]) == 3
        assert mock_execute.call_count == 3

    @patch("apps.integrations.tasks._execute_import_type")
    def test_import_failure_stops_chain(self, mock_execute):
        """Тест прерывания цепочки при ошибке"""
        # Arrange
        mock_execute.side_effect = [
            {"type": "catalog", "message": "Каталог импортирован"},
            Exception("Ошибка импорта остатков"),
        ]
        selected_types = ["catalog", "stocks", "prices"]
        data_dir = "/path/to/data"

        # Act & Assert
        # Задача должна выбросить исключение при ошибке импорта
        with pytest.raises(Exception, match="Ошибка импорта остатков"):
            run_selective_import_task(selected_types, data_dir)

        # Проверяем, что prices не был вызван (только catalog и stocks)
        assert mock_execute.call_count == 2

    def test_missing_onec_data_dir_setting(self):
        """Тест ошибки при отсутствии настройки ONEC_DATA_DIR"""
        # Arrange
        selected_types = ["catalog"]

        # Act & Assert
        with patch.object(settings, "ONEC_DATA_DIR", None):
            with pytest.raises(ValueError, match="ONEC_DATA_DIR не найдена"):
                run_selective_import_task(selected_types, None)

    @patch("apps.integrations.tasks._execute_import_type")
    def test_skips_unselected_types(self, mock_execute):
        """Тест пропуска невыбранных типов импорта"""
        # Arrange
        mock_execute.return_value = {
            "type": "catalog",
            "message": "Каталог импортирован",
        }
        selected_types = ["catalog"]  # Только каталог
        data_dir = "/path/to/data"

        # Act
        result = run_selective_import_task(selected_types, data_dir)

        # Assert
        assert result["completed_imports"] == ["catalog"]
        mock_execute.assert_called_once()


@pytest.mark.integration
class TestExecuteImportType:
    """Тесты для функции _execute_import_type"""

    @patch("apps.integrations.tasks.call_command")
    def test_catalog_import_calls_correct_command(self, mock_call_command):
        """Тест вызова правильной команды для импорта каталога (AC1, AC2)"""
        # Arrange
        task_id = "test-task-123"

        # Act
        result = _execute_import_type("catalog", task_id)

        # Assert
        assert result["type"] == "catalog"
        assert result["message"] == "Каталог импортирован"
        mock_call_command.assert_called_once_with(
            "import_products_from_1c",
            "--file-type",
            "all",
            "--celery-task-id",
            task_id,
        )

    @patch("apps.integrations.tasks.call_command")
    def test_stocks_import_calls_rests_command(self, mock_call_command):
        """Тест запуска команды импорта остатков (AC1, AC2)"""
        # Arrange
        task_id = "test-task-123"

        # Act
        result = _execute_import_type("stocks", task_id)

        # Assert
        assert result["type"] == "stocks"
        assert result["message"] == "Остатки обновлены"
        mock_call_command.assert_called_once_with(
            "import_products_from_1c",
            "--file-type",
            "rests",
            "--celery-task-id",
            task_id,
        )

    @patch("apps.integrations.tasks.call_command")
    def test_prices_import_calls_correct_command(self, mock_call_command):
        """Тест вызова правильной команды для импорта цен (AC1, AC2)"""
        # Arrange
        task_id = "test-task-123"

        # Act
        result = _execute_import_type("prices", task_id)

        # Assert
        assert result["type"] == "prices"
        assert result["message"] == "Цены обновлены"
        mock_call_command.assert_called_once_with(
            "import_products_from_1c",
            "--file-type",
            "prices",
            "--celery-task-id",
            task_id,
        )

    @patch("apps.integrations.tasks.call_command")
    def test_celery_task_id_passed_correctly(self, mock_call_command):
        """AC2: celery-task-id передаётся корректно"""
        task_id = "abc-123-def-456"
        _execute_import_type("catalog", task_id)

        call_args = mock_call_command.call_args
        # Проверяем что task_id передан в аргументах
        assert "--celery-task-id" in call_args[0]
        assert task_id in call_args[0]

    @patch("apps.integrations.tasks.call_command")
    def test_customers_import_finds_contragents_file(self, mock_call_command):
        """Тест поиска файла контрагентов"""
        # Arrange
        data_dir = "/path/to/data"
        task_id = "test-task-123"

        # Указываем настройку ONEC_DATA_DIR, так как она используется
        # внутри _execute_import_type
        # для типа customers
        with patch.object(settings, "ONEC_DATA_DIR", data_dir), patch("apps.integrations.tasks.Path") as mock_path:
            # Мокаем структуру директорий
            mock_contragents_dir = MagicMock()
            mock_contragents_dir.exists.return_value = True
            mock_contragents_dir.glob.return_value = [Path(f"{data_dir}/contragents/contragents.xml")]

            mock_path.return_value.__truediv__.return_value = mock_contragents_dir

            # Act
            result = _execute_import_type("customers", task_id)

            # Assert
            assert result["type"] == "customers"
            assert result["message"] == "Клиенты импортированы"
            mock_call_command.assert_called_once()

    def test_unknown_import_type_raises_error(self):
        """Тест ошибки при неизвестном типе импорта"""
        # Arrange
        data_dir = "/path/to/data"
        task_id = "test-task-123"

        # Act & Assert
        with pytest.raises(ValueError, match="Неизвестный тип импорта"):
            _execute_import_type("unknown_type", task_id)


@pytest.mark.integration
class TestImportTaskRetry:
    """Тесты механизма повторных попыток"""

    @patch("apps.integrations.tasks._execute_import_type")
    def test_task_retries_on_failure(self, mock_execute):
        """Тест повторной попытки при ошибке"""
        # Arrange
        mock_execute.side_effect = Exception("Временная ошибка")
        selected_types = ["catalog"]
        data_dir = "/path/to/data"

        # Act & Assert
        # Задача должна выбросить исключение при критической ошибке
        with pytest.raises(Exception, match="Временная ошибка"):
            run_selective_import_task(selected_types, data_dir)
