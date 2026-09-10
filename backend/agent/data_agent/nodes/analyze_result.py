"""analyze_result 节点 —— 结果分析 + 异常检测，并组装内部链路最终结果。"""

import time

from backend.agent.data_agent.analyzer import analyze
from backend.agent.data_agent.state import DataAgentState
from backend.agent.shared.sse import make_event


def analyze_result_node(state: DataAgentState) -> dict:
    if state.get("error"):
        return {}
    run_log = state.get("run_log")
    query = state.get("query", "").strip()
    spec = state.get("spec") or {}
    sql = state.get("sql", "")
    result = state.get("sql_result") or {}
    events: list[dict] = []

    t0 = time.time()
    analysis = analyze(query, spec.get("intent", "total"), spec.get("metric", "销量"),
                       spec.get("dimension", "month"), result.get("rows", []))
    if analysis.get("anomalies"):
        if run_log is not None:
            run_log.warn("anomaly_detected", count=len(analysis["anomalies"]))
        events.append(make_event(
            "anomaly_detected",
            f"检测到 {len(analysis['anomalies'])} 处异常波动",
            data={"anomalies": analysis["anomalies"]},
        ))
    if run_log is not None:
        run_log.tool_called("result_analyzer",
                            anomalies=len(analysis.get("anomalies", [])),
                            duration_ms=int((time.time() - t0) * 1000))

    return {
        "analysis": analysis,
        "internal": {
            "sql": sql,
            "spec": spec,
            "analysis": analysis,
            "table": {"columns": result.get("columns", []), "rows": result.get("rows", [])},
        },
        "events": events,
    }
