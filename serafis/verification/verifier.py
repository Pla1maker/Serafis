"""Pre-use verification of a decryptor the user has downloaded.

Nothing here runs the tool. Every check reports pass / fail / warning /
unavailable, and unavailable checks are shown explicitly to the user.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

from ..core.models import Candidate, CheckResult, VerificationReport
from .hashing import hashes_equal, normalize_sha256, sha256_file
from .origin import read_zone_identifier, url_is_official
from .signature import SignatureInfo, check_authenticode, signer_matches


def current_os() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


class Verifier:
    def __init__(self, signature_checker=check_authenticode, zone_reader=read_zone_identifier) -> None:
        self.signature_checker = signature_checker
        self.zone_reader = zone_reader

    def verify(
        self,
        file_path: Path | str,
        solution: dict,
        source_url: str | None = None,
        candidate: Candidate | None = None,
    ) -> VerificationReport:
        p = Path(file_path)
        if not p.is_file():
            raise FileNotFoundError(str(p))
        digest = sha256_file(p)
        rep = VerificationReport(str(p), p.name, solution.get("id"), digest, verified_at=datetime.now().astimezone().isoformat(timespec="seconds"))
        rep.checks.append(self._source(p, solution, source_url))
        rep.checks.append(self._hash(digest, solution))
        rep.checks.append(self._signature(p, solution))
        rep.checks.extend(self._compat(p, solution, candidate))
        return rep

    # -- individual checks -----------------------------------------------
    def _source(self, p: Path, sol: dict, source_url: str | None) -> CheckResult:
        domains = sol.get("official_domains", [])
        zone = self.zone_reader(p)
        urls = []
        if zone:
            urls = [u for u in (zone.get("hosturl"), zone.get("referrerurl")) if u]
        if source_url:
            urls.insert(0, source_url)
        if not urls:
            return CheckResult("source", "unavailable", "verify.source.unknown", {"domains": ", ".join(domains)})
        bad = [u for u in urls if not url_is_official(u, domains)]
        if not bad:
            return CheckResult("source", "pass", "verify.source.ok", {"url": urls[0][:200]})
        # about:internet / blob URLs from browsers are inconclusive, not fraud
        if all(not u.lower().startswith(("http://", "https://")) for u in bad):
            return CheckResult("source", "warning", "verify.source.inconclusive", {"url": bad[0][:200]})
        return CheckResult("source", "fail", "verify.source.mismatch", {"url": bad[0][:200], "domains": ", ".join(domains)})

    def _hash(self, digest: str, sol: dict) -> CheckResult:
        expected = normalize_sha256(sol.get("sha256"))
        if not expected:
            return CheckResult("sha256", "unavailable", "verify.hash.no_reference", {"sha256": digest})
        if hashes_equal(digest, expected):
            return CheckResult("sha256", "pass", "verify.hash.ok", {"sha256": digest})
        return CheckResult("sha256", "fail", "verify.hash.mismatch", {"sha256": digest, "expected": expected})

    def _signature(self, p: Path, sol: dict) -> CheckResult:
        sig_cfg = sol.get("signature", {}) or {}
        if p.suffix.lower() not in (".exe", ".dll", ".msi", ".ps1", ".cab", ".sys"):
            return CheckResult("signature", "unavailable", "verify.sig.not_pe", {})
        info: SignatureInfo = self.signature_checker(p)
        if not info.available:
            return CheckResult("signature", "unavailable", "verify.sig.unavailable", {"reason": info.error})
        if info.status == "NotSigned":
            return CheckResult("signature", "fail", "verify.sig.not_signed", {})
        if not info.valid:
            return CheckResult("signature", "fail", "verify.sig.invalid", {"status": info.status})
        kws = sig_cfg.get("expected_signer_keywords") or []
        if kws and not signer_matches(info.subject, kws):
            return CheckResult("signature", "warning", "verify.sig.signer_mismatch", {"subject": info.subject, "expected": ", ".join(kws)})
        if not kws:
            return CheckResult("signature", "warning", "verify.sig.valid_unknown_signer", {"subject": info.subject})
        return CheckResult("signature", "pass", "verify.sig.ok", {"subject": info.subject})

    def _compat(self, p: Path, sol: dict, cand: Candidate | None) -> list[CheckResult]:
        out: list[CheckResult] = []
        comp = sol.get("compatibility", {}) or {}
        oss = comp.get("os") or []
        if not oss:
            out.append(CheckResult("compatibility", "unavailable", "verify.compat.os_unknown", {}))
        elif current_os() in oss:
            out.append(CheckResult("compatibility", "pass", "verify.compat.os_ok", {"os": ", ".join(oss)}))
        else:
            out.append(CheckResult("compatibility", "warning", "verify.compat.os_other", {"os": ", ".join(oss)}))
        if cand is None:
            out.append(CheckResult("compatibility", "unavailable", "verify.compat.no_identification", {}))
            return out
        if not set(cand.catalog_ids) & set(sol.get("family_ids", [])):
            out.append(CheckResult("compatibility", "fail", "verify.compat.family_mismatch", {"family": cand.family_name}))
            return out
        variants = comp.get("variants") or []
        if not variants:
            out.append(CheckResult("compatibility", "pass", "verify.compat.family_ok", {"family": cand.family_name}))
        elif cand.variant is None:
            out.append(CheckResult("compatibility", "warning", "verify.compat.variant_unknown", {"variants": ", ".join(variants)}))
        elif cand.variant.lower() in {v.lower() for v in variants}:
            out.append(CheckResult("compatibility", "pass", "verify.compat.variant_ok", {"variant": cand.variant}))
        else:
            out.append(CheckResult("compatibility", "fail", "verify.compat.variant_mismatch", {"variant": cand.variant, "variants": ", ".join(variants)}))
        return out


def launch_allowed(rep: VerificationReport) -> tuple[bool, str]:
    """Serafis offers to open a tool only if nothing failed AND a
    cryptographic proof (trusted SHA-256 or valid vendor signature) passed."""
    if rep.has_failure:
        return False, "launch.blocked.failure"
    if not rep.strong_pass:
        return False, "launch.blocked.no_proof"
    return True, "launch.allowed"
