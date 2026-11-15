import builtins
import hashlib
import os

import pytest

from serafis.analysis import indicators
from serafis.analysis.scanner import ScanLimits, Scanner


def snapshot(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            st = os.stat(p)
            out[p] = (hashlib.sha256(open(p, "rb").read()).hexdigest(), st.st_mtime_ns, st.st_size)
    return out


def test_scan_is_read_only(rules, djvu_victim):
    before = snapshot(djvu_victim)
    Scanner(rules).scan([djvu_victim])
    assert snapshot(djvu_victim) == before


def test_scan_never_opens_personal_documents(rules, djvu_victim, monkeypatch):
    opened = []
    real_open = builtins.open

    def spy(file, mode="r", *a, **k):
        opened.append((str(file), mode))
        return real_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", spy)
    Scanner(rules).scan([djvu_victim])
    names = {os.path.basename(f) for f, _ in opened}
    assert names <= {"_readme.txt"}, names
    assert all("w" not in m and "a" not in m and "+" not in m for _, m in opened)


def test_scan_counts_and_notes(rules, djvu_victim):
    r = Scanner(rules).scan([djvu_victim]).result
    assert r.total_files == 23
    assert r.suspicious_files == 20
    assert r.suspicious_extension_counts == {".kodg": 20}
    assert len(r.ransom_notes) == 1 and r.ransom_notes[0].occurrences == 2
    note = r.ransom_notes[0]
    assert "support@example.test" in note.emails
    assert "0123abcdEFGHijklMNOPqrstUVWXyz" not in note.excerpt  # personal ID redacted
    assert sum(r.directory_distribution.values()) == 20


def test_ordinary_readme_not_flagged(rules, make_files):
    root = make_files({"proj/README.txt": "This project builds a library. See docs.", "proj/a.py": "print(1)"})
    r = Scanner(rules).scan([root]).result
    assert r.ransom_notes == [] and r.suspicious_files == 0


def test_symlinks_not_followed(rules, make_files, tmp_path):
    outside = make_files({"secret/x.locky": b"1"}, tmp_path / "outside")
    root = make_files({"a.txt": "x"})
    try:
        os.symlink(outside, root / "link", target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not supported")
    r = Scanner(rules).scan([root]).result
    assert r.suspicious_files == 0 and r.skipped >= 1


def test_cancel(rules, djvu_victim):
    s = Scanner(rules)
    s.cancel()
    r = s.scan([djvu_victim]).result
    assert r.cancelled


def test_file_limit(rules, djvu_victim):
    r = Scanner(rules, ScanLimits(max_files=5)).scan([djvu_victim]).result
    assert r.truncated


def test_invalid_directories_reported(rules, tmp_path):
    r = Scanner(rules).scan([tmp_path / "nope", ""]).result
    assert r.total_files == 0 and len(r.errors) == 2


def test_large_note_not_read(rules, make_files, monkeypatch):
    root = make_files({"_readme.txt": b"A" * (600 * 1024)})
    r = Scanner(rules).scan([root]).result
    assert r.ransom_notes and r.ransom_notes[0].sha256 is None


def test_html_note_stripped(rules, make_files):
    root = make_files({"x.dharma": b"1", "info.hta": "<html><script>alert(1)</script><b>All your files have been encrypted</b> write decrypt@mail.test bitcoin</html>"})
    r = Scanner(rules).scan([root]).result
    assert "<script>" not in r.ransom_notes[0].excerpt and "alert" not in r.ransom_notes[0].excerpt


def test_indicator_extraction():
    t = "write to a.b@example.com or visit http://" + "a" * 56 + ".onion pay to bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
    assert indicators.extract_emails(t) == ["a.b@example.com"]
    assert len(indicators.extract_onions(t)) == 1
    assert indicators.extract_btc(t)
    assert indicators.decode_untrusted("ciao".encode("utf-16")) == "ciao"
    assert indicators.decode_untrusted(b"\xff\xfe\xfa") is not None
