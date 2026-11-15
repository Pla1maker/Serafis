import os

from serafis.analysis.scanner import Scanner
from serafis.identification.engine import Identifier, combine, level_for
from serafis.core.models import Evidence


def identify(rules, root):
    o = Scanner(rules).scan([root])
    return Identifier(rules).identify(o.result, o.note_texts)


def test_djvu_strong(rules, djvu_victim):
    res = identify(rules, djvu_victim)
    best = res.best
    assert best.family_id == "stop_djvu"
    assert best.level == "strong"
    assert "djvu" in best.catalog_ids
    kinds = {e.kind for e in best.evidence}
    assert {"note_name", "note_content", "extension"} <= kinds


def test_dharma_pattern(rules, make_files):
    root = make_files({f"f{i}.xlsx.id-1A2B3C4D.[recover@mail.test].wallet": b"x" for i in range(5)} | {"FILES ENCRYPTED.txt": "all your files have been encrypted, decrypt with bitcoin"})
    best = identify(rules, root).best
    assert best.family_id == "dharma_crysis" and best.level == "strong"


def test_phobos_pattern_and_variant(rules, make_files):
    root = make_files({f"f{i}.pdf.id[1A2B3C4D-1234].[mail@mail.test].8base": b"x" for i in range(4)})
    best = identify(rules, root).best
    assert best.family_id == "phobos" and best.variant == "8Base"


def test_gandcrab_v5_linked_note(rules, make_files):
    root = make_files({f"doc{i}.docx.qwerty": b"x" for i in range(6)} | {"QWERTY-DECRYPT.txt": "GandCrab all your files decrypt"})
    best = identify(rules, root).best
    assert best.family_id == "gandcrab" and best.variant == "v5"


def test_gandcrab_v2_variant(rules, make_files):
    root = make_files({f"a{i}.jpg.crab": b"x" for i in range(5)} | {"CRAB-DECRYPT.txt": "your files are encrypted, decrypt"})
    best = identify(rules, root).best
    assert best.family_id == "gandcrab" and best.variant == "v2-v3"


def test_revil_linked(rules, make_files):
    root = make_files({f"a{i}.docx.k3x9q2": b"x" for i in range(5)} | {"k3x9q2-readme.txt": "---=== Welcome. Again. ===--- your files are encrypted decrypt"})
    best = identify(rules, root).best
    assert best.family_id == "revil" and best.level in ("strong", "probable")


def test_wannacry_has_no_catalog_solution(rules, make_files):
    root = make_files({f"a{i}.docx.WNCRY": b"x" for i in range(5)} | {"@Please_Read_Me@.txt": "Ooops, your important files are encrypted. bitcoin decrypt"})
    best = identify(rules, root).best
    assert best.family_id == "wannacry" and best.catalog_ids == []


def test_generic_extension_only_weak(rules, make_files):
    root = make_files({f"a{i}.docx.locked": b"x" for i in range(5)})
    res = identify(rules, root)
    assert all(c.level != "strong" for c in res.candidates)
    assert "missing.no_note" in res.missing_information


def test_clean_folder_no_match(rules, make_files):
    root = make_files({"a.docx": b"x", "b.pdf": b"y"})
    res = identify(rules, root)
    assert res.candidates == []
    assert {"missing.no_match", "missing.no_suspicious", "missing.confirm_externally"} <= set(res.missing_information)


def test_single_indicator_never_strong():
    ev = [Evidence("extension", ".x", 0.95)]
    assert level_for(combine(ev), ev) != "strong"


def test_combine_dedup():
    ev = [Evidence("note_name", "a", 0.5), Evidence("note_name", "a", 0.5)]
    assert combine(ev) == 0.5


def test_always_recommends_external_confirmation(rules, djvu_victim):
    assert "missing.confirm_externally" in identify(rules, djvu_victim).missing_information


def test_rules_reference_existing_catalog_families(rules):
    from serafis.catalog.catalog import load_bundled
    cat = load_bundled()
    for fam in rules.families:
        for fid in fam.catalog_family_ids:
            assert fid in cat.families, (fam.id, fid)


def test_invalid_rules_rejected():
    import pytest
    from serafis.identification.rules import RuleSet, RulesError
    with pytest.raises(RulesError):
        RuleSet.from_dict({"families": [{"id": "a", "name": "A", "extension_weight": 3}]})
    with pytest.raises(RulesError):
        RuleSet.from_dict({"families": [{"id": "a", "name": "A", "note_names": [{"regex": "("}]}]})
    with pytest.raises(RulesError):
        RuleSet.from_dict({"families": [{"id": "a", "name": "A"}, {"id": "a", "name": "B"}]})
