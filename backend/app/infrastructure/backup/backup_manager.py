import asyncio
import contextlib
import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from app.core.config import settings
from app.core.utils import utc_now_dt

# 备份包内清单文件名（记录排除的凭据与恢复指引，恢复时原样读出返回，不落盘）
BACKUP_MANIFEST_NAME = "_backup_manifest.json"

# 凭据排除清单（DATA_DIR 相对路径，正斜杠）——04-用户数据存储链路审查 P0-1：
# auth_token 为明文 Bearer 令牌；secret_key* / jwt_secret_key* 为机器指纹绑定的
# 密钥材料（Fernet 密文 + KDF 盐）。这些文件出包即成泄露面（备份 zip 无密码），
# 且密钥与机器指纹绑定，跨机恢复原本也不可用，入包只有风险没有收益。
CREDENTIAL_EXCLUDES: dict[str, str] = {
    "config/auth_token": "本地 API 鉴权令牌（明文存储）",
    "config/secret_key": "SECRET_KEY 密文（机器指纹绑定 Fernet 加密，解密 provider API Key 等加密配置的根密钥）",
    "config/secret_key.kdf-salt": "SECRET_KEY 的 PBKDF2 KDF 盐",
    "config/jwt_secret_key": "JWT 签名密钥密文（机器指纹绑定 Fernet 加密）",
    "config/jwt_secret_key.kdf-salt": "JWT 密钥的 PBKDF2 KDF 盐",
}

# 恢复后凭据处理指引（按排除清单逐项给出；旧备份无清单时使用默认全量列表）
CREDENTIAL_RECONFIGURE_HINTS: dict[str, str] = {
    "config/auth_token": "不入备份。恢复后沿用本机现有令牌即可，无需手动处理",
    "config/secret_key": "不入备份。同机恢复无需处理；跨机/重装系统恢复后，LLM 供应商 API Key 等加密配置将无法解密，需重新填写",
    "config/secret_key.kdf-salt": "不入备份。同上：同机恢复无需处理",
    "config/jwt_secret_key": "不入备份。同机恢复无需处理；跨机恢复后由后端自动重建，已有登录会话失效需重新登录",
    "config/jwt_secret_key.kdf-salt": "不入备份。同上：同机恢复无需处理",
}


def _default_credential_hints() -> list[dict[str, str]]:
    """无清单备份（历史包）的默认凭据指引：覆盖全部凭据类别。"""
    return [
        {"path": path, "hint": CREDENTIAL_RECONFIGURE_HINTS.get(path, "不入备份，恢复后请确认相关凭据可用")}
        for path in CREDENTIAL_EXCLUDES
    ]


