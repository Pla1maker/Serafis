"""Minimal, dependency-free localization (Italian / English)."""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from ..core.paths import resource_path

log = logging.getLogger(__name__)
LANGUAGES = {"it": "Italiano", "en": "English"}
FLAGS = {"it": "🇮🇹", "en": "🇬🇧"}
DEFAULT = "en"


@lru_cache(maxsize=4)
def load_strings(lang: str) -> dict[str, str]:
    path = resource_path("localization", f"{lang}.json")
    return json.loads(path.read_text(encoding="utf-8"))


class Translator:
    def __init__(self, lang: str = DEFAULT) -> None:
        self.lang = DEFAULT
        self.set_language(lang)

    def set_language(self, lang: str) -> None:
        self.lang = lang if lang in LANGUAGES else DEFAULT
        self._strings = load_strings(self.lang)
        self._fallback = load_strings(DEFAULT)

    def tr(self, key: str, **kwargs: Any) -> str:
        text = self._strings.get(key) or self._fallback.get(key)
        if text is None:
            log.debug("missing translation %s", key)
            return key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError, ValueError):
                return text
        return text

    __call__ = tr

    def i18n(self, value: Any) -> str:
        """Pick the right language from a {'en':..., 'it':...} object."""
        if isinstance(value, dict):
            return str(value.get(self.lang) or value.get(DEFAULT) or "")
        return "" if value is None else str(value)


translator = Translator()


def tr(key: str, **kwargs: Any) -> str:
    return translator.tr(key, **kwargs)
