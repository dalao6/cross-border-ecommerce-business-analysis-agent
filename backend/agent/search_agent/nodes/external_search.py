"""external_search 节点 —— 互联网公开信息搜索。"""

import time

from backend.agent.search_agent.state import SearchAgentState
from backend.agent.shared.sse import make_event
from backend.tools.external_web_search import external_web_search


def external_search_node(state: SearchAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    ext_query = state.get("search_query") or query
    events: list[dict] = []

    events.append(make_event("external_tool_required", "判断需要补充外部公开信息"))
    events.append(make_event("external_tool_calling", "调用 External Web Search"))

    t0 = time.time()
    ext_result = external_web_search(ext_query)
    n = len(ext_result.get("results", []))
    sources = [r["title"] for r in ext_result.get("results", [])]
    if run_log is not None:
        run_log.external_sources.extend(sources)
        run_log.tool_called("external_web_search",
                            query=ext_query, results_count=n,
                            duration_ms=int((time.time() - t0) * 1000))
    events.append(make_event(
        "external_tool_completed",
        f"获取 {n} 条外部相关信息",
        data={"query": ext_query, "sources": ext_result.get("results", [])},
    ))
    return {"external": ext_result, "events": events}
