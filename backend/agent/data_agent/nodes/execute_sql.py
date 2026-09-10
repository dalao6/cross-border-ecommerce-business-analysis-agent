"""execute_sql 节点 —— 执行 SQL（校验失败则跳过执行）。"""

import time

from backend.agent.data_agent.state import DataAgentState
from backend.agent.shared.sse import make_event
from backend.tools.sql_execute import sql_execute


def execute_sql_node(state: DataAgentState) -> dict:
    if state.get("error"):
        return {}
    run_log = state.get("run_log")
    sql = state.get("sql", "")
    events: list[dict] = []

    t0 = time.time()
    events.append(make_event("sql_executing", "正在查询企业数据库"))
    result = sql_execute(sql)
    if not result["ok"]:
        if run_log is not None:
            run_log.error("sql_execute_failed", sql=sql, error=result.get("error", ""))
        events.append(make_event(
            "sql_completed", f"SQL 执行失败：{result['error']}", status="error",
        ))
        events.append(make_event(
            "error", f"SQL 执行失败：{result['error']}", status="error",
        ))
        return {"error": result.get("error", ""), "events": events}

    if run_log is not None:
        run_log.tool_called("sql_execute",
                            row_count=result["row_count"],
                            duration_ms=int((time.time() - t0) * 1000))
    events.append(make_event(
        "sql_completed",
        f"查询完成，返回 {result['row_count']} 条数据",
        data={"row_count": result["row_count"]},
    ))
    return {"sql_result": result, "events": events}
