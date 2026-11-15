"""Final report: JSON, HTML and PDF export.

Privacy: the report contains the analysed directories, aggregate counts,
extensions and indicators. Individual file names are included only if the
user explicitly asks for it. Ransom-note excerpts are redacted. All values are
HTML-escaped (ransom notes and file names are untrusted).
"""
from __future__ import annotations

import html
import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .. import __app_name__, __version__


@dataclass
class ReportData:
    language: str
    scan: dict | None = None
    identification: dict | None = None
    solutions: list[dict] = field(default_factory=list)
    no_decryptor: bool = False
    verifications: list[dict] = field(default_factory=list)
    recovery: dict | None = None
    catalog: dict | None = None
    problems: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    include_file_names: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))


def build_report(d: ReportData) -> dict[str, Any]:
    scan = dict(d.scan or {})
    notes = []
    for n in scan.pop("ransom_notes", []) or []:
        notes.append({
            "name": n.get("name"),
            "size": n.get("size"),
            "sha256": n.get("sha256"),
            "occurrences": n.get("occurrences", 1),
            "emails": n.get("emails", []),
            "onion_urls": n.get("onion_urls", []),
            "btc_addresses": n.get("btc_addresses", []),
            "excerpt_redacted": n.get("excerpt", ""),
        })
    if not d.include_file_names:
        scan.pop("sample_suspicious_names", None)
    rec = dict(d.recovery or {})
    if rec and not d.include_file_names:
        rec["test_files"] = [
            {k: v for k, v in t.items() if k in ("status", "detail_key", "notes")} | {"extension": Path(t.get("original_name", "")).suffix}
            for t in rec.get("test_files", [])
        ]
        rec.pop("workspace", None)
    verifs = []
    for v in d.verifications:
        v = dict(v)
        if not d.include_file_names:
            v.pop("file_path", None)
        verifs.append(v)
    return {
        "report": {"tool": __app_name__, "version": __version__, "created_at": d.created_at, "language": d.language},
        "analysis": {
            "date": scan.get("started_at"),
            "directories": scan.get("directories", []),
            "summary": {k: scan.get(k) for k in ("total_files", "total_dirs", "suspicious_files", "double_extension_files", "skipped", "truncated", "cancelled")},
            "suspicious_extensions": scan.get("suspicious_extension_counts", {}),
            "directory_distribution": scan.get("directory_distribution", {}),
            "sample_file_names": scan.get("sample_suspicious_names") if d.include_file_names else None,
            "ransom_notes": notes,
            "errors": scan.get("errors", []),
        },
        "identification": d.identification,
        "catalog": d.catalog,
        "solutions": [
            {k: s.get(k) for k in ("id", "name", "vendor", "official_page", "download_url", "howto_url", "version", "sha256", "last_verified", "verification_status", "sources")}
            for s in d.solutions
        ],
        "no_verified_decryptor": d.no_decryptor,
        "verifications": verifs,
        "recovery_tests": rec or None,
        "problems": d.problems,
        "recommendations": d.recommendations,
    }


def export_json(report: dict, path: Path | str) -> Path:
    return _atomic(Path(path), json.dumps(report, indent=2, ensure_ascii=False).encode("utf-8"))


