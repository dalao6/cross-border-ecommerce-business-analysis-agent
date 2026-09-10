"""validate_sql 节点 —— SQL 安全校验（仅允许 SELECT）。

失败则记录 error，后续执行/分析节点据此跳过。
"""

from backend.agent.data_agent.state import DataAgentState
from backend.agent.shared.sse import make_event
from backend.security.sql_validator import validate_sql


def validate_sql_node(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    sql = state.get("sql", "")
    events: list[dict] = []

    ok, err = validate_sql(sql)
    if not ok:
        if run_log is not None:
            run_log.error("sql_validator_blocked", sql=sql, error=err)
        events.append(make_event(
            "sql_validated",
            f"SQL 安全检查未通过，已阻止执行：{err}", status="error",
        ))
        events.append(make_event(
            "error", "SQL 安全检查未通过，已阻止执行。", status="error",
        ))
        return {"error": err, "events": events}

    if run_log is not None:
        run_log.tool_called("sql_validator", result="pass")
    events.append(make_event("sql_validated", "SQL 安全检查通过（仅允许 SELECT）"))
    return {"events": events}
