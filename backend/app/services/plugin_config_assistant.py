"""CxPluginConfigAssistant — LuomiNest 插件配置 AI 助手服务。

参照研究报告 Phase 3 设计，让 LLM 通过自然语言完成插件相关操作：
1. **配置修改**：将用户自然语言请求转换为对插件 settings 的 JSON patch
2. **脚手架生成**：根据用户描述生成新插件目录骨架（manifest.json + main.py + README）
3. **配置解释**：用自然语言解释插件当前配置含义

设计原则：
- **manifest 约束**：所有配置修改必须符合 manifest.settings 声明，越界字段直接拒绝
- **类型校验**：根据 settings 字段的 type / enum / range 进行严格类型检查
- **不直接执行**：服务返回建议的 patch 与脚手架内容，由 API 层/用户确认后应用
- **品牌一致**：所有类与文件名使用 Cx 前缀
- **安全优先**：脚手架代码默认最小权限，不含 SYSTEM_COMMAND / FILE_SYSTEM 等高危权限
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any

from loguru import logger

from app.core.config import get_settings
from app.core.utils import utc_now
from app.infrastructure.database.json_store import JsonStore
from app.runtime.plugin.cxplugin.kv_store import PluginKVStore
from app.runtime.plugin.cxplugin.registry import cx_plugin_registry


# 插件配置存储命名空间（与 PluginKVStore 同一存储，但用专属前缀避免冲突）
_PLUGIN_CONFIG_PREFIX = "settings:"
# 脚手架历史记录（便于用户回看与重用）
_scaffold_store = JsonStore("cx_plugin_scaffolds.json")


@dataclass
class CxSettingPatch:
    """单个配置项的修改补丁。"""
    op: str                          # "set" / "remove" / "reset"
    key: str                         # 配置项 key（manifest.settings 中声明）
    value: Any = None                # set 时的值
    reason: str = ""                 # LLM 给出的修改原因
    validation_error: str = ""       # 校验失败原因（非空时表示该 patch 不合法）

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CxConfigSuggestion:
    """LLM 生成的配置修改建议。"""
    plugin_id: str
    user_request: str
    patches: list[CxSettingPatch] = field(default_factory=list)
    summary: str = ""                # 一句话总结建议
    confidence: float = 0.0
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "user_request": self.user_request,
            "patches": [p.to_dict() for p in self.patches],
            "summary": self.summary,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass
class CxPluginScaffold:
    """插件脚手架生成结果。"""
    plugin_id: str
    name: str
    description: str
    files: dict[str, str] = field(default_factory=dict)   # {相对路径: 文件内容}
    created_at: str = field(default_factory=utc_now)
    notes: list[str] = field(default_factory=list)        # 给用户的提示

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CxPluginConfigAssistant:
    """插件配置 AI 助手 — 全局单例 cx_plugin_config_assistant。

    对外提供：
    - suggest_config_change：根据用户自然语言生成配置 patch 建议
    - apply_config_patches：应用 patch 到插件 KV 存储
    - get_plugin_config：读取插件当前配置
    - explain_config：用自然语言解释插件配置
    - generate_scaffold：根据描述生成新插件脚手架
    - write_scaffold_to_disk：将脚手架写入 plugins/ 目录
    """

    def __init__(self) -> None:
        self._llm_adapter = None

    # ------------------------------------------------------------------
    # LLM 适配器（懒加载）
    # ------------------------------------------------------------------

    def _get_llm_adapter(self):
        if self._llm_adapter is None:
            from app.runtime.provider.llm.adapter import llm_adapter
            self._llm_adapter = llm_adapter
        return self._llm_adapter

    # ------------------------------------------------------------------
    # 配置读取
    # ------------------------------------------------------------------

    def get_plugin_config(self, plugin_id: str) -> dict[str, Any]:
        """获取插件当前配置（合并 manifest 默认值与 KV 存储值）。"""
        meta = cx_plugin_registry.get_plugin(plugin_id)
        if meta is None:
            raise ValueError(f"插件未加载: {plugin_id}")

        settings_decl = meta.manifest.settings or {}
        kv_store = PluginKVStore(plugin_id)
        result: dict[str, Any] = {}

        for key, decl in settings_decl.items():
            if not isinstance(decl, dict):
                continue
            default = decl.get("default")
            stored = kv_store.get(f"{_PLUGIN_CONFIG_PREFIX}{key}", default)
            result[key] = stored

        return {
            "plugin_id": plugin_id,
            "settings": result,
            "declarations": settings_decl,
        }

    def reset_plugin_config(self, plugin_id: str) -> dict[str, Any]:
        """重置插件配置到 manifest 默认值。"""
        meta = cx_plugin_registry.get_plugin(plugin_id)
        if meta is None:
            raise ValueError(f"插件未加载: {plugin_id}")

        settings_decl = meta.manifest.settings or {}
        kv_store = PluginKVStore(plugin_id)
        for key in settings_decl.keys():
            kv_store.delete(f"{_PLUGIN_CONFIG_PREFIX}{key}")

        logger.info(f"[CxPluginConfigAssistant] Reset config: {plugin_id}")
        return self.get_plugin_config(plugin_id)

    # ------------------------------------------------------------------
    # LLM 配置建议
    # ------------------------------------------------------------------

    async def suggest_config_change(
        self,
        plugin_id: str,
        user_request: str,
    ) -> CxConfigSuggestion:
        """让 LLM 根据用户自然语言生成配置 patch 建议。

        Args:
            plugin_id: 插件 id
            user_request: 用户的自然语言配置请求，如"把超时改成 30 秒"

        Returns:
            CxConfigSuggestion 对象，patches 已经过类型校验
        """
        meta = cx_plugin_registry.get_plugin(plugin_id)
        if meta is None:
            raise ValueError(f"插件未加载: {plugin_id}")

        current_config = self.get_plugin_config(plugin_id)
        settings_decl = current_config["declarations"]
        current_values = current_config["settings"]

        prompt = self._build_config_prompt(
            plugin_id, meta.manifest.name, user_request, settings_decl, current_values
        )

        try:
            llm = self._get_llm_adapter()
            from app.runtime.provider.llm.adapter import RouteHint
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": "你是插件配置助手。严格按 JSON 输出配置修改建议。"},
                    {"role": "user", "content": prompt},
                ],
                route_hint=RouteHint.CHAT,
                temperature=0.2,
                max_tokens=2048,
            )
            suggestion_text = str(response).strip()
        except Exception as e:
            logger.error(f"[CxPluginConfigAssistant] LLM call failed: {e}")
            raise RuntimeError(f"LLM 调用失败: {e}") from e

        suggestion_data = self._parse_config_response(suggestion_text)
        if suggestion_data is None:
            raise RuntimeError("LLM 返回内容无法解析为配置建议")

        # 构建 patch 列表并逐个校验
        patches: list[CxSettingPatch] = []
        for raw_patch in suggestion_data.get("patches", []):
            patch = CxSettingPatch(
                op=str(raw_patch.get("op", "set")),
                key=str(raw_patch.get("key", "")),
                value=raw_patch.get("value"),
                reason=str(raw_patch.get("reason", "")),
            )
            # 校验
            err = self._validate_patch(patch, settings_decl)
            if err:
                patch.validation_error = err
            patches.append(patch)

        return CxConfigSuggestion(
            plugin_id=plugin_id,
            user_request=user_request,
            patches=patches,
            summary=str(suggestion_data.get("summary", "")),
            confidence=float(suggestion_data.get("confidence", 0.0)),
        )

    def _build_config_prompt(
        self,
        plugin_id: str,
        plugin_name: str,
        user_request: str,
        settings_decl: dict[str, Any],
        current_values: dict[str, Any],
    ) -> str:
        """构建让 LLM 生成配置 patch 的 prompt。"""
        decl_lines = []
        for key, decl in settings_decl.items():
            if not isinstance(decl, dict):
                continue
            decl_lines.append(
                f"- `{key}` (type={decl.get('type', 'string')}, "
                f"default={json.dumps(decl.get('default'), ensure_ascii=False)}, "
                f"current={json.dumps(current_values.get(key), ensure_ascii=False)}, "
                f"description={decl.get('description', '')}, "
                f"enum={decl.get('enum', [])}, "
                f"range={decl.get('range', {})})"
            )
        decl_block = "\n".join(decl_lines) if decl_lines else "(无配置项声明)"

        return f"""请根据用户的自然语言请求，生成对插件 `{plugin_id}` ({plugin_name}) 配置的修改建议。

