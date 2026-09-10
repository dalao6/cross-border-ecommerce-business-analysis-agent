"""fetch_details 节点 —— 跨境平台商品详情抓取（链式，不依赖 LLM 决定）。"""

import time

from backend.agent.search_agent.state import SearchAgentState
from backend.agent.shared.sse import make_event
from backend.tools.fetch_product_detail import fetch_product_detail

# 用户问题中表示「想要商品详情/字段」的关键词
DETAIL_KEYWORDS = [
    "尺码", "价格", "月销", "月销量", "销量", "评论", "评分", "详情", "字段",
    "size", "price", "review", "rating", "monthly", "bought",
]


def _user_wants_details(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in DETAIL_KEYWORDS)


def fetch_details_node(state: SearchAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    mk_result = dict(state.get("marketplace") or {})
    products = mk_result.get("results", []) or []
    events: list[dict] = []

    events.append(make_event(
        "external_tool_required",
        "判断需要抓取商品详情（尺码/价格/月销/评论）"))
    fetch_n = 3 if _user_wants_details(query) else 2
    details = []
    for idx, p in enumerate(products[:fetch_n], start=1):
        if run_log is not None:
            run_log.info("fetch_detail_start", seq=idx, platform=p["platform"], url=p["url"])
        t0 = time.time()
        events.append(make_event(
            "external_tool_calling",
            f"抓取详情：{p['platform']} · {p['title'][:30]}…",
        ))
        detail = fetch_product_detail(url=p["url"], platform=p.get("platform", "auto"))
        if run_log is not None:
            run_log.tool_called(
                "fetch_product_detail",
                platform=p["platform"],
                ok=detail.get("ok", False),
                fields=[k for k in detail.keys()
                        if k not in ("url", "platform", "ok", "fetched_at",
                                     "fetch_backend", "note", "source_html_snippet")],
                duration_ms=int((time.time() - t0) * 1000),
            )
        details.append({"product": p, "detail": detail})
    if run_log is not None:
        run_log.info("fetch_detail_done", requested=fetch_n, succeeded=len(details))
    events.append(make_event(
        "external_tool_completed",
        f"已抓取 {len(details)} 个商品的详情",
        data={"details": details},
    ))
    mk_result["details"] = details
    return {"marketplace": mk_result, "events": events}
