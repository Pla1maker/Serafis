import hashlib
import os

import pytest

from serafis.core.models import RecoverySession
from serafis.recovery import workflow as wf


@pytest.fixture
def session(tmp_path):
    s = RecoverySession(backup_confirmed=True)
    s.workspace = str(wf.create_workspace(tmp_path / "ws_base"))
    return s


def test_workspace_structure(session):
    from pathlib import Path
    ws = Path(session.workspace)
    assert (ws / "1_encrypted_copies").is_dir() and (ws / "2_decrypted_output").is_dir()


def test_copy_leaves_original_untouched(session, tmp_path):
    orig = tmp_path / "victim" / "report.pdf.kodg"
    orig.parent.mkdir()
    data = os.urandom(5000)
    orig.write_bytes(data)
    mtime = orig.stat().st_mtime_ns
    [r] = wf.copy_test_files(session, [orig])
    assert orig.read_bytes() == data and orig.stat().st_mtime_ns == mtime
    from pathlib import Path
    assert Path(r.working_copy).read_bytes() == data


def test_copy_limits(session, tmp_path):
    files = []
    for i in range(11):
        f = tmp_path / f"f{i}.x"
        f.write_bytes(b"1")
        files.append(f)
    with pytest.raises(wf.RecoveryError) as e:
        wf.copy_test_files(session, files)
    assert e.value.key == "recovery.err.too_many"
    with pytest.raises(wf.RecoveryError):
        wf.copy_test_files(session, [tmp_path / "missing"])
    with pytest.raises(wf.RecoveryError):
        wf.copy_test_files(RecoverySession(), files[:1])


def test_copy_refuses_workspace_files(session):
    from pathlib import Path
    inside = Path(session.workspace) / "README.txt"
    with pytest.raises(wf.RecoveryError) as e:
        wf.copy_test_files(session, [inside])
    assert e.value.key == "recovery.err.inside_workspace"


@pytest.mark.parametrize("name,ext", [
    ("report.pdf.kodg", ".pdf"), ("a.docx.id-1A2B3C4D.[x@y.z].wallet", ".docx"), ("photo.jpg", ".jpg"), ("blob.xyz", ""),
])
def test_expected_extension(name, ext):
    assert wf.expected_extension(name) == ext


def _tf(session, tmp_path, name, content):
    src = tmp_path / name
    src.write_bytes(content)
    return wf.copy_test_files(session, [src])[0]


def test_check_success(session, tmp_path):
    tf = _tf(session, tmp_path, "report.pdf.kodg", os.urandom(100))
    out = tmp_path / "report.pdf"
    out.write_bytes(b"%PDF-1.7 hello")
    assert wf.check_decrypted(tf, out).status == "success"
    assert wf.evaluate(session) and session.full_recovery_unlocked


def test_check_unchanged_and_bad_header(session, tmp_path):
    enc = os.urandom(100)
    tf = _tf(session, tmp_path, "img.jpg.kodg", enc)
    same = tmp_path / "img_out.jpg"
    same.write_bytes(enc)
    assert wf.check_decrypted(tf, same).detail_key == "recovery.check.unchanged"
    bad = tmp_path / "img2.jpg"
    bad.write_bytes(b"\x00garbage")
    assert wf.check_decrypted(tf, bad).status == "failed"
    assert not wf.evaluate(session)


def test_check_unknown_type_inconclusive(session, tmp_path):
    tf = _tf(session, tmp_path, "data.xyz.kodg", b"enc")
    out = tmp_path / "data.xyz"
    out.write_bytes(b"plain")
    assert wf.check_decrypted(tf, out).status == "inconclusive"
    assert not wf.evaluate(session)


def test_launch_unsupported_off_windows(tmp_path):
    import sys
    if sys.platform == "win32":
        pytest.skip("windows")
    with pytest.raises(wf.RecoveryError):
        wf.open_tool_visibly(tmp_path / "x.exe")
