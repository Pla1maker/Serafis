"""Secure online catalog update.

Steps (all mandatory):
 1. URL must be HTTPS on an allow-listed host (redirects re-checked).
 2. Download with timeouts and a size limit.
 3. Ed25519 signature (provenance + integrity) checked against keys built
    into the application.
 4. JSON schema + semantic validation.
 5. Anti-downgrade: the catalog_version must be greater than the current one.
 6. Atomic write to the local cache.
Network errors never crash the application; they are reported as i18n keys.
"""
from __future__ import annotations

import hashlib
import logging
import os
import socket
import ssl
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

from .. import __version__
from .catalog import MAX_CATALOG_BYTES, Catalog, CatalogError, cached_catalog_path, validate_bytes
from .trust import ALLOWED_UPDATE_HOSTS, DEFAULT_UPDATE_URL

log = logging.getLogger(__name__)
TIMEOUT = 15


@dataclass
class UpdateResult:
    status: str          # updated | up_to_date | rejected | network_error
    key: str             # i18n key
    detail: str = ""
    new_version: int | None = None
    sha256: str | None = None


def check_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme != "https":
        raise CatalogError("catalog.err.not_https")
    if (p.hostname or "").lower() not in ALLOWED_UPDATE_HOSTS:
        raise CatalogError("catalog.err.host")


class _SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _opener() -> urllib.request.OpenerDirector:
    ctx = ssl.create_default_context()
    return urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx), _SafeRedirect())


def fetch(url: str, limit: int = MAX_CATALOG_BYTES, opener=None) -> bytes:
    check_url(url)
    req = urllib.request.Request(url, headers={"User-Agent": f"Serafis/{__version__}"})
    with (opener or _opener()).open(req, timeout=TIMEOUT) as resp:
        data = resp.read(limit + 1)
    if len(data) > limit:
        raise CatalogError("catalog.err.too_large")
    return data


def update_catalog(current: Catalog, url: str | None = None, fetcher=fetch) -> UpdateResult:
    url = url or DEFAULT_UPDATE_URL
    try:
        check_url(url)
        raw = fetcher(url)
        sig = fetcher(url + ".sig", 4096).decode("ascii", errors="replace")
        data, key_id = validate_bytes(raw, sig, require_signature=True)
    except CatalogError as exc:
        log.warning("catalog update rejected: %s", exc.key)
        return UpdateResult("rejected", exc.key, exc.detail)
    except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError, OSError) as exc:
        log.warning("catalog update network error: %s", type(exc).__name__)
        return UpdateResult("network_error", "catalog.err.network", type(exc).__name__)
    new_version = int(data["catalog_version"])
    digest = hashlib.sha256(raw).hexdigest()
    if new_version < current.version:
        return UpdateResult("rejected", "catalog.err.downgrade", f"{new_version} < {current.version}", new_version, digest)
    if new_version == current.version:
        return UpdateResult("up_to_date", "catalog.up_to_date", "", new_version, digest)
    try:
        _atomic_write(raw, sig)
    except OSError as exc:
        return UpdateResult("rejected", "catalog.err.write", type(exc).__name__)
    log.info("catalog updated to version %d (key %s)", new_version, key_id)
    return UpdateResult("updated", "catalog.updated", "", new_version, digest)


def _atomic_write(raw: bytes, sig: str) -> None:
    dest = cached_catalog_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    for target, content in ((dest.with_name(dest.name + ".sig"), sig.encode("ascii")), (dest, raw)):
        fd, tmp = tempfile.mkstemp(dir=str(dest.parent), suffix=".tmp")
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.replace(tmp, target)
