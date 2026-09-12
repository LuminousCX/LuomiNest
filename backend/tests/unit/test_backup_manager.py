"""备份管理器回归测试。

覆盖：
- create_backup 产出 zip 且不再因 list_backups 的 timezone NameError 被误删
- 备份内 luominest.db 为一致性快照（-wal/-shm 不入包），其他文件照旧打包
- list_backups 正常返回带 UTC 时区的条目
- restore_backup 对损坏 zip 预检失败，不污染现有数据
"""

import os
import sqlite3
import zipfile

import pytest

from app.core.config import settings
from app.infrastructure.backup.backup_manager import LumiBackupManager


def _make_data_dir(tmp_path):
    """构造一个带最小 SQLite 库与配置文件的数据目录。"""
    data_dir = tmp_path / "data"
    (data_dir / "config").mkdir(parents=True)
    conn = sqlite3.connect(data_dir / "luominest.db")
    try:
        conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY, name TEXT)")
        conn.executemany("INSERT INTO demo (name) VALUES (?)", [(f"row{i}",) for i in range(3)])
        conn.commit()
    finally:
        conn.close()
    # 模拟活库运行残留的 -wal/-shm，备份中不应出现
    (data_dir / "luominest.db-wal").write_bytes(b"wal")
    (data_dir / "luominest.db-shm").write_bytes(b"shm")
    (data_dir / "config" / "app.json").write_text("{}", encoding="utf-8")
    return data_dir


@pytest.fixture
def backup_env(tmp_path, monkeypatch):
    """把 DATA_DIR 指向临时目录，隔离真实数据。"""
    data_dir = _make_data_dir(tmp_path)
    monkeypatch.setattr(settings, "DATA_DIR", str(data_dir))
    return data_dir


def test_create_backup_produces_consistent_zip(backup_env):
    manager = LumiBackupManager()
    path = manager.create_backup(label="test")

    # 修复前：打完包后 _auto_cleanup 触发 NameError，备份在收尾阶段被误删
    assert path is not None
    assert os.path.exists(path)

    with zipfile.ZipFile(path) as zf:
        assert zf.testzip() is None
        # arcname 在 Windows 下可能是反斜杠，统一成 zip 惯用的正斜杠再断言
        names = [n.replace("\\", "/") for n in zf.namelist()]
        assert "luominest.db" in names
        assert "config/app.json" in names
        # -wal/-shm 是写时中间态，数据已含在快照中，不应入包
        assert "luominest.db-wal" not in names
        assert "luominest.db-shm" not in names
        db_bytes = zf.read("luominest.db")

    # 快照库可打开、完整性通过、行数与原库一致
    snap_db = backup_env.parent / "snapshot_check.db"
    snap_db.write_bytes(db_bytes)
    conn = sqlite3.connect(snap_db)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM demo").fetchone()[0] == 3
    finally:
        conn.close()


def test_list_backups_after_create(backup_env):
    manager = LumiBackupManager()
    path = manager.create_backup(label="test")
    assert path is not None

    # 修复前：list_backups 内 timezone 未导入会抛 NameError
    backups = manager.list_backups()
    assert len(backups) == 1
    assert backups[0]["name"] == os.path.basename(path)
    assert backups[0]["path"] == path
    # created_at 是带 UTC 时区的 isoformat
    assert backups[0]["created_at"].endswith("+00:00")


def test_restore_rejects_corrupted_zip(backup_env):
    manager = LumiBackupManager()
    corrupt = backup_env / "corrupt.zip"
    corrupt.write_bytes(b"PK\x03\x04 this is not a valid zip")

    assert manager.restore_backup(str(corrupt)) is False

    # 现有数据不被污染
    conn = sqlite3.connect(backup_env / "luominest.db")
    try:
        assert conn.execute("SELECT COUNT(*) FROM demo").fetchone()[0] == 3
    finally:
        conn.close()
