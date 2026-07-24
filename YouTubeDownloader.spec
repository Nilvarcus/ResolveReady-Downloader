# -*- mode: python ; coding: utf-8 -*-
import os
import customtkinter

# Get customtkinter path for theme bundling
ctk_path = os.path.dirname(customtkinter.__file__)

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('HandBrakeCLI.exe', '.'), 
        ('ffmpeg.exe', '.'),
        ('resolve_preset.json', '.'),
        ('Nilvarcus-Resolve-Downloader-icon.ico', '.'),
        (os.path.join(ctk_path, 'assets'), 'customtkinter/assets')
    ],
    hiddenimports=['yt_dlp'],
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
    a.binaries,
    a.datas,
    [],
    name='YouTubeDownloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    icon='Nilvarcus-Resolve-Downloader-icon.ico',
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
