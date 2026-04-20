# -*- mode: python ; coding: utf-8 -*-
import sys
import os
from pathlib import Path

block_cipher = None

backend_root = Path(SPECPATH).parent
is_windows = sys.platform == 'win32'
is_macos = sys.platform == 'darwin'
is_linux = sys.platform.startswith('linux')

icon_path = None
if is_windows:
    icon_candidate = backend_root / '..' / 'frontend' / 'resources' / 'icon.ico'
    if icon_candidate.exists():
        icon_path = str(icon_candidate)
elif is_macos:
    icon_candidate = backend_root / '..' / 'frontend' / 'resources' / 'icon.icns'
    if icon_candidate.exists():
        icon_path = str(icon_candidate)

hidden_imports = [
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'pydantic',
    'pydantic_settings',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.postgresql',
    'aiosqlite',
    'asyncpg',
    'redis',
    'paho.mqtt.client',
    'httpx',
    'websockets',
    'loguru',
    'orjson',
    'cryptography',
    'jose',
    'passlib',
    'passlib.handlers',
    'passlib.handlers.bcrypt',
]

if is_linux:
    hidden_imports += [
        'sqlalchemy.dialects.sqlite',
        'sqlite3',
    ]

excludes = [
    'tkinter',
    'matplotlib',
    'numpy.f2py',
    'PIL',
    'scipy',
    'pandas',
    'IPython',
    'jupyter',
    'pytest',
    'ruff',
    'mypy',
]

datas = [
    ('config', 'config'),
]

if is_macos:
    datas.append(('../LICENSE', '.'))

a = Analysis(
    ['main.py'],
    pathex=[str(backend_root)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='luominest-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=is_macos or is_linux,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path,
)
