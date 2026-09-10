"""SQL 安全校验。

对应 capsule 第十二节「SQL 安全校验」。默认只允许 SELECT，禁止一切 DDL/DML 与
危险关键字，从源头保护生产数据库不被修改。
"""

import re

# 危险关键字：命中即拒绝
FORBIDDEN_KEYWORDS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "GRANT", "REVOKE", "REPLACE", "MERGE", "ATTACH",
    "DETACH", "PRAGMA", "VACUUM", "REINDEX", "EXPLAIN",
]

# 危险函数/表达式（即便出现在 SELECT 中也应拒绝）
FORBIDDEN_PATTERNS = [
    r"\bsleep\s*\(",
    r"\bload_file\s*\(",
    r"\binto\s+outfile\b",
    r"\binto\s+dumpfile\b",
    r"\bunion\s+select\b",
]

# 注释标记，用于剥离后校验
COMMENT_MARKERS = ["--", "/*", "*/", "#"]


def validate_sql(sql: str) -> tuple[bool, str]:
    """校验 SQL 是否安全。返回 (是否通过, 原因)。"""
    if not sql or not sql.strip():
        return False, "SQL 为空，已阻止执行。"

    # 多语句分隔检测（SQLite 一次只执行一条）
    stripped = sql.strip().rstrip(";")
    if ";" in stripped:
        return False, "检测到多语句，已阻止执行。"

    # 去注释后再判断
    cleaned = _strip_comments(sql).upper()

    # 必须以 SELECT 或 WITH（CTE）开头
    leading = cleaned.lstrip()
    if not (leading.startswith("SELECT") or leading.startswith("WITH")):
        return False, "仅允许 SELECT 查询，检测到非查询语句，已阻止执行。"

    # 危险关键字
    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", cleaned):
            return False, f"SQL 包含危险关键字 {kw}，已阻止执行。"

    # 危险模式
    for pat in FORBIDDEN_PATTERNS:
        if re.search(pat, cleaned):
            return False, "SQL 包含危险模式，已阻止执行。"

    return True, ""


def _strip_comments(sql: str) -> str:
    """移除行注释与块注释，用于安全校验。"""
    # 块注释
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    # 行注释
    lines = []
    for line in sql.splitlines():
        for marker in ("--", "#"):
            if marker in line:
                line = line.split(marker)[0]
        lines.append(line)
    return "\n".join(lines)
