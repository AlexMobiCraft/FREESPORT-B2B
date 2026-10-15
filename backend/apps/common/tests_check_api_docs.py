"""
Тесты для команды check_api_docs
"""

from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.test import TestCase


class CheckApiDocsCommandTest(TestCase):
    """Тесты для команды проверки API документации"""

    def test_command_exists(self):
        """Тест что команда существует и запускается"""
        out = StringIO()
        call_command("check_api_docs", stdout=out)
        output = out.getvalue()
        self.assertIn("РЕЗУЛЬТАТЫ ПРОВЕРКИ API ДОКУМЕНТАЦИИ", output)

    def test_verbose_output(self):
        """Тест подробного вывода"""
        out = StringIO()
        call_command("check_api_docs", "--verbose", stdout=out)
        output = out.getvalue()
        self.assertIn("Проверка", output)
        self.assertIn("Статистика", output)

    def test_fail_on_missing_with_undocumented_endpoints(self):
        """Тест что команда завершается с ошибкой при недокументированных endpoints"""
        with self.assertRaises(CommandError) as cm:
            call_command("check_api_docs", "--fail-on-missing")

        self.assertIn("недокументированных endpoints", str(cm.exception))
        self.assertIn("CI проверка не пройдена", str(cm.exception))

    def test_command_help(self):
        """Тест что help команды работает корректно (выходит с кодом 0)"""
        # --help вызывает SystemExit(0), что нормально для команд
        with self.assertRaises(SystemExit) as cm:
            call_command("check_api_docs", "--help")

        # Проверяем что exit code = 0 (успешное завершение)
        self.assertEqual(cm.exception.code, 0)


@pytest.mark.integration
class CheckApiDocsIntegrationTest:
    """Интеграционные тесты команды check_api_docs"""

    def test_check_existing_viewsets(self):
        """Тест что команда находит существующие ViewSets"""
        out = StringIO()
        call_command("check_api_docs", "--verbose", stdout=out)
        output = out.getvalue()

        # Проверяем что находит основные ViewSets
        assert "ProductViewSet" in output
        assert "CategoryViewSet" in output
        assert "BrandViewSet" in output

    def test_documentation_coverage_calculation(self):
        """Тест правильности расчета покрытия документацией"""
        out = StringIO()
        call_command("check_api_docs", stdout=out)
        output = out.getvalue()

        # Проверяем что есть статистика
        assert "Статистика:" in output
        assert "Всего методов:" in output
        assert "Документированных:" in output
        assert "Покрытие:" in output

    def test_spectacular_validation_integration(self):
        """Тест интеграции с spectacular валидацией"""
        # Этот тест проверяет что spectacular может сгенерировать схему
        import os
        import tempfile

        from django.core.management import call_command

        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as tmp:
            try:
                # Должно выполниться без ошибок
                call_command("spectacular", "--file", tmp.name, "--validate")
                assert os.path.exists(tmp.name)
                assert os.path.getsize(tmp.name) > 0
            finally:
                os.unlink(tmp.name)
