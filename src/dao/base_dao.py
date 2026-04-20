"""DAO 基类，提供 SQLite 数据库的通用操作。

包含连接管理、表创建、CRUD 基础方法。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Optional

from src.exceptions import DaoError
from src.utils.logger import get_logger

logger = get_logger()


class BaseDao:
    """SQLite DAO 基类。

    提供数据库连接管理和基础 CRUD 操作模板。

    Attributes:
        db_path: SQLite 数据库文件路径。
    """

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接。

        Returns:
            sqlite3.Connection 对象。

        Raises:
            DaoError: 连接失败时抛出。
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            return conn
        except sqlite3.Error as e:
            logger.error(f"数据库连接失败: {self.db_path}, 错误: {e}")
            raise DaoError(message=f"数据库连接失败: {e}") from e

    def _execute(
        self,
        sql: str,
        params: tuple = (),
        fetch_one: bool = False,
        fetch_all: bool = False,
        commit: bool = True,
    ) -> Optional[sqlite3.Row | list[sqlite3.Row]]:
        """执行 SQL 语句的通用方法。

        Args:
            sql: SQL 语句。
            params: 参数元组。
            fetch_one: 是否获取单条结果。
            fetch_all: 是否获取全部结果。
            commit: 是否提交事务。

        Returns:
            查询结果或 None。

        Raises:
            DaoError: 执行失败时抛出。
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(sql, params)

            result = None
            if fetch_one:
                result = cursor.fetchone()
            elif fetch_all:
                result = cursor.fetchall()

            if commit:
                conn.commit()

            return result
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"SQL 执行失败: {sql}, 参数: {params}, 错误: {e}")
            raise DaoError(message=f"SQL 执行失败: {e}") from e
        finally:
            conn.close()

    def _execute_many(
        self,
        sql: str,
        params_list: list[tuple],
    ) -> None:
        """批量执行 SQL 语句。

        Args:
            sql: SQL 语句。
            params_list: 参数列表。

        Raises:
            DaoError: 执行失败时抛出。
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.executemany(sql, params_list)
            conn.commit()
        except sqlite3.Error as e:
            conn.rollback()
            logger.error(f"批量 SQL 执行失败: {sql}, 错误: {e}")
            raise DaoError(message=f"批量 SQL 执行失败: {e}") from e
        finally:
            conn.close()

    def _table_exists(self, table_name: str) -> bool:
        """检查表是否存在。"""
        result = self._execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
            fetch_one=True,
            commit=False,
        )
        return result is not None

    @staticmethod
    def _json_serialize(value: Any) -> Optional[str]:
        """将 Python 对象序列化为 JSON 字符串（用于 SQLite 存储）。"""
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    @staticmethod
    def _json_deserialize(value: Optional[str]) -> Any:
        """将 JSON 字符串反序列化为 Python 对象。"""
        if value is None:
            return None
        return json.loads(value)
