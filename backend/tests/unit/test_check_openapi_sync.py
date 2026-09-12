"""Тесты сверки контракта API с кодом (`manage.py check_openapi_sync`).

Проверяются чистые функции нормализации и сравнения, а также ранние отказы самой команды.
Генерация схемы здесь не запускается намеренно: она стоит секунды и уже покрыта тем, что
команда падает в CI при рассинхроне. Маркер `unit` проставляется автоматически по каталогу.
"""

from unittest import mock

import pytest
import yaml
from django.core.management.base import CommandError

from apps.common.management.commands.check_openapi_sync import (
    MAX_REPORTED_DIFFERENCES,
    Command,
    collect_differences,
    default_schema_path,
    load_schema,
    normalize,
)


def differences(from_code, from_file):
    """Список расхождений, чтобы не разворачивать генератор в каждом тесте."""
    return list(collect_differences(normalize(from_code), normalize(from_file)))


def yaml_dump(document):
    """YAML-текст документа для временных файлов контракта."""
    return yaml.safe_dump(document, allow_unicode=True)


class TestNormalize:
    """Приведение документа к виду, не зависящему от незначимого порядка."""

    @pytest.mark.parametrize("key", ["tags", "required", "enum"])
    def test_scalar_lists_are_sorted(self, key):
        assert normalize({key: ["b", "a", "c"]}) == {key: ["a", "b", "c"]}

    def test_other_scalar_lists_keep_order(self):
        """Порядок значим не везде: `servers` — упорядоченный список приоритета."""
        document = {"servers": ["https://b", "https://a"]}
        assert normalize(document) == document

    def test_parameters_sorted_by_location_and_name(self):
        document = {
            "parameters": [
                {"in": "query", "name": "page"},
                {"in": "path", "name": "id"},
                {"in": "query", "name": "limit"},
            ]
        }
        assert [p["name"] for p in normalize(document)["parameters"]] == ["id", "limit", "page"]

    def test_parameters_with_ref_do_not_break_sorting(self):
        """В списке параметров бывают `$ref` без `in`/`name` — сортировка обязана их пережить."""
        document = {"parameters": [{"$ref": "#/components/parameters/Page"}, {"in": "path", "name": "id"}]}
        assert len(normalize(document)["parameters"]) == 2

    def test_list_of_mappings_is_normalized_recursively(self):
        document = {"items": [{"tags": ["b", "a"]}]}
        assert normalize(document) == {"items": [{"tags": ["a", "b"]}]}

    def test_mixed_list_under_unordered_key_is_left_alone(self):
        """Сортировать список со словарями нечем — нормализация не должна падать."""
        document = {"tags": [{"name": "b"}, {"name": "a"}]}
        assert normalize(document) == document

    def test_scalars_pass_through(self):
        assert normalize("значение") == "значение"
        assert normalize(3) == 3
        assert normalize(None) is None

    @pytest.mark.parametrize(
        "value",
        [
            ["a", None],  # OpenAPI 3.1 разрешает enum с null
            [1, "a"],  # число рядом со строкой
            [True, "a", 2, None],  # всё сразу
        ],
    )
    def test_mixed_scalar_types_do_not_crash(self, value):
        """Голый sorted() падал бы TypeError — ровно на ручной правке контракта."""
        result = normalize({"enum": value})["enum"]
        assert sorted(map(repr, result)) == sorted(map(repr, value))

    def test_mixed_scalar_sorting_is_stable_across_input_order(self):
        """Нормализация обязана давать один результат независимо от исходного порядка."""
        assert normalize({"enum": ["a", None, 1]}) == normalize({"enum": [1, "a", None]})

    def test_empty_containers_survive(self):
        assert normalize({"enum": [], "parameters": [], "properties": {}}) == {
            "enum": [],
            "parameters": [],
            "properties": {},
        }

    def test_parameters_with_non_list_value_is_not_sorted(self):
        """`parameters: $ref` — не список; функция не должна пытаться его сортировать."""
        document = {"parameters": {"$ref": "#/components/parameters/Common"}}
        assert normalize(document) == document


