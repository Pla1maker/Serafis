"""Extraction of indicators from untrusted text (ransom notes).

Only text that already looks like a ransom note is ever read, and only
the first bytes of it.
"""
from __future__ import annotations

import re

EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}\b")
ONION_RE = re.compile(r"\b(?:https?://)?[a-z2-7]{16}(?:[a-z2-7]{40})?\.onion\b", re.IGNORECASE)
BTC_RE = re.compile(r"\b(?:bc1[ac-hj-np-z02-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})\b")
# Long hex / base64 blobs typically carry the victim's personal ID or key:
# they are redacted from excerpts.
_PERSONAL_ID_RE = re.compile(r"\b[A-Za-z0-9+/=]{24,}\b")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def decode_untrusted(data: bytes) -> str:
    """Decode bytes of unknown encoding without ever raising."""
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if len(data) > 4 and data[1:2] == b"\x00" and data[3:4] == b"\x00":
        try:
            return data.decode("utf-16-le")
        except UnicodeDecodeError:
            pass
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1", errors="replace")


def strip_markup(text: str) -> str:
    """Remove HTML tags/scripts from notes in .html/.hta format (as text only)."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return text


def clean_text(text: str) -> str:
    text = _CONTROL_RE.sub(" ", text)
    return re.sub(r"[ \t]+", " ", text)


def extract_emails(text: str, limit: int = 20) -> list[str]:
    return _unique(m.group(0).lower() for m in EMAIL_RE.finditer(text))[:limit]


def extract_onions(text: str, limit: int = 20) -> list[str]:
    return _unique(m.group(0).lower() for m in ONION_RE.finditer(text))[:limit]


def extract_btc(text: str, limit: int = 10) -> list[str]:
    return _unique(m.group(0) for m in BTC_RE.finditer(text))[:limit]


def redacted_excerpt(text: str, max_chars: int = 400) -> str:
    """Short excerpt with personal IDs removed. Plain text only."""
    text = clean_text(text)
    text = _PERSONAL_ID_RE.sub("[REDACTED-ID]", text)
    text = re.sub(r"\s*\n\s*", "\n", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + " …"
    return text


def _unique(items) -> list[str]:
    seen: dict[str, None] = {}
    for i in items:
        seen.setdefault(i, None)
    return list(seen)
