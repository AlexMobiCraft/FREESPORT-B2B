"""Стори 41.5: заголовки безопасности объявлены во всех локациях nginx.

Дефект FR-41-22: `add_header` внутри `location` **заменяет** унаследованный
набор, а не дополняет его. Как только в локации появляется хоть одна собственная
директива `add_header` (например `Cache-Control`), весь серверный набор
пропадает целиком — так `/static/`, `/media/`, картинки товаров и `/health`
отдавались без `X-Content-Type-Options: nosniff`.

Отсюда инвариант, который здесь закрепляется: **любая локация, объявляющая
собственный `add_header`, обязана переобъявить набор через `include` сниппета**
(единственное исключение — `location /`, у которого заголовками владеет
апстрим Next, см. ``_UPSTREAM_OWNED_LOCATIONS``).

.. warning::
   Все проверки этого файла читают **текст конфигурации** и доказывают только
   «объявлено», а не «доехало до клиента». Проверка «доехало» — это живой замер
   заголовков с работающих контейнеров (AC13 стори 41.5). Подмена одного другим
   в стори 41.0 трижды становилась находкой ревью.
"""

import re
from pathlib import Path

import pytest

# В тестовом контейнере смонтирован только backend/ (как /app), а каталог docker/
# подключается отдельным volume в /app/docker. В CI и локальном venv pytest
# стартует из backend/ полного checkout — там конфиги лежат на уровень выше.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_NGINX_DIR_CANDIDATES = (
    _BACKEND_ROOT / "docker" / "nginx",
    _BACKEND_ROOT.parent / "docker" / "nginx",
)


def _nginx_dir() -> Path | None:
    for candidate in _NGINX_DIR_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


nginx_dir = _nginx_dir()

pytestmark = pytest.mark.skipif(
    nginx_dir is None,
    reason=("docker/nginx недоступен из этого окружения " f"(искали в {[str(p) for p in _NGINX_DIR_CANDIDATES]})"),
)

# Три плоских сниппета — единственный источник набора заголовков.
SNIPPETS = ("security-headers.conf", "security-headers-no-hsts.conf", "app-headers.conf")

# frame-ancestors — единственная директива CSP, которой сниппетам разрешено
# различаться: 'self' там, где ответ отдаёт сайт, 'none' на локациях Django
# (согласовано с `X_FRAME_OPTIONS = "DENY"`).
EXPECTED_FRAME_ANCESTORS = {
    "security-headers.conf": "'self'",
    "security-headers-no-hsts.conf": "'self'",
    "app-headers.conf": "'none'",
}

# Vhost'ы вне объёма заголовков безопасности. Список ЯВНЫЙ, а не правило
# «пропускать блоки с return»: последнее заодно замаскировало бы `/media/1c_temp/`,
# который обязан получать заголовки на своём 404.
EXCLUDED_VHOSTS = {
    "5.35.124.149 localhost freesport.local optisport.ru www.optisport.ru": (
        "HTTP→HTTPS редирект: отвечает 301 без тела сайта"
    ),
    "freesport.ru www.freesport.ru": (
        "выведенный из эксплуатации домен: 410 Gone без тела сайта; "
        "add_header Content-Type там — не заголовок безопасности"
    ),
}

# Локации, у которых заголовками владеет апстрим, а nginx добавляет ровно один
# заголовок, которого апстрим не выставляет. Их собственный `add_header`
# намеренно вытесняет серверный набор — иначе каждый заголовок пришёл бы дважды.
_UPSTREAM_OWNED_LOCATIONS = {
    # location / → Next.js. Весь набор ставит frontend/next.config.ts,
    # nginx добавляет только HSTS: TLS терминируется на нём, Next о нём не знает.
    "/": {"Strict-Transport-Security"},
    # Тот же апстрим, то же правило. Без собственного add_header локация
    # наследовала серверный набор и задваивала его с заголовками Next.
    "/_next/webpack-hmr": {"Strict-Transport-Security"},
}


def _strip_comments(text: str) -> str:
    """Убрать комментарии: в них слова `add_header` и `include` встречаются часто."""
    return "\n".join(line.split("#", 1)[0] for line in text.split("\n"))