def _e(v: Any) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def render_html(report: dict, t: Callable[..., str]) -> str:
    a = report["analysis"]
    ident = report.get("identification") or {}
    parts: list[str] = []
    add = parts.append
    add(f"<!DOCTYPE html><html lang='{_e(report['report']['language'])}'><head><meta charset='utf-8'>")
    add("<meta http-equiv='Content-Security-Policy' content=\"default-src 'none'; style-src 'unsafe-inline'\">")
    add(f"<title>{_e(t('report.title'))}</title><style>"
        "body{font-family:Segoe UI,Arial,sans-serif;color:#1d2433;max-width:960px;margin:24px auto;padding:0 16px;line-height:1.45}"
        "h1{color:#173a6b;margin-bottom:0}h2{color:#173a6b;border-bottom:2px solid #dfe6f2;padding-bottom:4px;margin-top:28px}"
        "table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #dfe6f2;padding:6px 8px;text-align:left;vertical-align:top;font-size:13px}"
        "th{background:#f2f5fb}.warn{background:#fff4e0;border-left:4px solid #e69500;padding:10px 14px}.ok{color:#17803d}.fail{color:#b3261e}"
        ".muted{color:#66708a;font-size:12px}pre{white-space:pre-wrap;background:#f6f7f9;padding:8px;font-size:12px}</style></head><body>")
    add(f"<h1>SERAFIS</h1><div class='muted'>{_e(t('app.subtitle'))} · v{_e(report['report']['version'])}</div>")
    add(f"<p><b>{_e(t('report.created'))}:</b> {_e(report['report']['created_at'])}<br><b>{_e(t('report.analysis_date'))}:</b> {_e(a.get('date'))}</p>")

    add(f"<h2>{_e(t('report.section.analysis'))}</h2><table>")
    add(f"<tr><th>{_e(t('report.directories'))}</th><td>{'<br>'.join(_e(x) for x in a.get('directories', []))}</td></tr>")
    s = a.get("summary", {})
    for k in ("total_files", "suspicious_files", "double_extension_files", "skipped"):
        add(f"<tr><th>{_e(t('report.' + k))}</th><td>{_e(s.get(k))}</td></tr>")
    add("</table>")
    if a.get("suspicious_extensions"):
        add(f"<h3>{_e(t('report.suspicious_extensions'))}</h3><table><tr><th>{_e(t('report.extension'))}</th><th>{_e(t('report.count'))}</th></tr>")
        for e, n in list(a["suspicious_extensions"].items())[:40]:
            add(f"<tr><td>{_e(e)}</td><td>{_e(n)}</td></tr>")
        add("</table>")
    if a.get("ransom_notes"):
        add(f"<h3>{_e(t('report.notes'))}</h3><table><tr><th>{_e(t('report.name'))}</th><th>SHA-256</th><th>{_e(t('report.indicators'))}</th></tr>")
        for n in a["ransom_notes"]:
            ioc = ", ".join(n.get("emails", []) + n.get("onion_urls", []))
            add(f"<tr><td>{_e(n['name'])} (×{_e(n.get('occurrences'))})</td><td class='muted'>{_e(n.get('sha256'))}</td><td>{_e(ioc)}</td></tr>")
        add("</table>")

    add(f"<h2>{_e(t('report.section.identification'))}</h2>")
    cands = ident.get("candidates") or []
    if not cands:
        add(f"<p>{_e(t('ident.none'))}</p>")
    else:
        add(f"<table><tr><th>{_e(t('report.family'))}</th><th>{_e(t('report.variant'))}</th><th>{_e(t('report.confidence'))}</th><th>{_e(t('report.evidence'))}</th></tr>")
        for c in cands:
            ev = "<br>".join(f"{_e(t('evidence.' + e['kind']))}: {_e(e['value'])}" for e in c.get("evidence", []))
            add(f"<tr><td><b>{_e(c['family_name'])}</b></td><td>{_e(c.get('variant') or t('common.unknown'))}</td>"
                f"<td>{_e(t('level.' + c['level']))} ({round(c['score'] * 100)}%)</td><td>{ev}</td></tr>")
        add("</table>")
    add(f"<p class='muted'>{_e(t('ident.disclaimer'))}</p>")
    if ident.get("missing_information"):
        add(f"<h3>{_e(t('ident.missing_title'))}</h3><ul>" + "".join(f"<li>{_e(t(k))}</li>" for k in ident["missing_information"]) + "</ul>")

    add(f"<h2>{_e(t('report.section.solutions'))}</h2>")
    if report.get("no_verified_decryptor"):
        add(f"<div class='warn'><b>{_e(t('nodecryptor.title'))}</b></div>")
    for sol in report.get("solutions", []):
        add(f"<p><b>{_e(sol['name'])}</b> — {_e(sol['vendor'])}<br><span class='muted'>{_e(t('report.official_page'))}: {_e(sol['official_page'])}<br>"
            f"{_e(t('report.last_verified'))}: {_e(sol['last_verified'])} · {_e(t('status.' + sol['verification_status']))}</span></p>")
    cat = report.get("catalog") or {}
    if cat:
        add(f"<p class='muted'>{_e(t('report.catalog'))}: v{_e(cat.get('version'))} ({_e(cat.get('origin'))}) · SHA-256 {_e(cat.get('sha256'))}</p>")

    add(f"<h2>{_e(t('report.section.verification'))}</h2>")
    if not report.get("verifications"):
        add(f"<p>{_e(t('report.none'))}</p>")
    for v in report.get("verifications", []):
        add(f"<p><b>{_e(v['file_name'])}</b><br><span class='muted'>SHA-256: {_e(v['sha256'])}</span></p><table>")
        for c in v.get("checks", []):
            cls = {"pass": "ok", "fail": "fail"}.get(c["status"], "")
            add(f"<tr><td>{_e(t('check.' + c['check']))}</td><td class='{cls}'>{_e(t('status.' + c['status']))}</td><td>{_e(t(c['detail_key'], **c.get('detail_args', {})))}</td></tr>")
        add("</table>")

    add(f"<h2>{_e(t('report.section.tests'))}</h2>")
    rec = report.get("recovery_tests") or {}
    tests = rec.get("test_files") or []
    if not tests:
        add(f"<p>{_e(t('report.none'))}</p>")
    else:
        add("<table>")
        for tf in tests:
            label = tf.get("original_name") or tf.get("extension") or ""
            add(f"<tr><td>{_e(label)}</td><td>{_e(t('test.' + tf.get('status', 'pending')))}</td><td>{_e(t(tf['detail_key']) if tf.get('detail_key') else '')}</td><td>{_e(tf.get('notes'))}</td></tr>")
        add("</table>")

    if report.get("problems"):
        add(f"<h2>{_e(t('report.section.problems'))}</h2><ul>" + "".join(f"<li>{_e(p)}</li>" for p in report["problems"]) + "</ul>")
    add(f"<h2>{_e(t('report.section.recommendations'))}</h2><ul>" + "".join(f"<li>{_e(t(r))}</li>" for r in report.get("recommendations", [])) + "</ul>")
    add(f"<p class='muted'>{_e(t('report.footer'))}</p></body></html>")
    return "".join(parts)


