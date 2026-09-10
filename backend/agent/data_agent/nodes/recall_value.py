"""
字段取值召回步骤

负责召回用户问题中可能涉及的字段真实取值（如"美国""亚马逊""情趣内衣"）。
优先走 Elasticsearch 全文检索（IK 分词），向量后端不可用时回退到 SQLite 维度字段取值匹配。

返回：(取值 dict 列表, 取值实体列表)
"""

from backend.agent.data_agent.recall_backend import (
    is_vector_backend_available,
    mark_vector_backend_unavailable,
)


async def recall_value(query: str, keywords: list[str]) -> tuple[list[dict], list[dict]]:
    """召回与问题相关的字段取值。返回 (dict 列表, 实体列表)。"""
    if is_vector_backend_available():
        try:
            entities = await _es_recall(keywords)
            if entities:
                return [_value_to_dict(v) for v in entities], entities
        except Exception:  # noqa: BLE001
            mark_vector_backend_unavailable()

    # 回退：从 SQLite 维度字段 distinct 值做子串匹配
    dicts = _sqlite_recall(query)
    return dicts, []


async def _es_recall(keywords: list[str]) -> list:
    """Elasticsearch 全文检索字段取值，返回 ValueInfo 实体列表。"""
    from backend.clients.es_client_manager import es_client_manager
    from backend.repositories.es.value_es_repository import ValueESRepository

    repo = ValueESRepository(es_client_manager.client)

    value_map = {}
    for keyword in keywords:
        current_values = await repo.search(keyword)
        for value in current_values:
            if value.id not in value_map:
                value_map[value.id] = value

    return list(value_map.values())


def recall_value_sync(query: str) -> list[dict]:
    """同步版本（供工具注册表/规则规划器使用）：直接走 SQLite 兜底召回。"""
    return _sqlite_recall(query)


def _value_to_dict(value) -> dict:
    return {"column_id": value.column_id, "value": value.value}


def _sqlite_recall(query: str) -> list[dict]:
    """从 SQLite 查询维度字段的真实取值，做子串匹配作为兜底。"""
    from backend.database.connection import db
    from backend.database.metadata import COLUMN_METADATA

    # 只对文本型维度字段（可能作为 WHERE 条件的）做取值召回
    dim_columns = [
        c
        for c in COLUMN_METADATA
        if c["is_dimension"]
        and c["column_name"]
        in ("country", "platform", "category", "warehouse", "customer_type")
    ]

    results = []
    seen = set()
    for c in dim_columns:
        table, col = c["table_name"], c["column_name"]
        try:
            rows = db.query(f"SELECT DISTINCT {col} FROM {table} LIMIT 50")
        except Exception:  # noqa: BLE001
            continue
        for row in rows:
            val = str(row[col])
            key = f"{table}.{col}.{val}"
            if key in seen:
                continue
            # 命中 query 中的词才纳入（含英文大小写不敏感）
            if _hit(query, val) or _hit(query, c["column_comment"]):
                seen.add(key)
                results.append({"column_id": f"{table}.{col}", "value": val})

    return results


def _hit(query: str, value: str) -> bool:
    """判断 query 是否命中某个取值（中文子串或英文忽略大小写）。"""
    q = query.lower()
    v = str(value).lower()
    # 取值通常较短，直接做子串匹配
    return v in q or q in v
