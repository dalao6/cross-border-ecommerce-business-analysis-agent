"""marketplace_search 节点 —— 跨境平台商品搜索（阿里云 OpenSearch）。"""

import time

from backend.agent.search_agent.state import SearchAgentState
from backend.agent.shared.sse import make_event
from backend.tools.aliyun_marketplace_search import aliyun_marketplace_search


def _infer_platform(query: str) -> str:
    """从用户问题里推断主要跨境平台。"""
    q = query.lower()
    platforms = []
    if any(k in q for k in ["亚马逊", "amazon", "amz"]):
        platforms.append("amazon")
    if "temu" in q:
        platforms.append("temu")
    if any(k in q for k in ["ebay", "易贝"]):
        platforms.append("ebay")
    if not platforms:
        return "all"
    return platforms[0] if len(platforms) == 1 else "all"


def marketplace_search_node(state: SearchAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    events: list[dict] = []

    events.append(make_event(
        "external_tool_required", "判断需要在跨境平台搜索商品"))
    events.append(make_event(
        "external_tool_calling", "调用阿里云 OpenSearch 跨境平台商品搜索"))

    platform = _infer_platform(query)
    if run_log is not None:
        run_log.info("marketplace_search_start", platform=platform, top_k=8)
    t0 = time.time()
    mk_result = aliyun_marketplace_search(query=query, platform=platform, top_k=8)
    products = mk_result.get("results", [])
    sources = [f"{r['platform']}: {r['title'][:40]}" for r in products]
    if run_log is not None:
        run_log.external_sources.extend(sources)
        run_log.tool_called("aliyun_marketplace_search",
                            backend=mk_result.get("backend", "?"),
                            platform=platform,
                            results_count=len(products),
                            duration_ms=int((time.time() - t0) * 1000))
    n = len(products)
    events.append(make_event(
        "external_tool_completed",
        f"获取 {n} 条跨境平台商品链接（后端: {mk_result.get('backend','?')}）",
        data={
            "query": query,
            "platforms": mk_result.get("platforms", []),
            "products": products,
            "backend": mk_result.get("backend", "?"),
            "note": mk_result.get("note", ""),
        },
    ))
    return {"marketplace": mk_result, "events": events}
