"""Human-in-the-Loop 节点逻辑（supervisor 层）。

在派发子 Agent 前评估风险，高风险操作（执行 SQL / 跨境平台搜索 / 敏感经营数据查询）
在 manual 模式下通过 LangGraph interrupt() 暂停，等待人工确认后继续。

模式：
    - auto（默认）  高风险操作自动放行，不真正暂停（离线演示可端到端跑通）
    - manual        高风险操作前 interrupt，等待人工 approve / reject
"""

from __future__ import annotations

from backend.agent.shared.sse import make_event
from backend.config import settings

# 敏感经营数据信号（涉及成本/利润/库存等，需谨慎对外）
SENSITIVE_SIGNALS = [
    "删除", "修改", "更新", "退款", "退货", "缺货", "库存", "采购", "成本",
    "利润", "毛利", "客单价", "复购", "供应商", "账期",
]


def evaluate_risk(query: str, tool_names: list[str]) -> dict:
    """评估是否需要人工审核。返回 {required, reason, risk_level}。"""
    reasons: list[str] = []
    tools = set(tool_names or [])
    if "sql_execute" in tools:
        if any(k in query for k in SENSITIVE_SIGNALS):
            reasons.append("查询涉及敏感经营数据（库存/成本/利润等）")
        else:
            reasons.append("将执行企业数据库 SQL 查询")
    if {"aliyun_marketplace_search", "fetch_product_detail"} & tools:
        reasons.append("将发起跨境平台外部搜索/抓取")
    if "external_web_search" in tools:
        reasons.append("将检索互联网公开信息")

    if reasons:
        return {"required": True, "reason": "；".join(reasons), "risk_level": "high"}
    return {"required": False, "reason": "", "risk_level": "low"}


def hitl_review_node(state: dict, config=None) -> dict:
    """HITL 审核节点。manual 模式高风险时 interrupt，否则放行。"""
    from langgraph.types import interrupt

    run_log = None
    if config and isinstance(config, dict):
        run_log = config.get("configurable", {}).get("run_log")
    query = state.get("query", "").strip()
    tool_names = state.get("tool_names", [])
    events: list[dict] = []

    risk = evaluate_risk(query, tool_names)

    if not risk["required"]:
        events.append(make_event(
            "hitl_review", "低风险操作，无需人工审核",
            data={"decision": "approve", "risk_level": "low", "reason": ""}))
        return {"hitl_decision": "approve", "hitl_reason": "", "events": events}

    if settings.hitl_mode == "manual":
        # 真正暂停，等待人工确认
        decision = interrupt({
            "type": "hitl_review",
            "reason": risk["reason"],
            "question": query,
            "tools": tool_names,
        })
        if decision not in ("approve", "reject"):
            decision = "approve"
        if run_log is not None:
            run_log.warn("hitl_review", decision=decision, reason=risk["reason"])
        events.append(make_event(
            "hitl_review",
            f"人工审核结果：{'通过' if decision == 'approve' else '拒绝'}",
            data={"decision": decision, "reason": risk["reason"], "mode": "manual"}))
        if decision == "reject":
            events.append(make_event("error", "人工审核未通过，已中止执行。", status="error"))
            return {
                "hitl_decision": "reject",
                "hitl_reason": risk["reason"],
                "error": "人工审核未通过，已中止执行。",
                "events": events,
            }
        return {"hitl_decision": "approve", "hitl_reason": risk["reason"], "events": events}

    # auto：自动放行（演示模式）
    if run_log is not None:
        run_log.warn("hitl_review", decision="auto_approve", reason=risk["reason"])
    events.append(make_event(
        "hitl_review",
        f"已自动通过人工审核（演示模式）：{risk['reason']}",
        data={"decision": "approve", "reason": risk["reason"], "mode": "auto"}))
    return {"hitl_decision": "approve", "hitl_reason": risk["reason"], "events": events}
