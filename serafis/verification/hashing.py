from __future__ import annotations

import hashlib
import hmac
import re
import threading
from pathlib import Path

_HEX64 = re.compile(r"^[0-9a-fA-F]{64}$")


def sha256_file(path: Path | str, cancel: threading.Event | None = None, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            if cancel is not None and cancel.is_set():
                raise InterruptedError("cancelled")
            block = fh.read(chunk)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def normalize_sha256(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    return v if _HEX64.match(v) else None


def hashes_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.lower(), b.lower())
