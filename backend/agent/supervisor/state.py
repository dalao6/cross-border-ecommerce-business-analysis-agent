"""SupervisorState —— 主管 Agent 的全局状态。

Supervisor 是顶层编排，state 字段是 DataAgentState / SearchAgentState 的超集：
路由、规划、HITL 决策、子 Agent 结果汇总、最终答案都挂在这里。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


def _append_event(existing: list[dict] | None, new: list[dict]) -> list[dict]:
    if not existing:
        existing = []
    return existing + list(new or [])


def _merge_optional(existing, new):
    return new if new not in (None, "", {}, []) else existing


class SupervisorState(TypedDict, total=False):
    """主管 Agent 状态。"""

    # ---- 输入 ----
    query: str

    # ---- 意图与规划 ----
    intent: str                        # INTERNAL_DATA / EXTERNAL_INFORMATION / HYBRID_ANALYSIS / MARKETPLACE_INTEL
    intent_reason: str
    plan: list[dict[str, Any]]         # [{tool, args}, ...]
    tool_names: list[str]              # 计划中的工具名

    # ---- HITL 人工审核 ----
    hitl_decision: str                 # approve / reject
    hitl_reason: str                   # 审核理由（风险描述）

    # ---- 子 Agent 结果（汇总）----
    internal: Annotated[dict | None, _merge_optional]      # DataSubAgent 输出
    external: Annotated[dict | None, _merge_optional]      # SearchSubAgent 输出（网络）
    marketplace: Annotated[dict | None, _merge_optional]   # SearchSubAgent 输出（跨境平台）

    # ---- DataSubAgent 召回审计字段（回传到顶层，供审计日志）----
    retrieved_tables: Annotated[list[str] | None, _merge_optional]
    retrieved_column_infos: Annotated[list[dict] | None, _merge_optional]
    retrieved_metric_infos: Annotated[list[dict] | None, _merge_optional]

    # ---- 输出 ----
    answer: Annotated[dict | None, _merge_optional]
    error: Annotated[str, _merge_optional]

    # ---- 可观测 ----
    events: Annotated[list[dict], _append_event]
    request_id: str

    # ---- messages：保留 LangGraph 原生通道 ----
    messages: Annotated[list, add_messages]
