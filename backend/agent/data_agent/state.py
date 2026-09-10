"""DataAgentState —— 数据库子 Agent 的独立状态。

DataSubAgent 只负责企业数据库链路：召回 → NL2SQL → 校验 → 执行 → 分析。
它是 SupervisorState 的字段子集，被 Supervisor 作为子 Agent 独立调用。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict


def _append_event(existing: list[dict] | None, new: list[dict]) -> list[dict]:
    """Reducer：把节点产出的 SSE 事件追加到事件流。"""
    if not existing:
        existing = []
    return existing + list(new or [])


def _merge_optional(existing, new):
    """Reducer：有值则覆盖，空则保留旧值。"""
    return new if new not in (None, "", {}, []) else existing


class DataAgentState(TypedDict, total=False):
    """数据库子 Agent 状态。"""

    # ---- 输入 ----
    query: str

    # ---- 召回中间结果 ----
    keywords: list[str]                # jieba 抽取关键词（含原问题兜底）
    retrieved_tables: list[str]        # 由字段召回推导的表名
    retrieved_column_infos: list[dict] # 字段召回结果
    retrieved_value_infos: list[dict]  # 字段取值召回结果
    retrieved_metric_infos: list[dict] # 指标召回结果

    # ---- NL2SQL 生成/执行 ----
    spec: dict                         # NL2SQL 解析结果
    sql: str                           # 生成的 SQL
    sql_result: dict                   # SQL 执行结果
    analysis: dict                     # 结果分析 + 异常检测

    # ---- 输出 ----
    internal: Annotated[dict | None, _merge_optional]   # 数据库链路结果
    error: Annotated[str, _merge_optional]              # 错误信息

    # ---- 可观测 ----
    events: Annotated[list[dict], _append_event]        # SSE 事件流
    request_id: str
    run_log: Any
