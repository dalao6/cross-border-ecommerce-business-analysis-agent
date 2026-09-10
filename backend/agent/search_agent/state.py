"""SearchAgentState —— 搜索子 Agent 的独立状态。

SearchSubAgent 只负责外部信息搜索链路：外部 Web 搜索 + 跨境平台搜索 + 详情抓取。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _append_event(existing: list[dict] | None, new: list[dict]) -> list[dict]:
    if not existing:
        existing = []
    return existing + list(new or [])


def _merge_optional(existing, new):
    return new if new not in (None, "", {}, []) else existing


class SearchAgentState(TypedDict, total=False):
    """搜索子 Agent 状态。"""

    # ---- 输入 ----
    query: str
    intent: str                        # 意图（用于聚焦检索词）
    tool_names: list[str]              # 本次要执行的搜索工具（由 Supervisor 派发）
    search_query: str                  # 聚焦后的检索词（由 Supervisor 结合内部上下文构造，缺省回退 query）

    # ---- 输出 ----
    external: Annotated[dict | None, _merge_optional]      # 互联网公开信息
    marketplace: Annotated[dict | None, _merge_optional]   # 跨境平台搜索 + 详情
    error: Annotated[str, _merge_optional]

    # ---- 可观测 ----
    events: Annotated[list[dict], _append_event]
    request_id: str
    run_log: Any
