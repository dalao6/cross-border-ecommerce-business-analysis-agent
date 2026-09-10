"""SSE 事件构造（shared 层）。

把编排器 / 各 Agent 节点产出的事件统一封装为标准结构，
供 orchestrator 逐条 format_sse 后流式推送给前端。

    {
        "event": "<name>",
        "status": "completed" | "error" | "pending",
        "message": "<中文说明>",
        "data": { ... }   # 可选
    }
"""

from __future__ import annotations


def event(name: str, message: str = "", status: str = "completed",
          data: dict | None = None) -> dict:
    """构造一条标准 SSE 事件。"""
    e = {"event": name, "status": status, "message": message}
    if data is not None:
        e["data"] = data
    return e


# 别名：语义化命名，供节点调用时更直观
make_event = event
