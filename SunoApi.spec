# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    VSVersionInfo, VarFileInfo, VarStruct, StringFileInfo, 
    StringTable, StringStruct, FixedFileInfo
)

datas = []
binaries = []
hiddenimports = ['mutagen', 'requests', 'colorama', 'pyperclip', 'PIL', 'PIL._tkinter_finder']

# Include resources folder
import os
if os.path.exists('resources'):
    datas.append(('resources', 'resources'))

tmp_ret = collect_all('mutagen')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Version info to reduce false positives
version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(1, 0, 0, 0),
        prodvers=(1, 0, 0, 0),
        mask=0x3f,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0)
    ),
    kids=[
        StringFileInfo([
            StringTable(
                u'040904B0',
                [
                    StringStruct(u'CompanyName', u'SunoSync'),
                    StringStruct(u'FileDescription', u'Suno Music Downloader'),
                    StringStruct(u'FileVersion', u'1.0.0.0'),
                    StringStruct(u'InternalName', u'SunoApiDownloader'),
                    StringStruct(u'LegalCopyright', u'Copyright (C) 2024'),
                    StringStruct(u'OriginalFilename', u'SunoApiDownloader.exe'),
                    StringStruct(u'ProductName', u'SunoSync'),
                    StringStruct(u'ProductVersion', u'1.0.0.0')
                ]
            )
        ]),
        VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
    ]
)

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
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
    name='SunoSyncV2',
    icon='resources/icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # Disable UPX compression - major cause of false positives
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Disable console for clean build (enable if debugging needed)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=version_info,  # Add version info to reduce false positives
)
