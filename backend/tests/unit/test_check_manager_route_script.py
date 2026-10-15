"""
Скрипты HTTP-проверки раздела `/manager/` (`scripts/deploy/`).

По коду завершения `check-manager-route.sh` решается, прошли ли шаг `main.yml`
и проверка production после деплоя (`deploy.yml`); `check-manager-session.sh`
гоняет только `main.yml`. Тест запускает скрипты против локального
HTTP-сервера с заданными ответами:

- маршрут: успех — только 302 ровно на страницу входа и полностью полученная
  страница входа с кодом 200 (R42.4-15);
- вход менеджера: в CI приложение исправно, свой клиент в списке есть, а
  чужого нет, поэтому отказ скрипта на чужом клиенте (R42.4-20), на списке
  без своего (R42.4-30) и на оборванном списке (R42.4-37) проверяется здесь;
  форма входа уходит с Origin и Referer, как из браузера (R42.4-36).
"""

from __future__ import annotations

import shutil
import subprocess
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator, NamedTuple, Union
from urllib.parse import parse_qs

import pytest

# В тестовом контейнере scripts/ смонтирован в /app/scripts, в CI и venv
# pytest стартует из backend/ полного checkout — скрипт на уровень выше.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIRS = (_BACKEND_ROOT / "scripts" / "deploy", _BACKEND_ROOT.parent / "scripts" / "deploy")
_SCRIPT_DIR = next((path for path in _SCRIPT_DIRS if (path / "check-manager-route.sh").is_file()), None)
SCRIPT = _SCRIPT_DIR / "check-manager-route.sh" if _SCRIPT_DIR else None
SESSION_SCRIPT = _SCRIPT_DIR / "check-manager-session.sh" if _SCRIPT_DIR else None

pytestmark = pytest.mark.skipif(
    _SCRIPT_DIR is None or shutil.which("bash") is None or shutil.which("curl") is None,
    reason=f"нужны bash, curl и скрипты (искали в {[str(p) for p in _SCRIPT_DIRS]})",
)


class Reply(NamedTuple):
    status: int
    headers: dict[str, str]
    body: bytes = b""
    # Объявленная длина тела; None — настоящая. Больше настоящей — ответ
    # обрывается: сервер закрывает соединение, не дослав тело.
    content_length: int | None = None


class Request(NamedTuple):
    cookie: str
    form: dict[str, list[str]]
    origin: str = ""
    referer: str = ""
    # Адрес сервера, как его видит клиент: http://<Host>.
    base_url: str = ""


# Ответ на путь: готовый или вычисляемый по Cookie и полям формы запроса.
Route = Union[Reply, Callable[[Request], Reply]]


LOGIN_PAGE = b'<html><body><form id="login-form" method="post" action="/manager/login/"></form></body></html>'
TO_LOGIN = Reply(302, {"Location": "/manager/login/?next=/manager/"})
LOGIN_OK = Reply(200, {"Content-Type": "text/html"}, LOGIN_PAGE)


@contextmanager
def serve(routes: dict[str, Route]) -> Iterator[str]:
    """HTTP-сервер на свободном порту; ключ GET — путь, POST — `POST <путь>`; неизвестный — 404."""

    class Handler(BaseHTTPRequestHandler):
        # HTTP/1.0: соединение закрывается после ответа, оборванное тело curl замечает.
        def do_GET(self) -> None:
            self.reply(self.raw_path(), {})

        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0))).decode()
            self.reply(f"POST {self.raw_path()}", parse_qs(body))

        def raw_path(self) -> str:
            # self.path Python 3.12 схлопывает «//» в начале — путь берётся как прислан.
            return self.requestline.split()[1]

        def reply(self, key: str, form: dict[str, list[str]]) -> None:
            route = routes.get(key, Reply(404, {}))
            request = Request(
                self.headers.get("Cookie", ""),
                form,
                self.headers.get("Origin", ""),
                self.headers.get("Referer", ""),
                f"http://{self.headers.get('Host', '')}",
            )
            reply = route if isinstance(route, Reply) else route(request)
            self.send_response(reply.status)
            for name, value in reply.headers.items():
                self.send_header(name, value)
            length = len(reply.body) if reply.content_length is None else reply.content_length
            self.send_header("Content-Length", str(length))
            self.end_headers()
            self.wfile.write(reply.body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=10)


def run_script(routes: dict[str, Reply], suffix: str = "") -> subprocess.CompletedProcess[str]:
    with serve(routes) as base_url:
        return subprocess.run(
            ["bash", str(SCRIPT), base_url + suffix], capture_output=True, text=True, encoding="utf-8", timeout=120
        )


# Базовый URL со слэшем на конце — тот же адрес (R42.4-33).
@pytest.mark.parametrize("suffix", ["", "/"], ids=["plain", "trailing-slash"])
def test_section_routed_to_django_passes(suffix):
    result = run_script({"/manager/": TO_LOGIN, "/manager/login/": LOGIN_OK}, suffix)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "✅" in result.stdout


