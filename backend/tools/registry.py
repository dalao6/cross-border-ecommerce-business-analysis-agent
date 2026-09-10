"""工具注册表。

把 5 个能力工具统一登记为可被 Agent 循环调用的标准接口：
每个工具携带名称、描述（供 LLM 决策）与参数 Schema（供 function calling），
并提供统一的调用入口。LLM 规划器据此决定「何时调用哪个工具」，规则规划器
则按意图路由结果直接编排工具序列。
"""

from dataclasses import dataclass, field
from typing import Any, Callable

from backend.agent.data_agent.nodes.recall_value import recall_value_sync
from backend.tools import aliyun_marketplace_search, external_web_search, metric_recall, schema_recall, table_recall
from backend.tools.fetch_product_detail import fetch_product_detail
from backend.tools.sql_execute import sql_execute


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    required: list[str]
    func: Callable[..., Any]
    # 供前端「执行轨迹」展示的中文说明
    trace_label: str = ""


TOOLS: list[Tool] = [
    Tool(
        name="table_recall",
        description="根据用户问题从企业元数据字典召回相关数据表，返回表名、业务域与描述。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用户的自然语言问题"},
            },
        },
        required=["query"],
        func=table_recall.table_recall,
        trace_label="召回数据表",
    ),
    Tool(
        name="schema_recall",
        description="根据用户问题与已召回的表，召回相关字段（含类型、维度/度量角色）。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用户的自然语言问题"},
                "retrieved_tables": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "已召回的表名列表",
                },
            },
        },
        required=["query"],
        func=schema_recall.schema_recall,
        trace_label="召回字段",
    ),
    Tool(
        name="metric_recall",
        description="从企业指标字典召回业务指标口径（定义、公式、相关表字段），避免猜测指标定义。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用户的自然语言问题"},
            },
        },
        required=["query"],
        func=metric_recall.metric_recall,
        trace_label="召回指标",
    ),
    Tool(
        name="recall_value",
        description="召回用户问题中涉及的具体字段取值（如国家、平台、品类、仓库等维度枚举值），用于精确过滤。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "用户的自然语言问题"},
            },
        },
        required=["query"],
        func=recall_value_sync,
        trace_label="召回字段取值",
    ),
    Tool(
        name="sql_execute",
        description="执行一条已通过安全校验的 SELECT 查询，返回结果列与行数据。",
        parameters={
            "type": "object",
            "properties": {
                "validated_sql": {"type": "string", "description": "待执行的 SELECT SQL"},
            },
        },
        required=["validated_sql"],
        func=sql_execute,
        trace_label="执行 SQL",
    ),
    Tool(
        name="external_web_search",
        description="检索互联网公开信息（行业趋势、平台规则、贸易政策、汇率等），返回带来源与可信度的结构化结果。仅在涉及外部信息时调用。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要检索的公开信息主题"},
            },
        },
        required=["query"],
        func=external_web_search.external_web_search,
        trace_label="外部信息搜索",
    ),
    Tool(
        name="aliyun_marketplace_search",
        description="调用阿里云 OpenSearch 在 Amazon / Temu / eBay 等跨境平台搜索商品（用于找热销竞品链接）。返回 platform/title/url/price/monthly_sales/asin 等结构化字段。",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索词，例如 '情趣内衣 性感蕾丝' / 'plus size lingerie'"},
                "platform": {"type": "string", "description": "amazon | temu | ebay | all（默认 all）"},
                "top_k": {"type": "integer", "description": "返回条数（默认 8）"},
            },
        },
        required=["query"],
        func=aliyun_marketplace_search.aliyun_marketplace_search,
        trace_label="跨境平台商品搜索（阿里云）",
    ),
    Tool(
        name="fetch_product_detail",
        description="抓取一个商品 URL 的详情页，解析出 title/price/currency/sizes/colors/monthly_sales/review_count/rating 等结构化字段。",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "商品详情页 URL"},
                "platform": {"type": "string", "description": "amazon | temu | ebay | auto（自动识别）"},
            },
        },
        required=["url"],
        func=fetch_product_detail,
        trace_label="抓取商品详情",
    ),
]

TOOL_MAP: dict[str, Tool] = {t.name: t for t in TOOLS}


def call_tool(name: str, args: dict[str, Any]) -> Any:
    """统一工具调用入口。"""
    tool = TOOL_MAP[name]
    return tool.func(**args)


def tool_schemas_for_llm() -> list[dict[str, Any]]:
    """导出 OpenAI function calling 兼容的工具 Schema。"""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS
    ]
