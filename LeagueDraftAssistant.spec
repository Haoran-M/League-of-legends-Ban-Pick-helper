# -*- mode: python ; coding: utf-8 -*-
"""Windows builds. LEAGUE_BUILD_MODE selects onedir or onefile."""

import os
from pathlib import Path

root = Path(SPECPATH)
mode = os.environ.get("LEAGUE_BUILD_MODE", "onefile")
debug_build = os.environ.get("LEAGUE_DEBUG_BUILD") == "1"
if mode not in {"onedir", "onefile"}:
    raise ValueError("LEAGUE_BUILD_MODE must be onedir or onefile")

a = Analysis(
    [str(root / "scripts/app_entry.py")],
    pathex=[str(root / "src")],
    binaries=[],
    datas=[(str(root / "src/league_draft/resources"), "league_draft/resources"),
           (str(root / "src/league_draft/storage/migrations"), "league_draft/storage/migrations")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # pandas is used by the development aggregation script; runtime imports are stdlib-only.
    excludes=["pytest", "pandas", "matplotlib", "tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)
# Qt uses the unversioned ICU API provided by Windows 10/11. Dependency scanning
# can instead collect a developer-runtime ICU with version-suffixed exports,
# shadowing Windows' ICU and causing QtCore import failures. Keep this OS DLL
# resolved by Windows; do not redistribute a mismatched development copy.
a.binaries = [entry for entry in a.binaries
              if Path(entry[0]).name.casefold() not in {"icuuc.dll", "icuin.dll", "icudt78.dll"}]
if mode == "onedir":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="LeagueDraftAssistant",
              debug=debug_build, bootloader_ignore_signals=False, strip=False, upx=False,
              console=debug_build, disable_windowed_traceback=False)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="LeagueDraftAssistant")
else:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name="LeagueDraftAssistant",
              debug=debug_build, bootloader_ignore_signals=False, strip=False, upx=False,
              console=debug_build, disable_windowed_traceback=False)
