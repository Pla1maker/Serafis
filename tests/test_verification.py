import hashlib

import pytest

from serafis.core.models import Candidate
from serafis.verification import download as dl
from serafis.verification.hashing import normalize_sha256, sha256_file
from serafis.verification.origin import base_domain, host_is_official, url_is_official
from serafis.verification.signature import SignatureInfo, check_authenticode
from serafis.verification.verifier import Verifier, launch_allowed

SOL = {
    "id": "nmr.test.vendor",
    "family_ids": ["djvu"],
    "official_domains": ["www.emsisoft.com", "www.nomoreransom.org"],
    "sha256": None,
    "signature": {"type": "authenticode", "expected_signer_keywords": ["Emsisoft"]},
    "compatibility": {"os": ["windows", "linux", "macos"], "variants": []},
    "download_url": "https://www.emsisoft.com/download/x",
}
CAND = Candidate("stop_djvu", "STOP/Djvu", 0.9, "strong", catalog_ids=["djvu"])


def fake_sig(status="Valid", subject="CN=Emsisoft Ltd", available=True):
    return lambda p: SignatureInfo(available, status, subject)


@pytest.fixture
def tool(tmp_path):
    p = tmp_path / "decrypt_STOPDjvu.exe"
    p.write_bytes(b"MZ synthetic test binary - not a real program")
    return p


def test_sha256_known_vector(tmp_path):
    p = tmp_path / "a"
    p.write_bytes(b"abc")
    assert sha256_file(p) == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_normalize_sha256():
    assert normalize_sha256("  " + "A" * 64) == "a" * 64
    assert normalize_sha256("xyz") is None and normalize_sha256(None) is None


@pytest.mark.parametrize("host,ok", [
    ("www.emsisoft.com", True), ("dl.emsisoft.com", True), ("emsisoft.com", True),
    ("emsisoft.com.evil.net", False), ("evilemsisoft.com", False), ("www.nomoreransom.org", True), (None, False),
])
def test_host_is_official(host, ok):
    assert host_is_official(host, SOL["official_domains"]) is ok


def test_base_domain_multipart():
    assert base_domain("seed.kisa.or.kr") == "kisa.or.kr"
    assert base_domain("www.npa.go.jp") == "npa.go.jp"


def test_url_must_be_https():
    assert not url_is_official("http://www.emsisoft.com/x", SOL["official_domains"])


def test_hash_unavailable_reported(tool):
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, SOL, None, CAND)
    c = {x.check: x for x in rep.checks}
    assert c["sha256"].status == "unavailable" and c["sha256"].detail_args["sha256"] == rep.sha256
    assert c["source"].status == "unavailable"
    assert c["signature"].status == "pass"


def test_hash_match_and_mismatch(tool):
    good = dict(SOL, sha256=hashlib.sha256(tool.read_bytes()).hexdigest())
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, good, "https://dl.emsisoft.com/x.exe", CAND)
    assert rep.strong_pass and launch_allowed(rep)[0]
    bad = dict(SOL, sha256="0" * 64)
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, bad, None, CAND)
    assert rep.has_failure and not launch_allowed(rep)[0]


def test_non_official_source_fails(tool):
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, SOL, "https://free-decryptor.example/x.exe", CAND)
    assert {c.check: c.status for c in rep.checks}["source"] == "fail"
    assert launch_allowed(rep) == (False, "launch.blocked.failure")


def test_zone_identifier_used(tool):
    zone = lambda p: {"hosturl": "https://dl.emsisoft.com/decrypt.exe", "zoneid": "3"}
    rep = Verifier(fake_sig(), zone).verify(tool, SOL, None, CAND)
    assert {c.check: c.status for c in rep.checks}["source"] == "pass"


@pytest.mark.parametrize("sig,status", [
    (fake_sig("NotSigned"), "fail"), (fake_sig("HashMismatch"), "fail"),
    (fake_sig("Valid", "CN=Someone Else"), "warning"), (fake_sig(available=False), "unavailable"),
])
def test_signature_outcomes(tool, sig, status):
    rep = Verifier(sig, lambda p: None).verify(tool, SOL, None, CAND)
    assert {c.check: c.status for c in rep.checks}["signature"] == status