## 当前可用配置项
{decl_block}

## 用户请求
{user_request}

## 当前配置值
{json.dumps(current_values, ensure_ascii=False, indent=2)}

## 输出格式（严格 JSON）
```json
{{
  "summary": "一句话总结本次修改",
  "confidence": 0.0,
  "patches": [
    {{"op": "set", "key": "配置项 key", "value": "新值", "reason": "修改原因"}}
  ]
}}
```

注意：
- op 仅允许 "set"（设置）或 "remove"（删除，恢复默认）
- key 必须是上面列出的配置项之一，不要臆造
- value 类型必须与声明中的 type 匹配（string/number/boolean/array/object）
- 若 value 在 enum 中，必须取其中一个值
- 若声明了 range，value 必须在范围内
- 若用户请求无法理解或不涉及配置修改，返回空 patches 与 confidence=0
"""

    def _parse_config_response(self, text: str) -> dict[str, Any] | None:
        """解析 LLM 返回的 JSON 配置建议。"""
        candidates: list[str] = [text]
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            if end > start:
                candidates.insert(0, text[start:end].strip())
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            if end > start:
                candidates.insert(0, text[start:end].strip())

        for cand in candidates:
            try:
                data = json.loads(cand)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
        return None

    # ------------------------------------------------------------------
    # Patch 校验与应用
    # ------------------------------------------------------------------

    def _validate_patch(
        self,
        patch: CxSettingPatch,
        settings_decl: dict[str, Any],
    ) -> str:
        """校验单个 patch 合法性，返回错误字符串（空字符串表示通过）。"""
        if patch.op not in ("set", "remove", "reset"):
            return f"非法 op: {patch.op}"

        if patch.key not in settings_decl:
            return f"未声明的配置项: {patch.key}"

        if patch.op in ("remove", "reset"):
            return ""  # 重置类操作无需校验 value

        # set 操作需要类型校验
        decl = settings_decl[patch.key]
        if not isinstance(decl, dict):
            return ""  # 声明不规范，跳过校验

        decl_type = str(decl.get("type", "string"))
        value = patch.value

        type_map = {
            "string": str,
            "text": str,
            "number": (int, float),
            "integer": int,
            "boolean": bool,
            "array": list,
            "object": dict,
        }
        expected = type_map.get(decl_type)
        if expected and not isinstance(value, expected):
            return f"value 类型错误: 期望 {decl_type}, 实际 {type(value).__name__}"

        # 布尔特殊处理（Python bool 是 int 子类，需要排除）
        if decl_type == "boolean" and not isinstance(value, bool):
            return "value 类型错误: 期望 boolean"

        # 枚举校验
        enum_values = decl.get("enum")
        if enum_values and isinstance(enum_values, list) and value not in enum_values:
            return f"value 不在允许的 enum 范围内: {enum_values}"

        # 范围校验（number）
        range_decl = decl.get("range")
        if range_decl and isinstance(range_decl, dict) and isinstance(value, (int, float)):
            min_v = range_decl.get("min")
            max_v = range_decl.get("max")
            if min_v is not None and value < min_v:
                return f"value 小于最小值 {min_v}"
            if max_v is not None and value > max_v:
                return f"value 大于最大值 {max_v}"

        return ""

    def apply_config_patches(
        self,
        plugin_id: str,
        patches: list[CxSettingPatch],
        skip_invalid: bool = True,
    ) -> dict[str, Any]:
        """应用配置 patch 到插件 KV 存储。

        Args:
            plugin_id: 插件 id
            patches: patch 列表
            skip_invalid: 是否跳过校验失败的 patch（False 时遇到失败即抛错）

        Returns:
            应用结果字典，含 applied/skipped/failed 三个列表
        """
        meta = cx_plugin_registry.get_plugin(plugin_id)
        if meta is None:
            raise ValueError(f"插件未加载: {plugin_id}")

        settings_decl = meta.manifest.settings or {}
        kv_store = PluginKVStore(plugin_id)

        applied: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        failed: list[dict[str, Any]] = []

        for patch in patches:
            # 重新校验（防止 API 层传入未校验的 patch）
            err = patch.validation_error or self._validate_patch(patch, settings_decl)
            if err:
                if skip_invalid:
                    skipped.append({**patch.to_dict(), "skip_reason": err})
                    continue
                raise ValueError(f"patch 校验失败 [{patch.key}]: {err}")

            try:
                setting_key = f"{_PLUGIN_CONFIG_PREFIX}{patch.key}"
                if patch.op == "set":
                    kv_store.set(setting_key, patch.value)
                elif patch.op in ("remove", "reset"):
                    kv_store.delete(setting_key)
                applied.append(patch.to_dict())
            except Exception as e:
                failed.append({**patch.to_dict(), "error": str(e)})

        logger.info(
            f"[CxPluginConfigAssistant] Applied patches: plugin={plugin_id} "
            f"applied={len(applied)} skipped={len(skipped)} failed={len(failed)}"
        )

        return {
            "plugin_id": plugin_id,
            "applied": applied,
            "skipped": skipped,
            "failed": failed,
            "current_config": self.get_plugin_config(plugin_id),
        }

    # ------------------------------------------------------------------
    # 配置解释
    # ------------------------------------------------------------------

    async def explain_config(self, plugin_id: str) -> dict[str, Any]:
        """用 LLM 生成对插件当前配置的自然语言解释。"""
        meta = cx_plugin_registry.get_plugin(plugin_id)
        if meta is None:
            raise ValueError(f"插件未加载: {plugin_id}")

        current_config = self.get_plugin_config(plugin_id)
        settings_decl = current_config["declarations"]
        current_values = current_config["settings"]

        decl_lines = []
        for key, decl in settings_decl.items():
            if not isinstance(decl, dict):
                continue
            decl_lines.append(
                f"- `{key}` (type={decl.get('type', 'string')}, "
                f"default={json.dumps(decl.get('default'), ensure_ascii=False)}, "
                f"current={json.dumps(current_values.get(key), ensure_ascii=False)}, "
                f"description={decl.get('description', '')})"
            )
        decl_block = "\n".join(decl_lines) if decl_lines else "(无配置项声明)"

        prompt = (
            f"请用简洁的中文解释插件 `{plugin_id}` ({meta.manifest.name}) 的当前配置：\n\n"
            f"{decl_block}\n\n"
            f"输出格式：先一段总体描述，再逐项说明每个配置项当前值是否符合默认值，"
            f"若偏离默认值请说明可能的影响。"
        )

        try:
            llm = self._get_llm_adapter()
            from app.runtime.provider.llm.adapter import RouteHint
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": "你是插件配置解释助手，用清晰的中文解释配置含义。"},
                    {"role": "user", "content": prompt},
                ],
                route_hint=RouteHint.CHAT,
                temperature=0.3,
                max_tokens=2048,
            )
            explanation = str(response).strip()
        except Exception as e:
            logger.error(f"[CxPluginConfigAssistant] explain_config LLM failed: {e}")
            raise RuntimeError(f"LLM 调用失败: {e}") from e

        return {
            "plugin_id": plugin_id,
            "explanation": explanation,
            "current_config": current_values,
        }

    # ------------------------------------------------------------------
    # 插件脚手架生成
    # ------------------------------------------------------------------

    _PLUGIN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

    def validate_plugin_id(self, plugin_id: str) -> None:
        """校验插件 id 合法性。"""
        if not plugin_id or not self._PLUGIN_ID_PATTERN.match(plugin_id):
            raise ValueError(
                f"非法的 plugin_id: {plugin_id!r}（仅允许小写字母/数字/连字符，1-64 字符）"
            )

    async def generate_scaffold(
        self,
        plugin_id: str,
        name: str,
        description: str,
        *,
        author: str = "LuminousCX",
        category: str = "tool",
        permissions: list[str] | None = None,
        capabilities: list[str] | None = None,
        settings_decl: dict[str, dict[str, Any]] | None = None,
    ) -> CxPluginScaffold:
        """根据用户描述生成新插件脚手架。

        Args:
            plugin_id: 插件 id（kebab-case）
            name: 插件中文名
            description: 插件描述
            author: 作者，默认 LuminousCX
            category: 分类，默认 tool
            permissions: 权限列表，默认仅基础权限
            capabilities: 能力列表
            settings_decl: 配置项声明，由 LLM 根据描述生成或用户指定

        Returns:
            CxPluginScaffold 对象，含 manifest.json / main.py / README.md 内容
        """
        self.validate_plugin_id(plugin_id)

        # 若未提供 settings_decl，让 LLM 根据描述生成
        if settings_decl is None:
            settings_decl = await self._llm_generate_settings_decl(description)

        # 若未提供 capabilities，让 LLM 推断
        if capabilities is None:
            capabilities = await self._llm_infer_capabilities(description)

        # 默认权限：基础（不授予高危权限）
        safe_permissions = permissions or ["basic", "event_listen"]

        scaffold = CxPluginScaffold(
            plugin_id=plugin_id,
            name=name or plugin_id,
            description=description,
        )

        # 1. manifest.json
        manifest = {
            "id": plugin_id,
            "type": "plugin",
            "name": name or plugin_id,
            "version": "0.1.0",
            "description": description,
            "author": author,
            "license": "MIT",
            "entry": "main",
            "platform": "backend",
            "category": category,
            "tags": [],
            "capabilities": capabilities,
            "permissions": safe_permissions,
            "settings": settings_decl,
            "hooks": {},
        }
        scaffold.files["manifest.json"] = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"

        # 2. main.py（CxPluginBase 入口）
        scaffold.files["main.py"] = self._render_main_py(plugin_id, name, capabilities)
        scaffold.files["__init__.py"] = '"""LuomiNest CxPlugin package."""\n'

        # 3. README.md
        scaffold.files["README.md"] = self._render_readme_md(plugin_id, name, description, settings_decl)

        # 4. 提示信息
        scaffold.notes.extend([
            f"插件目录: plugins/{plugin_id}/",
            "请通过 /api/v1/plugins/reload-all 重载插件让脚手架生效",
            "manifest.permissions 仅授予基础权限，如需网络/文件访问请在 manifest 中显式声明",
            "main.py 中的 initialize/handle_event 已包含示例代码，请按需修改",
        ])

        # 持久化脚手架历史（便于回看）
        _scaffold_store.set(plugin_id, scaffold.to_dict())

        logger.success(
            f"[CxPluginConfigAssistant] Generated scaffold: {plugin_id} "
            f"files={len(scaffold.files)} settings={len(settings_decl)}"
        )
        return scaffold

    async def _llm_generate_settings_decl(self, description: str) -> dict[str, dict[str, Any]]:
        """让 LLM 根据插件描述生成配置项声明。"""
        prompt = (
            "请根据以下插件描述，生成 manifest.json 的 settings 配置项声明（JSON 对象）。\n\n"
            f"插件描述: {description}\n\n"
            "每个配置项的格式:\n"
            '{"key": {"type": "string|number|boolean|array|object", '
            '"default": ..., "description": "...", "enum": [...], "range": {"min":..., "max":...}}}\n\n'
            "最多 5 个配置项，不要臆造无关配置。若无需配置返回 {}。"
        )

        try:
            llm = self._get_llm_adapter()
            from app.runtime.provider.llm.adapter import RouteHint
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": "你是插件配置设计师，严格按 JSON 输出。"},
                    {"role": "user", "content": prompt},
                ],
                route_hint=RouteHint.CHAT,
                temperature=0.3,
                max_tokens=1024,
            )
            text = str(response).strip()
            # 提取 JSON
            if "```json" in text:
                start = text.find("```json") + 7
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            elif "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()

            data = json.loads(text)
            if isinstance(data, dict):
                # 清理非 dict 值
                cleaned = {k: v for k, v in data.items() if isinstance(v, dict)}
                return cleaned
        except Exception as e:
            logger.warning(f"[CxPluginConfigAssistant] LLM settings_decl failed: {e}")

        return {}

    async def _llm_infer_capabilities(self, description: str) -> list[str]:
        """让 LLM 推断插件 capabilities。"""
        prompt = (
            "根据插件描述，推断它的 capabilities 列表（JSON 字符串数组）。\n\n"
            f"插件描述: {description}\n\n"
            "可选能力: tool_register, event_listen, event_emit, message_platform, "
            "llm_provider, tts_engine, stt_engine, avatar_renderer, file_handler\n"
            "只返回 JSON 数组，如 [\"tool_register\"]。若不确定返回 []。"
        )

        try:
            llm = self._get_llm_adapter()
            from app.runtime.provider.llm.adapter import RouteHint
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": "严格按 JSON 数组输出。"},
                    {"role": "user", "content": prompt},
                ],
                route_hint=RouteHint.CHAT,
                temperature=0.2,
                max_tokens=256,
            )
            text = str(response).strip()
            if "```" in text:
                start = text.find("```") + 3
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
            data = json.loads(text)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception as e:
            logger.warning(f"[CxPluginConfigAssistant] LLM infer capabilities failed: {e}")

        return []

    def _render_main_py(
        self,
        plugin_id: str,
        name: str,
        capabilities: list[str],
    ) -> str:
        """渲染 main.py 脚手架代码。"""
        # 根据能力决定要导入的基类
        needs_tool = "tool_register" in capabilities

        tool_section = ""
        if needs_tool:
            tool_section = f'''
    def _register_tools(self) -> None:
        """注册插件提供的工具（capability=tool_register 时启用）。"""
        from app.runtime.tool.base import ToolBase, ToolResult

        class _ExampleTool(ToolBase):
            """示例工具 — 请根据实际需求修改。"""
            @property
            def name(self) -> str:
                return "{plugin_id}_example_tool"

            @property
            def description(self) -> str:
                return "示例工具描述"

            @property
            def parameters(self) -> dict:
                return {{
                    "type": "object",
                    "properties": {{
                        "input": {{"type": "string", "description": "输入文本"}},
                    }},
                    "required": ["input"],
                }}

            async def execute(self, **kwargs) -> ToolResult:
                input_text = kwargs.get("input", "")
                return ToolResult(success=True, output=f"Echo: {{input_text}}")

        self._context.register_tool(_ExampleTool())
'''

        return f'''"""CxPlugin {plugin_id} — {name} 插件入口。

