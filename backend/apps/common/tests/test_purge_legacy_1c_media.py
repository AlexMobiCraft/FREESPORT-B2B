"""Story 36.1: очистка legacy-каталогов обмена 1С из публичного MEDIA_ROOT.

nginx-гарды закрывают доступ по URL, но сами файлы остаются на media-томе,
который переживает деплой. Команда `purge_legacy_1c_media` удаляет их физически.
"""

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command


def _make_legacy_tree(media_root: Path) -> tuple[Path, Path]:
    """Создаёт остатки старого обмена под MEDIA_ROOT."""
    legacy_import = media_root / "1c_import"
    legacy_temp = media_root / "1c_temp"

    (legacy_import / "prices").mkdir(parents=True)
    (legacy_import / "prices" / "prices_1.xml").write_bytes(b"<prices/>")
    (legacy_import / "contragents").mkdir(parents=True)
    (legacy_import / "contragents" / "contragents_1.xml").write_bytes(b"<contragents/>")

    (legacy_temp / "sess-1").mkdir(parents=True)
    (legacy_temp / "sess-1" / "goods.xml").write_bytes(b"<goods/>")

    return legacy_import, legacy_temp


@pytest.fixture
def private_media_layout(settings, tmp_path):
    """MEDIA_ROOT и приватный каталог обмена разведены (штатное состояние после 36.1)."""
    media_root = tmp_path / "media"
    media_root.mkdir()
    private_root = tmp_path / "var" / "onec"

    settings.MEDIA_ROOT = str(media_root)
    settings.ONEC_EXCHANGE = {
        **settings.ONEC_EXCHANGE,
        "TEMP_DIR": private_root / "1c_temp",
        "IMPORT_DIR": private_root / "1c_import",
    }
    return media_root


class TestPurgeLegacyOneCMedia:
    def test_removes_legacy_dirs_from_media_root(self, private_media_layout):
        legacy_import, legacy_temp = _make_legacy_tree(private_media_layout)
        out = StringIO()

        call_command("purge_legacy_1c_media", stdout=out)

        assert not legacy_import.exists()
        assert not legacy_temp.exists()
        report = out.getvalue()
        assert "1c_import" in report
        assert "1c_temp" in report

    def test_dry_run_keeps_files(self, private_media_layout):
        legacy_import, legacy_temp = _make_legacy_tree(private_media_layout)
        out = StringIO()

        call_command("purge_legacy_1c_media", "--dry-run", stdout=out)

        assert legacy_import.exists()
        assert legacy_temp.exists()
        assert (legacy_import / "prices" / "prices_1.xml").exists()
        assert "DRY RUN" in out.getvalue()

    def test_noop_when_nothing_to_purge(self, private_media_layout):
        out = StringIO()

        call_command("purge_legacy_1c_media", stdout=out)

        assert "нечего удалять" in out.getvalue().lower()

    def test_refuses_when_active_exchange_dir_is_inside_media_root(self, settings, tmp_path):
        """Защита от отката: если IMPORT_DIR снова под MEDIA_ROOT — это рабочий каталог."""
        media_root = tmp_path / "media"
        media_root.mkdir()
        _make_legacy_tree(media_root)

        settings.MEDIA_ROOT = str(media_root)
        settings.ONEC_EXCHANGE = {
            **settings.ONEC_EXCHANGE,
            "TEMP_DIR": media_root / "1c_temp",
            "IMPORT_DIR": media_root / "1c_import",
        }

        with pytest.raises(CommandError, match="MEDIA_ROOT"):
            call_command("purge_legacy_1c_media")

        assert (media_root / "1c_import").exists()
        assert (media_root / "1c_temp").exists()
