"""Plain data structures shared by every module (no GUI dependencies)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class RansomNote:
    """A file that looks like a ransom note. Its content is untrusted."""
    path: str
    name: str
    size: int
    sha256: str | None = None
    excerpt: str = ""              # redacted, short, never rendered as HTML
    emails: list[str] = field(default_factory=list)
    onion_urls: list[str] = field(default_factory=list)
    btc_addresses: list[str] = field(default_factory=list)
    read_error: str | None = None
    occurrences: int = 1


@dataclass
class ScanResult:
    directories: list[str] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    total_files: int = 0
    total_dirs: int = 0
    suspicious_files: int = 0
    extension_counts: dict[str, int] = field(default_factory=dict)          # all extensions
    suspicious_extension_counts: dict[str, int] = field(default_factory=dict)
    directory_distribution: dict[str, int] = field(default_factory=dict)   # dir -> suspicious count
    sample_suspicious_names: list[str] = field(default_factory=list)       # file names only
    pattern_hits: dict[str, int] = field(default_factory=dict)             # family id -> files
    double_extension_files: int = 0
    ransom_notes: list[RansomNote] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: int = 0
    truncated: bool = False
    cancelled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Evidence:
    kind: str        # extension | filename_pattern | note_name | note_content | linked | yara
    value: str
    weight: float


@dataclass
class Candidate:
    family_id: str
    family_name: str
    score: float
    level: str                     # strong | probable | possible
    variant: str | None = None
    evidence: list[Evidence] = field(default_factory=list)
    catalog_ids: list[str] = field(default_factory=list)
    engine: str = "rules"


@dataclass
class IdentificationResult:
    candidates: list[Candidate] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)  # i18n keys
    engines_used: list[str] = field(default_factory=list)
    engines_unavailable: list[str] = field(default_factory=list)

    @property
    def best(self) -> Candidate | None:
        return self.candidates[0] if self.candidates else None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CheckResult:
    """Result of a single verification check."""
    check: str            # source | sha256 | signature | compatibility | zone
    status: str           # pass | fail | warning | unavailable
    detail_key: str       # i18n key
    detail_args: dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationReport:
    file_path: str
    file_name: str
    solution_id: str | None
    sha256: str
    checks: list[CheckResult] = field(default_factory=list)
    verified_at: str = ""

    @property
    def has_failure(self) -> bool:
        return any(c.status == "fail" for c in self.checks)

    @property
    def strong_pass(self) -> bool:
        """True if at least one cryptographic proof (hash or signature) passed
        and nothing failed."""
        if self.has_failure:
            return False
        return any(c.check in ("sha256", "signature") and c.status == "pass" for c in self.checks)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["has_failure"] = self.has_failure
        d["strong_pass"] = self.strong_pass
        return d


@dataclass
class TestFileResult:
    original_name: str
    working_copy: str
    output_file: str | None = None
    status: str = "pending"   # pending | success | failed | inconclusive
    detail_key: str = ""
    notes: str = ""


@dataclass
class RecoverySession:
    backup_confirmed: bool = False
    workspace: str | None = None
    test_files: list[TestFileResult] = field(default_factory=list)
    test_started: bool = False
    errors: list[str] = field(default_factory=list)
    full_recovery_unlocked: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