脚手架由 CxPluginConfigAssistant 生成，请按需修改。
"""
from __future__ import annotations

from typing import Any

from loguru import logger

from app.models.plugin import CxEventType
from app.runtime.plugin.cxplugin.base import CxPluginBase, CxPluginContext


class {self._pascal_case(plugin_id)}Plugin(CxPluginBase):
    """插件主类 — LuomiNest CxPlugin 标准入口。"""

    PLUGIN_ID = "{plugin_id}"

    async def initialize(self, context: CxPluginContext) -> None:
        """插件初始化（加载时调用）。"""
        self._context = context
        logger.info(f"[CxPlugin:{{self.PLUGIN_ID}}] Initialized")

        # 注册事件处理器
        context.on(CxEventType.ON_CHAT_MESSAGE, self.handle_chat_message)

        # 注册工具（若声明了 tool_register 能力）
        {tool_section.strip() or "pass"}

    async def handle_chat_message(self, instance: Any, event_data: dict[str, Any]) -> None:
        """处理 ON_CHAT_MESSAGE 事件（示例，请按需修改）。"""
        # self._context.kv.set("last_message", event_data)
        pass

    async def shutdown(self) -> None:
        """插件卸载时调用，用于清理资源。"""
        logger.info(f"[CxPlugin:{{self.PLUGIN_ID}}] Shutdown")


# CxPlugin 加载器入口函数
def create_plugin() -> {self._pascal_case(plugin_id)}Plugin:
    """CxPlugin 加载器调用此函数创建插件实例。"""
    return {self._pascal_case(plugin_id)}Plugin()
'''

    def _render_readme_md(
        self,
        plugin_id: str,
        name: str,
        description: str,
        settings_decl: dict[str, dict[str, Any]],
    ) -> str:
        """渲染 README.md 脚手架。"""
        settings_lines = []
        for key, decl in settings_decl.items():
            if not isinstance(decl, dict):
                continue
            settings_lines.append(
                f"- `{key}` ({decl.get('type', 'string')}): "
                f"{decl.get('description', '')} "
                f"(默认: `{decl.get('default')}`)"
            )
        settings_block = "\n".join(settings_lines) if settings_lines else "无配置项"

        return f"""# {name}