def export_html(report: dict, path: Path | str, t: Callable[..., str]) -> Path:
    return _atomic(Path(path), render_html(report, t).encode("utf-8"))


def export_pdf(report: dict, path: Path | str, t: Callable[..., str]) -> Path:
    """PDF via Qt (QTextDocument + QPdfWriter). Requires a QGuiApplication."""
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    path = Path(path)
    doc = QTextDocument()
    doc.setHtml(render_html(report, t))
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".pdf.tmp")
    os.close(fd)
    writer = QPdfWriter(tmp)
    writer.setPageLayout(QPageLayout(QPageSize(QPageSize.A4), QPageLayout.Portrait, QMarginsF(15, 15, 15, 15)))
    writer.setTitle("SERAFIS report")
    doc.print_(writer)
    del writer
    os.replace(tmp, path)
    return path


def default_recommendations(no_decryptor: bool, identified: bool) -> list[str]:
    recs = ["rec.keep_encrypted", "rec.keep_notes", "rec.isolate", "rec.no_pay_guarantee", "rec.report_police"]
    if no_decryptor:
        recs += ["rec.recheck_catalog", "rec.professional", "rec.backups"]
    else:
        recs += ["rec.test_first", "rec.backups"]
    if not identified:
        recs.insert(0, "rec.confirm_identification")
    recs.append("rec.change_passwords")
    return recs


def _atomic(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)
    return path
