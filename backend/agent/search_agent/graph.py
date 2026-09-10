"""SearchSubAgent StateGraph —— 搜索子 Agent 的编排图。

节点链路：

    START
      │
      ▼  (条件边 route_search：按 tool_names 扇出)
      ├─ external_search ─────────────────────────┐
      └─ marketplace_search → fetch_details ──────┤
                                                  ▼
                                                 END

    - external_search    互联网公开信息搜索（行业趋势/规则/政策）
    - marketplace_search 跨境平台商品搜索（阿里云 OpenSearch）
    - fetch_details      链式抓取商品详情（不依赖 LLM 决定）

该图由 Supervisor 作为子 Agent 调用（ainvoke），不直接对外暴露。
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from backend.agent.search_agent.nodes.external_search import external_search_node
from backend.agent.search_agent.nodes.fetch_details import fetch_details_node
from backend.agent.search_agent.nodes.marketplace_search import marketplace_search_node
from backend.agent.search_agent.state import SearchAgentState

# 跨境平台商品搜索/抓取工具
MARKETPLACE_TOOLS = {"aliyun_marketplace_search", "fetch_product_detail"}


def node_noop(state: SearchAgentState) -> dict:
    """空节点：无搜索任务时的占位。"""
    return {}


def route_search(state: SearchAgentState) -> tuple[str, ...]:
    """根据 tool_names 扇出到对应搜索链路。"""
    tool_names = set(state.get("tool_names", []))
    targets: list[str] = []
    if "external_web_search" in tool_names:
        targets.append("external_search")
    if MARKETPLACE_TOOLS & tool_names:
        targets.append("marketplace_search")
    if not targets:
        targets.append("noop")
    return tuple(targets)


def build_graph():
    workflow = StateGraph(SearchAgentState)

    workflow.add_node("external_search", external_search_node)
    workflow.add_node("marketplace_search", marketplace_search_node)
    workflow.add_node("fetch_details", fetch_details_node)
    workflow.add_node("noop", node_noop)

    workflow.add_conditional_edges(
        START,
        route_search,
        {
            "external_search": "external_search",
            "marketplace_search": "marketplace_search",
            "noop": "noop",
        },
    )
    workflow.add_edge("external_search", END)
    workflow.add_edge("marketplace_search", "fetch_details")
    workflow.add_edge("fetch_details", END)
    workflow.add_edge("noop", END)

    return workflow.compile()


# 单例子图（首次调用编译一次，后续复用）
_search_graph = None


def get_search_graph():
    global _search_graph
    if _search_graph is None:
        _search_graph = build_graph()
    return _search_graph