> {description}

## 基本信息

- **Plugin ID**: `{plugin_id}`
- **Author**: LuminousCX
- **License**: MIT
- **Platform**: backend

## 配置项

{settings_block}

## 开发说明

本插件由 CxPluginConfigAssistant 自动生成脚手架。请按以下步骤完善：

1. 修改 `main.py` 实现具体业务逻辑
2. 调整 `manifest.json` 中的 permissions 与 capabilities
3. 通过 `/api/v1/plugins/reload-all` 重载插件

## 事件订阅

默认订阅 `ON_CHAT_MESSAGE` 事件。如需订阅其他事件，请在 `initialize` 中调用 `context.on(...)`。
"""

    def _pascal_case(self, s: str) -> str:
        """将 kebab-case 转为 PascalCase（用于类名）。"""
        return "".join(part.capitalize() for part in s.split("-") if part)

    # ------------------------------------------------------------------
    # 写入脚手架到磁盘
    # ------------------------------------------------------------------

    def write_scaffold_to_disk(
        self,
        scaffold: CxPluginScaffold,
        overwrite: bool = False,
    ) -> dict[str, Any]:
        """将脚手架写入 plugins/ 目录。

        Args:
            scaffold: 脚手架对象
            overwrite: 是否覆盖已存在的目录

        Returns:
            操作结果字典
        """
        self.validate_plugin_id(scaffold.plugin_id)

        settings = get_settings()
        plugin_dir_root = settings.PLUGIN_DIR
        target_dir = os.path.join(plugin_dir_root, scaffold.plugin_id)

        # 路径越界校验
        resolved_target = os.path.realpath(target_dir)
        resolved_root = os.path.realpath(plugin_dir_root)
        if not resolved_target.startswith(resolved_root + os.sep) and resolved_target != resolved_root:
            raise ValueError(f"目标路径越界: {target_dir}")

        # 检查已存在
        if os.path.exists(target_dir) and not overwrite:
            raise ValueError(f"插件目录已存在: {target_dir}（overwrite=False）")

        os.makedirs(target_dir, exist_ok=True)

        written_files: list[str] = []
        for rel_path, content in scaffold.files.items():
            # 防路径遍历
            full_path = os.path.normpath(os.path.join(target_dir, rel_path))
            if not full_path.startswith(resolved_target + os.sep) and full_path != resolved_target:
                raise ValueError(f"非法的脚手架文件路径: {rel_path}")
            os.makedirs(os.path.dirname(full_path), exist_ok=True) if os.path.dirname(full_path) else None
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            written_files.append(full_path)

        logger.success(
            f"[CxPluginConfigAssistant] Wrote scaffold: {scaffold.plugin_id} "
            f"files={len(written_files)} dir={target_dir}"
        )

        return {
            "plugin_id": scaffold.plugin_id,
            "directory": target_dir,
            "files": written_files,
            "note": "请通过 /api/v1/plugins/reload-all 加载新插件",
        }

    # ------------------------------------------------------------------
    # 历史脚手架查询
    # ------------------------------------------------------------------

    def list_scaffolds(self) -> list[dict[str, Any]]:
        """列出所有历史脚手架记录。"""
        all_data = _scaffold_store.list_all()
        result = []
        for sid, data in all_data.items():
            if isinstance(data, dict):
                result.append({
                    "plugin_id": data.get("plugin_id", sid),
                    "name": data.get("name", ""),
                    "description": data.get("description", ""),
                    "created_at": data.get("created_at", ""),
                    "files": list(data.get("files", {}).keys()),
                })
        result.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        return result

    def get_scaffold(self, plugin_id: str) -> dict[str, Any] | None:
        """获取单个历史脚手架详情。"""
        return _scaffold_store.get(plugin_id)


# 全局单例
cx_plugin_config_assistant = CxPluginConfigAssistant()
