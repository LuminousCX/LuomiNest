"""CxSkill 加载器 — 扫描 skills/ 目录，解析 SKILL.md 与 manifest.json。

支持双轨格式：
- SKILL.md（推荐）：YAML frontmatter + Markdown 指令体，AI 原生可读
- manifest.json（兼容）：现有市场展示格式，从中构造 prompt body
- 双轨共存：SKILL.md 提供 prompt body + AI 元数据，manifest.json 提供市场展示元数据

SKILL.md 格式示例：

    ---
    id: travel-planner
    name: 旅行规划
    description: 根据用户需求规划旅行行程
    version: 1.0.0
    author: LuminousCX
    license: MIT
    tags: [travel, planning, lifestyle]
    category: lifestyle
    icon: Map
    trigger_keywords: [旅行, 旅游, 出行, 行程, travel, trip]
    ---

    # 旅行规划技能

    当用户询问旅行相关问题时，按以下步骤规划行程：
    1. 确认出发地、目的地、时间、预算
    2. 推荐景点与路线
    3. 给出交通与住宿建议
"""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from app.core.config import get_settings
from app.runtime.plugin.skill.models import (
    SkillDefinition,
    SkillSourceFormat,
    SkillStatus,
)
from app.runtime.plugin.skill.registry import cx_skill_registry


