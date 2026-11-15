"""Headless self-test of the packaged application (used by CI on Serafis.exe).

Uses only synthetic files created in a temporary directory: it checks that
bundled data (catalog + signature, rules, translations) load, that analysis,
identification, verification hashing and report export work.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def run_self_test(out_file: str | None = None) -> int:
    from .. import __version__
    from ..analysis.scanner import Scanner
    from ..catalog.catalog import load_bundled
    from ..identification.engine import Identifier
    from ..identification.rules import RuleSet
    from ..localization.i18n import Translator, load_strings
    from ..reporting.report import ReportData, build_report, export_html, export_json
    from ..verification.hashing import sha256_file

    results: dict[str, object] = {"version": __version__}
    ok = True
    try:
        cat = load_bundled()
        results["catalog"] = {"version": cat.version, "solutions": len(cat.solutions), "signed_by": cat.signed_by}
        ok &= cat.signed_by is not None and len(cat.solutions) > 0
        rules = RuleSet.load()
        results["rules_families"] = len(rules.families)
        ok &= set(load_strings("it")) == set(load_strings("en"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "victim"
            root.mkdir()
            for i in range(5):
                (root / f"doc{i}.docx.kodg").write_bytes(os.urandom(32))
            (root / "_readme.txt").write_text("ATTENTION!\nDon't worry, you can return all your files!\n", encoding="utf-8")
            o = Scanner(rules).scan([root])
            ident = Identifier(rules).identify(o.result, o.note_texts)
            best = ident.best
            results["identified"] = best.family_name if best else None
            ok &= bool(best and best.family_id == "stop_djvu")
            ok &= bool(cat.solutions_for(best.catalog_ids)) if best else False
            ok &= len(sha256_file(root / "_readme.txt")) == 64
            from dataclasses import asdict
            rep = build_report(ReportData("en", asdict(o.result), ident.to_dict()))
            export_json(rep, Path(tmp) / "r.json")
            export_html(rep, Path(tmp) / "r.html", Translator("it").tr)
            ok &= json.loads((Path(tmp) / "r.json").read_text(encoding="utf-8"))["analysis"]["summary"]["suspicious_files"] == 5
    except Exception as exc:  # noqa: BLE001 - report any failure
        ok = False
        results["error"] = f"{type(exc).__name__}: {exc}"
    results["ok"] = bool(ok)
    text = json.dumps(results, indent=2)
    if out_file:
        Path(out_file).write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0 if ok else 1
