"""Download-origin checks.

On Windows, files downloaded with a browser carry a ``Zone.Identifier``
alternate data stream with the ``HostUrl`` they came from. It is read (never
written) to confirm that the decryptor came from an official domain.
"""
from __future__ import annotations

import configparser
import sys
from pathlib import Path
from urllib.parse import urlparse

_MULTI_PART_SLD = {"co", "com", "or", "go", "gov", "gouv", "ac", "ne", "org"}


def base_domain(host: str) -> str:
    labels = host.lower().strip(".").split(".")
    if len(labels) >= 3 and labels[-2] in _MULTI_PART_SLD and len(labels[-1]) == 2:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def host_is_official(host: str | None, official_domains: list[str]) -> bool:
    """True if ``host`` equals an official domain or is a sub-domain of the
    same organisation (e.g. dl.emsisoft.com for www.emsisoft.com)."""
    if not host:
        return False
    host = host.lower().strip(".")
    for d in official_domains:
        d = d.lower().strip(".")
        if host == d or host.endswith("." + d):
            return True
        b = base_domain(d)
        if host == b or host.endswith("." + b):
            return True
    return False


def url_is_official(url: str | None, official_domains: list[str]) -> bool:
    if not url:
        return False
    p = urlparse(url.strip())
    return p.scheme == "https" and host_is_official(p.hostname, official_domains)


def read_zone_identifier(path: Path | str) -> dict[str, str] | None:
    """Return {'HostUrl':..., 'ReferrerUrl':..., 'ZoneId':...} or None."""
    if sys.platform != "win32":
        return None
    try:
        with open(str(path) + ":Zone.Identifier", "r", encoding="utf-8", errors="replace") as fh:
            text = fh.read(8192)
    except OSError:
        return None
    cp = configparser.ConfigParser(interpolation=None)
    try:
        cp.read_string(text)
    except configparser.Error:
        return None
    if not cp.has_section("ZoneTransfer"):
        return None
    return {k: v for k, v in cp.items("ZoneTransfer") if k.lower() in ("hosturl", "referrerurl", "zoneid")}
