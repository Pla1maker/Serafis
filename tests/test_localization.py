import json
import re
import string
from pathlib import Path

from serafis.localization.i18n import Translator, load_strings

ROOT = Path(__file__).resolve().parent.parent / "serafis"
DYNAMIC_PREFIXES = {
    "nav.": ["dashboard", "assessment", "identification", "options", "verification", "recovery", "results"],
    "level.": ["strong", "probable", "possible", "user"] + [f"{x}.explain" for x in ("strong", "probable", "possible", "user")],
    "evidence.": ["extension", "filename_pattern", "note_name", "note_content", "linked", "yara"],
    "status.": ["pass", "fail", "warning", "unavailable", "listed_by_official_source", "verified_by_maintainer", "unverified"],
    "check.": ["source", "sha256", "signature", "compatibility"],
    "test.": ["pending", "success", "failed", "inconclusive"],
    "options.sig.": ["authenticode", "none", "unknown"],
    "catalog.origin.": ["bundled", "cached"],
    "dash.first_aid.": ["isolate", "no_delete", "no_pay", "keep_notes", "no_restart_tools"],
    "recovery.s1.": list("abcd"), "recovery.s4.step.": list("abcde"), "recovery.s6.": list("abcde"),
    "nodecryptor.": ["keep_encrypted", "keep_notes", "no_delete", "isolate", "professional", "export_tip", "recheck", "no_promise"],
    "verify.verdict.": ["ok", "fail", "partial"],
    "report.": ["total_files", "suspicious_files", "double_extension_files", "skipped"],
}


def _code_keys():
    keys = set()
    pat_call = re.compile(r"\b(?:tr|t)\(\s*\"([a-z0-9_]+(?:\.[a-z0-9_]+)+)\"")
    pat_lit = re.compile(r"\"((?:catalog\.err\.|catalog\.up_to_date|catalog\.updated|download\.err\.|launch\.|missing\.|rec\.|recovery\.check\.|recovery\.err\.|verify\.(?:compat|hash|sig|source)\.)[a-z0-9_.]*)\"")
    for f in ROOT.rglob("*.py"):
        src = f.read_text(encoding="utf-8")
        keys |= set(pat_call.findall(src))
        keys |= {k for k in pat_lit.findall(src) if not k.endswith(".")}
    return keys


def test_same_keys_in_both_languages():
    assert set(load_strings("it")) == set(load_strings("en"))


def test_all_code_keys_translated():
    strings = load_strings("en")
    missing = sorted(k for k in _code_keys() if k not in strings)
    assert not missing, missing


def test_dynamic_keys_translated():
    for lang in ("it", "en"):
        s = load_strings(lang)
        for prefix, suffixes in DYNAMIC_PREFIXES.items():
            for suf in suffixes:
                assert prefix + suf in s, (lang, prefix + suf)


def test_placeholders_match():
    it, en = load_strings("it"), load_strings("en")
    fmt = string.Formatter()
    for k in en:
        a = {f for _, f, _, _ in fmt.parse(en[k]) if f}
        b = {f for _, f, _, _ in fmt.parse(it[k]) if f}
        assert a == b, k


def test_no_empty_strings():
    for lang in ("it", "en"):
        assert all(v.strip() for v in load_strings(lang).values())


def test_italian_is_really_italian():
    it, en = load_strings("it"), load_strings("en")
    proper_names = {"app.subtitle", "ident.external.sheriff"}  # product / service names
    same = [k for k in en if it[k] == en[k] and len(en[k]) > 25 and k not in proper_names]
    assert not same, same


def test_no_decryptor_message_exact():
    assert load_strings("it")["nodecryptor.title"] == "Nessun decryptor compatibile verificato è attualmente disponibile."
    assert load_strings("en")["nodecryptor.title"] == "No verified compatible decryptor is currently available."


def test_translator_fallback_and_format():
    t = Translator("it")
    assert t.tr("assess.done", files=5).startswith("Analisi completata: 5")
    assert t.tr("does.not.exist") == "does.not.exist"
    t.set_language("zz")
    assert t.lang == "en"
    assert t.i18n({"en": "A", "it": "B"}) == "A"
    t.set_language("it")
    assert t.i18n({"en": "A", "it": "B"}) == "B"
