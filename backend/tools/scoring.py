"""召回与执行工具共享的评分工具函数。"""


def hits(query: str, keywords: list[str]) -> int:
    """统计 query 中命中关键词的次数（子串匹配，适配中文无空格问法）。"""
    n = 0
    for kw in keywords:
        if kw and kw in query:
            n += 1
    return n


def score_candidates(query: str, candidates: list[dict], weight_map: dict[str, float]) -> list[dict]:
    """按多字段关键词命中加权打分，返回按分数降序的候选列表。"""
    scored = []
    for c in candidates:
        total = 0.0
        for field, weight in weight_map.items():
            values = c.get(field)
            if values is None:
                continue
            if isinstance(values, str):
                values = [values]
            total += weight * hits(query, values)
        scored.append({**c, "score": round(total, 3)})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
