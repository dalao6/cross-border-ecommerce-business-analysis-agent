"""SQLite 连接与只读执行。

sql_execute 工具通过这里访问企业数据库；默认使用只读连接（mode=ro + immutable），
从连接层就杜绝任何写操作，配合 SQL Validator 双重保障「默认只允许 SELECT」。
"""

import sqlite3
from typing import Any

from backend.config import settings


class Database:
    """轻量数据库访问封装。"""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or settings.db_path

    def _readonly_conn(self) -> sqlite3.Connection:
        # 只读 URI 需要同时提供 file: 前缀与 mode=ro
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def query(self, sql: str, params: list | tuple | None = None) -> list[dict[str, Any]]:
        """执行 SELECT 查询，返回字典列表。"""
        conn = self._readonly_conn()
        try:
            cur = conn.cursor()
            cur.execute(sql, params or [])
            rows = cur.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def query_single(self, sql: str, params: list | tuple | None = None) -> dict[str, Any] | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None


# 全局单例：Agent 与 API 层共用
db = Database()