class LumiBackupManager:
    """数据备份管理器。

    将 DATA_DIR 打包为 zip 备份文件（活库 luominest.db 先经 sqlite3 backup API
    取在线一致快照，-wal/-shm 中间态不入包），支持创建、恢复、列出、自动清理备份。

    安全约定（P0-1）：凭据文件（auth_token / secret_key* / jwt_secret_key*）一律
    不入包，包内 _backup_manifest.json 记录排除项与恢复后重配指引。
    """

    MAX_BACKUPS = 10

    def __init__(self):
        self._backup_dir = os.path.join(settings.DATA_DIR, "backups")
        os.makedirs(self._backup_dir, exist_ok=True)

    def create_backup(self, label: str = "") -> str | None:
        """创建数据备份，返回备份文件路径。"""
        timestamp = utc_now_dt().strftime("%Y%m%d_%H%M%S")
        suffix = f"_{label}" if label else ""
        backup_name = f"luominest_backup_{timestamp}{suffix}.zip"
        backup_path = os.path.join(self._backup_dir, backup_name)

        data_dir = Path(settings.DATA_DIR)
        if not data_dir.exists():
            logger.warning(f"[Backup] DATA_DIR does not exist: {data_dir}")
            return None

        try:
            # 活库不能直接拷贝打包（写入中途会得到不一致快照），
            # 先用 sqlite3 backup API 做在线一致快照，再以快照替代库文件入包
            db_path = data_dir / "luominest.db"
            snapshot_path = ""
            if db_path.exists():
                snapshot_path = self._snapshot_db(str(db_path))

            excluded_credentials: list[dict[str, str]] = []
            try:
                with zipfile.ZipFile(backup_path, "w", zipfile.ZIP_DEFLATED) as zf:
                    for root, _dirs, files in os.walk(data_dir):
                        if self._backup_dir in root:
                            continue
                        for file in files:
                            # -wal/-shm 是写时中间态，数据已含在快照中，不再打包
                            if file in ("luominest.db-wal", "luominest.db-shm"):
                                continue
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, data_dir).replace(os.sep, "/")
                            # 凭据文件一律不入包（P0-1），记录进包内清单
                            if arcname in CREDENTIAL_EXCLUDES:
                                excluded_credentials.append({
                                    "path": arcname,
                                    "reason": CREDENTIAL_EXCLUDES[arcname],
                                    "hint": CREDENTIAL_RECONFIGURE_HINTS.get(arcname, ""),
                                })
                                continue
                            # 锁文件与手工 .bak 残留不入包（P3-3：备份膨胀）
                            if file.endswith(".lock") or ".bak" in file:
                                continue
                            if file == "luominest.db" and os.path.abspath(file_path) == str(db_path):
                                zf.write(snapshot_path, "luominest.db")
                                continue
                            zf.write(file_path, arcname)
                    # 包内清单：列出被排除的凭据与恢复后重配指引（随包走，恢复端点原样返回）
                    zf.writestr(BACKUP_MANIFEST_NAME, json.dumps({
                        "schema": "luominest-backup/1",
                        "app": settings.APP_NAME,
                        "app_version": settings.APP_VERSION,
                        "created_at": utc_now_dt().isoformat(),
                        "note": "本备份不含任何凭据文件（auth_token / secret_key* / jwt_secret_key*）；恢复后请按 hint 处理对应凭据。",
                        "excluded_credentials": excluded_credentials,
                    }, ensure_ascii=False, indent=2))
            finally:
                # 快照只是打包用的中间产物，用完即清理
                if snapshot_path and os.path.exists(snapshot_path):
                    with contextlib.suppress(OSError):
                        os.remove(snapshot_path)

            size_mb = os.path.getsize(backup_path) / (1024 * 1024)
            logger.success(f"[Backup] Created: {backup_name} ({size_mb:.1f} MB)")

            self._auto_cleanup()
            return backup_path
        except Exception as e:
            logger.error(f"[Backup] Failed to create backup: {e}")
            if os.path.exists(backup_path):
                try:
                    os.remove(backup_path)
                except OSError as cleanup_error:
                    logger.warning(
                        f"[Backup] Failed to remove partial backup file {backup_path}: {cleanup_error}"
                    )
            return None

    def restore_backup(self, backup_path: str) -> dict:
        """从备份文件恢复数据，返回结构化结果摘要（P0-2：恢复能力产品化）。

        恢复语义：以备份内容覆盖 DATA_DIR（数据库外的同名文件/目录整体替换）。
        备份内不含凭据文件（P0-1），本机现有凭据不受影响；包内清单（若有）
        原样读出并入结果，指导恢复后需要重新配置的凭据。

        Returns:
            {
              "ok": bool,                        # 主库是否恢复成功（非库文件失败单列在 failed）
              "backup": str,                     # 备份文件名
              "db_restore_method": str,          # live_backup_api / file_replace / ""
              "restored": list[str],             # 已恢复的条目
              "failed": list[{item, error}],     # 恢复失败的条目（如被占用的日志文件）
              "credentials_to_reconfigure": list[{path, hint}],
              "restart_recommended": bool,       # 建议重启应用刷新内存缓存
              "message": str,
            }
        """
        result: dict = {
            "ok": False,
            "backup": os.path.basename(backup_path),
            "db_restore_method": "",
            "restored": [],
            "failed": [],
            "credentials_to_reconfigure": _default_credential_hints(),
            "restart_recommended": True,
            "message": "",
        }
        if not os.path.exists(backup_path):
            result["message"] = f"备份文件不存在: {backup_path}"
            logger.error(f"[Backup] Backup file not found: {backup_path}")
            return result

        data_dir = Path(settings.DATA_DIR)
        temp_restore = data_dir / "_restore_temp"
        temp_restore.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(backup_path, "r") as zf:
                # 预检 zip 完整性，损坏的备份直接拒绝，避免污染现有数据
                bad_file = zf.testzip()
                if bad_file is not None:
                    result["message"] = f"备份包损坏（条目: {bad_file}）"
                    logger.error(f"[Backup] Backup file corrupted at entry: {bad_file}")
                    return result
                # 包内清单（若有）：恢复响应据此给出"需要重新配置的凭据"指引
                if BACKUP_MANIFEST_NAME in zf.namelist():
                    try:
                        manifest = json.loads(zf.read(BACKUP_MANIFEST_NAME).decode("utf-8"))
                        creds = manifest.get("excluded_credentials") or []
                        if creds:
                            result["credentials_to_reconfigure"] = [
                                {"path": c.get("path", ""), "hint": c.get("hint", "")}
                                for c in creds
                                if c.get("path")
                            ]
                    except Exception as e:
                        logger.warning(f"[Backup] Failed to parse backup manifest: {e}")
                zf.extractall(temp_restore)

            # 覆盖现有数据前先校验解出的数据库完整性，坏库同样不能落盘
            restored_db = temp_restore / "luominest.db"
            if restored_db.exists():
                integrity = self._check_db_integrity(str(restored_db))
                if integrity != "ok":
                    result["message"] = f"备份数据库完整性校验失败: {integrity}"
                    logger.error(f"[Backup] Restored database failed integrity check: {integrity}")
                    return result

            # 恢复前清理 data_dir 残留 -wal/-shm：备份内是免 WAL 的一致快照（header 仍标记
            # WAL 模式），旧 sidecar 一旦残留，SQLite 打开新库时会 recovery 重放旧世代 WAL
            # （跨库世代重放 → 数据串写/损坏）
            for sidecar in ("luominest.db-wal", "luominest.db-shm"):
                sidecar_path = data_dir / sidecar
                if sidecar_path.exists():
                    try:
                        sidecar_path.unlink()
                        logger.info(f"[Backup] Removed stale sidecar before restore: {sidecar}")
                    except OSError as e:
                        logger.warning(f"[Backup] Failed to remove stale sidecar {sidecar}: {e}")

            for item in temp_restore.iterdir():
                # 清单是备份元数据而非数据，不落盘
                if item.name == BACKUP_MANIFEST_NAME:
                    continue
                target = data_dir / item.name
                if item.name == "luominest.db":
                    ok, method, error = self._restore_db_file(item, target)
                    if ok:
                        result["db_restore_method"] = method
                        result["restored"].append(item.name)
                    else:
                        result["failed"].append({"item": item.name, "error": error})
                    continue
                try:
                    if target.exists():
                        if target.is_dir():
                            shutil.rmtree(target)
                        else:
                            target.unlink()
                    shutil.move(str(item), str(target))
                    result["restored"].append(item.name)
                except OSError as e:
                    result["failed"].append({"item": item.name, "error": str(e)})
                    logger.warning(f"[Backup] Failed to restore item {item.name}: {e}")

            # ok 以主库恢复为准；非库文件的个别失败（如运行中被占用的日志）单列在 failed
            result["ok"] = restored_db.exists() is False or bool(result["db_restore_method"])
            result["message"] = "恢复完成，建议重启 LuomiNest 以刷新内存缓存"
            if result["failed"]:
                result["message"] += (
                    f"（{len(result['failed'])} 个条目未能恢复："
                    + "、".join(f["item"] for f in result["failed"])
                    + "）"
                )
            logger.success(
                f"[Backup] Restored from: {result['backup']} "
                f"(db via {result['db_restore_method']}, "
                f"failed items: {len(result['failed'])})"
            )
            return result
        except Exception as e:
            logger.error(f"[Backup] Failed to restore: {e}")
            result["message"] = f"恢复失败: {e}"
            return result
        finally:
            if temp_restore.exists():
                shutil.rmtree(temp_restore, ignore_errors=True)

    @staticmethod
    def _restore_db_file(source: Path, target: Path) -> tuple[bool, str, str]:
        """恢复主库文件，返回 (是否成功, 恢复方式, 失败原因)。

        优先经 sqlite3 backup API 把快照按页写回现库：数据在同一文件内替换，
        由 SQLite 锁管理器保证一致性，后端运行中（持有库句柄）也可安全落盘；
        现库损坏/不可写导致热恢复失败时，回退为整文件替换——该路径要求无进程
        持有库文件句柄（Windows 下运行中的后端会锁文件），失败时如实报错。
        """
        if not target.exists():
            try:
                shutil.move(str(source), str(target))
                return True, "file_replace", ""
            except OSError as e:
                return False, "", str(e)
        try:
            src = sqlite3.connect(str(source), timeout=30)
            try:
                dst = sqlite3.connect(str(target), timeout=30)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
            return True, "live_backup_api", ""
        except sqlite3.Error as e:
            logger.warning(f"[Backup] In-place db restore failed, fallback to file replace: {e}")
        try:
            target.unlink()
        except OSError as e:
            return False, "", f"数据库文件被占用且无法在线恢复，请停止后端后重试: {e}"
        try:
            shutil.move(str(source), str(target))
            return True, "file_replace", ""
        except OSError as e:
            return False, "", str(e)

    def resolve_backup_path(self, name: str) -> str | None:
        """校验备份文件名并解析为 backups 目录内的绝对路径（防路径穿越）。

        name 必须是以 .zip 结尾的纯文件名（与 list_backups 返回的 name 对称）；
        非法或文件不存在时返回 None。
        """
        stripped = (name or "").strip()
        safe = os.path.basename(stripped)
        if not safe.endswith(".zip") or safe != stripped:
            return None
        path = os.path.join(self._backup_dir, safe)
        return path if os.path.exists(path) else None

    @staticmethod
    def _snapshot_db(db_path: str) -> str:
        """对活库执行 sqlite3 在线备份，生成一致性快照，返回快照临时文件路径。"""
        fd, snapshot_path = tempfile.mkstemp(prefix="luominest_db_snapshot_", suffix=".db")
        os.close(fd)
        try:
            # timeout 与数据库引擎对齐（30s）：默认 5s 在写高峰会让快照locked失败→整体备份失败
            src = sqlite3.connect(db_path, timeout=30)
            try:
                dst = sqlite3.connect(snapshot_path)
                try:
                    src.backup(dst)
                finally:
                    dst.close()
            finally:
                src.close()
        except Exception:
            # 快照失败时清理半成品临时文件
            with contextlib.suppress(OSError):
                os.remove(snapshot_path)
            raise
        return snapshot_path

    @staticmethod
    def _check_db_integrity(db_path: str) -> str:
        """对 SQLite 数据库执行 PRAGMA integrity_check，返回首行检查结果。

        文件根本不是可读 SQLite 库（打开/查询抛 sqlite3.Error）同样视为未通过，
        返回错误描述——restore 侧统一以返回值判定，避免异常绕过校验分支。
        """
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            return row[0] if row else "no result"
        except sqlite3.Error as e:
            return f"not a readable sqlite database: {e}"
        finally:
            conn.close()

    def list_backups(self) -> list[dict]:
        """列出所有备份文件。"""
        backups = []
        if not os.path.exists(self._backup_dir):
            return backups

        for name in sorted(os.listdir(self._backup_dir), reverse=True):
            if not name.endswith(".zip"):
                continue
            path = os.path.join(self._backup_dir, name)
            stat = os.stat(path)
            backups.append({
                "name": name,
                "path": path,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
        return backups

    def delete_backup(self, backup_path: str) -> bool:
        """删除指定备份文件。"""
        if not os.path.exists(backup_path):
            return False
        try:
            os.remove(backup_path)
            logger.info(f"[Backup] Deleted: {os.path.basename(backup_path)}")
            return True
        except Exception as e:
            logger.error(f"[Backup] Failed to delete: {e}")
            return False

    def _auto_cleanup(self):
        """自动清理旧备份，保留最新的 MAX_BACKUPS 个。"""
        backups = self.list_backups()
        if len(backups) <= self.MAX_BACKUPS:
            return

        to_delete = backups[self.MAX_BACKUPS:]
        for backup in to_delete:
            self.delete_backup(backup["path"])
        logger.info(f"[Backup] Auto-cleaned {len(to_delete)} old backups")

    # ── Async wrappers ──

    async def create_backup_async(self, label: str = "") -> str | None:
        return await asyncio.to_thread(self.create_backup, label)

    async def restore_backup_async(self, backup_path: str) -> dict:
        return await asyncio.to_thread(self.restore_backup, backup_path)

    async def list_backups_async(self) -> list[dict]:
        return await asyncio.to_thread(self.list_backups)

    async def delete_backup_async(self, backup_path: str) -> bool:
        return await asyncio.to_thread(self.delete_backup, backup_path)


luominest_backup_manager = LumiBackupManager()
