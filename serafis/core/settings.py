"""Persistent user settings (language, catalog preferences)."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .paths import app_data_dir

log = logging.getLogger(__name__)

SUPPORTED_LANGUAGES = ("it", "en")


@dataclass
class Settings:
    language: str | None = None          # None until the user picks one
    catalog_update_url: str | None = None  # None = built-in default
    last_catalog_check: str | None = None
    include_file_names_in_report: bool = False
    extra: dict = field(default_factory=dict)

    @classmethod
    def path(cls) -> Path:
        return app_data_dir() / "settings.json"

    @classmethod
    def load(cls) -> "Settings":
        p = cls.path()
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("settings is not an object")
        except FileNotFoundError:
            return cls()
        except (OSError, ValueError) as exc:
            log.warning("settings file unreadable, using defaults: %s", type(exc).__name__)
            return cls()
        s = cls()
        lang = raw.get("language")
        s.language = lang if lang in SUPPORTED_LANGUAGES else None
        url = raw.get("catalog_update_url")
        s.catalog_update_url = url if isinstance(url, str) and url.startswith("https://") else None
        lc = raw.get("last_catalog_check")
        s.last_catalog_check = lc if isinstance(lc, str) else None
        s.include_file_names_in_report = bool(raw.get("include_file_names_in_report", False))
        extra = raw.get("extra")
        s.extra = extra if isinstance(extra, dict) else {}
        return s

    def save(self) -> None:
        p = self.path()
        data = json.dumps(asdict(self), indent=2, ensure_ascii=False)
        # atomic write
        fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".settings-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(data)
            os.replace(tmp, p)
        except OSError:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
