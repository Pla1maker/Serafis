# Contributing to SERAFIS

Thank you for helping people recover from ransomware.

## Ground rules
- Serafis is **strictly defensive**. Contributions adding encryption of user data, data exfiltration, persistence, AV tampering, hidden execution or automatic download/execution of unverified binaries will be rejected.
- **Never** add real malware samples to the repository. Tests use synthetic files only.
- **Never invent** catalog entries, URLs, hashes or versions. Every catalog fact must come from an official source (No More Ransom, the tool vendor, a recognised CERT/police agency) and be listed in `sources`.

## Development
```bash
pip install -r requirements-dev.txt
python -m pytest
python -m serafis            # run from source
pyinstaller Serafis.spec     # build (on Windows for Serafis.exe)
```

## Identification rules
Rules live in `serafis/data/rules/families.json`. Keep weights conservative (a single indicator must never produce a "strong" match) and add a test with synthetic file names in `tests/test_identification.py`.

## Translations
Every user-visible string is in `serafis/localization/{it,en}.json`. Both files must have the same keys and placeholders (enforced by tests).

## Catalog
See [docs/CATALOG.md](docs/CATALOG.md).
