"""
Скрипт `scripts/deploy/release-has-manager-route.sh` (R42.4-35).

`deploy.yml` после деплоя проверяет `/manager/` только у релиза, в коде которого
этот маршрут есть: откат (`image_tag`) на релиз до стори 42.4 разворачивает
исправный образ без раздела, и обязательная проверка дала бы ложный провал.
Решает код разворачиваемого коммита, а не ответ сервера. Тест строит временный
git-репозиторий с историей «до раздела → с разделом» и запускает скрипт в нём.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

# В тестовом контейнере scripts/deploy смонтирован в /app/scripts/deploy, в CI и
# venv pytest стартует из backend/ полного checkout — скрипт на уровень выше.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_DIRS = (_BACKEND_ROOT / "scripts" / "deploy", _BACKEND_ROOT.parent / "scripts" / "deploy")
_SCRIPT_NAME = "release-has-manager-route.sh"
SCRIPT = next((path / _SCRIPT_NAME for path in _SCRIPT_DIRS if (path / _SCRIPT_NAME).is_file()), None)
URLS = _BACKEND_ROOT / "freesport" / "urls.py"

pytestmark = pytest.mark.skipif(
    SCRIPT is None or shutil.which("bash") is None or shutil.which("git") is None,
    reason=f"нужны bash, git и скрипт (искали в {[str(p) for p in _SCRIPT_DIRS]})",
)

URLS_BEFORE_SECTION = 'urlpatterns = [\n    path("admin/", admin.site.urls),\n]\n'


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    ).stdout.strip()


def commit_urls(repo: Path, content: str) -> str:
    """Коммитит backend/freesport/urls.py с заданным текстом, возвращает SHA."""
    urls = repo / "backend" / "freesport" / "urls.py"
    urls.parent.mkdir(parents=True, exist_ok=True)
    urls.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "release")
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def history(tmp_path: Path) -> tuple[Path, str, str]:
    """Репозиторий: релиз до раздела, затем релиз с настоящим urls.py проекта (HEAD)."""
    git(tmp_path, "init", "-q")
    before = commit_urls(tmp_path, URLS_BEFORE_SECTION)
    current = commit_urls(tmp_path, URLS.read_text(encoding="utf-8"))
    return tmp_path, before, current


def run_script(repo: Path, release: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT), release], cwd=repo, capture_output=True, text=True, encoding="utf-8", timeout=60
    )


def test_current_release_has_section(history):
    """Настоящий urls.py проекта распознаётся: смена записи маршрута уронит тест, а не пропустит проверку."""
    repo, _, current = history

    result = run_script(repo, current)

    assert result.returncode == 0, result.stdout + result.stderr


def test_short_sha_is_resolved(history):
    """Теги образов в ghcr — короткий SHA коммита (`type=sha` в deploy.yml)."""
    repo, _, current = history

    result = run_script(repo, current[:7])

    assert result.returncode == 0, result.stdout + result.stderr


def test_release_before_section_is_not_checked(history):
    """Откат на релиз до 42.4: в рабочей копии раздел есть, но решает коммит релиза."""
    repo, before, _ = history

    result = run_script(repo, before)

    assert result.returncode == 1, result.stdout + result.stderr


def test_release_without_urls_file_is_not_checked(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "README.md").write_text("до backend\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")

    result = run_script(tmp_path, git(tmp_path, "rev-parse", "HEAD"))

    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("release", ["production", "0" * 40, ""], ids=["tag-name", "unknown-sha", "empty"])
def test_unknown_release_is_reported(history, release):
    """Неизвестный коммит — отдельный код: deploy.yml тогда проверяет /manager/, а не пропускает."""
    repo, _, _ = history

    result = run_script(repo, release)

    assert result.returncode == 2, result.stdout + result.stderr