def test_no_proof_blocks_launch(tool):
    rep = Verifier(fake_sig(available=False), lambda p: None).verify(tool, SOL, None, CAND)
    assert launch_allowed(rep) == (False, "launch.blocked.no_proof")


def test_variant_mismatch_fails(tool):
    sol = dict(SOL, family_ids=["gandcrabv1v4andv5uptov52versions"], compatibility={"os": [], "variants": ["v1", "v4", "v5"]})
    cand = Candidate("gandcrab", "GandCrab", 0.8, "strong", variant="v2-v3", catalog_ids=["gandcrabv1v4andv5uptov52versions"])
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, sol, None, cand)
    keys = [c.detail_key for c in rep.checks]
    assert "verify.compat.variant_mismatch" in keys and rep.has_failure


def test_family_mismatch_fails(tool):
    cand = Candidate("wannacry", "WannaCry", 0.8, "strong", catalog_ids=[])
    rep = Verifier(fake_sig(), lambda p: None).verify(tool, SOL, None, cand)
    assert "verify.compat.family_mismatch" in [c.detail_key for c in rep.checks]


def test_archive_signature_not_applicable(tmp_path):
    z = tmp_path / "tool.zip"
    z.write_bytes(b"PK\x03\x04")
    rep = Verifier(fake_sig(), lambda p: None).verify(z, SOL, None, CAND)
    assert {c.check: c.detail_key for c in rep.checks}["signature"] == "verify.sig.not_pe"


def test_authenticode_runner_parsing(tool):
    class P:
        returncode = 0
        stdout = '{"Status":"Valid","Subject":"CN=Emsisoft Ltd","Issuer":"CN=CA","Thumbprint":"AB"}'
    seen = {}

    def runner(cmd, **kw):
        seen.update(kw)
        return P()
    info = check_authenticode(tool, runner=runner)
    assert info.valid and info.subject == "CN=Emsisoft Ltd"
    assert seen["env"]["SERAFIS_TARGET"].endswith("decrypt_STOPDjvu.exe")  # path never in command line
    assert seen["timeout"] > 0


def test_download_refuses_non_official(tmp_path):
    with pytest.raises(dl.DownloadError) as e:
        dl.download_official(dict(SOL, download_url="https://evil.example/x.exe"), tmp_path)
    assert e.value.key == "download.err.not_official"
    with pytest.raises(dl.DownloadError):
        dl.download_official(dict(SOL, download_url="http://www.emsisoft.com/x.exe"), tmp_path)


class _Resp:
    def __init__(self, url, data, cd=""):
        self._url, self._data, self.headers = url, data, {"Content-Disposition": cd}

    def geturl(self):
        return self._url

    def read(self, n=-1):
        d, self._data = self._data[:n], self._data[n:]
        return d

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    def __init__(self, resp):
        self.resp = resp

    def open(self, req, timeout=None):
        assert timeout
        return self.resp


def test_download_saves_without_executing(tmp_path):
    op = _Opener(_Resp("https://dl.emsisoft.com/decrypt_STOPDjvu.exe", b"MZ" + b"0" * 1000, 'attachment; filename="../../decrypt_STOPDjvu.exe"'))
    path, final = dl.download_official(SOL, tmp_path, opener=op)
    assert path.parent == tmp_path and path.name == "decrypt_STOPDjvu.exe" and path.read_bytes().startswith(b"MZ")
    path2, _ = dl.download_official(SOL, tmp_path, opener=_Opener(_Resp(final, b"MZ2", "")))
    assert path2 != path and path.read_bytes().startswith(b"MZ0")  # never overwrites


def test_download_final_url_must_be_official(tmp_path):
    op = _Opener(_Resp("https://evil.example/x.exe", b"MZ"))
    with pytest.raises(dl.DownloadError) as e:
        dl.download_official(SOL, tmp_path, opener=op)
    assert e.value.key == "download.err.redirect"
    assert list(tmp_path.iterdir()) == []


def test_download_size_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(dl, "MAX_DOWNLOAD", 100)
    op = _Opener(_Resp("https://dl.emsisoft.com/x.exe", b"0" * 1000))
    with pytest.raises(dl.DownloadError) as e:
        dl.download_official(SOL, tmp_path, opener=op)
    assert e.value.key == "download.err.too_large" and list(tmp_path.iterdir()) == []