class TestCollectDifferences:
    """Поиск и именование расхождений."""

    def test_identical_documents_have_no_differences(self):
        document = {"paths": {"/health/": {"get": {"operationId": "health"}}}}
        assert differences(document, document) == []

    def test_http_method_order_inside_path_is_not_a_difference(self):
        """Ровно тот недетерминизм drf-spectacular, из-за которого нельзя сравнивать текст."""
        from_code = {"paths": {"/x/": {"get": {"id": 1}, "post": {"id": 2}}}}
        from_file = {"paths": {"/x/": {"post": {"id": 2}, "get": {"id": 1}}}}
        assert differences(from_code, from_file) == []

    def test_field_missing_in_file_is_named_by_full_path(self):
        from_code = {"components": {"schemas": {"ProductDetail": {"properties": {"opt4_price": {"type": "string"}}}}}}
        from_file = {"components": {"schemas": {"ProductDetail": {"properties": {}}}}}
        found = differences(from_code, from_file)
        assert len(found) == 1
        location, description = found[0]
        assert location == "components.schemas.ProductDetail.properties.opt4_price"
        assert "отсутствует в openapi.yaml" in description

    def test_field_missing_in_code_is_reported(self):
        found = differences({"paths": {}}, {"paths": {"/legacy/": {}}})
        assert found == [("paths./legacy/", "есть в openapi.yaml, отсутствует в коде")]

    def test_changed_scalar_is_reported_with_both_values(self):
        found = differences({"info": {"version": "2.0.0"}}, {"info": {"version": "1.0.0"}})
        assert len(found) == 1
        location, description = found[0]
        assert location == "info.version"
        assert "2.0.0" in description and "1.0.0" in description

    def test_list_length_mismatch_is_reported_once(self):
        found = differences({"servers": ["a", "b"]}, {"servers": ["a"]})
        assert len(found) == 1
        assert "разная длина списка" in found[0][1]

    def test_list_element_difference_is_indexed(self):
        found = differences({"servers": [{"url": "a"}]}, {"servers": [{"url": "b"}]})
        assert found[0][0] == "servers[0].url"

    def test_type_change_is_a_difference(self):
        found = differences({"x": {"a": 1}}, {"x": [1]})
        assert len(found) == 1

    def test_several_differences_are_all_collected(self):
        from_code = {"a": 1, "b": 2, "c": 3}
        from_file = {"a": 9, "b": 8, "c": 3}
        assert len(differences(from_code, from_file)) == 2

    def test_non_string_keys_do_not_crash(self):
        """Незакавыченный код ответа YAML разбирает как int — сортировка ключей обязана это пережить."""
        found = differences({"responses": {200: {}, "default": {}}}, {"responses": {"200": {}, "default": {}}})
        assert len(found) == 2  # 200 (int) есть только в коде, '200' (str) — только в файле

    @pytest.mark.parametrize(
        "code_value,file_value",
        [
            (0, False),  # в Python 0 == False
            (1, True),
            (1, 1.0),  # и 1 == 1.0
        ],
    )
    def test_equal_but_differently_typed_scalars_are_differences(self, code_value, file_value):
        """Подмена типа значения меняет генерируемый TypeScript — пропускать её нельзя."""
        assert len(differences({"default": code_value}, {"default": file_value})) == 1

    def test_none_differs_from_missing_key(self):
        assert differences({"x": None}, {}) == [("x", "есть в коде, отсутствует в openapi.yaml")]

    def test_empty_documents_have_no_differences(self):
        assert differences({}, {}) == []

    def test_long_values_are_truncated_in_report(self):
        """Смена типа крупного узла не должна выкидывать в лог CI repr всего поддерева."""
        found = differences({"x": "a" * 5000}, {"x": "b" * 5000})
        assert len(found) == 1
        assert "обрезано" in found[0][1]
        assert len(found[0][1]) < 700


class TestCommandEarlyExits:
    """Отказы до генерации схемы — они должны быть внятными, а не traceback."""

    def test_missing_file_raises_command_error(self, tmp_path):
        missing = tmp_path / "нет-такого.yaml"
        with pytest.raises(CommandError) as exc:
            Command().handle(schema_file=str(missing))
        assert str(missing) in str(exc.value)
        assert "--schema-file" in str(exc.value)

    def test_non_mapping_yaml_raises_command_error(self, tmp_path):
        broken = tmp_path / "openapi.yaml"
        broken.write_text("- просто\n- список\n", encoding="utf-8")
        with pytest.raises(CommandError) as exc:
            Command().handle(schema_file=str(broken))
        assert "не является отображением YAML" in str(exc.value)

    def test_directory_instead_of_file_raises_command_error(self, tmp_path):
        with pytest.raises(CommandError):
            Command().handle(schema_file=str(tmp_path))

    def test_broken_yaml_raises_command_error_not_traceback(self, tmp_path):
        broken = tmp_path / "openapi.yaml"
        broken.write_text("paths:\n  - [незакрытая скобка\n", encoding="utf-8")
        with pytest.raises(CommandError) as exc:
            Command().handle(schema_file=str(broken))
        assert "не разбирается как YAML" in str(exc.value)

    def test_empty_yaml_raises_command_error(self, tmp_path):
        empty = tmp_path / "openapi.yaml"
        empty.write_text("", encoding="utf-8")
        with pytest.raises(CommandError) as exc:
            Command().handle(schema_file=str(empty))
        assert "не является отображением YAML" in str(exc.value)


