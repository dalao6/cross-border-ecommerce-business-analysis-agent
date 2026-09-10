"""Table Recall —— 从元数据字典召回相关数据表。

输入：user_query
输出：按相关性排序的表及其业务域/描述。
"""

from backend.database.metadata import TABLE_METADATA
from backend.tools.scoring import score_candidates

# 各字段对得分的贡献权重
WEIGHTS = {
    "table_name": 1.0,
    "table_comment": 1.2,
    "business_domain": 1.0,
    "business_description": 0.4,
    "synonyms": 1.5,
}


def table_recall(query: str, top_k: int = 5) -> list[dict]:
    """召回与问题相关的数据表。"""
    candidates = [
        {
            "table_name": t["table_name"],
            "table_comment": t["table_comment"],
            "business_domain": t["business_domain"],
            "business_description": t["business_description"],
            "synonyms": t["synonyms"],
        }
        for t in TABLE_METADATA
    ]
    scored = score_candidates(query, candidates, WEIGHTS)

    # 若完全没有命中，回退到销售域默认表，避免空召回
    if not scored or scored[0]["score"] == 0:
        scored = score_candidates("销量 销售额 订单", candidates, WEIGHTS)

    return scored[:top_k]
