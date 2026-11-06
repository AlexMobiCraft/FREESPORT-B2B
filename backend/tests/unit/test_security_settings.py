"""Стори 41.5: Django — не второй источник HSTS.

До 41.5 источников было два: Django отдавал на `/api/` и `/admin/`
`max-age=31536000; includeSubDomains; preload`, nginx — свой заголовок на всём
остальном. Два значения на одном домене, причём Django-вариант содержал
`preload` (заявка на предзагруженный список браузеров, выход из которого
занимает месяцы) и `includeSubDomains` (запись в браузере на год, которую
снятием заголовка **не отозвать**).

Здесь фиксируется итог: HSTS выставляет только nginx, а Django-настройки
обнулены. Настройки читаются из **исходного текста** через `ast`, а не импортом
модуля: `settings/production.py` требует переменных окружения (`DB_NAME` и
прочие), которых нет в произвольном окружении, и тест из-за этого был бы
хрупким. Ограничение того же рода, что и у
`tests/unit/test_nginx_security_headers.py`: доказывается «объявлено», а не
«доехало» — последнее проверяется живым замером (AC13 стори 41.5).
"""

import ast
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_DIR = _BACKEND_ROOT / "freesport" / "settings"

# Каталог сниппетов nginx — там же, где его ищет test_nginx_security_headers.py
_SNIPPETS_CANDIDATES = (
    _BACKEND_ROOT / "docker" / "nginx" / "snippets",
    _BACKEND_ROOT.parent / "docker" / "nginx" / "snippets",
)


def _snippets_dir() -> Path | None:
    for candidate in _SNIPPETS_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def _module_constants(name: str) -> dict[str, object]:
    """Литеральные присваивания верхнего уровня модуля настроек."""
    source = (SETTINGS_DIR / name).read_text(encoding="utf-8")
    constants: dict[str, object] = {}
    for node in ast.parse(source).body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except ValueError:
            continue  # не литерал (config(...), вычисление) — не наше дело
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value
    return constants


class TestDjangoIsNotSecondHstsSource:
    """HSTS в Django обнулён — единственный источник заголовка это nginx."""

    @pytest.mark.parametrize("settings_module", ["base.py", "production.py"])
    def test_hsts_seconds_is_zero(self, settings_module: str) -> None:
        constants = _module_constants(settings_module)

        assert constants.get("SECURE_HSTS_SECONDS") == 0, (
            f"{settings_module}: SECURE_HSTS_SECONDS = "
            f"{constants.get('SECURE_HSTS_SECONDS')!r}. Django снова стал вторым "
            "источником HSTS — на /api/ и /admin/ заголовок придёт дважды, с "
            "разными значениями. Единственный источник — nginx "
            "(docker/nginx/snippets/)."
        )

    @pytest.mark.parametrize("settings_module", ["base.py", "production.py"])
    def test_preload_and_include_subdomains_disabled(self, settings_module: str) -> None:
        """`preload` и `includeSubDomains` — необратимые решения, не косметика.

        `includeSubDomains` записывается в браузер на год и НЕ отзывается снятием
        заголовка: перестаёт лишь продлеваться. У всех, кто уже был на сайте, год
        продолжает идти, и кнопки «всё равно перейти» под HSTS нет. У домена нет
        веб-поддоменов, кроме `www` (он защищается собственным заголовком при
        первом HTTPS-визите), поэтому выгода нулевая, а цена — необратимая.
        `preload` без `includeSubDomains` вдобавок невалиден.
        """
        constants = _module_constants(settings_module)

        assert constants.get("SECURE_HSTS_PRELOAD") is False, f"{settings_module}: SECURE_HSTS_PRELOAD снова True"
        assert (
            constants.get("SECURE_HSTS_INCLUDE_SUBDOMAINS") is False
        ), f"{settings_module}: SECURE_HSTS_INCLUDE_SUBDOMAINS снова True"


class TestDjangoOwnedHeadersUnchanged:
    """Заголовки, которыми на Django-локациях владеет именно Django."""

    @pytest.mark.parametrize("settings_module", ["base.py", "production.py"])
    def test_x_frame_options_stays_deny(self, settings_module: str) -> None:
        """DENY обязан быть согласован с `frame-ancestors 'none'` в app-headers.conf.

        Встраивать `/api/` и `/admin/` незачем, а `'self'` открыл бы клик-джекинг
        на форму входа в админку. В поддерживающих браузерах `frame-ancestors`
        перекрывает `X-Frame-Options`, поэтому значения меняются только вместе.
        """
        constants = _module_constants(settings_module)

        assert constants.get("X_FRAME_OPTIONS") == "DENY", (
            f"{settings_module}: X_FRAME_OPTIONS = {constants.get('X_FRAME_OPTIONS')!r}. "
            "Поменялось без парной правки frame-ancestors в "
            "docker/nginx/snippets/app-headers.conf."
        )

    @pytest.mark.parametrize("settings_module", ["base.py", "production.py"])
    def test_content_type_nosniff_enabled(self, settings_module: str) -> None:
        constants = _module_constants(settings_module)

        assert constants.get("SECURE_CONTENT_TYPE_NOSNIFF") is True, (
            f"{settings_module}: SECURE_CONTENT_TYPE_NOSNIFF выключен. На /api/ и "
            "/admin/ nosniff ставит именно Django — в app-headers.conf его нет "
            "намеренно, чтобы заголовок не задвоился."
        )


snippets_dir = _snippets_dir()


@pytest.mark.skipif(
    snippets_dir is None,
    reason=f"docker/nginx/snippets недоступен (искали в {[str(p) for p in _SNIPPETS_CANDIDATES]})",
)
class TestNginxHstsValue:
    """Вторая половина того же решения — значение HSTS в сниппетах nginx."""

    @pytest.mark.parametrize("snippet", ["security-headers.conf", "app-headers.conf"])
    @pytest.mark.parametrize("forbidden", ["includeSubDomains", "preload"])
    def test_snippet_has_no_irreversible_directives(self, snippet: str, forbidden: str) -> None:
        """Причина запрета — необратимость, а не веб-почта.

        Отказ сегодня стоит одной строки и отменяется любым днём позже; включение
        стоит года чужого браузерного состояния, которое нельзя отозвать. Условие
        возврата к `includeSubDomains`: у `mail.optisport.ru` появился валидный
        сертификат (сейчас там `CN=*.hosting.reg.ru`) И заведён веб-поддомен,
        ради которого это имеет смысл. Случайной правкой вернуть — нельзя.
        """
        assert snippets_dir is not None
        content = (snippets_dir / snippet).read_text(encoding="utf-8")
        # Комментарии не в счёт: в них эти слова объясняются
        directives = "\n".join(line.split("#", 1)[0] for line in content.split("\n"))

        assert forbidden not in directives, (
            f"{snippet}: в значении Strict-Transport-Security появился {forbidden}. "
            "Это необратимое решение: запись живёт в браузере год и снятием "
            "заголовка не отзывается."
        )

    def test_hsts_max_age_is_explicit_year(self) -> None:
        assert snippets_dir is not None
        for snippet in ("security-headers.conf", "app-headers.conf"):
            content = (snippets_dir / snippet).read_text(encoding="utf-8")
            assert (
                'Strict-Transport-Security "max-age=31536000"' in content
            ), f"{snippet}: ожидалось ровно `max-age=31536000` без дополнительных директив"