class SkillLoader:
    """技能加载器 — 扫描 SKILL_DIR 并加载所有合法技能。"""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._skill_dir = self._settings.SKILL_DIR
        self._loaded: set[str] = set()

    async def load_all(self) -> int:
        """扫描 SKILL_DIR 并加载所有技能，返回成功加载数量。"""
        if not os.path.isdir(self._skill_dir):
            logger.warning(f"[CxSkill] Skill directory not found: {self._skill_dir}")
            return 0

        count = 0
        for entry in os.listdir(self._skill_dir):
            entry_path = os.path.join(self._skill_dir, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry.startswith(".") or entry.startswith("_"):
                continue
            try:
                if await self.load_single(entry_path):
                    count += 1
            except Exception as e:
                logger.error(f"[CxSkill] Failed to load skill from {entry}: {e}")
        logger.info(f"[CxSkill] Loaded {count} skill(s) from {self._skill_dir}")
        return count

    async def load_single(self, skill_dir: str) -> bool:
        """加载单个技能目录，返回是否成功。

        优先解析 SKILL.md，其次 manifest.json，两者共存时合并。
        """
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        manifest_json_path = os.path.join(skill_dir, "manifest.json")

        has_skill_md = os.path.isfile(skill_md_path)
        has_manifest = os.path.isfile(manifest_json_path)

        if not has_skill_md and not has_manifest:
            logger.debug(f"[CxSkill] No SKILL.md or manifest.json in {skill_dir}, skipping")
            return False

        # 解析 SKILL.md
        skill_from_md: SkillDefinition | None = None
        if has_skill_md:
            try:
                skill_from_md = self._parse_skill_md(Path(skill_md_path), skill_dir)
            except Exception as e:
                logger.error(f"[CxSkill] Failed to parse SKILL.md at {skill_md_path}: {e}")

        # 解析 manifest.json
        manifest_data: dict[str, Any] | None = None
        if has_manifest:
            try:
                manifest_data = self._parse_manifest_json(manifest_json_path)
            except Exception as e:
                logger.error(f"[CxSkill] Failed to parse manifest.json at {manifest_json_path}: {e}")

        # 合并：SKILL.md 优先，manifest.json 补充
        if skill_from_md is not None and manifest_data is not None:
            skill = self._merge_skill_and_manifest(skill_from_md, manifest_data)
            skill.source_format = SkillSourceFormat.BOTH
            skill.source_path = skill_md_path
        elif skill_from_md is not None:
            skill = skill_from_md
            skill.source_format = SkillSourceFormat.SKILL_MD
        elif manifest_data is not None:
            skill = self._build_from_manifest(manifest_data, manifest_json_path, skill_dir)
            skill.source_format = SkillSourceFormat.MANIFEST_JSON
        else:
            return False

        # 跳过 type=plugin 的条目（由 CxPlugin 加载器处理）
        item_type = skill.metadata.get("type", "")
        if item_type == "plugin":
            logger.debug(f"[CxSkill] {skill.id} type=plugin, skipped by skill loader")
            return False

        if skill.id in self._loaded:
            logger.warning(f"[CxSkill] Skill {skill.id} already loaded, skipping")
            return False

        # 注册到全局 registry
        await cx_skill_registry.register(skill)
        self._loaded.add(skill.id)

        logger.success(
            f"[CxSkill] Loaded: {skill.id} v{skill.version} ({skill.name}) "
            f"format={skill.source_format.value} body_len={len(skill.body)}"
        )
        return True

    def _parse_skill_md(self, path: Path, skill_dir: str) -> SkillDefinition:
        """解析 SKILL.md 文件（YAML frontmatter + Markdown body）。"""
        content = path.read_text(encoding="utf-8")

        frontmatter: dict[str, Any] = {}
        body: str = content

        # 分离 frontmatter 与 body
        if content.startswith("---"):
            # 使用 split("---", 2) 分割为 ['', frontmatter, body]
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    if not isinstance(frontmatter, dict):
                        frontmatter = {}
                except yaml.YAMLError as e:
                    logger.warning(f"[CxSkill] YAML frontmatter parse error in {path}: {e}")
                    frontmatter = {}
                body = parts[2].strip()
            else:
                body = content.strip()

        # 从 frontmatter 提取标准字段
        skill_id = str(frontmatter.get("id") or path.parent.name)
        name = str(frontmatter.get("name") or skill_id)
        description = str(frontmatter.get("description") or "")
        version = str(frontmatter.get("version") or "1.0.0")
        author = str(frontmatter.get("author") or "")
        license_str = str(frontmatter.get("license") or "")
        tags = frontmatter.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        tags = [str(t) for t in tags]
        category = str(frontmatter.get("category") or "")
        icon = str(frontmatter.get("icon") or "")
        trigger_keywords = frontmatter.get("trigger_keywords") or []
        if not isinstance(trigger_keywords, list):
            trigger_keywords = [trigger_keywords] if trigger_keywords else []
        trigger_keywords = [str(k) for k in trigger_keywords]

        # 收集非标准字段到 metadata
        standard_keys = {
            "id", "name", "description", "version", "author", "license",
            "tags", "category", "icon", "trigger_keywords",
        }
        extra_metadata = {k: v for k, v in frontmatter.items() if k not in standard_keys}

        return SkillDefinition(
            id=skill_id,
            name=name,
            description=description,
            version=version,
            author=author,
            license=license_str,
            body=body,
            tags=tags,
            category=category,
            icon=icon,
            source_path=str(path),
            skill_dir=skill_dir,
            metadata=extra_metadata,
            trigger_keywords=trigger_keywords,
        )

    def _parse_manifest_json(self, path: str) -> dict[str, Any]:
        """解析 manifest.json 文件。"""
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _build_from_manifest(
        self,
        data: dict[str, Any],
        manifest_path: str,
        skill_dir: str,
    ) -> SkillDefinition:
        """从 manifest.json 构造 SkillDefinition（无 SKILL.md 时的回退方案）。

        manifest.json 主要面向市场展示，缺少 prompt body；
        此处从 description/parameters/capabilities/sources 字段构造简易 body。
        """
        skill_id = str(data.get("id") or os.path.basename(skill_dir))
        name = str(data.get("name") or skill_id)
        description = str(data.get("description") or "")
        version = str(data.get("version") or "1.0.0")
        author = str(data.get("author") or "")
        license_str = str(data.get("license") or "")
        tags = data.get("tags") or []
        if not isinstance(tags, list):
            tags = [tags] if tags else []
        tags = [str(t) for t in tags]
        category = str(data.get("category") or "")
        icon = str(data.get("icon") or "")

        # 从 manifest 字段构造 prompt body
        body = self._construct_body_from_manifest(data)

        # 收集非标准字段到 metadata
        standard_keys = {
            "id", "type", "name", "description", "version", "author", "license",
            "tags", "category", "icon", "summary", "minAppVersion",
            "parameters", "capabilities", "sources",
        }
        extra_metadata = {k: v for k, v in data.items() if k not in standard_keys}

        return SkillDefinition(
            id=skill_id,
            name=name,
            description=description,
            version=version,
            author=author,
            license=license_str,
            body=body,
            tags=tags,
            category=category,
            icon=icon,
            source_path=manifest_path,
            skill_dir=skill_dir,
            metadata={**extra_metadata, "type": data.get("type", "skill")},
            trigger_keywords=self._extract_keywords_from_manifest(data),
        )

    def _construct_body_from_manifest(self, data: dict[str, Any]) -> str:
        """从 manifest.json 字段构造 prompt body（无 SKILL.md 时的回退）。

        利用 description/parameters/capabilities/sources 字段生成结构化指令体，
        使 AI 也能理解并使用这类技能。
        """
        lines: list[str] = []
        name = data.get("name", "")
        description = data.get("description", "")
        summary = data.get("summary", "")

        if name:
            lines.append(f"# {name}")
        if summary:
            lines.append(f"\n{summary}")
        if description:
            lines.append(f"\n{description}")

        # 参数定义
        parameters = data.get("parameters") or {}
        if parameters:
            lines.append("\n## 参数")
            for param_name, param_spec in parameters.items():
                if isinstance(param_spec, dict):
                    ptype = param_spec.get("type", "")
                    pdesc = param_spec.get("description", "")
                    required = "（必填）" if param_spec.get("required") else "（可选）"
                    lines.append(f"- `{param_name}` ({ptype}){required}: {pdesc}")

        # 能力声明
        capabilities = data.get("capabilities") or []
        if capabilities:
            lines.append("\n## 能力")
            for cap in capabilities:
                lines.append(f"- {cap}")

        # 数据源说明
        sources = data.get("sources") or {}
        if sources and isinstance(sources, dict):
            # 过滤掉 integration_note 这种非数据源键
            data_sources = {
                k: v for k, v in sources.items()
                if isinstance(v, dict) and "name" in v
            }
            if data_sources:
                lines.append("\n## 数据源")
                for src_key, src_info in data_sources.items():
                    src_name = src_info.get("name", src_key)
                    src_url = src_info.get("url", "")
                    src_desc = src_info.get("description", "")
                    lines.append(f"- **{src_name}** ({src_url}): {src_desc}")
            # 集成说明
            integration_note = sources.get("integration_note")
            if integration_note:
                lines.append(f"\n## 集成说明\n{integration_note}")

        return "\n".join(lines).strip()

    def _extract_keywords_from_manifest(self, data: dict[str, Any]) -> list[str]:
        """从 manifest.json 字段提取触发关键词。"""
        keywords: list[str] = []
        name = data.get("name", "")
        if name:
            keywords.append(name)
        # 从 description 提取前几个词作为关键词（简单策略）
        description = data.get("description", "")
        if description:
            # 取描述中的名词性词（简单按标点切分取前 3 段）
            segments = [s.strip() for s in description.replace("，", ",").split(",") if s.strip()]
            keywords.extend(segments[:2])
        return keywords

    def _merge_skill_and_manifest(
        self,
        skill: SkillDefinition,
        manifest: dict[str, Any],
    ) -> SkillDefinition:
        """合并 SKILL.md 与 manifest.json — SKILL.md 优先，manifest 补充缺失字段。"""
        # SKILL.md 优先，manifest 补充空字段
        if not skill.name and manifest.get("name"):
            skill.name = str(manifest["name"])
        if not skill.description and manifest.get("description"):
            skill.description = str(manifest["description"])
        if not skill.author and manifest.get("author"):
            skill.author = str(manifest["author"])
        if not skill.license and manifest.get("license"):
            skill.license = str(manifest["license"])
        if not skill.icon and manifest.get("icon"):
            skill.icon = str(manifest["icon"])
        if not skill.category and manifest.get("category"):
            skill.category = str(manifest["category"])
        # tags 合并去重
        manifest_tags = manifest.get("tags") or []
        if isinstance(manifest_tags, list):
            for t in manifest_tags:
                t_str = str(t)
                if t_str not in skill.tags:
                    skill.tags.append(t_str)
        # 保留 manifest 的 type 到 metadata
        if manifest.get("type"):
            skill.metadata["type"] = manifest["type"]
        return skill

    async def unload_single(self, skill_id: str) -> bool:
        """卸载单个技能。"""
        if skill_id not in self._loaded:
            return False
        await cx_skill_registry.unregister(skill_id)
        self._loaded.discard(skill_id)
        logger.info(f"[CxSkill] Unloaded: {skill_id}")
        return True

    async def reload_single(self, skill_id: str) -> bool:
        """重载单个技能。"""
        skill = cx_skill_registry.get(skill_id)
        if skill is None:
            return False
        skill_dir = skill.skill_dir
        await self.unload_single(skill_id)
        return await self.load_single(skill_dir)

    async def reload_all(self) -> int:
        """重载所有技能。"""
        loaded_ids = set(self._loaded)
        for skill_id in list(loaded_ids):
            await self.unload_single(skill_id)
        cx_skill_registry.clear()
        return await self.load_all()

    def get_loaded_ids(self) -> set[str]:
        return set(self._loaded)

    # ------------------------------------------------------------------
    # 写入与删除（供 skill-creator 元技能与 API 调用）
    # ------------------------------------------------------------------

    _SKILL_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

    def validate_skill_id(self, skill_id: str) -> None:
        """校验 skill_id 合法性（kebab-case，防路径遍历）。"""
        if not skill_id or not self._SKILL_ID_PATTERN.match(skill_id):
            raise ValueError(
                f"非法的 skill_id: {skill_id!r}（仅允许小写字母/数字/连字符，1-64 字符）"
            )
        if ".." in skill_id or skill_id.startswith("-") or skill_id.endswith("-"):
            raise ValueError(f"非法的 skill_id: {skill_id!r}")

    def parse_skill_md(self, content: str) -> tuple[dict[str, Any], str]:
        """解析 SKILL.md 文本内容，返回 (frontmatter, body)。

        供 service 层在写入前校验内容合法性使用，避免重复实现解析逻辑。
        """
        frontmatter: dict[str, Any] = {}
        body: str = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    frontmatter = yaml.safe_load(parts[1]) or {}
                    if not isinstance(frontmatter, dict):
                        frontmatter = {}
                except yaml.YAMLError as e:
                    raise ValueError(f"YAML frontmatter 解析失败: {e}") from e
                body = parts[2].strip()
            else:
                body = content.strip()
        return frontmatter, body

    def validate_skill_md_content(self, content: str, expected_id: str) -> dict[str, Any]:
        """校验 SKILL.md 内容合法性，返回 frontmatter。

        Args:
            content: SKILL.md 文本内容
            expected_id: 期望的 skill_id（与目录名一致）

        Returns:
            frontmatter dict

        Raises:
            ValueError: 校验失败时抛出，包含具体原因
        """
        frontmatter, body = self.parse_skill_md(content)

        fm_id = str(frontmatter.get("id") or "")
        if fm_id != expected_id:
            raise ValueError(
                f"frontmatter.id ({fm_id!r}) 与目录名 ({expected_id!r}) 不一致"
            )

        name = str(frontmatter.get("name") or "")
        if not name:
            raise ValueError("frontmatter.name 不能为空")

        description = str(frontmatter.get("description") or "")
        if not description:
            raise ValueError("frontmatter.description 不能为空")

        trigger_keywords = frontmatter.get("trigger_keywords") or []
        if not isinstance(trigger_keywords, list) or len(trigger_keywords) < 3:
            raise ValueError("frontmatter.trigger_keywords 至少需要 3 个关键词")

        # type=plugin 会被插件加载器处理，不允许写入 skill 目录
        if frontmatter.get("type") == "plugin":
            raise ValueError("frontmatter.type=plugin 不允许写入 skills/ 目录")

        if not body.strip():
            raise ValueError("SKILL.md body（指令体）不能为空")

        return frontmatter

    def write_skill_md(self, skill_id: str, content: str) -> str:
        """将 SKILL.md 内容写入磁盘。

        Args:
            skill_id: 技能 id（kebab-case）
            content: SKILL.md 完整文本（含 frontmatter + body）

        Returns:
            写入的文件绝对路径

        Raises:
            ValueError: skill_id 或内容校验失败
            OSError: 文件系统错误
        """
        self.validate_skill_id(skill_id)
        self.validate_skill_md_content(content, skill_id)

        skill_dir = os.path.join(self._skill_dir, skill_id)
        # 二次校验目标路径在 SKILL_DIR 内（防路径遍历）
        resolved_skill_dir = os.path.realpath(skill_dir)
        resolved_base = os.path.realpath(self._skill_dir)
        if not resolved_skill_dir.startswith(resolved_base + os.sep) and resolved_skill_dir != resolved_base:
            raise ValueError(f"目标路径越界: {skill_dir}")

        os.makedirs(skill_dir, exist_ok=True)
        skill_md_path = os.path.join(skill_dir, "SKILL.md")
        # 原子写入：先写临时文件再 rename
        tmp_path = skill_md_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, skill_md_path)

        logger.success(f"[CxSkill] Wrote SKILL.md: {skill_md_path}")
        return skill_md_path

    def delete_skill_dir(self, skill_id: str) -> bool:
        """删除技能目录（含 SKILL.md 与所有资源）。

        Args:
            skill_id: 技能 id

        Returns:
            是否实际删除了目录（不存在时返回 False）

        Raises:
            ValueError: skill_id 校验失败或路径越界
        """
        self.validate_skill_id(skill_id)
        skill_dir = os.path.join(self._skill_dir, skill_id)
        resolved_skill_dir = os.path.realpath(skill_dir)
        resolved_base = os.path.realpath(self._skill_dir)
        if not resolved_skill_dir.startswith(resolved_base + os.sep) and resolved_skill_dir != resolved_base:
            raise ValueError(f"目标路径越界: {skill_dir}")

        if not os.path.isdir(skill_dir):
            return False

        shutil.rmtree(skill_dir)
        logger.info(f"[CxSkill] Deleted skill dir: {skill_dir}")
        return True

    async def write_and_load(self, skill_id: str, content: str) -> bool:
        """写入 SKILL.md 并立即加载（新建或更新场景）。

        若 skill_id 已加载，先卸载再重新加载。
        """
        self.write_skill_md(skill_id, content)
        if skill_id in self._loaded:
            await self.unload_single(skill_id)
        return await self.load_single(os.path.join(self._skill_dir, skill_id))

    async def delete_and_unload(self, skill_id: str) -> bool:
        """删除技能目录并从注册表卸载。"""
        unloaded = False
        if skill_id in self._loaded:
            unloaded = await self.unload_single(skill_id)
        deleted = self.delete_skill_dir(skill_id)
        return unloaded or deleted


# 全局单例
cx_skill_loader = SkillLoader()
