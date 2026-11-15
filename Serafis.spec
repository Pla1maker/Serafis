# PyInstaller spec for the Windows one-file build:  pyinstaller Serafis.spec
from pathlib import Path

root = Path(SPECPATH)
datas = [
    (str(root / "serafis" / "data"), "serafis/data"),
    (str(root / "serafis" / "localization" / "en.json"), "serafis/localization"),
    (str(root / "serafis" / "localization" / "it.json"), "serafis/localization"),
    (str(root / "serafis" / "resources"), "serafis/resources"),
]

excluded = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml", "PySide6.QtQuick",
    "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtNetwork", "PySide6.QtSql", "PySide6.QtTest",
    "tkinter", "unittest", "pydoc",
]

a = Analysis(
    [str(root / "Serafis.py")],
    pathex=[str(root)],
    datas=datas,
    hiddenimports=["jsonschema_specifications"],
    excludes=excluded,
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="Serafis",
    icon=str(root / "serafis" / "resources" / "serafis.ico"),
    version=str(root / "scripts" / "version_info.txt"),
    console=False,
    upx=False,
    debug=False,
    strip=False,
)
