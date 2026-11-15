import json

import pytest

from serafis.core.paths import UnsafePathError, safe_join, sanitize_filename, unique_path, validate_directory
from serafis.core.settings import Settings
from serafis.core.logging_setup import RedactingFilter


@pytest.mark.parametrize("evil", ["../x", "../../etc/passwd", "a/../../b", "/etc/passwd"])
def test_safe_join_blocks_traversal(tmp_path, evil):
    with pytest.raises(UnsafePathError):
        safe_join(tmp_path, evil)


def test_safe_join_allows_children(tmp_path):
    assert safe_join(tmp_path, "a", "b.txt") == (tmp_path / "a" / "b.txt").resolve()


@pytest.mark.parametrize("name,expected", [
    ("../../evil.exe", "evil.exe"), ("a\\..\\b.txt", "b.txt"), ("CON.txt", "_CON.txt"),
    ("x<y>:z?.pdf", "x_y__z_.pdf"), ("..", "file"), ("", "file"), ("a\x00b", "a_b"),
])
def test_sanitize_filename(name, expected):
    assert sanitize_filename(name) == expected


def test_sanitize_long_name_keeps_extension():
    n = sanitize_filename("a" * 300 + ".pdf")
    assert len(n) <= 120 and n.endswith(".pdf")


def test_unique_path_never_overwrites(tmp_path):
    (tmp_path / "f.txt").write_text("orig")
    p = unique_path(tmp_path, "f.txt")
    assert p.name == "f (1).txt" and not p.exists()
    assert (tmp_path / "f.txt").read_text() == "orig"


def test_validate_directory(tmp_path):
    assert validate_directory(tmp_path) == tmp_path.resolve()
    with pytest.raises(FileNotFoundError):
        validate_directory(tmp_path / "missing")
    f = tmp_path / "file"
    f.write_text("x")
    with pytest.raises(NotADirectoryError):
        validate_directory(f)
    with pytest.raises(ValueError):
        validate_directory("")
    with pytest.raises(ValueError):
        validate_directory("a\x00b")


def test_settings_persist_language(serafis_home):
    s = Settings.load()
    assert s.language is None
    s.language = "it"
    s.save()
    assert Settings.load().language == "it"


def test_settings_reject_invalid_values(serafis_home):
    Settings.path().write_text(json.dumps({"language": "xx", "catalog_update_url": "http://evil", "extra": 3}))
    s = Settings.load()
    assert s.language is None and s.catalog_update_url is None and s.extra == {}


def test_settings_corrupted_file(serafis_home):
    Settings.path().write_text("{not json")
    assert Settings.load().language is None


def test_log_redaction(tmp_path):
    from pathlib import Path
    f = RedactingFilter()
    out = f.redact(f"{Path.home()}/secret/file.docx contact bad@evil.example")
    assert str(Path.home()) not in out and "bad@evil.example" not in out
