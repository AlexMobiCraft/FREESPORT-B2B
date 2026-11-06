"""Сверка `docs/api/openapi.yaml` со схемой, которую drf-spectacular строит из кода.

Зачем: файл контракта и сгенерированные из него TS-типы коммитятся, но ничем не
проверяются — рассинхрон не даёт ни ошибки сборки, ни красного CI. Эта команда делает
рассинхрон видимым: она строит схему из текущих сериализаторов и вью и сравнивает её
с закоммиченным файлом.

Сравниваются **разобранные структуры**, а не текст. drf-spectacular недетерминирован в
порядке HTTP-методов внутри пути, поэтому побайтовое сравнение давало бы ложные падения.
Равенство словарей Python к порядку ключей нечувствительно по построению, а списки, чей
порядок в OpenAPI семантически не значим, приводятся к канону функцией `normalize`.

Подробности решения — `_bmad-output/planning-artifacts/tech-debt.md`, пункт 20.
"""

import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

# Списки скаляров, для которых порядок в OpenAPI ничего не означает.
UNORDERED_SCALAR_KEYS = ("tags", "required", "enum")

# Сколько расхождений печатать, прежде чем свернуть вывод. При дрейфе всей схемы список
# иначе занимает экраны и прячет первое — самое информативное — расхождение.
MAX_REPORTED_DIFFERENCES = 20

# Предел длины значения в отчёте. Без него смена типа крупного узла выкидывает в лог CI
# repr целого поддерева — одной строкой, ровно тогда, когда лог нужно читать.
MAX_VALUE_REPR = 200


def _sort_key(value):
    """Ключ сортировки, устойчивый к разнотипным элементам.

    OpenAPI 3.1 допускает `enum: [..., null]`, а незакавыченный код ответа YAML разбирает
    как `int`. Голый `sorted()` на таких списках падает `TypeError`, то есть команда
    рушилась бы traceback'ом ровно в том случае, ради которого написана, — при ручной
    правке контракта. Имя типа в ключе даёт полный порядок на любой смеси значений.
    """
    return (type(value).__name__, str(value))


def _short(value):
    """Repr значения, урезанный до читаемой длины."""
    text = repr(value)
    if len(text) <= MAX_VALUE_REPR:
        return text
    return f"{text[:MAX_VALUE_REPR]}… (обрезано, всего {len(text)} символов)"


def _all_scalar(items):
    """Все ли элементы списка — скаляры (сортировать можно только такие)."""
    return all(not isinstance(item, (dict, list)) for item in items)


def _parameter_sort_key(parameter):
    """Ключ упорядочивания для элемента `parameters` — списка словарей."""
    if isinstance(parameter, dict):
        return (
            str(parameter.get("in", "")),
            str(parameter.get("name", "")),
            str(parameter.get("$ref", "")),
        )
    return ("", "", str(parameter))


def _normalize_value(key, value):
    """Нормализует значение с учётом имени ключа, под которым оно лежит."""
    if isinstance(value, list):
        if key in UNORDERED_SCALAR_KEYS and _all_scalar(value):
            return sorted(value, key=_sort_key)
        if key == "parameters":
            return sorted((normalize(item) for item in value), key=_parameter_sort_key)
    return normalize(value)


def normalize(node):
    """Приводит документ к виду, в котором сравнение не зависит от незначимого порядка."""
    if isinstance(node, dict):
        return {key: _normalize_value(key, value) for key, value in node.items()}
    if isinstance(node, list):
        return [normalize(item) for item in node]
    return node


def collect_differences(from_code, from_file, path=""):
    """Расхождения между схемой из кода и содержимым файла.

    Возвращает генератор пар `(путь_в_документе, описание)`. Путь именует конкретное
    место — например `components.schemas.ProductDetail.properties.opt4_price`, — потому что
    сообщение «файлы отличаются» не помогает понять, что именно забыли перегенерировать.
    """
    if isinstance(from_code, dict) and isinstance(from_file, dict):
        for key in sorted(set(from_code) | set(from_file), key=_sort_key):
            child = f"{path}.{key}" if path else str(key)
            if key not in from_file:
                yield (child, "есть в коде, отсутствует в openapi.yaml")
            elif key not in from_code:
                yield (child, "есть в openapi.yaml, отсутствует в коде")
            else:
                yield from collect_differences(from_code[key], from_file[key], child)
    elif isinstance(from_code, list) and isinstance(from_file, list):
        if len(from_code) != len(from_file):
            yield (path, f"разная длина списка: в коде {len(from_code)}, в файле {len(from_file)}")
        else:
            for index, (code_item, file_item) in enumerate(zip(from_code, from_file)):
                yield from collect_differences(code_item, file_item, f"{path}[{index}]")
    # Тип сверяется отдельно от значения: в Python `False == 0` и `1 == 1.0`, поэтому
    # голое `!=` пропустило бы подмену булева значения числовым — а `openapi-typescript`
    # сгенерирует по ним разный TypeScript.
    elif type(from_code) is not type(from_file) or from_code != from_file:
        yield (path, f"значения различаются: в коде {_short(from_code)}, в файле {_short(from_file)}")


