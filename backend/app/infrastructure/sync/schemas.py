"""LuomiNest sync 模块序列化模型 — snake_case(Python) ↔ camelCase(JSON) 单一映射源。

背景（B8 命名统一）：registry_sync/github_sync 此前散落手写 "updatedAt"/"createdAt" 等
camelCase 字面量 key 构造 dict，易漏字段、易写错。现统一收敛为 Pydantic alias 模型：
- Python 侧一律 snake_case；
- JSON 边界（远程 manifest / cxp-registry index.json / 前端市场响应）通过
  ``Field(alias=...)`` + ``model_dump(by_alias=True)`` 序列化；
- 字段集合与既有输出逐一对齐，不改变任何外部契约。
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class _CamelAliasModel(BaseModel):
    """alias 序列化基类：允许按字段名或 alias 构造，按 alias 输出。"""

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ManifestItem(_CamelAliasModel):
    """GitHub 仓库 manifest.json 中单个条目（输入边界）。

    未知 key 不进入模型（extra=ignore），由 github_sync._parse_manifest_item
    归入 extra 字段，保持与旧手写类一致的行为。
    """

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = ""
    name: str = ""
    type: str = "plugin"  # plugin / skill / agent
    summary: str = ""
    description: str = ""
    icon: str = ""
    category: str = ""
    tags: list[Any] = Field(default_factory=list)
    version: str = "0.1.0"
    author: Any = Field(default_factory=dict)
    homepage: str = ""
    repository: str = ""
    license: str = ""
    rating: float = 0.0
    download_count: int = Field(default=0, alias="downloadCount")
    installed_count: int = Field(default=0, alias="installedCount")
    featured: bool = False
    screenshots: list[Any] = Field(default_factory=list)
    versions: list[Any] = Field(default_factory=list)
    size: int = 0
    min_app_version: str = Field(default="", alias="minAppVersion")
    created_at: str = Field(default="", alias="createdAt")
    updated_at: str = Field(default="", alias="updatedAt")
    download_url: str = Field(default="", alias="downloadUrl")
    extra: dict[str, Any] = Field(default_factory=dict)


class GitHubMarketplaceEntry(_CamelAliasModel):
    """GitHub 同步产出的市场条目（输出边界，字段与历史输出严格一致）。"""

    id: str
    name: str
    type: str
    summary: str
    description: str
    icon: str
    category: str
    tags: list[Any]
    version: str
    author: dict[str, Any]
    homepage: str
    repository: str
    license: str
    rating: float
    download_count: int = Field(alias="downloadCount")
    installed_count: int = Field(alias="installedCount")
    featured: bool
    screenshots: list[Any]
    versions: list[Any]
    size: int
    min_app_version: str = Field(alias="minAppVersion")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    download_url: str = Field(alias="downloadUrl")
    install_status: str = Field(default="none", alias="installStatus")
    is_favorite: bool = Field(default=False, alias="isFavorite")
    extra: dict[str, Any] = Field(default_factory=dict)


class RegistryMarketplaceEntry(_CamelAliasModel):
    """cxp-registry 远程索引条目归一化后的市场条目（输出边界，字段与历史输出严格一致）。"""

    id: str = ""
    type: str = "plugin"
    name: str = ""
    description: str = ""
    summary: str = ""
    version: str = "0.0.0"
    author: dict[str, Any] = Field(default_factory=dict)
    category: str = ""
    tags: list[Any] = Field(default_factory=list)
    icon: str = ""
    license: str = ""
    platform: str = "backend"
    min_app_version: str = Field(default="", alias="minAppVersion")
    repo: str = ""
    download_url: str = Field(default="", alias="downloadUrl")
    homepage: str = ""
    created_at: str = Field(default="", alias="createdAt")
    updated_at: str = Field(default="", alias="updatedAt")
    install_status: str = Field(default="none", alias="installStatus")
    is_favorite: bool = Field(default=False, alias="isFavorite")
    featured: bool = False
    rating: float = 0.0
    rating_count: int = Field(default=0, alias="ratingCount")
    download_count: int = Field(default=0, alias="downloadCount")
    installed_count: int = Field(default=0, alias="installedCount")
    like_count: int = Field(default=0, alias="likeCount")
    versions: list[Any] = Field(default_factory=list)
    screenshots: list[Any] = Field(default_factory=list)
    source: str = "remote"


class RegistryIndexEntry(_CamelAliasModel):
    """写入 cxp-registry index.json 的本地插件/技能索引条目（输出边界）。"""

    id: str
    name: str
    version: str = "0.0.0"
    description: str = ""
    author: dict[str, Any] = Field(default_factory=dict)
    category: str = ""
    tags: list[Any] = Field(default_factory=list)
    icon: str = ""
    # 仅插件条目携带 platform/min_app_version；技能条目省略（exclude_unset 输出）
    platform: Optional[str] = None
    license: str = ""
    min_app_version: Optional[str] = Field(default=None, alias="minAppVersion")
    repo: str = ""
    download_url: str = Field(default="", alias="downloadUrl")
    created_at: str = Field(default="", alias="createdAt")
    updated_at: str = Field(default="", alias="updatedAt")
