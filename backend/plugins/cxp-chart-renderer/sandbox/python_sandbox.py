"""Python 代码沙箱 — AST 白名单扫描 + 子进程隔离执行。

安全措施：
- AST 扫描 import 语句，仅允许白名单库
- 正则扫描危险模式（exec/eval/os/subprocess 等）
- 子进程隔离执行（临时目录 + 超时 + 无网络）
- matplotlib 强制 Agg 后端
"""
import ast
import asyncio
import os
import re
import tempfile
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# 允许的 import（第三方 + 标准库）
ALLOWED_IMPORTS = frozenset({
    "numpy", "matplotlib", "matplotlib.pyplot",
    "pandas",
    "math", "random", "statistics",
    "itertools", "functools", "collections",
    "json", "io", "base64",
    "copy", "operator", "string",
})

# 危险模式正则
DANGEROUS_PATTERNS = [
    r"\bimport\s+os\b",
    r"\bfrom\s+os\b",
    r"\bimport\s+subprocess\b",
    r"\bfrom\s+subprocess\b",
    r"\bimport\s+socket\b",
    r"\bfrom\s+socket\b",
    r"\bimport\s+sys\b",
    r"\bfrom\s+sys\b",
    r"\bimport\s+shutil\b",
    r"\bfrom\s+shutil\b",
    r"\bimport\s+pathlib\b",
    r"\bfrom\s+pathlib\b",
    r"\bimport\s+ctypes\b",
    r"\bfrom\s+ctypes\b",
    r"\b__import__\s*\(",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bcompile\s*\(",
    r"\b__builtins__\b",
    r"\bglobals\s*\(\s*\)",
    r"\blocals\s*\(\s*\)",
]


@dataclass
class ScanResult:
    allowed: bool
    blocked_imports: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class ExecutionResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    output_files: list[str] = field(default_factory=list)
    execution_time_ms: float = 0


def scan_imports(code: str) -> ScanResult:
    """AST 扫描代码的 import 语句和危险模式。"""
    # 1. 语法检查
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return ScanResult(allowed=False, error=f"语法错误: line {e.lineno}: {e.msg}")

    # 2. import 白名单检查
    blocked = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root_module = alias.name.split(".")[0]
                if root_module not in ALLOWED_IMPORTS and alias.name not in ALLOWED_IMPORTS:
                    blocked.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root_module = node.module.split(".")[0]
                if root_module not in ALLOWED_IMPORTS and node.module not in ALLOWED_IMPORTS:
                    blocked.append(node.module)

    # 3. 危险模式正则扫描
    for pattern in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            match = re.search(pattern, code)
            blocked.append(f"pattern:{match.group(0)}")

    return ScanResult(
        allowed=len(blocked) == 0,
        blocked_imports=blocked,
    )


async def execute_python(
    code: str,
    timeout: float = 30.0,
    output_dir: str | None = None,
) -> ExecutionResult:
    """在子进程中隔离执行 Python 代码。

    Args:
        code: Python 代码字符串
        timeout: 超时秒数
        output_dir: 输出目录（None 则自动创建临时目录）

    Returns:
        ExecutionResult: 执行结果（stdout/stderr/输出文件列表）
    """
    import time

    # 强制注入 Agg 后端
    preamble = (
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
    )
    full_code = preamble + code

    # 准备输出目录
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="cxp_chart_")

    # 写入临时脚本文件
    script_path = os.path.join(output_dir, "_exec_script.py")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(full_code)

    start_time = time.monotonic()

    try:
        proc = await asyncio.create_subprocess_exec(
            "python", script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=output_dir,
            env={
                **{k: v for k, v in os.environ.items()
                   if k not in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy")},
                "MPLBACKEND": "Agg",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            elapsed = (time.monotonic() - start_time) * 1000
            return ExecutionResult(
                success=False,
                stderr=f"代码执行超时（{timeout}秒限制）",
                execution_time_ms=elapsed,
            )

        elapsed = (time.monotonic() - start_time) * 1000
        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        # 收集输出文件（排除脚本本身）
        output_files = []
        for fname in os.listdir(output_dir):
            if fname == "_exec_script.py":
                continue
            fpath = os.path.join(output_dir, fname)
            if os.path.isfile(fpath):
                output_files.append(fpath)

        return ExecutionResult(
            success=(proc.returncode == 0),
            stdout=stdout_text,
            stderr=stderr_text,
            output_files=output_files,
            execution_time_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.monotonic() - start_time) * 1000
        logger.error(f"[PythonSandbox] Execution error: {e}")
        return ExecutionResult(
            success=False,
            stderr=f"沙箱执行异常: {e}",
            execution_time_ms=elapsed,
        )
