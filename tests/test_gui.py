"""GUI tests (offscreen). Modal dialogs are replaced by stubs."""
import json

import pytest

from serafis.analysis.scanner import Scanner
from serafis.catalog.catalog import load_catalog
from serafis.core.settings import Settings
from serafis.localization.i18n import translator


@pytest.fixture
def no_dialogs(monkeypatch):
    calls = {"confirm": [], "error": [], "info": []}
    import serafis.gui.widgets as w
    mods = ["serafis.gui.widgets", "serafis.gui.main_window", "serafis.gui.pages.assessment", "serafis.gui.pages.identification",
            "serafis.gui.pages.options", "serafis.gui.pages.verification", "serafis.gui.pages.recovery", "serafis.gui.pages.results"]
    import importlib
    for m in mods:
        mod = importlib.import_module(m)
        for name in ("confirm", "error", "info"):
            if hasattr(mod, name):
                monkeypatch.setattr(mod, name, lambda *a, _n=name, **k: calls[_n].append(a) or True)
    return calls


@pytest.fixture
def window(qtbot, rules, no_dialogs):
    from serafis.gui.main_window import MainWindow
    from serafis.gui.state import AppState
    state = AppState(Settings.load(), rules, load_catalog())
    win = MainWindow(state)
    qtbot.addWidget(win)
    return win


def test_first_screen_is_language_choice(window):
    from serafis.gui.language import LanguageScreen
    assert isinstance(window.centralWidget(), LanguageScreen)
    assert set(window.centralWidget().buttons) == {"it", "en"}


def test_language_choice_persists(window, qtbot, serafis_home):
    window.centralWidget().buttons["it"].click()
    assert translator.lang == "it"
    assert Settings.load().language == "it"
    assert window.nav["assessment"].text().endswith("Analisi")
    assert json.loads(Settings.path().read_text())["language"] == "it"


@pytest.mark.parametrize("lang", ["it", "en"])
def test_all_pages_build(window, lang):
    window.set_language(lang)
    for name in window.pages:
        window.go(name)
        assert window.stack.currentWidget() is window.pages[name]


def test_switch_language_keeps_state(window, djvu_victim):
    window.set_language("en")
    window.state.d.directories.append(str(djvu_victim))
    window.set_language("it")
    assert window.pages["assessment"].list.count() == 1


def _run_scan(window, root):
    page = window.pages["assessment"]
    window.state.d.directories[:] = [str(root)]
    outcome = Scanner(window.state.rules).scan([root])
    page._done(outcome)
    return outcome


def test_full_flow_with_decryptor(window, djvu_victim, tmp_path, no_dialogs):
    window.set_language("en")
    _run_scan(window, djvu_victim)
    assert window.state.step_done("assessment")
    window.go("identification")
    assert window.state.d.chosen.family_id == "stop_djvu"
    window.go("options")
    sols = window.state.solutions()
    assert sols and sols[0]["vendor"] == "Emsisoft"
    window.pages["options"]._select(sols[0]["id"])
    assert window.stack.currentWidget() is window.pages["verification"]
    tool = tmp_path / "decrypt_STOPDjvu.exe"
    tool.write_bytes(b"MZ synthetic")
    rep = window.pages["verification"].verifier.verify(tool, sols[0], None, window.state.d.chosen)
    window.pages["verification"]._verified(rep)
    assert window.state.step_done("verification")
    window.go("recovery")
    window.go("results")
    out = window.pages["results"]
    out._silent = True
    for kind in ("json", "html", "pdf"):
        p = out.export(kind, str(tmp_path / f"report.{kind}"))
        assert p and p.exists() and p.stat().st_size > 200
    d = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert d["solutions"][0]["vendor"] == "Emsisoft" and d["no_verified_decryptor"] is False
    assert window.state.step_done("results")


def test_no_decryptor_flow(window, make_files, tmp_path):
    window.set_language("it")
    root = make_files({f"a{i}.docx.WNCRY": b"x" for i in range(5)} | {"@Please_Read_Me@.txt": "Ooops, your important files are encrypted. bitcoin decrypt"})
    _run_scan(window, root)
    window.go("identification")
    window.go("options")
    assert window.state.no_decryptor()
    from PySide6.QtWidgets import QLabel
    texts = [l.text() for l in window.pages["options"].findChildren(QLabel)]
    assert "Nessun decryptor compatibile verificato è attualmente disponibile." in texts
    out = window.pages["results"]
    out._silent = True
    p = out.export("json", str(tmp_path / "r.json"))
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["no_verified_decryptor"] is True and "rec.recheck_catalog" in d["recommendations"]


def test_manual_family_selection(window):
    window.set_language("en")
    page = window.pages["identification"]
    window.state.d.identification = None
    idx = page.combo.findData("djvu")
    page.combo.setCurrentIndex(idx)
    page.use_manual()
    assert window.state.d.chosen.family_id == "djvu" and window.state.d.chosen.level == "user"


def test_scan_requires_directories(window, no_dialogs):
    window.set_language("en")
    window.pages["assessment"].start_scan()
    assert no_dialogs["error"]


def test_background_scan_thread(window, djvu_victim, qtbot):
    window.set_language("en")
    page = window.pages["assessment"]
    window.state.d.directories[:] = [str(djvu_victim)]
    page.start_scan()
    qtbot.waitUntil(lambda: window.state.d.scan is not None, timeout=20000)
    assert window.state.d.scan.result.suspicious_files == 20
