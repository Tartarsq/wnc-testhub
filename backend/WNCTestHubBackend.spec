# -*- mode: python ; coding: utf-8 -*-

import glob

# QXDM automation locates on-screen UI elements by matching these PNG
# templates with OpenCV (see controllers/qxdm_controller.py). They're plain
# data files, not Python source, so PyInstaller's own import analysis never
# picks them up on its own - without listing them here explicitly, the
# packaged app would be missing them entirely and QXDM's Settings autofill
# (and command-bar location) would fail every time.
controller_template_datas = [
    (png_path, "controllers")
    for png_path in glob.glob("controllers/*.png")
]

a = Analysis(
    ['backend_launcher.py'],
    pathex=[],
    binaries=[],
    datas=controller_template_datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='WNCTestHubBackend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='WNCTestHubBackend',
)
