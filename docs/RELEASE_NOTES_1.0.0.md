# SERAFIS 1.0.0 — first release / prima release

**Ransomware Recovery Companion** for Windows — single `Serafis.exe`, no installation required.

## Features / Funzionalità
- 🇮🇹 / 🇬🇧 full Italian and English interface, persistent language choice.
- **Assessment** (read-only): multi-folder scan of file names and extensions, ransom-note detection, distribution of suspicious files, file/time limits and cancel.
- **Identification**: maintainable JSON rules for 30 families (extensions, file-name patterns, ransom-note names and text, note↔extension links); confidence levels (strong / probable / possible), alternatives, missing information; pluggable engine architecture with optional YARA engine.
- **Recovery options**: catalog of 222 official tools for 184 families, built from the official No More Ransom decryption tools page (retrieved 2026-11-15), signed with Ed25519.
- **Secure online catalog update**: HTTPS + allow-listed hosts, Ed25519 signature, JSON schema, anti-downgrade, size limits, safe network error handling.
- **Verification**: official origin (including the Windows *Zone.Identifier* download origin), SHA-256 against a trusted value when available, Authenticode signature, declared compatibility; unavailable checks are shown explicitly.
- **Recovery**: backup guidance, copy-only work folder with bit-identical verification, explicit confirmations, official tool opened only in a visible window and only after a cryptographic proof, result check by file header, full recovery unlocked only after a successful test.
- **No decryptor case**: “Nessun decryptor compatibile verificato è attualmente disponibile.” with recommendations and periodic catalog re-check.
- **Reports**: JSON, HTML and PDF export without unnecessary personal data.

## Known limitations / Limiti noti
- The executable is not code-signed: SmartScreen/antivirus may warn about it. Verify the SHA-256 published below.
- No More Ransom does not publish SHA-256 values or versions of the tools: for most catalog entries the hash check is reported as *not available* and authenticity relies on the official origin and the vendor's Authenticode signature.
- Identification is heuristic; always confirm it (e.g. ID Ransomware, No More Ransom Crypto Sheriff).
