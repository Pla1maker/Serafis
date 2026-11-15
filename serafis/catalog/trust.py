"""Trust anchors for catalog provenance.

Online catalog updates are accepted only if they carry a valid Ed25519
signature made with one of these keys. Adding or rotating a key requires a
new application release, so a compromised download location alone can never
inject a catalog.
"""
from __future__ import annotations

import base64
import binascii

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

TRUSTED_KEYS: dict[str, str] = {
    "serafis-catalog-2026-1": "3ffcaYFao/8Y0IPbtawmO3M3zVYKqHdTVbHxHq6sr84=",
}

# Hosts from which catalog updates may be downloaded (HTTPS only).
ALLOWED_UPDATE_HOSTS = frozenset({"raw.githubusercontent.com", "github.com", "objects.githubusercontent.com"})

DEFAULT_UPDATE_URL = "https://raw.githubusercontent.com/Pla1maker/Serafis/main/serafis/data/catalog.json"


def verify_signature(data: bytes, signature_b64: str, keys: dict[str, str] | None = None) -> str | None:
    """Return the id of the key that signed ``data`` or ``None``."""
    try:
        sig = base64.b64decode(signature_b64.strip(), validate=True)
    except (binascii.Error, ValueError):
        return None
    if len(sig) != 64:
        return None
    for key_id, pub in (keys or TRUSTED_KEYS).items():
        try:
            Ed25519PublicKey.from_public_bytes(base64.b64decode(pub)).verify(sig, data)
            return key_id
        except (InvalidSignature, ValueError):
            continue
    return None
