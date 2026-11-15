"""Catalog model, validation and loading."""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema

from ..core.paths import app_data_dir, resource_path
from .trust import verify_signature

log = logging.getLogger(__name__)

BUNDLED_CATALOG = resource_path("data", "catalog.json")
SCHEMA_PATH = resource_path("data", "catalog.schema.json")
MAX_CATALOG_BYTES = 8 * 1024 * 1024


class CatalogError(ValueError):
    """Catalog invalid; ``key`` is an i18n key describing the problem."""

    def __init__(self, key: str, detail: str = "") -> None:
        super().__init__(f"{key}: {detail}")
        self.key = key
        self.detail = detail


def cached_catalog_path() -> Path:
    return app_data_dir() / "catalog" / "catalog.json"


_schema_cache: dict | None = None


def load_schema() -> dict:
    global _schema_cache
    if _schema_cache is None:
        _schema_cache = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _schema_cache


@dataclass
class Catalog:
    data: dict[str, Any]
    sha256: str
    origin: str               # "bundled" | "cached"
    signed_by: str | None = None
    families: dict[str, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.families = {f["id"]: f for f in self.data["families"]}

    @property
    def version(self) -> int:
        return int(self.data["catalog_version"])

    @property
    def generated_at(self) -> str:
        return str(self.data["generated_at"])

    @property
    def solutions(self) -> list[dict]:
        return self.data["solutions"]

    def solution(self, sid: str) -> dict | None:
        return next((s for s in self.solutions if s["id"] == sid), None)

    def solutions_for(self, family_ids: list[str]) -> list[dict]:
        wanted = {f.lower() for f in family_ids}
        return [s for s in self.solutions if wanted & set(s["family_ids"])]

    def family_name(self, fid: str) -> str:
        f = self.families.get(fid)
        return f["name"] if f else fid


def validate_bytes(raw: bytes, signature: str | None, require_signature: bool = True) -> tuple[dict, str | None]:
    """Validate raw catalog bytes. Returns (data, key id)."""
    if len(raw) > MAX_CATALOG_BYTES:
        raise CatalogError("catalog.err.too_large")
    key_id = None
    if signature is not None:
        key_id = verify_signature(raw, signature)
        if key_id is None:
            raise CatalogError("catalog.err.signature")
    elif require_signature:
        raise CatalogError("catalog.err.no_signature")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CatalogError("catalog.err.json", type(exc).__name__) from exc
    try:
        jsonschema.validate(data, load_schema())
    except jsonschema.ValidationError as exc:
        raise CatalogError("catalog.err.schema", exc.message[:200]) from exc
    _semantic_checks(data)
    return data, key_id


def _semantic_checks(data: dict) -> None:
    ids = [s["id"] for s in data["solutions"]]
    if len(ids) != len(set(ids)):
        raise CatalogError("catalog.err.schema", "duplicate solution id")
    fam = {f["id"] for f in data["families"]}
    for s in data["solutions"]:
        if not set(s["family_ids"]) <= fam:
            raise CatalogError("catalog.err.schema", f"unknown family in {s['id']}")
    try:
        gen = datetime.fromisoformat(data["generated_at"].replace("Z", "+00:00"))
    except ValueError as exc:
        raise CatalogError("catalog.err.schema", "bad generated_at") from exc
    if gen.tzinfo is None:
        gen = gen.replace(tzinfo=timezone.utc)
    if gen > datetime.now(timezone.utc) + timedelta(days=2):
        raise CatalogError("catalog.err.future")


def _read_signed(path: Path) -> tuple[bytes, str | None]:
    raw = path.read_bytes()
    sig_path = path.with_name(path.name + ".sig")
    sig = sig_path.read_text(encoding="ascii") if sig_path.exists() else None
    return raw, sig


def load_bundled() -> Catalog:
    raw, sig = _read_signed(BUNDLED_CATALOG)
    # The bundled catalog ships inside the application; its signature is still
    # checked to detect corruption. A bad signature is logged (signed_by=None,
    # caught by the self-test) but the schema must always be valid.
    try:
        data, key = validate_bytes(raw, sig, require_signature=False)
    except CatalogError as exc:
        if exc.key != "catalog.err.signature":
            raise
        log.error("bundled catalog signature mismatch")
        data, key = validate_bytes(raw, None, require_signature=False)
    return Catalog(data, hashlib.sha256(raw).hexdigest(), "bundled", key)


def load_catalog() -> Catalog:
    """Load the newest valid catalog: cached update if valid and newer, else bundled."""
    bundled = load_bundled()
    cp = cached_catalog_path()
    if cp.exists():
        try:
            raw, sig = _read_signed(cp)
            data, key = validate_bytes(raw, sig, require_signature=True)
            cached = Catalog(data, hashlib.sha256(raw).hexdigest(), "cached", key)
            if cached.version > bundled.version:
                return cached
        except (OSError, CatalogError) as exc:
            log.warning("cached catalog rejected: %s", exc)
    return bundled
