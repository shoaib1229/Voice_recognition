# -*- mode: python ; coding: utf-8 -*-
"""
nova.spec
=========
PyInstaller specification file for Nova Voice Assistant.

Features:
- Packages the CustomTkinter desktop GUI application into a standalone Windows executable.
- Collects CustomTkinter assets, themes, and font files.
- Includes speech synthesis (pyttsx3 / SAPI5) and audio capture (SpeechRecognition / PyAudio).
- Strictly excludes sensitive files (.env, logs), test frameworks (pytest), and caches.
- Configured with console=False (windowed mode) so the GUI launches cleanly without a command prompt.
"""

import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files

block_cipher = None

# 1. Collect CustomTkinter assets (fonts, themes, icons)
datas = []
datas += collect_data_files('customtkinter')

# 2. Collect runtime hidden imports
hiddenimports = [
    'customtkinter',
    'pyttsx3',
    'pyttsx3.drivers',
    'pyttsx3.drivers.sapi5',
    'speech_recognition',
    'pyaudio',
    'requests',
    'dotenv',
    'PIL',
]

# 3. Explicitly exclude test frameworks and development-only libraries
excludes = [
    # SpeechRecognition ships an unused optional Whisper API adapter that
    # otherwise pulls in the OpenAI SDK. Nova uses its Google STT backend.
    'openai',
    'pytest',
    'pytest_mock',
    '_pytest',
    'unittest',
    'tests',
    # SpeechRecognition offers optional offline engines, but Nova uses its
    # Google STT backend. Keep their large ML/scientific stacks out of the GUI build.
    'whisper',
    'faster_whisper',
    'vosk',
    'torch',
    'scipy',
    'pandas',
    'pyarrow',
    'matplotlib',
]

a = Analysis(
    ['app.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Nova',
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
    # icon='assets/icon.ico',  # Uncomment if an .ico file is provided
)
