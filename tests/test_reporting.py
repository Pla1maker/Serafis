import json
from dataclasses import asdict

import pytest

from serafis.analysis.scanner import Scanner
from serafis.identification.engine import Identifier
from serafis.localization.i18n import Translator
from serafis.reporting.report import ReportData, build_report, default_recommendations, export_html, export_json, render_html


@pytest.fixture
def scan_data(rules, djvu_victim):
    o = Scanner(rules).scan([djvu_victim])
    ident = Identifier(rules).identify(o.result, o.note_texts)
    return asdict(o.result), ident.to_dict()


def test_json_report_contents(scan_data, tmp_path):
    scan, ident = scan_data
    rep = build_report(ReportData("en", scan, ident, recommendations=default_recommendations(False, True)))
    p = export_json(rep, tmp_path / "r.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["analysis"]["date"] and d["analysis"]["directories"]
    assert d["analysis"]["summary"]["suspicious_files"] == 20
    assert d["identification"]["candidates"][0]["family_name"] == "STOP/Djvu"
    assert d["analysis"]["ransom_notes"][0]["name"] == "_readme.txt"
    assert "rec.keep_encrypted" in d["recommendations"]


def test_report_excludes_file_names_by_default(scan_data):
    scan, ident = scan_data
    txt = json.dumps(build_report(ReportData("en", scan, ident)))
    assert "report0.docx" not in txt and "untouched.pdf" not in txt
    assert "0123abcdEFGHijklMNOPqrstUVWXyz" not in txt  # victim ID redacted
    txt2 = json.dumps(build_report(ReportData("en", scan, ident, include_file_names=True)))
    assert ".kodg" in txt2 and "report" in txt2


def test_html_escapes_untrusted_content(tmp_path):
    scan = {"directories": ["C:/x"], "ransom_notes": [{"name": "<script>alert(1)</script>.txt", "excerpt": "<img src=x onerror=alert(1)>", "emails": ["<b>@x.y"]}],
            "suspicious_extension_counts": {"<i>.evil": 3}}
    t = Translator("it")
    html = render_html(build_report(ReportData("it", scan, None, no_decryptor=True)), t.tr)
    assert "<script>" not in html and "<img" not in html and "<i>" not in html
    assert "&lt;script&gt;" in html
    assert "Nessun decryptor compatibile verificato è attualmente disponibile." in html
    assert "Content-Security-Policy" in html
    export_html(build_report(ReportData("it", scan, None)), tmp_path / "r.html", t.tr)
    assert (tmp_path / "r.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")


def test_no_decryptor_recommendations():
    recs = default_recommendations(True, False)
    assert {"rec.keep_encrypted", "rec.keep_notes", "rec.isolate", "rec.professional", "rec.recheck_catalog", "rec.confirm_identification"} <= set(recs)


def test_pdf_export(qapp, scan_data, tmp_path):
    from serafis.reporting.report import export_pdf
    scan, ident = scan_data
    p = export_pdf(build_report(ReportData("en", scan, ident)), tmp_path / "r.pdf", Translator("en").tr)
    assert p.read_bytes()[:4] == b"%PDF" and p.stat().st_size > 1000
