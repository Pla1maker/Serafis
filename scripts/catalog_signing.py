#!/usr/bin/env python3
"""Ed25519 signing tool for the Serafis catalog.

    python scripts/catalog_signing.py genkey  .signing/catalog_ed25519.key
    python scripts/catalog_signing.py sign    .signing/catalog_ed25519.key serafis/data/catalog.json
    python scripts/catalog_signing.py verify  serafis/data/catalog.json

``sign`` writes ``<catalog>.sig`` (base64 signature of the exact file bytes).
The public key printed by ``genkey`` must be added to
``serafis/catalog/trust.py`` (TRUSTED_KEYS) and shipped in a new release.
The private key must NEVER be committed.
"""
from __future__ import annotations

import base64
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def genkey(path: str) -> None:
    p = Path(path)
    if p.exists():
        sys.exit(f"refusing to overwrite existing key {p}")
    key = Ed25519PrivateKey.generate()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    pub = key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    print("public key (base64):", base64.b64encode(pub).decode())


def sign(key_path: str, catalog: str) -> None:
    key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    data = Path(catalog).read_bytes()
    sig = key.sign(data)
    Path(catalog + ".sig").write_text(base64.b64encode(sig).decode() + "\n", encoding="ascii")
    print("signed", catalog)


def verify(catalog: str) -> None:
    from serafis.catalog.trust import verify_signature

    data = Path(catalog).read_bytes()
    sig = Path(catalog + ".sig").read_text(encoding="ascii")
    key_id = verify_signature(data, sig)
    print("valid signature, key:", key_id) if key_id else sys.exit("INVALID signature")


if __name__ == "__main__":
    cmd, *args = sys.argv[1:] or ["help"]
    {"genkey": genkey, "sign": sign, "verify": verify}.get(cmd, lambda *a: sys.exit(__doc__))(*args)
