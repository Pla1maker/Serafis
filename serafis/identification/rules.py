"""Loading and compiling the maintainable identification rules."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..core.paths import resource_path

DEFAULT_RULES = resource_path("data", "rules", "families.json")
_MAX_REGEX_LEN = 400


class RulesError(ValueError):
    pass


@dataclass
class WeightedRegex:
    regex: re.Pattern
    weight: float
    variant: str | None = None
    source: str = ""


@dataclass
class FamilyRule:
    id: str
    name: str
    aliases: list[str]
    catalog_family_ids: list[str]
    extensions: set[str]
    extension_weight: float
    filename_patterns: list[WeightedRegex]
    note_names: list[WeightedRegex]
    note_keywords: list[tuple[str, float]]
    linked_note: WeightedRegex | None
    random_ext_with_note: dict[str, Any] | None
    variants: list[dict[str, Any]]
    references: list[str]

    def variant_for(self, extensions: set[str], note_names: set[str]) -> str | None:
        for v in self.variants:
            exts = {e.lower() for e in v.get("extensions", [])}
            if exts & extensions:
                return v["name"]
            nr = v.get("note_regex")
            if nr and any(re.match(nr, n) for n in note_names):
                return v["name"]
        return None


@dataclass
class RuleSet:
    version: int
    families: list[FamilyRule]
    generic_note_regexes: list[re.Pattern]
    note_name_keywords: list[str]
    note_text_extensions: set[str]
    generic_extensions: set[str]
    generic_extension_weight: float
    note_content_keywords: list[str]
    known_extensions: dict[str, list[str]] = field(default_factory=dict)  # ext -> family ids

    @classmethod
    def load(cls, path: Path | str | None = None) -> "RuleSet":
        p = Path(path) if path else DEFAULT_RULES
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise RulesError(f"cannot read rules: {exc}") from exc
        return cls.from_dict(raw)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuleSet":
        if not isinstance(raw, dict) or not isinstance(raw.get("families"), list):
            raise RulesError("rules file must contain a 'families' list")
        g = raw.get("generic", {})
        families: list[FamilyRule] = []
        seen: set[str] = set()
        for f in raw["families"]:
            fid = _req_str(f, "id")
            if fid in seen:
                raise RulesError(f"duplicate family id {fid}")
            seen.add(fid)
            linked = f.get("linked_note")
            families.append(
                FamilyRule(
                    id=fid,
                    name=_req_str(f, "name"),
                    aliases=list(f.get("aliases", [])),
                    catalog_family_ids=[x.lower() for x in f.get("catalog_family_ids", [])],
                    extensions={_ext(e) for e in f.get("extensions", [])},
                    extension_weight=_weight(f.get("extension_weight", 0.3)),
                    filename_patterns=[_wre(x) for x in f.get("filename_patterns", [])],
                    note_names=[_wre(x) for x in f.get("note_names", [])],
                    note_keywords=[(str(k["text"]).lower(), _weight(k["weight"])) for k in f.get("note_keywords", [])],
                    linked_note=_wre(linked) if linked else None,
                    random_ext_with_note=f.get("random_extension_with_note"),
                    variants=list(f.get("variants", [])),
                    references=list(f.get("references", [])),
                )
            )
        rs = cls(
            version=int(raw.get("rules_version", 0)),
            families=families,
            generic_note_regexes=[_compile(r) for r in g.get("note_name_regexes", [])],
            note_name_keywords=[k.lower() for k in g.get("note_name_keywords", [])],
            note_text_extensions={_ext(e) for e in g.get("note_text_extensions", [".txt", ".html", ".htm", ".hta"])},
            generic_extensions={_ext(e) for e in g.get("generic_ransom_extensions", [])},
            generic_extension_weight=_weight(g.get("generic_extension_weight", 0.15)),
            note_content_keywords=[k.lower() for k in g.get("ransom_note_content_keywords", [])],
        )
        for fam in families:
            for e in fam.extensions:
                rs.known_extensions.setdefault(e, []).append(fam.id)
        return rs

    # -- helpers used by the scanner -------------------------------------
    def is_note_name(self, name: str) -> bool:
        for fam in self.families:
            if any(w.regex.match(name) for w in fam.note_names):
                return True
            if fam.linked_note and fam.linked_note.regex.match(name):
                return True
        return any(r.match(name) for r in self.generic_note_regexes)

    def filename_pattern_hits(self, name: str) -> list[str]:
        """Return the ids of families whose structured file name pattern matches."""
        return [fam.id for fam in self.families if any(p.regex.search(name) for p in fam.filename_patterns)]

    def family(self, fid: str) -> FamilyRule | None:
        return next((f for f in self.families if f.id == fid), None)


def _req_str(d: dict, key: str) -> str:
    v = d.get(key)
    if not isinstance(v, str) or not v.strip():
        raise RulesError(f"missing '{key}'")
    return v


def _ext(e: str) -> str:
    e = str(e).strip().lower()
    return e if e.startswith(".") else "." + e


def _weight(w: Any) -> float:
    w = float(w)
    if not 0.0 <= w <= 1.0:
        raise RulesError(f"weight out of range: {w}")
    return w


def _compile(r: str) -> re.Pattern:
    if not isinstance(r, str) or len(r) > _MAX_REGEX_LEN:
        raise RulesError("invalid regex")
    try:
        return re.compile(r)
    except re.error as exc:
        raise RulesError(f"invalid regex {r!r}: {exc}") from exc


def _wre(d: dict) -> WeightedRegex:
    return WeightedRegex(_compile(d["regex"]), _weight(d.get("weight", 0.3)), d.get("variant"), d["regex"])
