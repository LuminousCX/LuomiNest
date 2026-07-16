import re
from pathlib import Path

_pyproject = Path(__file__).parent.parent / "pyproject.toml"
try:
    _content = _pyproject.read_text(encoding="utf-8")
    _match = re.search(r'^version\s*=\s*"([^"]+)"', _content, re.MULTILINE)
    __version__ = _match.group(1) if _match else "0.0.0"
except Exception:
    __version__ = "0.0.0"
