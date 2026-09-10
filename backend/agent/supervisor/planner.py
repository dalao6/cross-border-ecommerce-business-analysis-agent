"""规划器（Planner）—— Agent 的「大脑」。

决定一次提问需要调用哪些工具、按什么顺序调用。这是「工具调用式 Agent」的决策层：

    - RulePlanner：确定性规则规划器（离线可跑），按意图路由结果给出工具序列。
    - LLMPlanner：基于大模型 function calling 的自主规划器（配置 LLM_API_KEY 时启用），
      由模型自行决定调用哪些工具；任何失败都会回退到规则规划器，保证链路永不中断。

二者都只回答「调用什么工具」，工具内部怎么做（召回/NL2SQL/校验/执行）是固定的，
这正符合「写死的工作流作为固定工具，何时调用由智能体决定」的架构原则。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import httpx

from backend.config import settings
from backend.tools.registry import tool_schemas_for_llm


@dataclass
class PlanStep:
    tool: str
    args: dict


class RulePlanner:
    """确定性规划：按意图返回工具序列。"""

    PLAN_MAP = {
        "INTERNAL_DATA": ["table_recall", "schema_recall", "metric_recall", "sql_execute"],
        "EXTERNAL_INFORMATION": ["external_web_search"],
        "MARKETPLACE_INTEL": ["aliyun_marketplace_search", "fetch_product_detail"],
        "HYBRID_ANALYSIS": ["table_recall", "schema_recall", "metric_recall", "sql_execute", "external_web_search"],
    }

    def plan(self, intent: str, query: str, run_log=None) -> list[PlanStep]:
        tools = self.PLAN_MAP.get(intent, self.PLAN_MAP["INTERNAL_DATA"])
        if run_log is not None:
            run_log.info("rule_planner", intent=intent, tools=",".join(tools))
        steps = []
        for t in tools:
            if t == "schema_recall":
                # 表名在运行时由编排器补齐
                steps.append(PlanStep(t, {"query": query, "retrieved_tables": None}))
            elif t == "fetch_product_detail":
                # url 在运行时由编排器从 search 结果中取
                steps.append(PlanStep(t, {"url": None}))
            elif t == "aliyun_marketplace_search":
                steps.append(PlanStep(t, {"query": query, "platform": "all", "top_k": 8}))
            else:
                steps.append(PlanStep(t, {"query": query}))
        return steps


class LLMPlanner:
    """大模型自主规划器（function calling）。"""

    SYSTEM_PROMPT = (
        "你是「依伊服饰 AI 跨境电商经营分析智能体」的决策中枢。"
        "根据用户问题，从可用工具中选择本次必须调用的工具（按调用顺序）。\n"
        "工具说明：\n"
        "- table_recall：召回相关数据表\n"
        "- schema_recall：召回相关字段\n"
        "- metric_recall：召回业务指标口径\n"
        "- sql_execute：执行企业内部数据查询（自动完成 SQL 生成与安全校验）\n"
        "- external_web_search：检索互联网公开信息（行业趋势/平台规则/政策/汇率等）\n"
        "- aliyun_marketplace_search：在 Amazon / Temu / eBay 等跨境平台搜索商品（找热销竞品链接）\n"
        "- fetch_product_detail：抓取一个商品 URL 的详情页（尺码/价格/月销/评论等）\n"
        "规则：纯内部数据问题只调数据库工具；纯跨境平台商品搜索问题只调 aliyun_marketplace_search"
        "（如需详情可同时调 fetch_product_detail，url 由编排器在运行时补齐）；"
        "纯外部信息问题只调 external_web_search；"
        "因果/混合问题同时调数据库工具与 external_web_search。"
    )

    async def plan(self, intent: str, query: str, run_log: "RunLog | None" = None) -> list[PlanStep]:
        """调用 LLM 决定工具序列，失败则回退规则规划器。

        若传入 run_log，会把本次 LLM 调用的 token 用量累加进去，便于终端日志观察消耗。
        """
        try:
            payload = {
                "model": settings.llm_model,
                "messages": [
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": query},
                ],
                "tools": tool_schemas_for_llm(),
                "tool_choice": "auto",
                "temperature": 0,
            }
            headers = {"Authorization": f"Bearer {settings.llm_api_key}"}
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    f"{settings.llm_base_url}/chat/completions",
                    json=payload, headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()

            # 1) 记录 token 用量（OpenAI 兼容 usage 字段）
            usage = data.get("usage") or {}
            if usage and run_log is not None:
                run_log.tokens.add(usage)
                run_log.info(
                    "llm_planner token_usage",
                    model=settings.llm_model,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                )

            # 2) 解析 function calling 决策
            message = data["choices"][0]["message"]
            calls = message.get("tool_calls", [])
            steps = []
            for c in calls:
                name = c["function"]["name"]
                args = json.loads(c["function"].get("arguments", "{}"))
                args.setdefault("query", query)
                steps.append(PlanStep(name, args))
            if steps:
                return steps
        except Exception as exc:  # noqa: BLE001
            if run_log is not None:
                run_log.warn("llm_planner fallback_to_rule", error=str(exc)[:200])
        return RulePlanner().plan(intent, query, run_log)


def get_planner():
    """根据配置返回 LLM 或规则规划器。"""
    if settings.use_llm:
        return LLMPlanner()
    return RulePlanner()
