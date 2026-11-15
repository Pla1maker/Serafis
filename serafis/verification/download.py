"""Explicitly authorised download of an official tool.

The file is only *saved*, never executed. The URL and every redirect must be
HTTPS on an official domain of the catalog entry. The download is size and
time bounded and written to a new file (never overwriting).
"""
from __future__ import annotations

import os
import threading
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from .. import __version__
from ..core.paths import sanitize_filename, unique_path
from .origin import url_is_official

MAX_DOWNLOAD = 300 * 1024 * 1024
TIMEOUT = 30


class DownloadError(Exception):
    def __init__(self, key: str) -> None:
        super().__init__(key)
        self.key = key


class _OfficialRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self, domains: list[str]) -> None:
        self.domains = domains

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not url_is_official(newurl, self.domains):
            raise DownloadError("download.err.redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_official(solution: dict, dest_dir: Path, cancel: threading.Event | None = None, progress=None, opener=None) -> tuple[Path, str]:
    url = solution.get("download_url")
    domains = solution.get("official_domains", [])
    if not url or not url_is_official(url, domains):
        raise DownloadError("download.err.not_official")
    op = opener or urllib.request.build_opener(_OfficialRedirect(domains))
    req = urllib.request.Request(url, headers={"User-Agent": f"Serafis/{__version__}"})
    try:
        resp = op.open(req, timeout=TIMEOUT)
    except DownloadError:
        raise
    except OSError as exc:
        raise DownloadError("download.err.network") from exc
    with resp:
        final_url = resp.geturl()
        if not url_is_official(final_url, domains):
            raise DownloadError("download.err.redirect")
        name = _filename(resp.headers.get("Content-Disposition", ""), final_url)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = unique_path(dest_dir, name)
        tmp = target.with_name(target.name + ".part")
        total = 0
        try:
            with open(tmp, "xb") as fh:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise DownloadError("download.err.cancelled")
                    block = resp.read(1 << 16)
                    if not block:
                        break
                    total += len(block)
                    if total > MAX_DOWNLOAD:
                        raise DownloadError("download.err.too_large")
                    fh.write(block)
                    if progress:
                        progress(total)
            os.replace(tmp, target)
        except BaseException:
            try:
                tmp.unlink()
            except OSError:
                pass
            raise
    return target, final_url


def _filename(cd: str, url: str) -> str:
    name = ""
    if "filename=" in cd:
        name = cd.split("filename=")[-1].strip().strip('";\'')
    if not name:
        name = unquote(Path(urlparse(url).path).name)
    return sanitize_filename(name or "decryptor.bin")
