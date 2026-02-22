"""
Unit tests for normalize_image_path() function (Story 27.2, AC4)

Tests the image path normalization that ensures consistent path handling
across XML import and admin panel imports.
"""

import pytest

from apps.products.services.variant_import import normalize_image_path


@pytest.mark.unit
class TestNormalizeImagePath:
    """Тесты для normalize_image_path() (Story 27.2, AC4)"""

    def test_removes_import_files_prefix(self):
        """Путь с import_files/ prefix → возвращает путь без prefix"""
        result = normalize_image_path("import_files/xx/file.jpg")
        assert result == "xx/file.jpg"

    def test_preserves_path_without_prefix(self):
        """Путь без import_files/ prefix → возвращает путь без изменений"""
        result = normalize_image_path("xx/file.jpg")
        assert result == "xx/file.jpg"

    def test_empty_string(self):
        """Пустая строка → пустая строка"""
        result = normalize_image_path("")
        assert result == ""

    def test_only_filename(self):
        """Только имя файла без директорий"""
        result = normalize_image_path("file.jpg")
        assert result == "file.jpg"

    def test_deep_path_with_prefix(self):
        """Глубокий путь с import_files/ prefix"""
        result = normalize_image_path("import_files/a/b/c/file.jpg")
        assert result == "a/b/c/file.jpg"

    def test_import_files_in_middle_not_removed(self):
        """import_files в середине пути НЕ удаляется"""
        result = normalize_image_path("xx/import_files/file.jpg")
        assert result == "xx/import_files/file.jpg"

    def test_import_files_only_prefix(self):
        """Только prefix import_files/ без файла"""
        result = normalize_image_path("import_files/")
        assert result == ""

    def test_import_files_exact_match(self):
        """Строка 'import_files' без слэша не удаляется"""
        result = normalize_image_path("import_files")
        assert result == "import_files"

    def test_import_files_different_case_not_removed(self):
        """import_files с другим регистром НЕ удаляется (case-sensitive)"""
        result = normalize_image_path("Import_Files/xx/file.jpg")
        assert result == "Import_Files/xx/file.jpg"

    def test_multiple_import_files_prefix_removes_only_first(self):
        """Множественные import_files/ - удаляется только первый prefix"""
        result = normalize_image_path("import_files/import_files/file.jpg")
        assert result == "import_files/file.jpg"

    def test_windows_style_path_not_normalized(self):
        """Windows-style пути с backslash не обрабатываются (ожидаемое поведение)"""
        # Функция работает только с forward slashes как в XML
        result = normalize_image_path("import_files\\xx\\file.jpg")
        assert result == "import_files\\xx\\file.jpg"

    def test_path_with_special_characters(self):
        """Путь с особыми символами в имени файла"""
        result = normalize_image_path("import_files/xx/file-name_v2 (1).jpg")
        assert result == "xx/file-name_v2 (1).jpg"

    def test_path_with_uuid(self):
        """Путь с UUID в имени файла (реальный формат из 1С)"""
        result = normalize_image_path("import_files/00/001a16a4-b810-11ed-860f-fa163edba792_24062354.jpg")
        assert result == "00/001a16a4-b810-11ed-860f-fa163edba792_24062354.jpg"

    def test_path_with_cyrillic_characters(self):
        """Путь с кириллическими символами"""
        result = normalize_image_path("import_files/товары/изображение.jpg")
        assert result == "товары/изображение.jpg"
