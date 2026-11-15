# Recovery catalog

`serafis/data/catalog.json` is validated against `serafis/data/catalog.schema.json` and signed (`catalog.json.sig`, Ed25519).

## Where the data comes from
The initial catalog (version 1) was generated on 2026-11-15 by `scripts/build_catalog_nmr.py` from the official
[No More Ransom decryption tools page](https://www.nomoreransom.org/en/decryption-tools.html): family, tool name,
vendor, official download link and how-to guide are copied as published there. Fields No More Ransom does not publish
(version, SHA-256) are left `null`; nothing is invented. Entries checked directly on the vendor's page are marked
`verified_by_maintainer` (e.g. Emsisoft STOP Djvu: version and vendor-stated limitations).

## Updating the catalog
```bash
curl -L -o nmr.html https://www.nomoreransom.org/en/decryption-tools.html
python scripts/build_catalog_nmr.py nmr.html --version <N+1>
python scripts/catalog_signing.py sign <private-key> serafis/data/catalog.json
python scripts/catalog_signing.py verify serafis/data/catalog.json
python -m pytest
```
`catalog_version` must always increase: clients refuse older versions (anti-downgrade).

Clients download `catalog.json` and `catalog.json.sig` from the update URL (default: this repository, branch `main`,
`serafis/data/catalog.json`). Allowed hosts: `raw.githubusercontent.com`, `github.com`, `objects.githubusercontent.com`.

## Moving the catalog to a separate repository
1. Create e.g. `Pla1maker/serafis-catalog` containing `catalog.json` + `catalog.json.sig`.
2. Change `DEFAULT_UPDATE_URL` in `serafis/catalog/trust.py` (or set `catalog_update_url` in the user settings file).
   The signature check makes the location irrelevant to trust: only catalogs signed with a key in `TRUSTED_KEYS` are accepted.

## Signing keys
- Public keys: `TRUSTED_KEYS` in `serafis/catalog/trust.py`. Rotating/adding a key requires a new application release.
- The private key must **never** be committed (`.signing/` is git-ignored). Generate a new one with
  `python scripts/catalog_signing.py genkey .signing/catalog_ed25519.key`.

## Adding a SHA-256
Only add `sha256` when the value is published by the vendor (or obtained by the maintainers from the official download,
recorded in `sha256_source` with date and method). A mismatch makes Serafis block the tool, so stale hashes must be
updated when vendors publish new builds.
