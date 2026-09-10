"""Supervisor StateGraph —— 主管 Agent 的编排图。

多 Agent + HITL 架构：

    START
      │
      ▼
    route_intent ── 意图识别（rule-based）
      │
      ▼
    plan_tasks ── 任务分配（LLM 自主决策 or 规则回退）
      │
      ▼
    hitl_review ── 人工审核决策（manual 模式高风险时 interrupt）
      │
      ▼ (条件边 route_dispatch)
      ├─ data_agent ── DataSubAgent（召回→NL2SQL→校验→执行→分析）
      │     │
      │     ▼ (条件边 route_after_data)
      │     ├─ search_agent ── SearchSubAgent（外部搜索 / 跨境平台 / 详情）
      │     └──────────────┐
      ├─ search_agent ────────────────────────────┤
      └─ build_answer ────────────────────────────┤
                                                   ▼
                                                  END

    - 主管负责任务分配与结果汇总，子 Agent 各自独立 StateGraph。
    - HYBRID_ANALYSIS 场景下先跑 DataSubAgent，再用其内部上下文聚焦 SearchSubAgent 检索词。
    - HITL 通过 MemorySaver checkpointer 支持 interrupt 暂停与 Command(resume) 恢复。
    - run_log（不可序列化对象）经 config["configurable"]["run_log"] 传递，不进 state，
      避免 checkpointer 序列化失败。
"""

from __future__ import annotations

import inspect
from typing import Any

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from backend.agent.shared.answer import build_answer
from backend.agent.shared.sse import make_event
from backend.agent.supervisor.hitl import hitl_review_node
from backend.agent.supervisor.planner import get_planner
from backend.agent.supervisor.router import router
from backend.agent.supervisor.state import SupervisorState

# 企业内部数据库链路的工具
INTERNAL_TOOLS = {"table_recall", "schema_recall", "metric_recall", "sql_execute"}

# 搜索子 Agent 覆盖的工具
SEARCH_TOOLS = {"external_web_search", "aliyun_marketplace_search", "fetch_product_detail"}


def _run_log_from(config) -> Any:
    """从 LangGraph 注入的 config 里取 run_log（不可序列化，故不放 state）。"""
    if not config:
        return None
    configurable = config.get("configurable", {}) if isinstance(config, dict) else {}
    return configurable.get("run_log")


def _build_search_query(query: str, internal: dict | None, search_tools: list[str]) -> str:
    """构造聚焦的外部检索词（仅 external_web_search 需要；marketplace 用原 query）。"""
    if "external_web_search" not in search_tools:
        return query
    tokens: list[str] = []
    if internal and internal.get("spec"):
        filters = internal["spec"].get("filters", {})
        if filters.get("country"):
            tokens.append(filters["country"])
        if filters.get("platform"):
            tokens.append(filters["platform"])
    if not tokens:
        tokens.append("跨境电商 内衣")
    tokens.append("市场 趋势")
    if any(k in query for k in ["规则", "政策", "平台"]):
        tokens.append("规则 政策")
    return " ".join(tokens)


# ---------------------------------------------------------------------------
# 节点
# ---------------------------------------------------------------------------
def node_route_intent(state: SupervisorState, config=None) -> dict:
    """第一步：识别意图。规则实现，离线可跑、0 token。"""
    run_log = _run_log_from(config)
    query = state.get("query", "").strip()
    route = router.route(query)
    intent = route["intent"]
    events = [make_event(
        "intent_detected",
        f"识别意图：{intent}（{route['reason']}）",
        data={"intent": intent, "reason": route["reason"], "tools": []},
    )]
    if run_log is not None:
        run_log.intent = intent
        run_log.info("intent_routed",
                     intent=intent,
                     signals_internal=",".join(route["signals"]["internal"]),
                     signals_external=",".join(route["signals"]["external"]))
    return {
        "intent": intent,
        "intent_reason": route["reason"],
        "events": events,
        "tool_names": [],
        "plan": [],
    }


async def node_plan_tasks(state: SupervisorState, config=None) -> dict:
    """第二步：决定本次要执行哪些工具（任务分配）。"""
    run_log = _run_log_from(config)
    query = state.get("query", "").strip()
    intent = state.get("intent", "INTERNAL_DATA")

    planner = get_planner()
    plan = planner.plan(intent, query, run_log=run_log)
    if inspect.isawaitable(plan):
        plan = await plan
    tool_names = [s.tool for s in plan]
    if run_log is not None:
        run_log.tools = tool_names
    events = [make_event(
        "plan_ready",
        f"规划完成：调用 {len(tool_names)} 个工具",
        data={"tools": tool_names, "plan": [
            {"tool": s.tool, "args": s.args} for s in plan
        ]},
    )]
    return {
        "plan": [{"tool": s.tool, "args": s.args} for s in plan],
        "tool_names": tool_names,
        "events": events,
    }


