# SERAFIS — Quick start / Guida rapida

## 🇮🇹 Italiano
1. **Scollega** il computer colpito dalla rete se l'attacco potrebbe essere ancora in corso.
2. Avvia **Serafis.exe** (non richiede installazione né Python). Windows SmartScreen può avvisare che l'app non è firmata: scegli *Ulteriori informazioni → Esegui comunque* solo se l'hai scaricata dalla pagina ufficiale delle release GitHub e lo SHA-256 coincide con `Serafis.exe.sha256`.
3. Scegli la lingua (🇮🇹 / 🇬🇧). La scelta viene ricordata.
4. Segui i 6 passi: **Analisi → Identificazione → Opzioni di recupero → Verifica → Recupero → Risultati**.
5. Serafis non modifica, sposta o cancella i tuoi file. Lavora sempre su copie.
6. Esporta il rapporto (JSON / HTML / PDF) e conservalo.

Verifica dell'eseguibile (PowerShell):
```powershell
Get-FileHash .\Serafis.exe -Algorithm SHA256
```

## 🇬🇧 English
1. **Disconnect** the affected computer from the network if the attack may still be in progress.
2. Run **Serafis.exe** (no installation, no Python needed). Windows SmartScreen may warn that the app is unsigned: choose *More info → Run anyway* only if you downloaded it from the official GitHub releases page and its SHA-256 matches `Serafis.exe.sha256`.
3. Pick your language (🇮🇹 / 🇬🇧). The choice is remembered.
4. Follow the 6 steps: **Assessment → Identification → Recovery options → Verification → Recovery → Results**.
5. Serafis never modifies, moves or deletes your files. Always work on copies.
6. Export the report (JSON / HTML / PDF) and keep it.

Settings, logs and the catalog cache are stored in `%APPDATA%\Serafis`.
