"""模型目录解析（STT/TTS 共用）.

原先 faster_whisper_stt / funasr_stt / sherpa_onnx_stt / sherpa_onnx_tts
各自维护一份几乎相同的 `_resolve_model_root` / `_resolve_model_dir` 实现，
本模块将其收口为单一入口 `resolve_model_dir`，语义为四份实现的并集：

1. 环境变量（绝对路径覆盖，运维/测试用）
2. 打包态：sys.executable 同级 models/{kind}/（内置模型，只读）
3. 打包态回退：settings.DATA_DIR / "models" / {kind}（用户下载目录，可写）
4. 开发态：backend/models/{kind}/（__file__ 位于 backend/app/runtime/provider/，
   parents[3] = backend/）
"""

import os
import sys
from pathlib import Path


def _join(base: Path, kind: str, default_subdir: str) -> Path:
    """在 base 下拼接 models/{kind}[/{default_subdir}]（子目录为空时返回根目录）."""
    root = base / "models" / kind
    return root / default_subdir if default_subdir else root


def resolve_model_dir(
    kind: str,
    env_var: str,
    default_subdir: str = "",
    *,
    require_nonempty_builtin: bool = False,
) -> Path:
    """解析某类模型（kind: "st" / "tts"）的模型目录.

    Args:
        kind: 模型类别（"stt" 或 "tts"）
        env_var: 覆盖用的环境变量名（如 LUOMINEST_STT_MODEL_DIR）
        default_subdir: kind 根目录下的默认模型子目录（STT 传根目录本身时留空）
        require_nonempty_builtin: 打包态内置目录是否要求"存在且非空"才采用
            （STT 实现要求非空，TTS 实现仅要求存在）

    Returns:
        模型目录的绝对/相对路径
    """
    env_dir = os.environ.get(env_var)
    if env_dir:
        return Path(env_dir)
    if getattr(sys, "frozen", False):
        builtin_root = _join(Path(sys.executable).parent, kind, default_subdir)
        if builtin_root.exists() and (
            not require_nonempty_builtin or any(builtin_root.iterdir())
        ):
            return builtin_root
        # 打包态未内置模型，下载到用户数据目录（避免写入只读的 Program Files）
        from app.core.config import settings
        return _join(Path(settings.DATA_DIR), kind, default_subdir)
    return _join(Path(__file__).resolve().parents[3], kind, default_subdir)