class TestLoadSchema:
    def test_unreadable_file_raises_command_error(self, tmp_path):
        """`is_file()` проходит, а чтение падает — сообщение должно быть внятным."""
        path = tmp_path / "openapi.yaml"
        path.write_text("openapi: 3.1.0\n", encoding="utf-8")
        with mock.patch.object(type(path), "read_text", side_effect=OSError("отказано в доступе")):
            with pytest.raises(CommandError) as exc:
                load_schema(path)
        assert "Не удалось прочитать" in str(exc.value)


class TestHandleWithStubbedGeneration:
    """Полный путь команды без реальной генерации схемы — она стоит секунды."""

    def _run(self, tmp_path, committed, generated, **options):
        path = tmp_path / "openapi.yaml"
        path.write_text(yaml_dump(committed), encoding="utf-8")
        target = "apps.common.management.commands.check_openapi_sync.generate_schema"
        with mock.patch(target, return_value=generated):
            return Command().handle(schema_file=str(path), **options)

    def test_synchronous_contract_returns_without_error(self, tmp_path):
        document = {"openapi": "3.1.0", "paths": {"/health/": {"get": {"operationId": "health"}}}}
        assert self._run(tmp_path, document, document) is None

    def test_drift_raises_command_error(self, tmp_path):
        with pytest.raises(CommandError) as exc:
            self._run(tmp_path, {"info": {"version": "1.0.0"}}, {"info": {"version": "2.0.0"}})
        assert "не соответствует коду" in str(exc.value)
        assert "--validate" in str(exc.value)

    def test_report_truncates_to_limit(self, tmp_path, capsys):
        committed = {f"k{i}": i for i in range(30)}
        generated = {f"k{i}": i + 1 for i in range(30)}
        with pytest.raises(CommandError):
            self._run(tmp_path, committed, generated)
        printed = capsys.readouterr().out
        assert printed.count("  - k") == MAX_REPORTED_DIFFERENCES
        assert f"и ещё {30 - MAX_REPORTED_DIFFERENCES}" in printed

    def test_limit_zero_prints_everything(self, tmp_path, capsys):
        committed = {f"k{i}": i for i in range(30)}
        generated = {f"k{i}": i + 1 for i in range(30)}
        with pytest.raises(CommandError):
            self._run(tmp_path, committed, generated, limit=0)
        printed = capsys.readouterr().out
        assert printed.count("  - k") == 30
        assert "и ещё" not in printed

    def test_missing_limit_option_does_not_crash(self, tmp_path):
        """Команду вызывают напрямую из тестов, минуя argparse — ключа `limit` тогда нет."""
        with pytest.raises(CommandError) as exc:
            self._run(tmp_path, {"a": 1}, {"a": 2})
        assert "не соответствует коду" in str(exc.value)

    def test_empty_generated_schema_raises_command_error(self, tmp_path):
        path = tmp_path / "openapi.yaml"
        path.write_text(yaml_dump({"openapi": "3.1.0"}), encoding="utf-8")
        target = "apps.common.management.commands.check_openapi_sync.call_command"
        with mock.patch(target):  # spectacular «отработал», но файла не создал
            with pytest.raises(CommandError) as exc:
                Command().handle(schema_file=str(path))
        assert "Не удалось прочитать" in str(exc.value) or "пустой результат" in str(exc.value)

    def test_generation_failure_is_explained(self, tmp_path):
        path = tmp_path / "openapi.yaml"
        path.write_text(yaml_dump({"openapi": "3.1.0"}), encoding="utf-8")
        target = "apps.common.management.commands.check_openapi_sync.call_command"
        with mock.patch(target, side_effect=RuntimeError("дублирующийся operationId")):
            with pytest.raises(CommandError) as exc:
                Command().handle(schema_file=str(path))
        assert "Не удалось построить схему из кода" in str(exc.value)
        assert "не рассинхрон контракта" in str(exc.value)


class TestDefaultSchemaPath:
    def test_points_at_repository_docs(self):
        path = default_schema_path()
        assert path.parts[-3:] == ("docs", "api", "openapi.yaml")
