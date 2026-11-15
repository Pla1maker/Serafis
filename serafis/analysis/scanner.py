"""Read-only file-system assessment.

Guarantees (verified by tests):

* files are never modified, renamed, moved or deleted;
* symbolic links and junctions are never followed;
* the *content* of a file is read only if its **name** looks like a ransom
  note, it has a text extension and it is small (first 64 KiB at most);
  personal documents are never opened;
* the walk honours a file limit, a time limit and a cancel flag.
"""
from __future__ import annotations

import hashlib
import logging
import os
import stat
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from ..core.models import RansomNote, ScanResult
from ..core.paths import validate_directory
from ..identification.rules import RuleSet
from . import indicators
from .benign import BENIGN_EXTENSIONS, DOCUMENT_EXTENSIONS

log = logging.getLogger(__name__)

MAX_NOTE_BYTES_READ = 64 * 1024
MAX_NOTE_SIZE = 512 * 1024
MAX_NOTES = 40
MAX_SAMPLES = 25
_REPARSE = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

ProgressCallback = Callable[[int, int, str], None]  # files, suspicious, current dir


@dataclass
class ScanLimits:
    max_files: int = 2_000_000
    max_seconds: float = 3600.0
    max_depth: int = 64


@dataclass
class ScanOutcome:
    result: ScanResult
    note_texts: dict[str, str] = field(default_factory=dict)  # note key -> text (never exported)


def _ext(name: str) -> str:
    _, dot, ext = name.rpartition(".")
    return "." + ext.lower() if dot and ext and len(ext) <= 40 else ""


def _inner_ext(name: str) -> str:
    parts = name.lower().split(".")
    return "." + parts[-2] if len(parts) >= 3 else ""


