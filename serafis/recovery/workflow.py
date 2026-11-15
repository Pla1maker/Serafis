"""Guided, non-destructive recovery workflow.

* Test files are **copied** into a dedicated workspace; originals are never
  opened for writing, renamed or deleted.
* A copy is accepted only if its SHA-256 equals the original's.
* Results are checked by looking at the file header ("magic bytes") of the
  decrypted copies selected by the user.
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

from ..core.models import RecoverySession, TestFileResult
from ..core.paths import is_within, unique_path
from ..verification.hashing import sha256_file

log = logging.getLogger(__name__)

MAX_TEST_FILES = 10
MAX_TEST_FILE_SIZE = 200 * 1024 * 1024

# Header signatures of common document types.
MAGIC: dict[str, list[bytes]] = {
    ".pdf": [b"%PDF"],
    ".png": [b"\x89PNG\r\n\x1a\n"],
    ".jpg": [b"\xff\xd8\xff"], ".jpeg": [b"\xff\xd8\xff"],
    ".gif": [b"GIF87a", b"GIF89a"],
    ".bmp": [b"BM"],
    ".tif": [b"II*\x00", b"MM\x00*"], ".tiff": [b"II*\x00", b"MM\x00*"],
    ".zip": [b"PK\x03\x04", b"PK\x05\x06"],
    ".docx": [b"PK\x03\x04"], ".xlsx": [b"PK\x03\x04"], ".pptx": [b"PK\x03\x04"],
    ".odt": [b"PK\x03\x04"], ".ods": [b"PK\x03\x04"], ".odp": [b"PK\x03\x04"],
    ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    ".ppt": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"], ".msg": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    ".rar": [b"Rar!\x1a\x07"], ".7z": [b"7z\xbc\xaf\x27\x1c"],
    ".mp3": [b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"],
    ".mp4": [], ".mov": [],  # checked via 'ftyp' at offset 4
    ".rtf": [b"{\\rtf"],
    ".sqlite": [b"SQLite format 3\x00"], ".db": [b"SQLite format 3\x00"],
    ".psd": [b"8BPS"],
    ".wav": [b"RIFF"], ".avi": [b"RIFF"], ".webp": [b"RIFF"],
}


class RecoveryError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


def create_workspace(base: Path, scanned_dirs: list[str] | None = None) -> Path:
    base = Path(base).expanduser().resolve()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    ws = unique_path(base, f"Serafis_Workspace_{stamp}")
    (ws / "1_encrypted_copies").mkdir(parents=True)
    (ws / "2_decrypted_output").mkdir()
    (ws / "README.txt").write_text(
        "SERAFIS workspace\n\n1_encrypted_copies: copies of the encrypted test files (originals untouched).\n"
        "2_decrypted_output: point the official decryptor's output here, if it allows it.\n",
        encoding="utf-8",
    )
    return ws


def copy_test_files(session: RecoverySession, files: list[str | Path]) -> list[TestFileResult]:
    if not session.workspace:
        raise RecoveryError("recovery.err.no_workspace")
    if len(files) + len(session.test_files) > MAX_TEST_FILES:
        raise RecoveryError("recovery.err.too_many")
    dest_dir = Path(session.workspace) / "1_encrypted_copies"
    added: list[TestFileResult] = []
    for f in files:
        src = Path(f)
        if not src.is_file() or src.is_symlink():
            raise RecoveryError("recovery.err.not_file")
        if is_within(src, session.workspace):
            raise RecoveryError("recovery.err.inside_workspace")
        if src.stat().st_size > MAX_TEST_FILE_SIZE:
            raise RecoveryError("recovery.err.too_large")
        dest = unique_path(dest_dir, src.name)
        # copy (never move); then verify the copy is bit-identical
        with open(src, "rb") as fin, open(dest, "xb") as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)
        if sha256_file(src) != sha256_file(dest):
            dest.unlink(missing_ok=True)
            raise RecoveryError("recovery.err.copy_mismatch")
        r = TestFileResult(original_name=src.name, working_copy=str(dest))
        session.test_files.append(r)
        added.append(r)
    return added


def expected_extension(encrypted_name: str) -> str:
    """Best guess of the original extension: 'report.pdf.djvu' -> '.pdf'."""
    name = encrypted_name
    # Dharma/Phobos style: strip ".id-XXXX.[mail].ext" suffixes
    for marker in (".id-", ".id[", ".["):
        i = name.find(marker)
        if i > 0:
            name = name[:i]
            break
    parts = name.lower().split(".")
    if len(parts) >= 3 and "." + parts[-2] in MAGIC:
        return "." + parts[-2]
    if len(parts) >= 2 and "." + parts[-1] in MAGIC:
        return "." + parts[-1]
    return ""


def check_decrypted(result: TestFileResult, output_file: str | Path) -> TestFileResult:
    out = Path(output_file)
    result.output_file = str(out)
    if not out.is_file():
        result.status, result.detail_key = "failed", "recovery.check.missing"
        return result
    if out.stat().st_size == 0:
        result.status, result.detail_key = "failed", "recovery.check.empty"
        return result
    try:
        if sha256_file(out) == sha256_file(result.working_copy):
            result.status, result.detail_key = "failed", "recovery.check.unchanged"
            return result
    except OSError:
        pass
    ext = out.suffix.lower()
    exp = expected_extension(result.original_name)
    check_ext = ext if ext in MAGIC else exp
    with open(out, "rb") as fh:
        head = fh.read(32)
    if check_ext in (".mp4", ".mov"):
        ok = head[4:8] == b"ftyp"
    elif check_ext in MAGIC and MAGIC[check_ext]:
        ok = any(head.startswith(m) for m in MAGIC[check_ext])
    else:
        ok = None
    if ok is True:
        result.status, result.detail_key = "success", "recovery.check.valid_header"
    elif ok is False:
        result.status, result.detail_key = "failed", "recovery.check.bad_header"
    else:
        result.status, result.detail_key = "inconclusive", "recovery.check.unknown_type"
    return result


def evaluate(session: RecoverySession) -> bool:
    """Full recovery is suggested only after >=1 successful test and no failure."""
    done = [t for t in session.test_files if t.status != "pending"]
    ok = bool(done) and any(t.status == "success" for t in done) and not any(t.status == "failed" for t in done)
    session.full_recovery_unlocked = ok
    return ok


def open_tool_visibly(path: Path | str) -> None:
    """Open the verified official tool in its own visible window.

    Uses the Windows shell (same as a double-click), so UAC and SmartScreen
    prompts are shown normally. Never hidden, never with arguments.
    """
    if sys.platform != "win32":
        raise RecoveryError("recovery.err.launch_unsupported")
    os.startfile(str(path))  # type: ignore[attr-defined]  # noqa: S606
