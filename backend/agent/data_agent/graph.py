"""DataSubAgent StateGraph —— 数据库子 Agent 的编排图。

节点链路（线性细粒度流水线）：

    START
      │
      ▼
    extract_keywords ── 用 jieba 抽取检索关键词
      │
      ▼
    recall_column ── 字段召回（Qdrant 向量 → scoring 回退），推导涉及表
      │
      ▼
    recall_value ── 字段取值召回（ES 全文 → SQLite 回退）
      │
      ▼
    recall_metric ── 指标召回（Qdrant 向量 → scoring 回退）
      │
      ▼
    merge_retrieved ── 合并三路召回（供 SSE 展示与审计）
      │
      ▼
    generate_sql ── NL2SQL（确定性规则引擎）
      │
      ▼
    validate_sql ── SQL 安全校验（仅允许 SELECT）
      │
      ▼
    execute_sql ── 执行 SQL（校验失败则跳过）
      │
      ▼
    analyze_result ── 结果分析 + 异常检测
      │
      ▼
    END

字段/指标召回优先走 Qdrant 向量检索、字段取值走 ES 全文检索，向量后端不可用时
自动回退到 scoring.py 关键词打分方案，保证离线可跑。

该图由 Supervisor 作为子 Agent 调用（ainvoke），不直接对外暴露。
"""

from __future__ import annotations

import time

from langgraph.graph import END, START, StateGraph

from backend.agent.data_agent.nodes.analyze_result import analyze_result_node
from backend.agent.data_agent.nodes.execute_sql import execute_sql_node
from backend.agent.data_agent.nodes.extract_keywords import extract_keywords
from backend.agent.data_agent.nodes.generate_sql import generate_sql_node
from backend.agent.data_agent.nodes.merge_retrieved_info import merge_retrieved_info
from backend.agent.data_agent.nodes.recall_column import recall_column
from backend.agent.data_agent.nodes.recall_metric import recall_metric
from backend.agent.data_agent.nodes.recall_value import recall_value
from backend.agent.data_agent.nodes.validate_sql import validate_sql_node
from backend.agent.data_agent.state import DataAgentState
from backend.agent.shared.sse import make_event


def _tables_from_columns(columns: list[dict]) -> list[str]:
    """从字段召回结果推导涉及的表名（去重排序）。"""
    return sorted({c.get("table_name") for c in columns if c.get("table_name")})


# ---------------------------------------------------------------------------
# 节点包装函数（从 state 取输入 → 调纯函数 → 写 state + events + run_log）
# ---------------------------------------------------------------------------
def node_extract_keywords(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    keywords = extract_keywords(query)
    if run_log is not None:
        run_log.info("keywords_extracted", keywords=",".join(keywords[:8]))
    return {
        "keywords": keywords,
        "events": [make_event(
            "keywords_extracted",
            f"抽取关键词 {len(keywords)} 个",
            data={"keywords": keywords},
        )],
    }


async def node_recall_column(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    keywords = state.get("keywords") or [query]
    events: list[dict] = []

    t0 = time.time()
    columns, _entities = await recall_column(query, keywords)
    tables = _tables_from_columns(columns)
    if run_log is not None:
        run_log.tool_called("table_recall",
                            tables=",".join(tables),
                            duration_ms=int((time.time() - t0) * 1000))
        run_log.tool_called("schema_recall",
                            columns_count=len(columns),
                            duration_ms=int((time.time() - t0) * 1000))
    events.append(make_event(
        "table_recall",
        f"已召回数据表：{', '.join(tables) if tables else '（无）'}",
        data={"tables": tables},
    ))
    events.append(make_event(
        "schema_recall",
        f"已召回相关字段 {len(columns)} 个",
        data={"columns": columns},
    ))
    return {
        "retrieved_column_infos": columns,
        "retrieved_tables": tables,
        "events": events,
    }


async def node_recall_value(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    keywords = state.get("keywords") or [query]

    t0 = time.time()
    values, _entities = await recall_value(query, keywords)
    if run_log is not None:
        run_log.tool_called("value_recall",
                            value_count=len(values),
                            duration_ms=int((time.time() - t0) * 1000))
    return {
        "retrieved_value_infos": values,
        "events": [make_event(
            "value_recall",
            f"已召回相关字段取值 {len(values)} 个",
            data={"values": values},
        )],
    }


async def node_recall_metric(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    keywords = state.get("keywords") or [query]

    t0 = time.time()
    metrics, _entities = await recall_metric(query, keywords)
    if run_log is not None:
        run_log.tool_called("metric_recall",
                            metrics=",".join(m["metric_name"] for m in metrics),
                            duration_ms=int((time.time() - t0) * 1000))
    return {
        "retrieved_metric_infos": metrics,
        "events": [make_event(
            "metric_recall",
            f"已召回指标：{', '.join(m['metric_name'] for m in metrics)}",
            data={"metrics": metrics},
        )],
    }


def node_merge_retrieved(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    columns = state.get("retrieved_column_infos") or []
    values = state.get("retrieved_value_infos") or []
    metrics = state.get("retrieved_metric_infos") or []

    merged = merge_retrieved_info(columns, values, metrics)
    if run_log is not None:
        run_log.info("retrieval_merged",
                     tables=",".join(merged["table_names"]),
                     columns=merged["column_count"],
                     values=merged["value_count"],
                     metrics=",".join(merged["metric_names"]))
    return {
        "events": [make_event(
            "retrieval_merged",
            f"三路召回合并：{merged['column_count']} 字段 / {merged['value_count']} 取值 / {len(merged['metric_names'])} 指标",
            data=merged,
        )],
    }


# ---------------------------------------------------------------------------
# 构建 StateGraph
# ---------------------------------------------------------------------------
def build_graph():
    workflow = StateGraph(DataAgentState)

    workflow.add_node("extract_keywords", node_extract_keywords)
    workflow.add_node("recall_column", node_recall_column)
    workflow.add_node("recall_value", node_recall_value)
    workflow.add_node("recall_metric", node_recall_metric)
    workflow.add_node("merge_retrieved", node_merge_retrieved)
    workflow.add_node("generate_sql", generate_sql_node)
    workflow.add_node("validate_sql", validate_sql_node)
    workflow.add_node("execute_sql", execute_sql_node)
    workflow.add_node("analyze_result", analyze_result_node)

    workflow.add_edge(START, "extract_keywords")
    workflow.add_edge("extract_keywords", "recall_column")
    workflow.add_edge("recall_column", "recall_value")
    workflow.add_edge("recall_value", "recall_metric")
    workflow.add_edge("recall_metric", "merge_retrieved")
    workflow.add_edge("merge_retrieved", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    workflow.add_edge("validate_sql", "execute_sql")
    workflow.add_edge("execute_sql", "analyze_result")
    workflow.add_edge("analyze_result", END)

    return workflow.compile()


# 单例子图（首次调用编译一次，后续复用）
_data_graph = None


def get_data_graph():
    global _data_graph
    if _data_graph is None:
        _data_graph = build_graph()
    return _data_graph