@pytest.mark.parametrize(
    "routes",
    [
        # Страница входа оборвана: curl завершается с ошибкой 18, хотя форма уже пришла.
        pytest.param(
            {"/manager/": TO_LOGIN, "/manager/login/": LOGIN_OK._replace(content_length=9999)},
            id="login-body-truncated",
        ),
        # Форма входа в теле, но код не 200.
        pytest.param(
            {"/manager/": TO_LOGIN, "/manager/login/": Reply(302, {"Location": "/manager/login/"}, LOGIN_PAGE)},
            id="login-302-with-form",
        ),
        pytest.param(
            {"/manager/": TO_LOGIN, "/manager/login/": Reply(200, {}, b"<html>Next.js</html>")},
            id="login-without-form",
        ),
        pytest.param(
            {"/manager/": TO_LOGIN._replace(content_length=9999, body=b"x"), "/manager/login/": LOGIN_OK},
            id="redirect-truncated",
        ),
        pytest.param(
            {"/manager/": Reply(302, {"Location": "/admin/login/?next=/admin/"}), "/manager/login/": LOGIN_OK},
            id="redirect-elsewhere",
        ),
        pytest.param({"/manager/login/": LOGIN_OK}, id="section-404"),
    ],
)
def test_broken_route_fails(routes):
    result = run_script(routes)

    assert result.returncode != 0, result.stdout
    assert "❌" in result.stdout
    assert "✅" not in result.stdout


MANAGER = ("manager@example.com", "manager-pass")
OWN_EMAIL = "own-client@example.com"
FOREIGN_EMAIL = "foreign-client@example.com"
CSRF = "csrf-token-value"
SESSION = "sessionid=manager-session"


def session_routes(changelist_emails: list[str]) -> dict[str, Route]:
    """Вход Django: форма с CSRF, POST ставит сессию, список без сессии — на вход.

    POST входа без Origin и Referer своего сайта — 403, как у production-настроек
    за HTTPS-прокси (`SECURE_PROXY_SSL_HEADER`): Django сверяет их с адресом
    сайта, и вход формой без них не проходит (R42.4-36).
    """

    def login(request: Request) -> Reply:
        if request.origin != request.base_url or request.referer != f"{request.base_url}/manager/login/":
            return Reply(403, {"Content-Type": "text/html"}, b"<html>CSRF verification failed</html>")
        sent = (request.form.get("csrfmiddlewaretoken"), request.form.get("username"), request.form.get("password"))
        if sent != ([CSRF], [MANAGER[0]], [MANAGER[1]]):
            return Reply(200, {"Content-Type": "text/html"}, b"<html>error</html>")
        return Reply(302, {"Location": "/manager/", "Set-Cookie": f"{SESSION}; Path=/"})

    def changelist(request: Request) -> Reply:
        if SESSION not in request.cookie:
            return Reply(302, {"Location": "/manager/login/?next=/manager/users/user/"})
        rows = "".join(f"<tr><td>{email}</td></tr>" for email in changelist_emails)
        return Reply(200, {"Content-Type": "text/html"}, f"<table>{rows}</table>".encode())

    form = f'<form id="login-form"><input type="hidden" name="csrfmiddlewaretoken" value="{CSRF}"></form>'
    return {
        "/manager/login/": Reply(200, {"Content-Type": "text/html"}, form.encode()),
        "POST /manager/login/": login,
        "/manager/users/user/": changelist,
    }


def run_session_script(routes: dict[str, Route], suffix: str = "") -> subprocess.CompletedProcess[str]:
    with serve(routes) as base_url:
        return subprocess.run(
            ["bash", str(SESSION_SCRIPT), base_url + suffix, *MANAGER, OWN_EMAIL, FOREIGN_EMAIL],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=120,
        )


@pytest.mark.parametrize("suffix", ["", "/"], ids=["plain", "trailing-slash"])
def test_session_with_own_client_only_passes(suffix):
    """Положительный контроль: вход проходит, в списке только свой клиент; слэш в конце URL не мешает (R42.4-33)."""
    result = run_session_script(session_routes([OWN_EMAIL]), suffix)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "✅" in result.stdout


def test_session_with_foreign_client_fails():
    """Вход и список в порядке, но в списке и чужой клиент — скрипт обязан упасть (R42.4-20)."""
    result = run_session_script(session_routes([OWN_EMAIL, FOREIGN_EMAIL]))

    assert result.returncode != 0, result.stdout
    assert f"клиент другого менеджера {FOREIGN_EMAIL}" in result.stdout
    assert "✅" not in result.stdout


def test_session_without_own_client_fails():
    """Пустой список: чужого клиента нет, но и своего — скрипт обязан упасть (R42.4-30)."""
    result = run_session_script(session_routes([]))

    assert result.returncode != 0, result.stdout
    assert f"нет клиента менеджера {OWN_EMAIL}" in result.stdout
    assert "✅" not in result.stdout


def test_session_with_truncated_changelist_fails():
    """Список оборван после своего клиента: чужой мог остаться в недополученной части (R42.4-37).

    HTTP 200 и свой email в полученной части есть, чужого в ней нет — без проверки
    кода curl скрипт сообщил бы об успехе.
    """
    routes = session_routes([OWN_EMAIL])
    full_changelist = routes["/manager/users/user/"]
    assert callable(full_changelist)
    routes["/manager/users/user/"] = lambda request: full_changelist(request)._replace(content_length=9999)

    result = run_session_script(routes)

    assert result.returncode != 0, result.stdout
    assert "/manager/users/user/: запрос не выполнен целиком" in result.stdout
    assert "✅" not in result.stdout
