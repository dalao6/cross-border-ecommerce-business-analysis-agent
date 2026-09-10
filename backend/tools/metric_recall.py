"""Metric Recall —— 从指标字典召回业务指标口径。

输入：user_query
输出：指标定义、公式、相关表与字段，避免 LLM 猜测企业指标口径。
"""

from backend.database.metadata import METRIC_METADATA
from backend.tools.scoring import score_candidates

WEIGHTS = {
    "metric_name": 1.2,
    "business_domain": 0.8,
    "metric_definition": 0.4,
    "synonyms": 1.6,
}


def metric_recall(query: str, top_k: int = 5) -> list[dict]:
    """召回与问题相关的业务指标。"""
    candidates = [
        {
            "metric_name": m["metric_name"],
            "metric_definition": m["metric_definition"],
            "formula": m["formula"],
            "related_tables": m["related_tables"],
            "related_columns": m["related_columns"],
            "business_domain": m["business_domain"],
            "synonyms": m["synonyms"],
        }
        for m in METRIC_METADATA
    ]
    scored = score_candidates(query, candidates, WEIGHTS)

    if not scored or scored[0]["score"] == 0:
        scored = score_candidates("销量 销售额", candidates, WEIGHTS)

    return scored[:top_k]
