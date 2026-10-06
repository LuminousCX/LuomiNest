"""数据备份与恢复 API。

04-用户数据存储链路审查 P0-2：restore_backup 此前为死代码（无端点无 UI），
此处把备份管理器暴露为受统一鉴权中间件保护的端点，供设置页"数据备份与恢复"
区块调用。所有操作针对 backups 目录内经 list 接口返回的备份文件名（防路径穿越）。
"""
import os

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from app.core.utils import ok
from app.infrastructure.backup.backup_manager import luominest_backup_manager

router = APIRouter(prefix="/backup", tags=["backup"])


class BackupNameRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256, description="backups 目录内的备份文件名（.zip）")


class BackupCreateRequest(BaseModel):
    label: str = Field(default="", max_length=64, description="备份名后缀（可选，仅限字母数字-_）")


@router.get("/list")
async def list_backups():
    """列出全部备份文件（name/size_mb/created_at）。"""
    return ok(await luominest_backup_manager.list_backups_async())


@router.post("/create")
async def create_backup(req: BackupCreateRequest):
    """立即创建一次数据备份（凭据文件不入包）。"""
    label = req.label.strip()
    if label and not label.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="备份标签仅允许字母数字与 -_")
    path = await luominest_backup_manager.create_backup_async(label)
    if not path:
        raise HTTPException(status_code=500, detail="备份创建失败，请查看后端日志")
    return ok({"name": os.path.basename(path), "path": path})


@router.post("/restore")
async def restore_backup(req: BackupNameRequest):
    """从指定备份恢复数据（覆盖现有数据）。

    执行前已做两级完整性校验（zip 预检 + 解出库 PRAGMA integrity_check）。
    返回恢复摘要：恢复方式、失败条目、需要重新配置的凭据清单。
    """
    path = luominest_backup_manager.resolve_backup_path(req.name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"备份文件不存在或名称非法: {req.name}")
    logger.info(f"[Backup] Restore requested via API: {req.name}")
    result = await luominest_backup_manager.restore_backup_async(path)
    if not result.get("ok"):
        raise HTTPException(status_code=500, detail=result.get("message") or "恢复失败，现有数据未受影响")
    return ok(result)


@router.post("/delete")
async def delete_backup(req: BackupNameRequest):
    """删除指定备份文件。"""
    path = luominest_backup_manager.resolve_backup_path(req.name)
    if path is None:
        raise HTTPException(status_code=404, detail=f"备份文件不存在或名称非法: {req.name}")
    if not await luominest_backup_manager.delete_backup_async(path):
        raise HTTPException(status_code=500, detail="备份删除失败")
    return ok({"name": req.name})
