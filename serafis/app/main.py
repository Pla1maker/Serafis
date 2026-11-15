"""SERAFIS entry point."""
from __future__ import annotations

import logging
import sys


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    from .. import __version__

    if "--version" in argv:
        print(f"SERAFIS {__version__}")
        return 0

    from ..core.logging_setup import setup_logging
    setup_logging()
    if "--self-test" in argv:
        from .selftest import run_self_test
        i = argv.index("--self-test")
        out = argv[i + 1] if len(argv) > i + 1 else None
        return run_self_test(out)
    log = logging.getLogger("serafis")

    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from ..catalog.catalog import CatalogError, load_catalog
    from ..core.settings import Settings
    from ..gui.main_window import MainWindow
    from ..gui.state import AppState
    from ..gui.style import QSS
    from ..identification.rules import RuleSet

    app = QApplication.instance() or QApplication(argv)
    app.setApplicationName("Serafis")
    app.setApplicationVersion(__version__)
    app.setStyleSheet(QSS)
    settings = Settings.load()
    try:
        catalog = load_catalog()
        rules = RuleSet.load()
    except (CatalogError, OSError, ValueError) as exc:
        from PySide6.QtWidgets import QMessageBox
        log.error("startup data invalid: %s", exc)
        QMessageBox.critical(None, "SERAFIS", f"Internal data error / Errore dati interni:\n{exc}")
        return 2
    state = AppState(settings, rules, catalog)
    win = MainWindow(state)
    win.show()
    if "--smoke-test" in argv:  # used by CI to prove the packaged app starts
        QTimer.singleShot(1500, app.quit)
    log.info("Serafis %s started", __version__)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
