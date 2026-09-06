"""扩展市场模块的内部工具处理函数（market.*）。

从原 register_tools.py 拆出（大文件拆分重构），处理函数体保持原样；
注册顺序与 schema 见 register_tools.register_internal_tools。
"""

import json
from typing import Any

from loguru import logger

from app.core.workflow.models import WorkflowTaskResult
from app.core.workflow.tool_domains.common import _get_emitter


async def _market_install(args: dict[str, Any]) -> WorkflowTaskResult:
    """安装扩展市场内容"""
    item_id = args.get("item_id", "")
    item_type = args.get("item_type", "")
    item_name = args.get("item_name", "")
    download_url = args.get("download_url", "")
    version = args.get("version", "1.0.0")

    if not item_id or not item_type or not item_name:
        return WorkflowTaskResult(
            success=False,
            error="Missing required parameters: item_id, item_type, item_name",
        )

    try:
        from app.infrastructure.install.install_service import download_item, is_installed

        if is_installed(item_id):
            return WorkflowTaskResult(
                success=False,
                error=f"条目 {item_id} 已安装",
            )

        result = await download_item(
            item_id=item_id,
            download_url=download_url,
            item_type=item_type,
            item_name=item_name,
            version=version,
        )

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="market",
                action="installed",
                success=result.get("status") == "installed",
                output=f"已安装: {item_name}",
                error=result.get("error", ""),
                metadata={"item_id": item_id, "item_type": item_type},
            )

        return WorkflowTaskResult(
            success=result.get("status") == "installed",
            output=f"已安装: {item_name}",
            metadata={"item_id": item_id, "item_type": item_type},
        )
    except Exception as e:
        logger.error("[Workflow:market.install] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_uninstall(args: dict[str, Any]) -> WorkflowTaskResult:
    """卸载扩展市场内容"""
    item_id = args.get("item_id", "")
    if not item_id:
        return WorkflowTaskResult(success=False, error="Missing required parameter: item_id")

    try:
        from app.infrastructure.install.install_service import uninstall_item

        result = await uninstall_item(item_id)
        if not result.get("success"):
            return WorkflowTaskResult(
                success=False,
                error=result.get("error", "卸载失败"),
            )

        emitter = _get_emitter()
        if emitter:
            await emitter.emit_module_action(
                module="market",
                action="uninstalled",
                success=True,
                output=f"已卸载: {item_id}",
                metadata={"item_id": item_id},
            )

        return WorkflowTaskResult(
            success=True,
            output=f"已卸载: {item_id}",
            metadata={"item_id": item_id},
        )
    except Exception as e:
        logger.error("[Workflow:market.uninstall] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_list_installed(args: dict[str, Any]) -> WorkflowTaskResult:
    """列出已安装的扩展市场内容"""
    item_type = args.get("item_type")

    try:
        from app.infrastructure.install.install_service import get_installed_items

        items = get_installed_items()
        if item_type and item_type in ("plugin", "skill", "agent"):
            items = [i for i in items if i.get("type") == item_type]

        return WorkflowTaskResult(
            success=True,
            output=json.dumps(items, ensure_ascii=False),
            metadata={"count": len(items)},
        )
    except Exception as e:
        logger.error("[Workflow:market.list_installed] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))


async def _market_get_leaderboard(args: dict[str, Any]) -> WorkflowTaskResult:
    """获取扩展市场排行榜"""
    item_type = args.get("item_type")
    sort_by = args.get("sort_by", "composite")
    limit = min(args.get("limit", 20), 100)

    try:
        from app.infrastructure.database.json_store import marketplace_stats_store

        all_stats = await marketplace_stats_store.list_all_async()
        items = []
        for item_id, stats in all_stats.items():
            if item_id.startswith("__"):
                continue
            if item_type and stats.get("type") != item_type:
                continue
            dl = stats.get("downloadCount", 0)
            lk = stats.get("likeCount", 0)
            items.append({
                "itemId": item_id,
                "downloadCount": dl,
                "likeCount": lk,
                "type": stats.get("type", ""),
                "score": dl + lk * 3,
            })

        if sort_by == "downloads":
            items.sort(key=lambda x: x["downloadCount"], reverse=True)
        elif sort_by == "likes":
            items.sort(key=lambda x: x["likeCount"], reverse=True)
        else:
            items.sort(key=lambda x: x["score"], reverse=True)

        result = items[:limit]
        return WorkflowTaskResult(
            success=True,
            output=json.dumps(result, ensure_ascii=False),
            metadata={"count": len(result)},
        )
    except Exception as e:
        logger.error("[Workflow:market.get_leaderboard] Failed: {}", str(e), exc_info=True)
        return WorkflowTaskResult(success=False, error=str(e))
