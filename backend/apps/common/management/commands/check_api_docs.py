"""
Django management command для проверки полноты API документации.
Проверяет что все ViewSets имеют @extend_schema декораторы и proper описания.
"""

import inspect
from typing import Any, Dict, List

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet


class Command(BaseCommand):
    """Management-команда для проверки полноты API-документации."""

    help = "Проверяет полноту API документации для всех ViewSets"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verbosity = 1
        self.verbose = False
        self.fail_on_missing = False

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-missing",
            action="store_true",
            help="Завершить с ошибкой при обнаружении недокументированных endpoints",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод с информацией о каждом ViewSet",
        )

    def handle(self, *args, **options):
        self.verbosity = options.get("verbosity", 1)
        self.verbose = options.get("verbose", False)
        self.fail_on_missing = options.get("fail_on_missing", False)

        self.stdout.write(self.style.HTTP_INFO("Проверка полноты API документации...\n"))

        # Получаем все ViewSets из приложений
        viewsets = self._get_all_viewsets()

        if not viewsets:
            self.stdout.write(self.style.WARNING("WARNING: Не найдено ни одного ViewSet для проверки"))
            return

        # Проверяем документацию каждого ViewSet
        undocumented_items = []
        total_methods = 0
        documented_methods = 0

        for viewset_info in viewsets:
            issues = self._check_viewset_documentation(viewset_info)
            if issues:
                undocumented_items.extend(issues)

            # Подсчитываем статистику
            methods_count = len(viewset_info["methods"])
            total_methods += methods_count
            documented_methods += methods_count - len(issues)

        # Выводим результаты
        self._print_results(undocumented_items, total_methods, documented_methods)

        # Завершаем с ошибкой если требуется
        if undocumented_items and self.fail_on_missing:
            raise CommandError(
                "ERROR: Найдено {len(undocumented_items)} " "недокументированных endpoints. CI проверка не пройдена."
            )

    def _get_all_viewsets(self) -> List[Dict[str, Any]]:
        """Получает все ViewSets из Django приложений."""
        viewsets = []

        for app_config in apps.get_app_configs():
            if not app_config.name.startswith("apps."):
                continue

            try:
                views_module = __import__(f"{app_config.name}.views", fromlist=[""])
            except ImportError:
                continue

            # Ищем ViewSets в модуле
            for name, obj in inspect.getmembers(views_module):
                if (
                    inspect.isclass(obj)
                    and (
                        issubclass(obj, ViewSet)
                        or issubclass(obj, ModelViewSet)
                        or issubclass(obj, ReadOnlyModelViewSet)
                    )
                    and obj not in [ViewSet, ModelViewSet, ReadOnlyModelViewSet]
                    and obj.__module__ == views_module.__name__
                ):
                    methods = self._get_viewset_methods(obj)
                    if methods:  # Только если есть методы для проверки
                        viewsets.append(
                            {
                                "name": f"{app_config.name}.{name}",
                                "class": obj,
                                "methods": methods,
                            }
                        )

        return viewsets

    def _get_viewset_methods(self, viewset_class: Any) -> List[Dict[str, Any]]:
        """Получает все методы ViewSet, которые нуждаются в документации."""
        methods = []

        # Стандартные CRUD методы
        crud_methods = [
            "list",
            "create",
            "retrieve",
            "update",
            "partial_update",
            "destroy",
        ]
        for method_name in crud_methods:
            if hasattr(viewset_class, method_name):
                methods.append(
                    {
                        "name": method_name,
                        "type": "crud",
                        "method": getattr(viewset_class, method_name),
                    }
                )

        # Custom action методы
        for name, method in inspect.getmembers(viewset_class, inspect.isfunction):
            if hasattr(method, "mapping"):  # Это @action декоратор
                methods.append({"name": name, "type": "action", "method": method})

        return methods

    def _check_viewset_documentation(self, viewset_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Проверяет документацию для ViewSet."""
        issues = []

        if self.verbose:
            self.stdout.write(f'\nПроверка {viewset_info["name"]}:')

        for method_info in viewset_info["methods"]:
            method = method_info["method"]
            method_name = method_info["name"]

            # Проверяем наличие @extend_schema декоратора
            has_schema = self._has_extend_schema(method)

            if not has_schema:
                issue = {
                    "viewset": viewset_info["name"],
                    "method": method_name,
                    "type": method_info["type"],
                    "issue": "missing_extend_schema",
                }
                issues.append(issue)

                if self.verbose:
                    self.stdout.write(f"  [X] {method_name}: отсутствует @extend_schema декоратор")
            else:
                # Проверяем качество документации
                schema_issues = self._check_schema_quality(method, method_name)
                if schema_issues:
                    for schema_issue in schema_issues:
                        issue = {
                            "viewset": viewset_info["name"],
                            "method": method_name,
                            "type": method_info["type"],
                            "issue": schema_issue,
                        }
                        issues.append(issue)

                        if self.verbose:
                            self.stdout.write(f"  [!] {method_name}: {schema_issue}")

                if self.verbose and not schema_issues:
                    self.stdout.write(f"  [OK] {method_name}: документация в порядке")

        return issues

    def _has_extend_schema(self, method: Any) -> bool:
        """Проверяет наличие @extend_schema декоратора у метода."""

        # Получаем функцию из метода
        if hasattr(method, "__func__"):
            func = method.__func__
        else:
            func = method

        # 1. Проверяем через атрибуты spectacular
        if hasattr(func, "kwargs"):
            # Проверяем есть ли в kwargs spectacular данные
            kwargs = getattr(func, "kwargs", {})
            if any(key in ["summary", "description", "operation_id", "tags", "parameters"] for key in kwargs.keys()):
                return True

        # 2. Проверяем через _spectacular_annotation атрибут
        if hasattr(func, "_spectacular_annotation"):
            return True

        # 3. Проверяем исходный код на наличие @extend_schema
        try:
            source = inspect.getsource(func)
            if "@extend_schema" in source:
                return True
        except (OSError, TypeError):
            pass

        # 4. Проверяем через __wrapped__ (если есть декораторы)
        current_func = func
        while hasattr(current_func, "__wrapped__"):
            current_func = current_func.__wrapped__
            if hasattr(current_func, "_spectacular_annotation"):
                return True
            if hasattr(current_func, "kwargs"):
                kwargs = getattr(current_func, "kwargs", {})
                if any(
                    key in ["summary", "description", "operation_id", "tags", "parameters"] for key in kwargs.keys()
                ):
                    return True

        # 5. Проверяем через registry drf-spectacular (если доступен)
        try:
            from drf_spectacular.openapi import AutoSchema  # noqa: F401

            # Если функция имеет атрибуты схемы
            if hasattr(func, "operation_summary") or hasattr(func, "operation_description"):
                return True
        except ImportError:
            pass

        return False

    def _check_schema_quality(self, method: Any, method_name: str) -> List[str]:
        """Проверяет качество схемы документации."""
        issues = []

        # Для более детальной проверки нужно интеграция с drf-spectacular
        # Пока делаем базовую проверку

        try:
            # Проверяем docstring метода
            if not method.__doc__ or len(method.__doc__.strip()) < 10:
                issues.append("отсутствует или слишком короткое описание в docstring")
        except Exception:
            pass

        return issues

    def _print_results(
        self,
        undocumented_items: List[Dict[str, Any]],
        total_methods: int,
        documented_methods: int,
    ) -> None:
        """Выводит результаты проверки."""
        coverage_percent = (documented_methods / total_methods * 100) if total_methods > 0 else 0

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("РЕЗУЛЬТАТЫ ПРОВЕРКИ API ДОКУМЕНТАЦИИ")
        self.stdout.write("=" * 60)

        if undocumented_items:
            self.stdout.write(self.style.ERROR(f"ERROR: Найдено {len(undocumented_items)} проблем с документацией:"))

            # Группируем проблемы по ViewSet
            issues_by_viewset: dict[str, list[dict[str, Any]]] = {}
            for item in undocumented_items:
                viewset = item["viewset"]
                if viewset not in issues_by_viewset:
                    issues_by_viewset[viewset] = []
                issues_by_viewset[viewset].append(item)

            for viewset, issues in issues_by_viewset.items():
                self.stdout.write(f"\n{viewset}:")
                for issue in issues:
                    self.stdout.write(f'  - {issue["method"]} ({issue["type"]}): {issue["issue"]}')
        else:
            self.stdout.write(self.style.SUCCESS("SUCCESS: Все endpoints имеют proper документацию!"))

        # Статистика
        self.stdout.write("\nСтатистика:")
        self.stdout.write(f"  - Всего методов: {total_methods}")
        self.stdout.write(f"  - Документированных: {documented_methods}")
        self.stdout.write(f"  - Покрытие: {coverage_percent:.1f}%")

        if coverage_percent >= 90:
            style = self.style.SUCCESS
            prefix = "EXCELLENT"
        elif coverage_percent >= 70:
            style = self.style.WARNING
            prefix = "WARNING"
        else:
            style = self.style.ERROR
            prefix = "POOR"

        self.stdout.write(style(f"  {prefix}: Уровень документированности: {coverage_percent:.1f}%"))

        self.stdout.write("\n" + "=" * 60)
