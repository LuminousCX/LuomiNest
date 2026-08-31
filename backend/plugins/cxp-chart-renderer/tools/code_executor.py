"""execute_plot_code — 自由代码执行工具（沙箱安全执行）。

对齐 tool-system-optimization.md §4.9.3：
- 执行失败时返回结构化错误信息 + 修正建议
- LLM 在 function calling 循环中自行修正重试
- retry=true 返回修正建议，retry=false 返回原始错误
"""
import os
import sys

from app.core.tools import ToolBase, ToolResult


class ExecutePlotCodeTool(ToolBase):
    tier = "domain"
    scope = "shared"

    @property
    def name(self) -> str:
        return "execute_plot_code"

    @property
    def description(self) -> str:
        return (
            "在安全沙箱中执行 Python 绘图代码。适用于预置图表工具无法满足的复杂/定制可视化需求。"
            "代码中可使用 numpy、matplotlib、pandas 及 Python 标准库（math/random/statistics 等）。"
            "执行失败时返回结构化错误信息和修正建议，你可以修正代码后重新调用。"
            "禁止 import os/subprocess/socket 等危险模块。"
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "完整的 Python 绘图代码。代码应自包含（含 import 语句）。"
                },
                "retry": {
                    "type": "boolean",
                    "description": "执行失败时是否返回修正建议（默认 true）",
                    "default": True,
                },
            },
            "required": ["code"],
        }

    def bind_plugin(self, plugin):
        self._plugin = plugin
        return self

    async def execute(self, arguments: dict) -> ToolResult:
        code = arguments.get("code", "").strip()
        if not code:
            return ToolResult.fail("缺少 code 参数")

        retry = arguments.get("retry", True)

        # 确保插件目录在 sys.path 中
        plugin_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if plugin_dir not in sys.path:
            sys.path.insert(0, plugin_dir)

        from sandbox.python_sandbox import scan_imports, execute_python
        from utils.image_utils import encode_output, validate_image

        # 1. AST 安全扫描
        scan = scan_imports(code)
        if not scan.allowed:
            error_msg = f"代码包含不允许的导入或危险操作: {scan.blocked_imports}"
            if retry:
                error_msg += "\n建议: 移除上述不允许的导入/操作后重试。允许的库: numpy, matplotlib, pandas, math, random, statistics, itertools, functools, collections, json, io, base64"
            return ToolResult.fail(error_msg)

        # 2. 沙箱执行
        timeout = int(self._plugin.context.get_config("execution_timeout", 30) or 30)
        data_dir = self._plugin.context.get_data_dir()
        result = await execute_python(code, timeout=timeout)

        if result.success:
            # 查找生成的图片文件
            image_files = [f for f in result.output_files
                          if f.endswith((".png", ".svg", ".jpg", ".jpeg"))]

            if image_files:
                # 读取第一个图片文件
                with open(image_files[0], "rb") as f:
                    image_bytes = f.read()

                validation = validate_image(image_bytes)
                if not validation.get("valid", True):
                    return ToolResult.fail(f"图片验证失败: {validation.get('error', '')}")

                inline_threshold_kb = int(
                    self._plugin.context.get_config("inline_threshold_kb", 50) or 50
                )
                output = encode_output(image_bytes, inline_threshold_kb, data_dir)
                return ToolResult.ok(
                    output.get("markdown", ""),
                    metadata={"mode": output.get("mode", ""), "size_kb": output.get("size_kb", 0)},
                )
            else:
                # 没有生成图片，返回 stdout
                return ToolResult.ok(
                    result.stdout or "代码执行成功，但未生成图片文件。请确保代码中有 plt.savefig() 调用。",
                    metadata={"execution_time_ms": result.execution_time_ms},
                )
        else:
            # 执行失败 — 返回结构化错误
            error_info = self._format_error(result, retry)
            return ToolResult.fail(error_info)

    def _format_error(self, result, retry: bool) -> str:
        """格式化错误信息，可选附加修正建议。"""
        stderr = result.stderr.strip()

        if not retry:
            return f"代码执行失败:\n{stderr}"

        # 基于错误类型生成修正建议
        suggestion = ""
        if "ModuleNotFoundError" in stderr or "ImportError" in stderr:
            suggestion = "\n\n修正建议: 代码尝试导入不在允许列表中的库。允许的库: numpy, matplotlib, pandas, math, random, statistics, itertools, functools, collections, json, io, base64。请替换为等效的允许库。"
        elif "SyntaxError" in stderr:
            suggestion = "\n\n修正建议: 代码存在语法错误。请检查报错行号附近的代码语法（括号匹配、缩进、冒号等）。"
        elif "NameError" in stderr:
            suggestion = "\n\n修正建议: 变量或函数未定义。请检查是否缺少 import 语句或变量名拼写错误。"
        elif "ValueError" in stderr or "TypeError" in stderr:
            suggestion = "\n\n修正建议: 参数值或类型错误。请检查传入参数的值和数据类型。"
        elif "超时" in stderr:
            suggestion = "\n\n修正建议: 代码执行超时。请优化代码（减少数据量、简化计算、避免无限循环）。"
        elif "MemoryError" in stderr:
            suggestion = "\n\n修正建议: 内存超限。请减少数据规模或分批处理。"
        else:
            suggestion = "\n\n修正建议: 请检查代码逻辑，修正错误后重新调用 execute_plot_code。"

        return f"代码执行失败:\n{stderr}{suggestion}"
