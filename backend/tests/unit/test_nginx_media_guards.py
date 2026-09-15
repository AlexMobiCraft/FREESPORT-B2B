"""Story 36.1: nginx обязан закрывать legacy-каталоги обмена 1С под /media/.

Каталоги `1c_import`/`1c_temp` перенесены в приватный `ONEC_PRIVATE_DIR`, но на
production media-volume сохраняется между деплоями: файлы незавершённых обменов,
записанные до переезда, физически остаются под `MEDIA_ROOT` и без 404-guard
продолжают отдаваться по прямой ссылке. Тест фиксирует наличие guard'ов в
конфигурации nginx как defense-in-depth (очистка самих файлов — команда
`purge_legacy_1c_media`).
"""

import re
from pathlib import Path

import pytest

# В тестовом контейнере смонтирован только backend/ (как /app), а каталог docker/
# подключается отдельным volume в /app/docker. В CI и локальном venv
# pytest стартует из backend/ полного checkout — там конфиги лежат на уровень выше.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_NGINX_CONF_CANDIDATES = (
    _BACKEND_ROOT / "docker" / "nginx" / "conf.d",
    _BACKEND_ROOT.parent / "docker" / "nginx" / "conf.d",
)


def _nginx_conf_dir() -> Path | None:
    for candidate in _NGINX_CONF_CANDIDATES:
        if candidate.is_dir():
            return candidate
    return None


def _guard_pattern(subdir: str) -> re.Pattern[str]:
    """location /media/<subdir>/ { ... return 404; ... }"""
    return re.compile(
        r"location\s+/media/" + re.escape(subdir) + r"/\s*\{[^}]*return\s+404\s*;",
        re.DOTALL,
    )


def _media_location_blocks(content: str) -> list[str]:
    """Все блоки `location /media/ { ... }` конфига, с учётом вложенных скобок.

    Проверять файл целиком нельзя: guard'ы в HTTPS-vhost удовлетворяют поиску по
    всему тексту, а внутренний HTTP-vhost (`server_name nginx`) при этом остаётся
    открытым. Каждый vhost, раздающий media, обязан закрывать legacy-каталоги сам.
    """
    blocks: list[str] = []
    for match in re.finditer(r"location\s+/media/\s*\{", content):
        opening = content.index("{", match.start())
        depth = 0
        for pos in range(opening, len(content)):
            if content[pos] == "{":
                depth += 1
            elif content[pos] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(content[opening : pos + 1])
                    break
    return blocks


conf_dir = _nginx_conf_dir()

pytestmark = pytest.mark.skipif(
    conf_dir is None,
    reason=(
        "docker/nginx/conf.d недоступен из этого окружения " f"(искали в {[str(p) for p in _NGINX_CONF_CANDIDATES]})"
    ),
)


class TestLegacyOneCMediaGuards:
    """Оба legacy-каталога обмена должны отдавать 404 во всех конфигах nginx."""

    @pytest.mark.parametrize("conf_name", ["default.conf", "local.conf"])
    @pytest.mark.parametrize("subdir", ["1c_import", "1c_temp"])
    def test_legacy_exchange_dir_returns_404(self, conf_name: str, subdir: str) -> None:
        assert conf_dir is not None  # для mypy: skipif уже отсеял None
        conf_path = conf_dir / conf_name
        assert conf_path.is_file(), f"Конфиг {conf_name} не найден в {conf_dir}"

        content = conf_path.read_text(encoding="utf-8")

        assert _guard_pattern(subdir).search(content), (
            f"{conf_name}: нет 404-guard для /media/{subdir}/. "
            "Legacy-файлы обмена 1С на сохранившемся media-volume останутся "
            "доступны анонимно по прямой ссылке."
        )

    @pytest.mark.parametrize("conf_name", ["default.conf", "local.conf"])
    @pytest.mark.parametrize("subdir", ["1c_import", "1c_temp"])
    def test_every_media_vhost_has_guard(self, conf_name: str, subdir: str) -> None:
        """Guard обязан быть в каждом vhost, который раздаёт media.

        Регресс на находке повторного review: в default.conf 404-правила стояли
        только в HTTPS-vhost, а внутренний `server_name nginx` (listen 80)
        отдавал те же файлы по Host: nginx напрямую.
        """
        assert conf_dir is not None
        content = (conf_dir / conf_name).read_text(encoding="utf-8")

        blocks = _media_location_blocks(content)
        assert blocks, f"{conf_name}: не найдено ни одного блока location /media/"

        unguarded = [index for index, block in enumerate(blocks) if not _guard_pattern(subdir).search(block)]
        assert not unguarded, (
            f"{conf_name}: блок(и) location /media/ №{unguarded} раздают media "
            f"без 404-guard для /media/{subdir}/. Всего блоков: {len(blocks)}."
        )
