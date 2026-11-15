import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "serafis"


def test_version_cli():
    out = subprocess.run([sys.executable, "-m", "serafis", "--version"], capture_output=True, text=True, cwd=ROOT, timeout=60)
    assert out.returncode == 0 and out.stdout.startswith("SERAFIS ")


def test_smoke_start(serafis_home):
    import os
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", SERAFIS_HOME=str(serafis_home))
    out = subprocess.run([sys.executable, "-m", "serafis", "--smoke-test"], capture_output=True, text=True, cwd=ROOT, timeout=120, env=env)
    assert out.returncode == 0, out.stderr[-2000:]
    assert (serafis_home / "logs" / "serafis.log").exists()


def _sources():
    return {p: p.read_text(encoding="utf-8") for p in PKG.rglob("*.py")}


def test_subprocess_only_for_signature_check():
    users = [p.name for p, s in _sources().items() if re.search(r"\bimport subprocess\b|\bsubprocess\.", s)]
    assert users == ["signature.py"], users
    sig = (PKG / "verification" / "signature.py").read_text()
    assert "shell=True" not in sig


def test_network_only_in_updater_and_download():
    users = sorted(p.name for p, s in _sources().items() if re.search(r"urllib\.request|import socket|http\.client|requests", s))
    assert users == ["download.py", "updater.py"], users


def test_no_dangerous_primitives():
    banned = [r"(?<![.\w])eval\(", r"(?<![.\w])exec\(", r"pickle", r"os\.system", r"shell=True", r"ctypes", r"\bos\.remove\(", r"shutil\.rmtree", r"winreg", r"\.encrypt\("]
    for p, s in _sources().items():
        for b in banned:
            assert not re.search(b, s), (p.name, b)


def test_startfile_only_in_recovery():
    users = [p.name for p, s in _sources().items() if "startfile" in s]
    assert users == ["workflow.py"]


def test_scanner_has_no_write_operations():
    s = (PKG / "analysis" / "scanner.py").read_text()
    for b in (r"\.unlink\(", r"\.rename\(", r"os\.replace", r"\.rmdir\(", r"\.write(_text|_bytes)?\(", r"chmod",
              r"open\([^)]*[\"'](w|a|r\+|x)", r"\.truncate\(", r"shutil\."):
        assert not re.search(b, s), b


def test_self_test(tmp_path, serafis_home):
    import json
    import os
    out = tmp_path / "st.json"
    env = dict(os.environ, SERAFIS_HOME=str(serafis_home))
    r = subprocess.run([sys.executable, "-m", "serafis", "--self-test", str(out)], cwd=ROOT, env=env, timeout=120)
    assert r.returncode == 0
    d = json.loads(out.read_text())
    assert d["ok"] and d["identified"] == "STOP/Djvu"
