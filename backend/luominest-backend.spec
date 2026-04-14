# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

backend_root = Path(SPECPATH).parent

a = Analysis(
    ['main.py'],
    pathex=[str(backend_root)],
    binaries=[],
    datas=[
        ('config', 'config'),
    ],
    hiddenimports=[
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
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy.f2py',
        'PIL',
        'scipy',
        'pandas',
        'IPython',
        'jupyter',
    ],
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
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
