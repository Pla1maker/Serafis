"""Safe path helpers.

Every path coming from the user, from the file system or from external data
(ransom notes, catalog, archives) is treated as untrusted.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_INVALID_WIN_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED_WIN_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


class UnsafePathError(ValueError):
    """Raised when a path would escape its allowed base directory."""


def resource_path(*parts: str) -> Path:
    """Return the path of a bundled read-only resource.

    Works both from source and from a PyInstaller one-file bundle.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base:
        root = Path(base) / "serafis"
    else:
        root = Path(__file__).resolve().parent.parent
    return root.joinpath(*parts)


def app_data_dir() -> Path:
    """Per-user writable directory for settings, logs and catalog cache."""
    override = os.environ.get("SERAFIS_HOME")
    if override:
        path = Path(override)
    elif sys.platform == "win32":
        path = Path(os.environ.get("APPDATA", Path.home())) / "Serafis"
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "Serafis"
    else:
        path = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "serafis"
    path.mkdir(parents=True, exist_ok=True)
    return path


def is_within(path: Path | str, base: Path | str) -> bool:
    """True if ``path`` resolves to ``base`` or to something inside it."""
    try:
        Path(path).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False


def safe_join(base: Path | str, *parts: str) -> Path:
    """Join ``parts`` to ``base`` refusing any result outside ``base``.

    Protects against path traversal (``..``), absolute components and
    drive letters coming from untrusted names.
    """
    base_path = Path(base).resolve()
    candidate = base_path.joinpath(*parts).resolve()
    if not is_within(candidate, base_path):
        raise UnsafePathError(f"path escapes base directory: {parts!r}")
    return candidate


def sanitize_filename(name: str, max_len: int = 120) -> str:
    """Turn an untrusted string into a safe single file name component."""
    name = name.replace("\\", "/").split("/")[-1]
    name = _INVALID_WIN_CHARS.sub("_", name).strip(" .")
    if not name or name in {".", ".."}:
        name = "file"
    stem = name.split(".")[0].upper()
    if stem in _RESERVED_WIN_NAMES:
        name = "_" + name
    if len(name) > max_len:
        root, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 20:
            name = root[: max_len - len(ext) - 1] + "." + ext
        else:
            name = name[:max_len]
    return name


def unique_path(directory: Path, filename: str) -> Path:
    """Return a non-existing path in ``directory`` for ``filename``.

    Never returns an existing file, so callers can never overwrite data.
    """
    filename = sanitize_filename(filename)
    candidate = safe_join(directory, filename)
    if not candidate.exists():
        return candidate
    stem, dot, ext = filename.rpartition(".")
    if not dot:
        stem, ext = filename, ""
    for i in range(1, 10_000):
        name = f"{stem} ({i}).{ext}" if ext else f"{stem} ({i})"
        candidate = safe_join(directory, name)
        if not candidate.exists():
            return candidate
    raise FileExistsError("could not find a free file name")


def validate_directory(path: str | Path) -> Path:
    """Validate a user-selected directory for analysis (read-only)."""
    if path is None or str(path).strip() == "":
        raise ValueError("empty path")
    if "\x00" in str(path):
        raise ValueError("invalid character in path")
    p = Path(path).expanduser()
    if not p.exists():
        raise FileNotFoundError(str(p))
    if not p.is_dir():
        raise NotADirectoryError(str(p))
    return p.resolve()
