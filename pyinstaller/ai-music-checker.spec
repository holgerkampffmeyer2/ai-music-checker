# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['../ai_music_checker/cli.py'],
    pathex=[],
    binaries=[],
    datas=[('../ai_music_checker/data', 'ai_music_checker/data')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ai-music-checker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ai-music-checker',
)