async def node_data_agent(state: SupervisorState, config=None) -> dict:
    """派发 DataSubAgent：召回 → NL2SQL → 校验 → 执行 → 分析。"""
    from backend.agent.data_agent.graph import get_data_graph

    run_log = _run_log_from(config)
    query = state.get("query", "").strip()
    request_id = state.get("request_id", "")

    sub = get_data_graph()
    sub_input = {
        "query": query,
        "events": [],
        "request_id": request_id,
        "run_log": run_log,
    }
    result = await sub.ainvoke(sub_input)
    return {
        "internal": result.get("internal"),
        "error": result.get("error"),
        "retrieved_tables": result.get("retrieved_tables"),
        "retrieved_column_infos": result.get("retrieved_column_infos"),
        "retrieved_metric_infos": result.get("retrieved_metric_infos"),
        "events": result.get("events", []),
    }


async def node_search_agent(state: SupervisorState, config=None) -> dict:
    """派发 SearchSubAgent：外部搜索 / 跨境平台搜索 + 详情抓取。"""
    from backend.agent.search_agent.graph import get_search_graph

    run_log = _run_log_from(config)
    query = state.get("query", "").strip()
    request_id = state.get("request_id", "")
    intent = state.get("intent", "")
    tool_names = state.get("tool_names", [])
    internal = state.get("internal")

    search_tools = [t for t in tool_names if t in SEARCH_TOOLS]
    search_query = _build_search_query(query, internal, search_tools)

    sub = get_search_graph()
    sub_input = {
        "query": query,
        "intent": intent,
        "tool_names": search_tools,
        "search_query": search_query,
        "events": [],
        "request_id": request_id,
        "run_log": run_log,
    }
    result = await sub.ainvoke(sub_input)
    return {
        "external": result.get("external"),
        "marketplace": result.get("marketplace"),
        "error": result.get("error"),
        "events": result.get("events", []),
    }


def node_build_answer(state: SupervisorState, config=None) -> dict:
    """汇总：把 internal / external / marketplace 装配成最终答案。"""
    run_log = _run_log_from(config)
    query = state.get("query", "").strip()
    intent = state.get("intent", "INTERNAL_DATA")
    internal = state.get("internal")
    external = state.get("external")
    marketplace = state.get("marketplace")

    events = [make_event("result_analysis", "正在综合分析")]

    answer = build_answer(intent, query, internal, external, marketplace)
    if run_log is not None:
        run_log.info("answer_built",
                     sections=[s["key"] for s in answer.get("sections", [])])
    events.append(make_event(
        "answer_generated", "分析完成",
        data={"answer": answer, "request_id": state.get("request_id", "")},
    ))
    return {"answer": answer, "events": events}


# ---------------------------------------------------------------------------
# 条件边
# ---------------------------------------------------------------------------
def route_dispatch(state: SupervisorState) -> str:
    """HITL 之后：派发到 DataSubAgent / SearchSubAgent / 直接汇总。"""
    if state.get("hitl_decision") == "reject":
        return "build_answer"
    tool_names = set(state.get("tool_names", []))
    need_data = bool(INTERNAL_TOOLS & tool_names)
    need_search = bool(SEARCH_TOOLS & tool_names)
    if need_data:
        return "data_agent"
    if need_search:
        return "search_agent"
    return "build_answer"


def route_after_data(state: SupervisorState) -> str:
    """DataSubAgent 之后：是否还需跑 SearchSubAgent（HYBRID 场景）。"""
    if state.get("hitl_decision") == "reject":
        return "build_answer"
    if SEARCH_TOOLS & set(state.get("tool_names", [])):
        return "search_agent"
    return "build_answer"


# ---------------------------------------------------------------------------
# 构建 StateGraph
# ---------------------------------------------------------------------------
# MemorySaver 单例：供 HITL interrupt 暂停与 Command(resume) 恢复
_checkpointer = MemorySaver()


def build_graph():
    workflow = StateGraph(SupervisorState)

    workflow.add_node("route_intent", node_route_intent)
    workflow.add_node("plan_tasks", node_plan_tasks)
    workflow.add_node("hitl_review", hitl_review_node)
    workflow.add_node("data_agent", node_data_agent)
    workflow.add_node("search_agent", node_search_agent)
    workflow.add_node("build_answer", node_build_answer)

    workflow.add_edge(START, "route_intent")
    workflow.add_edge("route_intent", "plan_tasks")
    workflow.add_edge("plan_tasks", "hitl_review")

    workflow.add_conditional_edges(
        "hitl_review",
        route_dispatch,
        {
            "data_agent": "data_agent",
            "search_agent": "search_agent",
            "build_answer": "build_answer",
        },
    )
    workflow.add_conditional_edges(
        "data_agent",
        route_after_data,
        {
            "search_agent": "search_agent",
            "build_answer": "build_answer",
        },
    )
    workflow.add_edge("search_agent", "build_answer")
    workflow.add_edge("build_answer", END)

    return workflow.compile(checkpointer=_checkpointer)


# 单例主管图（首次调用编译一次，后续复用）
_supervisor_graph = None


def get_supervisor_graph():
    global _supervisor_graph
    if _supervisor_graph is None:
        _supervisor_graph = build_graph()
    return _supervisor_graph
