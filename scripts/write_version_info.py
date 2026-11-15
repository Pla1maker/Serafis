#!/usr/bin/env python3
"""Generate the Windows version resource used by PyInstaller from serafis.__version__."""
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from serafis import __version__  # noqa: E402

parts = [int(x) for x in __version__.split(".")] + [0] * 4
v = tuple(parts[:4])
(root / "scripts" / "version_info.txt").write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Serafis contributors'),
      StringStruct('FileDescription', 'SERAFIS - Ransomware Recovery Companion'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'Serafis'),
      StringStruct('LegalCopyright', 'MIT License'),
      StringStruct('OriginalFilename', 'Serafis.exe'),
      StringStruct('ProductName', 'SERAFIS'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")
print(__version__)
