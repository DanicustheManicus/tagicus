# -*- mode: python ; coding: utf-8 -*-
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))
APP_DIR = os.path.join(PROJECT_ROOT, "app")

if sys.platform == "win32":
    fpcalc_src = os.path.join(PROJECT_ROOT, "vendor", "fpcalc", "windows", "fpcalc.exe")
else:
    fpcalc_src = os.path.join(PROJECT_ROOT, "vendor", "fpcalc", "linux", "fpcalc")

hiddenimports = [
    "server", "database", "scanner", "tag_writer", "config", "paths", "models",
    "sources", "sources.tag_reader", "sources.filename_parser", "sources.acoustid_source",
    "sources.musicbrainz_source", "sources.discogs_source", "sources.deezer_source",
    "sources.audiodb_source", "sources.wikidata_source", "sources.openopus_source",
    "sources.vgmdb_source", "sources.vocadb_source", "sources.metallum_source",
    "sources.lrclib_source", "sources.compare",
    "uvicorn.logging", "uvicorn.loops", "uvicorn.loops.auto",
    "uvicorn.protocols", "uvicorn.protocols.http", "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets", "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan", "uvicorn.lifespan.on",
]

ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")

a = Analysis(
    ["main.py"],
    pathex=[PROJECT_ROOT, APP_DIR],
    binaries=[(fpcalc_src, ".")],
    datas=[
        (os.path.join(APP_DIR, "static"), "static"),
        (os.path.join(ASSETS_DIR, "icon.png"), "."),
        (os.path.join(ASSETS_DIR, "icon.ico"), "."),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PyQt5", "PySide2", "PySide6", "PyQt6"],
    noarchive=False,
)

# The GTK/WebKit2 hook pulls in every installed cursor/icon theme and GTK
# widget theme on the build machine (~980MB here) even though the app just
# needs a single WebKit2 render surface. The end user's own desktop already
# has icon/cursor/GTK themes installed, so these bundled copies are pure
# duplication - strip them to keep the onefile size sane.
_EXCLUDED_DATA_PREFIXES = ("share/icons/", "share/themes/", "share/locale/")
a.datas = [d for d in a.datas if not d[0].startswith(_EXCLUDED_DATA_PREFIXES)]

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="Tagicus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(ASSETS_DIR, "icon.ico"),
)
