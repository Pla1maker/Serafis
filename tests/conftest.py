import os
import sys
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


@pytest.fixture(autouse=True)
def serafis_home(tmp_path, monkeypatch):
    home = tmp_path / "serafis_home"
    monkeypatch.setenv("SERAFIS_HOME", str(home))
    return home


@pytest.fixture(scope="session")
def rules():
    from serafis.identification.rules import RuleSet
    return RuleSet.load()


@pytest.fixture
def make_files(tmp_path):
    """Create synthetic files (no real malware is ever used)."""
    def _make(spec: dict[str, bytes | str], base: Path | None = None) -> Path:
        root = base or (tmp_path / "victim")
        for rel, content in spec.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, str):
                content = content.encode("utf-8")
            p.write_bytes(content)
        root.mkdir(parents=True, exist_ok=True)
        return root
    return _make


DJVU_NOTE = (
    "ATTENTION!\n\nDon't worry, you can return all your files!\nAll your files like photos, databases, documents "
    "and other important are encrypted with strongest encryption and unique key.\nPrice of private key and decrypt "
    "software is $980.\nDiscount 50% available if you contact us first 72 hours, that's price for you is $490.\n"
    "To get this software you need write on our e-mail:\nsupport@example.test\n\nYour personal ID:\n"
    "0123abcdEFGHijklMNOPqrstUVWXyz0123456789abcdEF\n"
)


@pytest.fixture
def djvu_victim(make_files):
    spec = {f"Documents/report{i}.docx.kodg": os.urandom(256) for i in range(12)}
    spec.update({f"Pictures/img{i}.jpg.kodg": os.urandom(256) for i in range(8)})
    spec["Documents/_readme.txt"] = DJVU_NOTE
    spec["Pictures/_readme.txt"] = DJVU_NOTE
    spec["Documents/untouched.pdf"] = b"%PDF-1.4 personal content"
    return make_files(spec)


@pytest.fixture(autouse=True)
def _reset_language():
    from serafis.localization.i18n import translator
    translator.set_language("en")
    yield
    translator.set_language("en")
