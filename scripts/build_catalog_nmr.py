#!/usr/bin/env python3
"""Build serafis/data/catalog.json from the official No More Ransom page.

Usage:
    curl -L -o nmr.html https://www.nomoreransom.org/en/decryption-tools.html
    python scripts/build_catalog_nmr.py nmr.html --version 2 --date 2026-11-15

Every entry is taken *only* from the No More Ransom page (tool name, vendor,
download link, how-to guide). No hash or version is invented: No More Ransom
does not publish them, so they are left ``null`` and the application reports
the SHA-256 check as "not available" for those tools.
After building, sign the catalog with scripts/catalog_signing.py.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

NMR_PAGE = "https://www.nomoreransom.org/en/decryption-tools.html"

# Signer name keywords expected in the Authenticode certificate. Used as a
# heuristic only: a mismatch produces a warning asking the user to check.
SIGNER_KEYWORDS = {
    "Emsisoft": ["Emsisoft"],
    "Kaspersky Lab": ["Kaspersky"],
    "Avast": ["Avast", "Gen Digital"],
    "Bitdefender": ["Bitdefender"],
    "Trend Micro": ["Trend Micro"],
    "ESET": ["ESET"],
}

# Variants explicitly named in the No More Ransom title of the entry.
VARIANTS = {
    "gandcrabv1v4andv5uptov52versions": ["v1", "v4", "v5"],
    "cerberv1": ["V1"],
    "lockbit30": ["3.0"],
    "hivev1tov4": ["v1", "v2", "v3", "v4"],
    "teslacryptv1": ["V1"], "teslacryptv2": ["V2"], "teslacryptv3": ["V3"], "teslacryptv4": ["V4"],
    "cryptxxxv1": ["V1"], "cryptxxxv2": ["V2"], "cryptxxxv3": ["V3"], "cryptxxxv4": ["V4"], "cryptxxxv5": ["V5"],
    "jsworm20": ["2.0"], "jsworm40": ["4.0"],
}

OS_HINTS = {
    "linuxencoder1": ["linux"], "linuxencoder3": ["linux"],
    "simplelocker": ["android"], "simplocker": ["android"], "macransom": ["macos"],
}

# Details checked by the maintainers directly on the vendor's official page.
# Only facts literally stated on that page are recorded here.
VENDOR_PAGE_OVERRIDES = {
    "nmr.djvu.emsisoft": {
        "name": "Emsisoft Decryptor for STOP Djvu",
        "official_page": "https://www.emsisoft.com/en/ransomware-decryption/stop-djvu/",
        "version": "1.0.0.5",
        "verification_status": "verified_by_maintainer",
        "extra_sources": ["https://www.emsisoft.com/en/ransomware-decryption/stop-djvu/"],
        "limitations": [
            {
                "en": "Vendor statement: for all versions of STOP Djvu, files can be decrypted only if they were encrypted by an offline key that Emsisoft has. For Old Djvu, encrypted/original file pairs can also be used; this does not apply to New Djvu after August 2019.",
                "it": "Dichiarazione del produttore: per tutte le versioni di STOP Djvu i file possono essere decrittati solo se cifrati con una chiave offline in possesso di Emsisoft. Per Old Djvu si possono usare anche coppie di file cifrato/originale; ciò non vale per New Djvu dopo agosto 2019.",
            },
            {
                "en": "Vendor statement: the tool may not work with versions released after the tool was created.",
                "it": "Dichiarazione del produttore: lo strumento potrebbe non funzionare con versioni rilasciate dopo la sua creazione.",
            },
        ],
    },
}

GENERIC_LIMITATION = {
    "en": "Supported variants and requirements are defined by the vendor: read the official how-to guide before use. Decryption is not guaranteed.",
    "it": "Le varianti supportate e i requisiti sono definiti dal produttore: leggere la guida ufficiale prima dell'uso. La decrittazione non è garantita.",
}


def parse(page: str) -> list[dict]:
    out = []
    for block in page.split('<div class="expandable">')[1:]:
        m = re.search(r'id="([^"]*)">(.*?)</button>', block, re.S)
        if not m:
            continue
        anchor = m.group(1)
        title = html.unescape(re.sub(r"\s+", " ", m.group(2))).strip()
        tools = []
        for item in re.findall(r"<li><p>(.*?)</li>", block, re.S):
            desc = html.unescape(re.sub(r"<[^>]+>", "", item.split("</p>")[0]))
            dl = re.findall(r'title="download" href="([^"]+)"', item)
            how = re.findall(r'title="how-to guide" href="([^"]+)"', item)
            ven = re.findall(r"Tool made by\s*(.*?)</p>", item, re.S)
            tools.append({
                "desc": re.sub(r"\s+", " ", desc).strip(),
                "download": [urljoin(NMR_PAGE, html.unescape(d)) for d in dl],
                "howto": [urljoin(NMR_PAGE, html.unescape(h).replace(" ", "%20")) for h in how],
                "vendor": html.unescape(re.sub(r"<[^>]+>", "", ven[0])).strip() if ven else None,
            })
        out.append({"anchor": anchor, "title": title, "tools": tools})
    return out


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", s.lower())[:80]


def build(entries: list[dict], version: int, date: str) -> dict:
    families, solutions, used = [], [], set()
    for e in entries:
        fid = slug(e["anchor"])
        fname = re.sub(r"\s+Ransom$", "", e["title"])
        ref = f"{NMR_PAGE}#{e['anchor']}"
        families.append({"id": fid, "name": fname, "reference": ref})
        for t in e["tools"]:
            if not t["download"] or not t["vendor"]:
                continue
            url = t["download"][0]
            if not url.startswith("https://"):
                continue
            m = re.match(r"(.*?)\s+is designed to decrypt", t["desc"])
            name = (m.group(1).strip() if m else "") or f"{t['vendor']} decryptor"
            if name == "Decryptor":
                name = f"{t['vendor']} decryptor"
            sid = f"nmr.{fid}.{slug(t['vendor'])}"
            n = 2
            while sid in used:
                sid = f"nmr.{fid}.{slug(t['vendor'])}{n}"
                n += 1
            used.add(sid)
            host = urlparse(url).hostname or ""
            is_exe = urlparse(url).path.lower().endswith(".exe")
            howto = t["howto"][0] if t["howto"] and t["howto"][0].startswith("https://") else None
            solutions.append({
                "id": sid,
                "family_ids": [fid],
                "variant": None,
                "name": name,
                "vendor": t["vendor"],
                "official_page": ref,
                "howto_url": howto,
                "download_url": url,
                "official_domains": sorted({host, "www.nomoreransom.org"}),
                "version": None,
                "sha256": None,
                "sha256_source": None,
                "signature": {
                    "type": "authenticode" if is_exe or t["vendor"] in SIGNER_KEYWORDS else "unknown",
                    "expected_signer_keywords": SIGNER_KEYWORDS.get(t["vendor"], []),
                    "notes": "Signer keywords are a heuristic derived from the vendor name.",
                },
                "compatibility": {
                    "os": OS_HINTS.get(fid, ["windows"] if is_exe else []),
                    "variants": VARIANTS.get(fid, []),
                    "description": {
                        "en": f"Listed by No More Ransom for: {e['title']}.",
                        "it": f"Indicato da No More Ransom per: {e['title']}.",
                    },
                },
                "limitations": [GENERIC_LIMITATION],
                "last_verified": date,
                "verification_status": "listed_by_official_source",
                "sources": [ref],
            })
    for sol in solutions:
        ov = VENDOR_PAGE_OVERRIDES.get(sol["id"])
        if ov:
            for k in ("name", "official_page", "version", "verification_status"):
                sol[k] = ov[k]
            sol["limitations"] = ov["limitations"] + sol["limitations"]
            sol["sources"] = sol["sources"] + ov["extra_sources"]
    return {
        "schema_version": 1,
        "catalog_version": version,
        "generated_at": f"{date}T00:00:00Z",
        "publisher": "Serafis project",
        "notice": {
            "en": "Entries are taken from the official No More Ransom decryption tools page. Always download tools from the official link and verify them. SHA-256 values are not published by No More Ransom and are therefore not included unless independently obtained from the vendor.",
            "it": "Le voci provengono dalla pagina ufficiale degli strumenti di decrittazione di No More Ransom. Scarica sempre gli strumenti dal link ufficiale e verificali. I valori SHA-256 non sono pubblicati da No More Ransom e quindi non sono inclusi, salvo quando ottenuti direttamente dal produttore.",
        },
        "sources": [{"name": "No More Ransom - Decryption Tools", "url": NMR_PAGE, "retrieved_at": date}],
        "families": families,
        "solutions": solutions,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("html")
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "serafis" / "data" / "catalog.json"))
    a = ap.parse_args()
    cat = build(parse(Path(a.html).read_text(encoding="utf-8")), a.version, a.date)
    Path(a.out).write_text(json.dumps(cat, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"families={len(cat['families'])} solutions={len(cat['solutions'])} -> {a.out}")


if __name__ == "__main__":
    main()
