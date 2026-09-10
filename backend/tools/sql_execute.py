"""SQL Execute 工具 —— 执行通过安全校验的 SQL。

输入：validated_sql
输出：查询结果（列名 + 行数据 + 行数）。
"""

from backend.database.connection import db
from backend.security.sql_validator import validate_sql


def sql_execute(validated_sql: str, params: list | tuple | None = None) -> dict:
    """执行 SQL。执行前再次做防御性安全校验。"""
    ok, err = validate_sql(validated_sql)
    if not ok:
        return {"ok": False, "error": err, "sql": validated_sql}

    try:
        rows = db.query(validated_sql, params or [])
        columns = list(rows[0].keys()) if rows else []
        return {
            "ok": True,
            "sql": validated_sql,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
        }
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": f"SQL 执行失败：{e}", "sql": validated_sql}