def default_schema_path():
    """Штатное расположение файла контракта относительно корня репозитория."""
    return Path(settings.BASE_DIR).parent / "docs" / "api" / "openapi.yaml"


def load_schema(path):
    """Читает и разбирает YAML-документ, переводя любой отказ в `CommandError`.

    Без этого битый YAML или нечитаемый файл дают traceback парсера, тогда как команда
    обязана объяснять человеку, что именно не так с его контрактом.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CommandError(f"Не удалось прочитать файл контракта {path}: {exc}") from exc

    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise CommandError(f"Файл контракта не разбирается как YAML: {path}\n{exc}") from exc


def generate_schema():
    """Строит схему из текущего кода тем же путём, что и `manage.py spectacular`."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        target = Path(tmp_dir) / "schema.yaml"
        try:
            # --validate сохраняет проверку, которая раньше жила отдельным шагом backend-ci.yml.
            call_command("spectacular", "--file", str(target), "--format", "openapi", "--validate")
        except CommandError:
            raise
        except Exception as exc:  # noqa: BLE001 — любой отказ генерации нужно объяснить человеком
            raise CommandError(
                f"Не удалось построить схему из кода ({type(exc).__name__}): {exc}\n"
                "Это отказ самой генерации, а не рассинхрон контракта: чините сериализаторы "
                "и вью, регенерация файла тут не поможет."
            ) from exc

        generated = load_schema(target)

    if not isinstance(generated, dict):
        raise CommandError("Генерация схемы дала пустой результат — сверять нечего.")
    return generated


class Command(BaseCommand):
    """Management-команда сверки контракта API с кодом."""

    help = "Сверяет docs/api/openapi.yaml со схемой, построенной из текущего кода"

    def add_arguments(self, parser):
        parser.add_argument(
            "--schema-file",
            default=None,
            help=(
                "Путь к файлу контракта. По умолчанию docs/api/openapi.yaml от корня "
                "репозитория. Задавать явно нужно там, где смонтирован только backend/ "
                "(тестовый контейнер)."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=MAX_REPORTED_DIFFERENCES,
            help=(
                f"Сколько расхождений напечатать (по умолчанию {MAX_REPORTED_DIFFERENCES}); "
                "0 или отрицательное — все."
            ),
        )

    def handle(self, *args, **options):
        schema_file = options.get("schema_file")
        schema_path = Path(schema_file) if schema_file else default_schema_path()

        if not schema_path.is_file():
            raise CommandError(
                f"Файл контракта не найден: {schema_path}\n"
                "Укажите путь через --schema-file. В тестовом контейнере смонтирован только "
                "backend/, поэтому docs/api/openapi.yaml туда не попадает."
            )

        committed = load_schema(schema_path)
        if not isinstance(committed, dict):
            raise CommandError(f"Файл контракта не является отображением YAML: {schema_path}")

        self.stdout.write("Генерация схемы из текущего кода...")
        generated = generate_schema()

        differences = list(collect_differences(normalize(generated), normalize(committed)))

        if not differences:
            self.stdout.write(self.style.SUCCESS(f"Контракт синхронен с кодом: {schema_path}"))
            return

        # .get: команду вызывают и напрямую из тестов, минуя argparse, — тогда ключа нет.
        self._report(schema_path, differences, options.get("limit", MAX_REPORTED_DIFFERENCES))

    def _report(self, schema_path, differences, limit):
        """Печатает расхождения и завершает команду ошибкой."""
        self.stdout.write(self.style.ERROR(f"Контракт разошёлся с кодом ({len(differences)} расхождений):"))

        shown = differences if limit <= 0 else differences[:limit]
        for location, description in shown:
            self.stdout.write(f"  - {location or '<корень документа>'}: {description}")

        hidden = len(differences) - len(shown)
        if hidden > 0:
            self.stdout.write(f"  ... и ещё {hidden} (показать все — --limit 0)")

        raise CommandError(
            f"{schema_path} не соответствует коду. Перегенерируйте контракт и типы фронта:\n"
            "  python manage.py spectacular --file ../docs/api/openapi.yaml --format openapi --validate\n"
            "  cd frontend && npm run generate:types\n"
            "Флаг --validate обязателен: гейт генерирует схему именно с ним, и без него "
            "локально будет чисто, а в CI — падение на валидации."
        )
