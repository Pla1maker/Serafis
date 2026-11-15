#!/usr/bin/env python3
"""Render README screenshots offscreen from the real GUI using synthetic data."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["SERAFIS_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication  # noqa: E402

from serafis.analysis.scanner import Scanner  # noqa: E402
from serafis.catalog.catalog import load_catalog  # noqa: E402
from serafis.core.settings import Settings  # noqa: E402
from serafis.gui.main_window import MainWindow  # noqa: E402
from serafis.gui.state import AppState  # noqa: E402
from serafis.gui.style import QSS  # noqa: E402
from serafis.identification.rules import RuleSet  # noqa: E402

out = Path(__file__).resolve().parent.parent / "resources" / "screenshots"
out.mkdir(parents=True, exist_ok=True)
app = QApplication(sys.argv)
app.setStyleSheet(QSS)

victim = Path(tempfile.mkdtemp()) / "Documents"
victim.mkdir()
for i in range(40):
    (victim / f"file{i}.docx.kodg").write_bytes(os.urandom(64))
for i in range(25):
    (victim / f"photo{i}.jpg.kodg").write_bytes(os.urandom(64))
(victim / "_readme.txt").write_text("ATTENTION!\nDon't worry, you can return all your files!\nDiscount 50% available if you contact us first 72 hours\nsupport@example.test\n", encoding="utf-8")


def shot(win, name):
    app.processEvents()
    win.grab().save(str(out / name))


rules = RuleSet.load()
win = MainWindow(AppState(Settings.load(), rules, load_catalog()))
win.resize(1200, 820)
win.show()
shot(win, "language.png")
for lang in ("en", "it"):
    win.set_language(lang)
    win.state.d.__init__()
    win.go("dashboard")
    shot(win, f"dashboard_{lang}.png")
    win.state.d.directories[:] = [str(victim)]
    win.pages["assessment"]._done(Scanner(rules).scan([victim]))
    win.go("assessment")
    shot(win, f"assessment_{lang}.png")
    win.go("identification")
    shot(win, f"identification_{lang}.png")
    win.go("options")
    shot(win, f"options_{lang}.png")
wc = Path(tempfile.mkdtemp()) / "Desktop"
wc.mkdir()
for i in range(10):
    (wc / f"doc{i}.docx.WNCRY").write_bytes(os.urandom(64))
(wc / "@Please_Read_Me@.txt").write_text("Ooops, your important files are encrypted. bitcoin decrypt", encoding="utf-8")
win.set_language("it")
win.state.d.__init__()
win.state.d.directories[:] = [str(wc)]
win.pages["assessment"]._done(Scanner(rules).scan([wc]))
win.go("identification")
win.go("options")
shot(win, "no_decryptor_it.png")
print("screenshots in", out)
