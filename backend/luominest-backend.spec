# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LuomiNest backend.

Bundles the FastAPI backend (main.py + app package) into a single executable.
Voice/STT providers that depend on heavy native libs (torch, faster-whisper,
sherpa-onnx, funasr) are NOT bundled by default - they are lazily imported
at runtime inside try/except blocks, so the backend starts fine without them.
Users who need local voice features should install the `voice` extra into the
runtime environment next to the executable.
"""

import sys
from pathlib import Path

block_cipher = None

# Project root (backend/)
PROJECT_ROOT = Path(SPECPATH)

# 后端 exe 图标（Windows），使任务管理器/通知显示项目图标而非默认图标
ICON_PATH = str(PROJECT_ROOT.parent / 'frontend' / 'resources' / 'icon.ico')
if not Path(ICON_PATH).exists():
    ICON_PATH = None

# ---------------------------------------------------------------------------
# Hidden imports - modules that PyInstaller's static analysis can't detect
# because they are imported dynamically via importlib / importlib.import_module
# or inside try/except blocks.
# ---------------------------------------------------------------------------
hiddenimports = [
    # --- FastAPI / Starlette / Pydantic ---
    'fastapi',
    'fastapi.middleware.cors',
    'fastapi.responses',
    'starlette.responses',
    'starlette.routing',
    'starlette.middleware',
    'pydantic',
    'pydantic_settings',
    'pydantic.fields',

    # --- Uvicorn ---
    'uvicorn',
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

    # --- Database ---
    'aiosqlite',
    'sqlalchemy',
    'sqlalchemy.dialects.sqlite',
    'sqlalchemy.dialects.sqlite.aiosqlite',
    'sqlalchemy.dialects.postgresql',
    'sqlalchemy.dialects.postgresql.asyncpg',
    'asyncpg',
    'pgvector',

    # --- Redis / MQTT ---
    'redis',
    'redis.asyncio',
    'paho.mqtt.client',

    # --- HTTP / WebSocket clients ---
    'httpx',
    'aiohttp',
    'websockets',

    # --- LLM providers ---
    'litellm',
    'openai',
    'anthropic',

    # --- Auth / crypto ---
    'cryptography',
    'jose',
    'passlib',
    'passlib.handlers.bcrypt',

    # --- Document parsing ---
    'fitz',            # PyMuPDF
    'docx',            # python-docx

    # --- Utils ---
    'loguru',
    'orjson',
    'tenacity',
    'numpy',
    'PIL',
    'apscheduler',
    'apscheduler.triggers.interval',
    'apscheduler.triggers.cron',
    'apscheduler.triggers.date',
    'edge_tts',
    'mcp',

    # --- Sherpa-ONNX TTS（离线 TTS 引擎，含 native lib）---
    'sherpa_onnx',
    'soundfile',

    # --- App internal packages (dynamically imported in app_factory lifespan) ---
    'app.core.tools',
    'app.core.tools.builtin',
    'app.core.tools.mcp',
    'app.core.tools.mcp.manager',
    'app.core.scheduler',
    'app.core.scheduler.manager',
    'app.core.workflow',
    'app.core.workflow.register_tools',
    'app.engines.memory',
    'app.infrastructure.database.conversation_store',
    'app.infrastructure.database.json_store',
    'app.services.platform_router',
    'app.services.cleanup_service',
    'app.runtime.platform.registry',
    'app.runtime.provider.tts',
    'app.runtime.provider.tts.tts_registry',
    'app.runtime.provider.stt',
    'app.runtime.provider.llm',
]

# ---------------------------------------------------------------------------
# Packages to exclude - heavy / unused / platform-specific
# ---------------------------------------------------------------------------
excludes = [
    # Heavy ML stack - not bundled by default. Voice providers fall back
    # gracefully when these are missing (try/except in their modules).
    'torch',
    'torchaudio',
    'torchvision',
    'transformers',
    'tokenizers',
    'whisper_cpp_python',
    'faster_whisper',
    'funasr',
    'modelscope',
    'sounddevice',
    'pyaudio',
    # Optional DB drivers probed by SQLAlchemy's hook but not used here.
    # Project uses aiosqlite (SQLite) + asyncpg (PostgreSQL) only.
    'pysqlite2',
    'MySQLdb',
    'mysql',
    'psycopg2',
    # Test / lint tooling - never needed at runtime
    'pytest',
    'pytest_asyncio',
    'pytest_cov',
    'ruff',
    'mypy',
    # Misc
    'tkinter',
    'matplotlib',
    'IPython',
    'notebook',
    'jupyter',
    # PyGObject / GTK - not used by LuomiNest. PyInstaller's hook-gi.py
    # unconditionally queries pygobject metadata at hook-load time and crashes
    # when pygobject is absent. Excluding 'gi' prevents the hook from firing.
    'gi',
    'pygobject',
]

# ---------------------------------------------------------------------------
# Data files - ship config templates so the executable can run standalone
# ---------------------------------------------------------------------------
datas = [
    (str(PROJECT_ROOT / 'config'), 'config'),
    (str(PROJECT_ROOT / 'plugins'), 'plugins'),
    (str(PROJECT_ROOT / 'skills'), 'skills'),
    (str(PROJECT_ROOT.parent / 'LICENSE'), '.'),
]

# Filter out paths that don't exist (keeps spec robust on partial checkouts)
datas = [(src, dst) for src, dst in datas if Path(src).exists()]

a = Analysis(
    [str(PROJECT_ROOT / 'main.py')],
    pathex=[str(PROJECT_ROOT)],
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

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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
    icon=ICON_PATH,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='luominest-backend',
)
