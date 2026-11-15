"""Authenticode signature check (Windows only).

Uses the built-in PowerShell cmdlet ``Get-AuthenticodeSignature`` which only
*reads* the file; the inspected program is never executed. The path is passed
through an environment variable, never interpolated in the command line.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

TIMEOUT = 30
_PS = (
    "$ErrorActionPreference='Stop';"
    "$s=Get-AuthenticodeSignature -LiteralPath $env:SERAFIS_TARGET;"
    "[pscustomobject]@{Status=[string]$s.Status;Message=[string]$s.StatusMessage;"
    "Subject=[string]$s.SignerCertificate.Subject;Issuer=[string]$s.SignerCertificate.Issuer;"
    "Thumbprint=[string]$s.SignerCertificate.Thumbprint;NotAfter=[string]$s.SignerCertificate.NotAfter}"
    "|ConvertTo-Json -Compress"
)


@dataclass
class SignatureInfo:
    available: bool
    status: str = "Unknown"      # Valid | NotSigned | HashMismatch | UnknownError | ...
    subject: str = ""
    issuer: str = ""
    thumbprint: str = ""
    error: str = ""

    @property
    def valid(self) -> bool:
        return self.available and self.status == "Valid"


def check_authenticode(path: Path | str, runner=subprocess.run) -> SignatureInfo:
    if sys.platform != "win32" and runner is subprocess.run:
        return SignatureInfo(False, error="not_windows")
    env = dict(os.environ, SERAFIS_TARGET=str(Path(path).resolve()))
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = runner(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", _PS],
            capture_output=True, text=True, timeout=TIMEOUT, env=env, creationflags=flags,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return SignatureInfo(False, error=type(exc).__name__)
    if proc.returncode != 0:
        return SignatureInfo(False, error="powershell_error")
    try:
        d = json.loads(proc.stdout.strip() or "{}")
    except ValueError:
        return SignatureInfo(False, error="bad_output")
    return SignatureInfo(
        True,
        status=str(d.get("Status", "Unknown")),
        subject=str(d.get("Subject", ""))[:500],
        issuer=str(d.get("Issuer", ""))[:500],
        thumbprint=str(d.get("Thumbprint", ""))[:100],
    )


def signer_matches(subject: str, keywords: list[str]) -> bool:
    s = subject.lower()
    return any(k.lower() in s for k in keywords)
