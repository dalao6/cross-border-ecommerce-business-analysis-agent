"""generate_sql 节点 —— NL2SQL：把问题转成 SQL（确定性规则引擎）。"""

import time

from backend.agent.data_agent.nl2sql import generate_sql
from backend.agent.data_agent.state import DataAgentState
from backend.agent.shared.sse import make_event


def generate_sql_node(state: DataAgentState) -> dict:
    run_log = state.get("run_log")
    query = state.get("query", "").strip()

    t0 = time.time()
    spec = generate_sql(query)
    sql = spec["sql"]
    if run_log is not None:
        run_log.sql = sql
        run_log.tool_called("nl2sql", sql=sql,
                            duration_ms=int((time.time() - t0) * 1000))
    return {
        "spec": spec,
        "sql": sql,
        "events": [make_event("sql_generated", "SQL 生成完成", data={"sql": sql})],
    }
