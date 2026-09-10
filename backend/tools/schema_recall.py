"""Schema Recall —— 从已召回表中召回相关字段。

输入：user_query, retrieved_tables
输出：相关字段（含字段类型、维度/度量角色、同义词）。
"""

from backend.database.metadata import COLUMN_METADATA
from backend.tools.scoring import score_candidates

WEIGHTS = {
    "column_name": 0.6,
    "column_comment": 1.2,
    "business_meaning": 1.0,
    "synonyms": 1.5,
}


def schema_recall(query: str, retrieved_tables: list[str] | None = None, top_k: int = 12) -> list[dict]:
    """召回相关字段。retrieved_tables 为空时对全库字段召回。"""
    table_set = set(retrieved_tables) if retrieved_tables else None
    candidates = [
        {
            "table_name": c["table_name"],
            "column_name": c["column_name"],
            "column_comment": c["column_comment"],
            "business_meaning": c["business_meaning"],
            "data_type": c["data_type"],
            "is_dimension": c["is_dimension"],
            "is_measure": c["is_measure"],
            "synonyms": c["synonyms"],
        }
        for c in COLUMN_METADATA
        if table_set is None or c["table_name"] in table_set
    ]
    scored = score_candidates(query, candidates, WEIGHTS)

    # 回退：返回销售订单表的基础字段
    if not scored or scored[0]["score"] == 0:
        fallback = [c for c in candidates if c["table_name"] == "sales_order"]
        scored = fallback

    return scored[:top_k]