class Scanner:
    def __init__(self, rules: RuleSet, limits: ScanLimits | None = None) -> None:
        self.rules = rules
        self.limits = limits or ScanLimits()
        self.cancel_event = threading.Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    # ------------------------------------------------------------------
    def scan(self, directories: list[str | Path], progress: ProgressCallback | None = None) -> ScanOutcome:
        res = ScanResult(started_at=_now())
        roots: list[Path] = []
        for d in directories:
            try:
                p = validate_directory(d)
            except (OSError, ValueError) as exc:
                res.errors.append(f"invalid_directory:{type(exc).__name__}")
                continue
            if p not in roots:
                roots.append(p)
        res.directories = [str(r) for r in roots]

        ext_counts: Counter[str] = Counter()
        ext_dirs: dict[str, Counter[str]] = defaultdict(Counter)   # non-benign ext -> dir -> n
        susp_flag_exts: Counter[str] = Counter()                     # ext flagged per-file
        double_ext: Counter[str] = Counter()
        pattern_hits: Counter[str] = Counter()
        samples: dict[str, list[str]] = defaultdict(list)
        notes: dict[tuple[str, str | None], RansomNote] = {}
        note_texts: dict[str, str] = {}
        start = time.monotonic()
        last_progress = 0.0

        stack: list[tuple[Path, int]] = [(r, 0) for r in reversed(roots)]
        while stack:
            if self.cancel_event.is_set():
                res.cancelled = True
                break
            if time.monotonic() - start > self.limits.max_seconds:
                res.truncated = True
                res.errors.append("time_limit_reached")
                break
            current, depth = stack.pop()
            try:
                it = os.scandir(current)
            except OSError as exc:
                res.errors.append(f"unreadable_directory:{type(exc).__name__}")
                res.skipped += 1
                continue
            res.total_dirs += 1
            with it:
                subdirs: list[Path] = []
                for entry in it:
                    try:
                        if entry.is_symlink() or _is_reparse(entry):
                            res.skipped += 1
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            if depth + 1 <= self.limits.max_depth:
                                subdirs.append(Path(entry.path))
                            else:
                                res.skipped += 1
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                    except OSError:
                        res.skipped += 1
                        continue
                    res.total_files += 1
                    if res.total_files > self.limits.max_files:
                        res.truncated = True
                        break
                    name = entry.name
                    ext = _ext(name)
                    ext_counts[ext] += 1
                    flagged = False
                    hits = self.rules.filename_pattern_hits(name) if "@" in name or "[" in name else []
                    if hits:
                        for h in hits:
                            pattern_hits[h] += 1
                        flagged = True
                    if ext in self.rules.known_extensions or ext in self.rules.generic_extensions:
                        flagged = True
                    if ext and ext not in BENIGN_EXTENSIONS:
                        ext_dirs[ext][str(current)] += 1
                        if _inner_ext(name) in DOCUMENT_EXTENSIONS:
                            double_ext[ext] += 1
                    if flagged:
                        susp_flag_exts[ext] += 1
                    if (flagged or (ext and ext not in BENIGN_EXTENSIONS)) and len(samples[ext]) < 5:
                        samples[ext].append(name)
                    if self.rules.is_note_name(name):
                        self._handle_note(entry, name, notes, note_texts, res)
                    now = time.monotonic()
                    if progress and now - last_progress > 0.2:
                        last_progress = now
                        progress(res.total_files, sum(susp_flag_exts.values()), str(current))
                if res.truncated:
                    break
                for sd in reversed(subdirs):
                    stack.append((sd, depth + 1))

        res.ransom_notes = list(notes.values())
        res.pattern_hits = dict(pattern_hits)
        res.extension_counts = dict(ext_counts.most_common())
        res.double_extension_files = sum(double_ext.values())
        self._finalize(res, ext_counts, ext_dirs, susp_flag_exts, double_ext, samples)
        res.finished_at = _now()
        if progress:
            progress(res.total_files, res.suspicious_files, "")
        log.info("scan finished: %d files, %d suspicious, %d notes", res.total_files, res.suspicious_files, len(res.ransom_notes))
        return ScanOutcome(res, note_texts)

    # ------------------------------------------------------------------
    def _handle_note(self, entry: os.DirEntry, name: str, notes: dict, note_texts: dict, res: ScanResult) -> None:
        try:
            size = entry.stat(follow_symlinks=False).st_size
        except OSError:
            return
        ext = _ext(name)
        readable = ext in self.rules.note_text_extensions and size <= MAX_NOTE_SIZE
        digest = None
        text = ""
        error = None
        if readable and len(notes) < MAX_NOTES:
            try:
                # Opened read-only, binary, bounded.
                with open(entry.path, "rb") as fh:
                    data = fh.read(MAX_NOTE_BYTES_READ)
                digest = hashlib.sha256(data).hexdigest()
                text = indicators.decode_untrusted(data)
                if ext in (".html", ".htm", ".hta"):
                    text = indicators.strip_markup(text)
            except OSError as exc:
                error = type(exc).__name__
        key = (name.lower(), digest)
        if key in notes:
            notes[key].occurrences += 1
            return
        if len(notes) >= MAX_NOTES:
            return
        # Notes are only kept as notes if the name is specific OR the text
        # looks like a ransom demand (avoid flagging an ordinary README.txt).
        if text and not self._looks_like_note(name, text):
            return
        note = RansomNote(path=entry.path, name=name, size=size, sha256=digest, read_error=error)
        if text:
            note.excerpt = indicators.redacted_excerpt(text)
            note.emails = indicators.extract_emails(text)
            note.onion_urls = indicators.extract_onions(text)
            note.btc_addresses = indicators.extract_btc(text)
            note_texts[f"{name}|{digest}"] = text
        notes[key] = note

    def _looks_like_note(self, name: str, text: str) -> bool:
        for fam in self.rules.families:
            if any(w.regex.match(name) for w in fam.note_names) or (fam.linked_note and fam.linked_note.regex.match(name)):
                return True
        low = text.lower()
        hits = sum(1 for k in self.rules.note_content_keywords if k in low)
        return hits >= 2

    def _finalize(self, res, ext_counts, ext_dirs, susp_flag_exts, double_ext, samples) -> None:
        suspicious: set[str] = {e for e in susp_flag_exts}
        # extensions linked by a ransom note name ("<ext>-readme.txt")
        for note in res.ransom_notes:
            for fam in self.rules.families:
                if fam.linked_note:
                    m = fam.linked_note.regex.match(note.name)
                    if m and "ext" in m.groupdict():
                        suspicious.add("." + m.group("ext").lower())
        # extensions appended to document extensions ("report.pdf.xyz12")
        for e, n in double_ext.items():
            total = ext_counts.get(e, 0)
            if n >= 3 or (total and n / total >= 0.5 and n >= 1 and res.ransom_notes):
                suspicious.add(e)
        suspicious.discard("")
        counts = {e: ext_counts[e] for e in suspicious if ext_counts.get(e)}
        res.suspicious_extension_counts = dict(sorted(counts.items(), key=lambda kv: -kv[1]))
        res.suspicious_files = sum(counts.values())
        dist: Counter[str] = Counter()
        for e in counts:
            for d, n in ext_dirs.get(e, {}).items():
                dist[d] += n
        # known extensions that are "benign" are not tracked in ext_dirs; fine.
        res.directory_distribution = dict(dist.most_common(50))
        names: list[str] = []
        for e in res.suspicious_extension_counts:
            names.extend(samples.get(e, []))
        res.sample_suspicious_names = names[:MAX_SAMPLES]


def _is_reparse(entry: os.DirEntry) -> bool:
    try:
        attrs = getattr(entry.stat(follow_symlinks=False), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attrs & _REPARSE)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
