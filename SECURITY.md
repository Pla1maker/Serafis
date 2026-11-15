# Security policy

## Design principles
- Read-only analysis; originals are never modified, renamed, moved or deleted (tested).
- File content is read only for small files whose *name* looks like a ransom note (first 64 KiB).
- All external content (ransom notes, file names, catalog, downloads) is treated as untrusted: plain-text rendering in the GUI, HTML escaping and a restrictive CSP in reports, path sanitisation and traversal protection.
- Network access only on explicit user action (catalog update, official download), HTTPS only, allow-listed hosts / official domains, timeouts and size limits.
- Catalog updates must be signed (Ed25519) with a key built into the application; downgrades are refused.
- Downloaded tools are never executed automatically. A tool is opened (visibly, via the Windows shell) only after the user confirms and only if a trusted SHA-256 or a valid vendor Authenticode signature was confirmed and no check failed.
- No telemetry. Logs are local and redact the home directory and e-mail addresses.

## Reporting a vulnerability
Please open a private security advisory on GitHub (Security → Report a vulnerability) instead of a public issue.
