"""验收测试：跑通 capsule 第三十一节的 5 个最终验收案例。

用 pytest 风格（也可直接 python tests/test_cases.py 运行）。
断言要点：
    - 意图路由正确
    - 内部/外部工具调用符合预期
    - 最终答案分区正确、内部外部数据严格区分
"""

import asyncio
import sys
from pathlib import Path

# 让脚本可被直接运行
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.agent.orchestrator import Orchestrator  # noqa: E402


async def _run(query: str):
    """跑一次编排，返回 (事件列表, 最终答案)。"""
    events = []
    answer = None
    orch = Orchestrator()
    async for e in orch.run(query):
        events.append(e)
        if e["event"] == "answer_generated":
            answer = e["data"]["answer"]
    return events, answer


def _tool_names(events):
    """从 SSE 事件里提取本次调用的工具列表。

    兼容两种来源：
        - intent_detected（旧编排器把 plan 嵌入此事件）
        - plan_ready（LangGraph 版本把 plan 单独发事件）
    """
    for e in events:
        if e["event"] == "plan_ready":
            return e["data"]["tools"]
        if e["event"] == "intent_detected" and e["data"].get("tools"):
            return e["data"]["tools"]
    return []


def _section_keys(answer):
    return [s["key"] for s in answer.get("sections", [])]


async def case1():
    q = "2025年各月销量变化趋势如何？"
    events, answer = await _run(q)
    assert answer["intent"] == "INTERNAL_DATA"
    assert "external_web_search" not in _tool_names(events)
    assert _section_keys(answer) == ["internal"]
    sec = answer["sections"][0]
    assert sec["chart_type"] == "line"
    assert sec["sql"].strip().upper().startswith("SELECT")
    print("[PASS] Case 1 各月销量趋势 → 内部链路 + 折线图，未调用外部工具")


async def case2():
    q = "2025年美国内衣市场有什么趋势？"
    events, answer = await _run(q)
    assert answer["intent"] == "EXTERNAL_INFORMATION"
    assert _tool_names(events) == ["external_web_search"]
    assert _section_keys(answer) == ["external"]
    assert len(answer["sections"][0]["sources"]) > 0
    print("[PASS] Case 2 市场趋势 → 仅外部搜索，未查询企业数据库")


async def case3():
    q = "为什么我们2025年美国市场销量下降？"
    events, answer = await _run(q)
    assert answer["intent"] == "HYBRID_ANALYSIS"
    tools = _tool_names(events)
    assert "sql_execute" in tools and "external_web_search" in tools
    keys = _section_keys(answer)
    assert keys == ["internal", "external", "conclusion"]
    assert any(u for u in answer.get("uncertain", []))
    print("[PASS] Case 3 混合分析 → 内部 + 外部 + 综合判断（含推测标记）")


async def case4():
    q = "TikTok Shop最近有什么规则变化，会不会影响我们的销量？"
    events, answer = await _run(q)
    assert answer["intent"] == "HYBRID_ANALYSIS"
    tools = _tool_names(events)
    assert "external_web_search" in tools and "sql_execute" in tools
    ext = answer["sections"][1]
    titles = "".join(s["title"] for s in ext["sources"])
    assert "TikTok" in titles
    print("[PASS] Case 4 平台规则 → 优先 TikTok 官方信息 + 内部销量")


async def case5():
    q = "哪个SKU未来15天可能缺货？"
    events, answer = await _run(q)
    assert answer["intent"] == "INTERNAL_DATA"
    assert "external_web_search" not in _tool_names(events)
    sec = answer["sections"][0]
    assert sec["chart_type"] == "bar"
    assert "缺货" in sec["conclusion"] or "可能缺货" in sec["conclusion"]
    print("[PASS] Case 5 缺货预测 → 仅内部数据（未擅自调用外部工具）")


async def case6():
    """MARKETPLACE_INTEL：跨境平台商品搜索 + 链式详情抓取。"""
    q = "搜索亚马逊,temu,eBay的情趣内衣热销榜的链接"
    events, answer = await _run(q)
    assert answer["intent"] == "MARKETPLACE_INTEL", f"应为 MARKETPLACE_INTEL，实际 {answer['intent']}"
    sec_keys = [s["key"] for s in answer["sections"]]
    assert "marketplace" in sec_keys, f"应含 marketplace 分区，实际 {sec_keys}"
    mp = next(s for s in answer["sections"] if s["key"] == "marketplace")
    assert len(mp["products"]) >= 3, f"应至少 3 个商品，实际 {len(mp['products'])}"
    # 链式抓取的详情
    assert mp.get("details") and len(mp["details"]) >= 1, "应有链式抓取的详情"
    for d in mp["details"][:2]:
        det = d["detail"]
        assert det.get("price") is not None
        assert det.get("monthly_sales") is not None
        assert det.get("review_count") is not None
    # SSE 中应出现"抓取详情"步骤
    fetch_msgs = [e.get("message", "") for e in events if "抓取详情" in e.get("message", "")]
    assert len(fetch_msgs) >= 1, "SSE 应有抓取详情步骤"
    print("[PASS] Case 6 marketplace 搜索 → 阿里云 + 链式详情抓取")


async def main():
    print("=" * 64)
    print("依伊服饰 AI 跨境电商经营分析智能体 · 验收测试")
    print("=" * 64)
    await case1()
    await case2()
    await case3()
    await case4()
    await case5()
    await case6()
    print("=" * 64)
    print("全部 6 个验收案例通过 ✅")


if __name__ == "__main__":
    asyncio.run(main())
