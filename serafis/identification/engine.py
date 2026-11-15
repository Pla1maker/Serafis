"""Identification engines.

The design is pluggable: every engine implements :class:`IdentificationEngine`
and returns :class:`Evidence` grouped by family. Scores from all engines are
combined conservatively. A YARA engine is provided and activates only when
``yara-python`` is installed and rule files are present; it only ever scans
ransom-note files, never personal documents.
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

from ..core.models import Candidate, Evidence, IdentificationResult, ScanResult
from .rules import RuleSet

log = logging.getLogger(__name__)

STRONG_THRESHOLD = 0.80
PROBABLE_THRESHOLD = 0.50
MIN_REPORTED_SCORE = 0.15


class IdentificationEngine(ABC):
    name: str = "engine"

    def available(self) -> bool:
        return True

    @abstractmethod
    def collect(self, scan: ScanResult, note_texts: dict[str, str]) -> dict[str, list[Evidence]]:
        """Return evidence per family id."""


class RuleEngine(IdentificationEngine):
    name = "rules"

    def __init__(self, rules: RuleSet) -> None:
        self.rules = rules

    def collect(self, scan: ScanResult, note_texts: dict[str, str]) -> dict[str, list[Evidence]]:
        out: dict[str, list[Evidence]] = {}
        exts = scan.extension_counts
        susp_total = max(1, scan.suspicious_files)
        note_names = {n.name for n in scan.ransom_notes}
        pattern_hits = scan.pattern_hits

        for fam in self.rules.families:
            ev: list[Evidence] = []
            # 1. known extensions, weighted by prevalence among suspicious files
            for e in sorted(fam.extensions):
                n = exts.get(e, 0)
                if n:
                    share = min(1.0, n / susp_total)
                    ev.append(Evidence("extension", f"{e} ({n})", round(fam.extension_weight * (0.6 + 0.4 * share), 3)))
            # 2. structured file-name patterns
            n = pattern_hits.get(fam.id, 0)
            if n:
                w = max(p.weight for p in fam.filename_patterns)
                ev.append(Evidence("filename_pattern", f"{fam.filename_patterns[0].source} ({n})", w))
            # 3. ransom note file names
            for wre in fam.note_names:
                hits = sorted(x for x in note_names if wre.regex.match(x))
                if hits:
                    ev.append(Evidence("note_name", hits[0], wre.weight))
            # 4. note linked to an extension (e.g. "<ext>-readme.txt" + "*.<ext>")
            if fam.linked_note:
                for nn in sorted(note_names):
                    m = fam.linked_note.regex.match(nn)
                    if m and "ext" in m.groupdict():
                        linked_ext = "." + m.group("ext").lower()
                        cnt = exts.get(linked_ext, 0)
                        if cnt:
                            ev.append(Evidence("linked", f"{nn} ↔ {linked_ext} ({cnt})", fam.linked_note.weight))
                            break
            # 5. a characteristic note together with random extensions
            rnd = fam.random_ext_with_note
            rnd_notes = sorted(x for x in note_names if rnd and re.match(rnd["note_regex"], x))
            if rnd_notes:
                ext_re = re.compile(rnd["extension_regex"])
                rnd_exts = [e for e in scan.suspicious_extension_counts if ext_re.match(e)]
                if rnd_exts:
                    ev.append(Evidence("linked", f"{rnd_notes[0]} + {', '.join(sorted(rnd_exts)[:3])}", float(rnd["weight"])))
            # 6. keywords inside note text (untrusted, matched as plain text)
            for kw, w in fam.note_keywords:
                if any(kw in t for t in note_texts.values()):
                    ev.append(Evidence("note_content", kw, w))
            if ev:
                out[fam.id] = ev
        return out


class YaraEngine(IdentificationEngine):
    """Optional engine. Scans ONLY ransom notes with user-provided YARA rules."""
    name = "yara"

    def __init__(self, rules_dir: Path | None) -> None:
        self.rules_dir = rules_dir
        self._compiled = None
        try:
            import yara  # type: ignore  # noqa: F401
            self._yara = yara
        except Exception:  # pragma: no cover - optional dependency
            self._yara = None

    def available(self) -> bool:
        return bool(self._yara and self.rules_dir and self.rules_dir.is_dir() and any(self.rules_dir.glob("*.yar")))

    def collect(self, scan: ScanResult, note_texts: dict[str, str]) -> dict[str, list[Evidence]]:  # pragma: no cover - optional
        if not self.available():
            return {}
        if self._compiled is None:
            files = {p.stem: str(p) for p in self.rules_dir.glob("*.yar")}
            self._compiled = self._yara.compile(filepaths=files)
        out: dict[str, list[Evidence]] = {}
        for text in note_texts.values():
            for m in self._compiled.match(data=text.encode("utf-8", "replace"), timeout=10):
                fam = str(m.meta.get("family", m.rule)).lower()
                w = min(0.9, float(m.meta.get("weight", 0.5)))
                out.setdefault(fam, []).append(Evidence("yara", m.rule, w))
        return out


def combine(evidence: list[Evidence]) -> float:
    """Noisy-OR combination of independent indicators, deduplicated by kind+value."""
    seen: dict[tuple[str, str], float] = {}
    for e in evidence:
        key = (e.kind, e.value)
        seen[key] = max(seen.get(key, 0.0), e.weight)
    p = 1.0
    for w in seen.values():
        p *= 1.0 - w
    return round(1.0 - p, 3)


def level_for(score: float, evidence: list[Evidence]) -> str:
    kinds = {e.kind for e in evidence}
    if score >= STRONG_THRESHOLD and len(kinds) >= 2:
        return "strong"
    if score >= PROBABLE_THRESHOLD:
        return "probable"
    return "possible"


class Identifier:
    def __init__(self, rules: RuleSet, engines: list[IdentificationEngine] | None = None) -> None:
        self.rules = rules
        self.engines = engines if engines is not None else [RuleEngine(rules)]

    def identify(self, scan: ScanResult, note_texts: dict[str, str] | None = None) -> IdentificationResult:
        note_texts = {k: v.lower() for k, v in (note_texts or {}).items()}
        result = IdentificationResult()
        per_family: dict[str, list[Evidence]] = {}
        for eng in self.engines:
            if not eng.available():
                result.engines_unavailable.append(eng.name)
                continue
            result.engines_used.append(eng.name)
            try:
                for fid, ev in eng.collect(scan, note_texts).items():
                    per_family.setdefault(fid, []).extend(ev)
            except Exception as exc:  # engines must never crash the app
                log.warning("engine %s failed: %s", eng.name, type(exc).__name__)
                result.engines_unavailable.append(eng.name)

        note_names = {n.name for n in scan.ransom_notes}
        ext_set = set(scan.extension_counts)
        for fid, ev in per_family.items():
            score = combine(ev)
            if score < MIN_REPORTED_SCORE:
                continue
            fam = self.rules.family(fid)
            variant = None
            if fam:
                variant = fam.variant_for(ext_set, note_names)
                if variant is None and fam.linked_note and fam.linked_note.variant and any(e.kind == "linked" for e in ev):
                    variant = fam.linked_note.variant
            result.candidates.append(
                Candidate(
                    family_id=fid,
                    family_name=fam.name if fam else fid,
                    score=score,
                    level=level_for(score, ev),
                    variant=variant,
                    evidence=sorted(ev, key=lambda e: -e.weight),
                    catalog_ids=list(fam.catalog_family_ids) if fam else [],
                    engine=",".join(sorted({"yara" if e.kind == "yara" else "rules" for e in ev})),
                )
            )
        result.candidates.sort(key=lambda c: (-c.score, c.family_name))
        result.candidates = result.candidates[:6]
        result.missing_information = self._missing(scan, result)
        return result

    def _missing(self, scan: ScanResult, result: IdentificationResult) -> list[str]:
        miss: list[str] = []
        if scan.total_files == 0:
            miss.append("missing.no_files")
        if not scan.ransom_notes:
            miss.append("missing.no_note")
        if scan.suspicious_files == 0:
            miss.append("missing.no_suspicious")
        if not result.candidates:
            miss.append("missing.no_match")
        else:
            best = result.candidates[0]
            if best.level != "strong":
                miss.append("missing.weak_evidence")
            if len(result.candidates) > 1 and result.candidates[1].score >= best.score - 0.1:
                miss.append("missing.ambiguous")
            if best.variant is None:
                miss.append("missing.variant_unknown")
        miss.append("missing.confirm_externally")
        return miss
