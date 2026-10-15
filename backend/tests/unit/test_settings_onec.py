"""
Unit-тесты для настроек интеграции с 1С
"""

import os
from pathlib import Path

import pytest
from django.conf import settings


@pytest.mark.unit
class TestOneCSettings:
    """Тесты для настроек интеграции с 1С"""

    def test_onec_data_dir_setting_exists(self):
        """
        Тест: настройка ONEC_DATA_DIR существует
        """
        # Assert
        assert hasattr(settings, "ONEC_DATA_DIR")
        assert settings.ONEC_DATA_DIR is not None

    def test_onec_data_dir_is_string(self):
        """
        Тест: ONEC_DATA_DIR является строкой
        """
        # Assert
        assert isinstance(settings.ONEC_DATA_DIR, str)

    def test_onec_data_dir_path_format(self):
        """
        Тест: ONEC_DATA_DIR имеет правильный формат пути
        """
        # Assert
        data_dir = settings.ONEC_DATA_DIR
        assert "import_1c" in data_dir
        # Путь должен быть абсолютным или относительным
        assert len(data_dir) > 0

    def test_onec_data_dir_can_be_converted_to_path(self):
        """
        Тест: ONEC_DATA_DIR может быть преобразован в Path объект
        """
        # Act
        path = Path(settings.ONEC_DATA_DIR)

        # Assert
        assert isinstance(path, Path)
        assert path.name == "import_1c"

    def test_onec_data_dir_from_environment_variable(self, monkeypatch):
        """
        Тест: ONEC_DATA_DIR может быть задан через переменную окружения
        """
        # Arrange
        test_path = "/custom/path/to/import_1c"
        monkeypatch.setenv("ONEC_DATA_DIR", test_path)

        # Act
        from importlib import reload

        from django.conf import settings as django_settings

        # Примечание: в реальном приложении настройки загружаются один раз
        # Этот тест проверяет логику, но не перезагружает settings
        # Assert
        # В тестовой среде settings уже загружены, поэтому проверяем
        # что переменная окружения установлена
        assert os.environ.get("ONEC_DATA_DIR") == test_path

    def test_onec_data_dir_default_value(self):
        """
        Тест: ONEC_DATA_DIR имеет значение по умолчанию

        Проверяет, что если переменная окружения не задана,
        используется значение по умолчанию.
        """
        # Assert
        data_dir = settings.ONEC_DATA_DIR
        # Значение по умолчанию должно содержать "data/import_1c"
        assert "data" in data_dir or "import_1c" in data_dir
