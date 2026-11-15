import base64
import json
import socket
import urllib.error

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from serafis.catalog import catalog as cat_mod
from serafis.catalog import trust
from serafis.catalog.catalog import CatalogError, cached_catalog_path, load_bundled, load_catalog, validate_bytes
from serafis.catalog.updater import check_url, update_catalog


@pytest.fixture
def signing_key(monkeypatch):
    key = Ed25519PrivateKey.generate()
    pub = base64.b64encode(key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    monkeypatch.setattr(trust, "TRUSTED_KEYS", {**trust.TRUSTED_KEYS, "test-key": pub})
    return key


def signed(key, data: dict) -> tuple[bytes, str]:
    raw = json.dumps(data).encode()
    return raw, base64.b64encode(key.sign(raw)).decode()


def bundled_data():
    return json.loads(cat_mod.BUNDLED_CATALOG.read_text(encoding="utf-8"))


def test_bundled_catalog_valid_and_signed():
    c = load_bundled()
    assert c.version >= 1 and len(c.solutions) > 100
    assert c.signed_by == "serafis-catalog-2026-1"


def test_bundled_entries_are_sourced():
    for s in load_bundled().solutions:
        assert s["sources"] and all(u.startswith("https://") for u in s["sources"])
        assert s["official_page"].startswith("https://")
        assert s["verification_status"] in ("listed_by_official_source", "verified_by_maintainer")
        assert s["sha256"] is None or len(s["sha256"]) == 64
        if s["download_url"]:
            from serafis.verification.origin import url_is_official
            assert url_is_official(s["download_url"], s["official_domains"]), s["id"]


def test_djvu_solution_present():
    c = load_bundled()
    sols = c.solutions_for(["djvu"])
    assert sols and sols[0]["vendor"] == "Emsisoft"


def test_schema_rejects_missing_field():
    d = bundled_data()
    del d["solutions"][0]["official_page"]
    with pytest.raises(CatalogError) as e:
        validate_bytes(json.dumps(d).encode(), None, require_signature=False)
    assert e.value.key == "catalog.err.schema"


def test_schema_rejects_http_url():
    d = bundled_data()
    d["solutions"][0]["download_url"] = "http://evil.example/x.exe"
    with pytest.raises(CatalogError):
        validate_bytes(json.dumps(d).encode(), None, require_signature=False)


def test_unknown_family_rejected():
    d = bundled_data()
    d["solutions"][0]["family_ids"] = ["nonexistent_family"]
    with pytest.raises(CatalogError):
        validate_bytes(json.dumps(d).encode(), None, require_signature=False)


def test_tampered_signature_rejected():
    raw = cat_mod.BUNDLED_CATALOG.read_bytes()
    sig = (cat_mod.BUNDLED_CATALOG.with_name("catalog.json.sig")).read_text()
    with pytest.raises(CatalogError) as e:
        validate_bytes(raw.replace(b"Emsisoft", b"Evilsoft", 1), sig)
    assert e.value.key == "catalog.err.signature"


def test_unsigned_rejected_when_required():
    with pytest.raises(CatalogError) as e:
        validate_bytes(cat_mod.BUNDLED_CATALOG.read_bytes(), None, require_signature=True)
    assert e.value.key == "catalog.err.no_signature"


def test_invalid_json():
    with pytest.raises(CatalogError) as e:
        validate_bytes(b"{nope", None, require_signature=False)
    assert e.value.key == "catalog.err.json"


def test_future_date_rejected():
    d = bundled_data()
    d["generated_at"] = "2999-01-01T00:00:00Z"
    with pytest.raises(CatalogError) as e:
        validate_bytes(json.dumps(d).encode(), None, require_signature=False)
    assert e.value.key == "catalog.err.future"


def _fetcher(files):
    def f(url, limit=None):
        v = files[url]
        if isinstance(v, Exception):
            raise v
        return v
    return f


URL = "https://raw.githubusercontent.com/x/y/main/catalog.json"


def test_update_success_and_persisted(signing_key):
    current = load_bundled()
    d = bundled_data()
    d["catalog_version"] = current.version + 1
    raw, sig = signed(signing_key, d)
    res = update_catalog(current, URL, _fetcher({URL: raw, URL + ".sig": sig.encode()}))
    assert res.status == "updated" and res.new_version == current.version + 1
    assert cached_catalog_path().exists()
    loaded = load_catalog()
    assert loaded.origin == "cached" and loaded.version == current.version + 1


def test_update_downgrade_blocked(signing_key):
    current = load_bundled()
    d = bundled_data()
    d["catalog_version"] = 1
    current.data["catalog_version"] = 5
    raw, sig = signed(signing_key, d)
    res = update_catalog(current, URL, _fetcher({URL: raw, URL + ".sig": sig.encode()}))
    assert res.status == "rejected" and res.key == "catalog.err.downgrade"
    assert not cached_catalog_path().exists()


def test_update_same_version(signing_key):
    current = load_bundled()
    raw, sig = signed(signing_key, bundled_data())
    assert update_catalog(current, URL, _fetcher({URL: raw, URL + ".sig": sig.encode()})).status == "up_to_date"


def test_update_bad_signature(signing_key):
    current = load_bundled()
    d = bundled_data()
    d["catalog_version"] += 1
    raw, _ = signed(signing_key, d)
    other = Ed25519PrivateKey.generate()
    bad = base64.b64encode(other.sign(raw)).decode()
    res = update_catalog(current, URL, _fetcher({URL: raw, URL + ".sig": bad.encode()}))
    assert res.key == "catalog.err.signature"


@pytest.mark.parametrize("exc", [urllib.error.URLError("down"), socket.timeout(), ConnectionResetError()])
def test_update_network_errors(exc):
    res = update_catalog(load_bundled(), URL, _fetcher({URL: exc}))
    assert res.status == "network_error" and res.key == "catalog.err.network"


@pytest.mark.parametrize("url,key", [
    ("http://raw.githubusercontent.com/x", "catalog.err.not_https"),
    ("https://evil.example.com/catalog.json", "catalog.err.host"),
    ("https://raw.githubusercontent.com.evil.com/c.json", "catalog.err.host"),
])
def test_update_url_policy(url, key):
    with pytest.raises(CatalogError) as e:
        check_url(url)
    assert e.value.key == key
    assert update_catalog(load_bundled(), url).key == key


def test_corrupted_cache_falls_back(signing_key):
    p = cached_catalog_path()
    p.parent.mkdir(parents=True)
    p.write_bytes(b"garbage")
    p.with_name("catalog.json.sig").write_text("AAAA")
    assert load_catalog().origin == "bundled"