def _matching_brace(text: str, opening: int) -> int:
    depth = 0
    for pos in range(opening, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return pos
    raise AssertionError(f"Не закрыта скобка, открытая на позиции {opening}")


def _server_blocks(content: str) -> list[tuple[str, str]]:
    """[(server_name, тело vhost без внешних скобок)] по всему конфигу."""
    blocks: list[tuple[str, str]] = []
    for match in re.finditer(r"(?m)^\s*server\s*\{", content):
        opening = content.index("{", match.start())
        closing = _matching_brace(content, opening)
        body = content[opening + 1 : closing]
        name_match = re.search(r"(?m)^\s*server_name\s+([^;]+);", body)
        blocks.append((name_match.group(1).strip() if name_match else "", body))
    return blocks


def _location_blocks(body: str) -> list[tuple[str, str]]:
    """[(аргумент location, собственное тело без вложенных location)] — рекурсивно."""
    found: list[tuple[str, str]] = []
    for match in re.finditer(r"(?m)^\s*location\s+([^{]+?)\s*\{", body):
        opening = body.index("{", match.start())
        closing = _matching_brace(body, opening)
        inner = body[opening + 1 : closing]
        nested = _location_blocks(inner)
        own = inner
        # Убрать тела вложенных локаций: их директивы принадлежат им, не родителю
        for _, nested_body in nested:
            own = own.replace(nested_body, "", 1)
        found.append((match.group(1).strip(), own))
        found.extend(nested)
    return found


def _directive_values(text: str, directive: str) -> list[str]:
    """Аргументы директивы до завершающей `;`, с учётом кавычек.

    Наивный `[^;]+` здесь неприменим: точка с запятой встречается ВНУТРИ значений
    (`X-XSS-Protection "1; mode=block"`, CSP с несколькими директивами), и разбор
    обрывался бы на середине значения.
    """
    values: list[str] = []
    for match in re.finditer(rf"(?m)^[ \t]*{directive}[ \t]+", text):
        pos = match.end()
        quote: str | None = None
        while pos < len(text):
            char = text[pos]
            if quote is not None:
                if char == quote:
                    quote = None
            elif char in "\"'":
                quote = char
            elif char == ";":
                break
            pos += 1
        values.append(text[match.end() : pos].strip())
    return values


def _header_names(text: str) -> list[str]:
    return [m.group(1) for m in re.finditer(r"(?m)^\s*add_header\s+([\w-]+)", text)]


def _snippet_header_value(snippet_text: str, header: str) -> str | None:
    match = re.search(rf'(?m)^\s*add_header\s+{re.escape(header)}\s+"([^"]*)"', snippet_text)
    return match.group(1) if match else None


def _read(*parts: str) -> str:
    assert nginx_dir is not None  # skipif уже отсеял None
    return _strip_comments(nginx_dir.joinpath(*parts).read_text(encoding="utf-8"))


class TestSnippetsExist:
    """Сниппеты — единственный источник набора; без них конфиг не стартует."""

    @pytest.mark.parametrize("snippet", SNIPPETS)
    def test_snippet_file_exists(self, snippet: str) -> None:
        assert nginx_dir is not None
        path = nginx_dir / "snippets" / snippet
        assert path.is_file(), (
            f"Нет {path}. Конфиги подключают его через include — " "nginx упадёт на старте с open() ... failed."
        )


class TestSnippetContent:
    """Состав каждого сниппета: флаг always и полнота набора."""

    @pytest.mark.parametrize("snippet", SNIPPETS)
    def test_every_add_header_is_always(self, snippet: str) -> None:
        """Без `always` заголовки не доходят на ответы вне 200/204/301/302/304.

        Под `/media/` живут `return 404` (1c_temp, 1c_import) и `deny all`
        (php|py|pl|sh) — именно там заголовки нужнее всего.
        """
        content = _read("snippets", snippet)
        without_always = [value for value in _directive_values(content, "add_header") if not value.endswith("always")]

        assert not without_always, f"{snippet}: add_header без флага always: {without_always}"

    @pytest.mark.parametrize("snippet", SNIPPETS)
    def test_x_xss_protection_present(self, snippet: str) -> None:
        """`X-XSS-Protection` обязан быть во ВСЕХ трёх сниппетах.

        Единственный источник этого заголовка — nginx: `SECURE_BROWSER_XSS_FILTER`
        в Django мёртв (заголовок не отдаётся с версии 4.0). Локация с собственным
        `add_header` теряет его вместе со всем унаследованным набором и молча
        остаётся без него — это нарушило бы AC12 стори 41.5.
        """
        content = _read("snippets", snippet)

        assert "X-XSS-Protection" in _header_names(content), (
            f"{snippet}: нет X-XSS-Protection. Локации, подключающие этот сниппет, "
            "потеряют заголовок, который получают сегодня."
        )

    def test_csp_differs_only_in_frame_ancestors(self) -> None:
        """Плата за отказ от вложенных include: три CSP сверяются между собой."""
        policies = {
            snippet: _snippet_header_value(_read("snippets", snippet), "Content-Security-Policy")
            for snippet in SNIPPETS
        }

        for snippet, policy in policies.items():
            assert policy, f"{snippet}: нет add_header Content-Security-Policy"
            expected = EXPECTED_FRAME_ANCESTORS[snippet]
            assert f"frame-ancestors {expected}" in policy, (
                f"{snippet}: ожидался frame-ancestors {expected}, политика: {policy}. "
                "Значение обязано быть согласовано с X-Frame-Options той же поверхности: "
                "рассогласование молча меняет фактическую политику встраивания."
            )

        # Всё, кроме frame-ancestors, обязано совпадать посимвольно
        def without_frame_ancestors(policy: str) -> str:
            return re.sub(r"\s*;?\s*frame-ancestors\s+[^;]+", "", policy).strip()

        normalized = {snippet: without_frame_ancestors(policy or "") for snippet, policy in policies.items()}
        assert len(set(normalized.values())) == 1, (
            f"CSP расходятся не только во frame-ancestors: {normalized}. "
            "Это тихое ужесточение или ослабление политики мимо AC4."
        )

    def test_permissions_policy_identical_and_without_interest_cohort(self) -> None:
        values = {
            snippet: _snippet_header_value(_read("snippets", snippet), "Permissions-Policy") for snippet in SNIPPETS
        }

        for snippet, value in values.items():
            assert value, f"{snippet}: нет add_header Permissions-Policy"
            assert "interest-cohort" not in value, (
                f"{snippet}: interest-cohort снят из Chrome 115+ и даёт " "Unrecognized feature в консоли браузера."
            )

        assert len(set(values.values())) == 1, f"Permissions-Policy расходятся между сниппетами: {values}"

    def test_hsts_only_where_tls_exists(self) -> None:
        """Версия no-hsts обязана оставаться без HSTS, остальные две — с ним."""
        assert "Strict-Transport-Security" not in _header_names(_read("snippets", "security-headers-no-hsts.conf")), (
            "security-headers-no-hsts.conf существует ровно ради отсутствия HSTS: "
            "он подключается там, где TLS нет (внутренний vhost, local.conf)."
        )
        for snippet in ("security-headers.conf", "app-headers.conf"):
            assert "Strict-Transport-Security" in _header_names(_read("snippets", snippet)), f"{snippet}: пропал HSTS"


class TestLocationsReDeclareHeaders:
    """Главный страж: локация со своим add_header обязана подключить сниппет."""

    @pytest.mark.parametrize("conf_name", ["default.conf", "local.conf"])
    def test_location_with_own_add_header_includes_snippet(self, conf_name: str) -> None:
        content = _read("conf.d", conf_name)
        offenders: list[str] = []

        for server_name, body in _server_blocks(content):
            if server_name in EXCLUDED_VHOSTS:
                continue
            for location, own_body in _location_blocks(body):
                headers = _header_names(own_body)
                if not headers:
                    # Своих add_header нет → набор наследуется, include не нужен
                    continue
                includes = _directive_values(own_body, "include")
                if any("snippets/" in value for value in includes):
                    continue
                allowed = _UPSTREAM_OWNED_LOCATIONS.get(location)
                if allowed is not None and set(headers) <= allowed:
                    continue
                offenders.append(f"server_name={server_name!r} location {location} → add_header {headers}")

        assert not offenders, (
            f"{conf_name}: локации объявляют свой add_header, но не подключают сниппет — "
            "унаследованный набор заголовков безопасности в них теряется целиком "
            f"(это и есть дефект FR-41-22):\n  " + "\n  ".join(offenders)
        )

    @pytest.mark.parametrize(
        "conf_name,location",
        [
            ("default.conf", "/static/"),
            ("default.conf", "/media/"),
            ("default.conf", "/health"),
            ("default.conf", "/api/"),
            ("default.conf", "/admin/"),
            ("default.conf", "/swagger/"),
            ("default.conf", "/redoc/"),
            ("local.conf", "/static/"),
            ("local.conf", "/media/"),
            ("local.conf", "/health"),
        ],
    )
    def test_known_location_is_covered(self, conf_name: str, location: str) -> None:
        """Поимённо: локации, ради которых стори и делалась, не должны исчезнуть.

        Предыдущий тест молчит, если локацию просто удалить или лишить своего
        `add_header`; здесь фиксируется, что она есть и сниппет подключён.
        """
        content = _read("conf.d", conf_name)
        covered = [
            own_body
            for server_name, body in _server_blocks(content)
            if server_name not in EXCLUDED_VHOSTS
            for loc, own_body in _location_blocks(body)
            if loc == location
        ]

        assert covered, f"{conf_name}: локация {location} исчезла из конфига"
        # Именно `all`, а не `any`: одно и то же имя локации встречается в разных
        # vhost'ах одного файла (`/media/` есть и в HTTPS-, и во внутреннем
        # vhost `server_name nginx`). С `any` покрытый экземпляр маскировал бы
        # непокрытый — ровно та ошибка, которую разбирала стори 36.1.
        uncovered = [
            index
            for index, own_body in enumerate(covered)
            if not any("snippets/" in value for value in _directive_values(own_body, "include"))
        ]
        assert not uncovered, (
            f"{conf_name}: экземпляр(ы) локации {location} №{uncovered} из {len(covered)} "
            "не подключают ни одного сниппета заголовков"
        )


class TestUpstreamOwnedLocations:
    """Локации, проксируемые в Next: набор ставит апстрим, nginx — только HSTS."""

    @pytest.mark.parametrize("location", sorted(_UPSTREAM_OWNED_LOCATIONS))
    def test_declares_own_header_and_no_snippet(self, location: str) -> None:
        """Отсутствие своего `add_header` здесь — не «чисто», а дефект.

        Предыдущий страж пропускает локацию без единого `add_header`: она
        наследует серверный набор, и для того, что nginx отдаёт сам, это
        правильно. Но эти локации отдаёт Next, который ставит набор сам, —
        унаследованное от сервера складывается с ним, и каждый заголовок
        приходит дважды. Ровно так задваивал `/_next/webpack-hmr`.
        """
        allowed = _UPSTREAM_OWNED_LOCATIONS[location]
        content = _read("conf.d", "default.conf")
        instances = [
            own_body
            for server_name, body in _server_blocks(content)
            if server_name not in EXCLUDED_VHOSTS
            for loc, own_body in _location_blocks(body)
            if loc == location
        ]

        assert instances, f"default.conf: локация {location} исчезла из конфига"

        for index, own_body in enumerate(instances):
            headers = set(_header_names(own_body))
            assert headers == allowed, (
                f"default.conf: локация {location} №{index} объявляет add_header {sorted(headers)}, "
                f"ожидалось ровно {sorted(allowed)}. Пустой набор означает, что локация "
                "наследует серверный и задваивает заголовки с апстримом; лишний — "
                "что тот же заголовок придёт и от nginx, и от Next."
            )
            includes = _directive_values(own_body, "include")
            assert not any("snippets/" in value for value in includes), (
                f"default.conf: локация {location} №{index} подключает сниппет. "
                "Здесь он не нужен и приведёт к дублированию: набор ставит апстрим."
            )


class TestSnippetsMounted:
    """Каталог сниппетов обязан попасть в контейнер: nginx монтируется пофайлово."""

    @pytest.mark.parametrize("compose_name", ["docker-compose.yml", "docker-compose.prod.yml"])
    def test_snippets_directory_is_mounted(self, compose_name: str) -> None:
        assert nginx_dir is not None
        compose_path = nginx_dir.parent / compose_name
        assert compose_path.is_file(), f"Не найден {compose_path}"

        content = compose_path.read_text(encoding="utf-8")

        assert "./nginx/snippets:/etc/nginx/snippets" in content, (
            f"{compose_name}: не смонтирован ./nginx/snippets. Каталога conf.d целиком "
            "в монтировании нет — без отдельного пункта nginx упадёт на старте с "
            'open() "/etc/nginx/snippets/..." failed.'
        )
