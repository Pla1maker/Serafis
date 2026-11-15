"""Logging that never writes sensitive data.

* User home directory is replaced with ``~``.
* E-mail addresses are masked.
* Logs are local only; nothing is ever sent anywhere (no telemetry).
"""
from __future__ import annotations

import logging
import logging.handlers
import re
from pathlib import Path

from .paths import app_data_dir

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class RedactingFilter(logging.Filter):
    def __init__(self) -> None:
        super().__init__()
        home = str(Path.home())
        self._homes = {home, home.replace("\\", "/")} if len(home) > 3 else set()

    def redact(self, text: str) -> str:
        for h in self._homes:
            text = text.replace(h, "~")
        return _EMAIL.sub("<email>", text)

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:  # pragma: no cover - malformed record
            msg = str(record.msg)
        record.msg = self.redact(msg)
        record.args = None
        return True


def setup_logging(level: int = logging.INFO) -> Path:
    log_dir = app_data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "serafis.log"
    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        if getattr(h, "_serafis", False):
            root.removeHandler(h)
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler._serafis = True  # type: ignore[attr-defined]
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    handler.addFilter(RedactingFilter())
    root.addHandler(handler)
    return log_file
