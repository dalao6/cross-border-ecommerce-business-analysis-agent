"""意图路由（Intent Router）。

把用户问题划分为四类，决定后续走哪条链路：

    - INTERNAL_DATA        仅需企业数据库（走召回 → NL2SQL → 执行 → 分析）
    - EXTERNAL_INFORMATION 仅需互联网公开信息（走外部搜索）
    - MARKETPLACE_INTEL    需要在跨境平台（Amazon/Temu/eBay）找商品链接与详情
    - HYBRID_ANALYSIS      需企业数据 + 外部信息交叉分析

路由是确定性规则实现（保证离线可跑），同时预留 LLM 路由扩展点。
"""

from enum import Enum

# 企业内部数据信号
INTERNAL_SIGNALS = [
    "销量", "销售额", "GMV", "营收", "收入", "库存", "复购", "回购", "客单价",
    "毛利", "利润", "客户", "店铺", "SKU", "商品", "采购", "缺货", "质检",
    "不合格", "退货", "延期", "交付", "交期", "我们", "本公司", "企业",
]

# 外部公开信息话题信号
EXTERNAL_SIGNALS = [
    "行业", "规则", "政策", "汇率", "竞品", "竞争对手", "贸易", "关税",
    "市场趋势", "行业趋势", "消费者趋势", "市场环境", "有什么趋势", "有什么规则",
    "有哪些规则", "政策变化", "市场怎么样", "市场如何",
]

# 跨境平台/商品搜索信号（用于区分 MARKETPLACE_INTEL 与 EXTERNAL_INFORMATION）
MARKETPLACE_SIGNALS = [
    "亚马逊", "amazon", "amz",
    "temu", "拼多多跨境",
    "ebay", "易贝",
    "平台热销", "热销榜", "热销", "bestseller", "best seller",
    "商品搜索", "商品链接", "商品详情", "找链接", "找商品", "找热销",
    "竞品链接", "竞品详情",
    "跨境平台", "跨境电商平台",
]

# 因果/比较信号（提示需要交叉分析）
CAUSAL_SIGNALS = [
    "为什么", "是不是因为", "会不会影响", "符合", "原因", "影响", "相比", "比较",
    "是否因为", "跟市场", "和市场", "与市场",
]


class Intent(Enum):
    INTERNAL_DATA = "INTERNAL_DATA"
    EXTERNAL_INFORMATION = "EXTERNAL_INFORMATION"
    MARKETPLACE_INTEL = "MARKETPLACE_INTEL"
    HYBRID_ANALYSIS = "HYBRID_ANALYSIS"


class IntentRouter:
    """规则意图路由。"""

    def route(self, query: str) -> dict:
        internal = [k for k in INTERNAL_SIGNALS if k in query]
        external = [k for k in EXTERNAL_SIGNALS if k in query]
        marketplace = [k for k in MARKETPLACE_SIGNALS if k in query]
        causal = [k for k in CAUSAL_SIGNALS if k in query]

        # 优先级 1：纯跨境平台商品搜索/详情查询 → MARKETPLACE_INTEL
        if marketplace and not internal and not (external and not marketplace):
            return {
                "intent": Intent.MARKETPLACE_INTEL.value,
                "reason": "问题指向跨境平台商品搜索/详情，走阿里云 OpenSearch 链路",
                "confidence": 0.9,
                "signals": {
                    "internal": internal,
                    "external": external,
                    "marketplace": marketplace,
                    "causal": causal,
                },
            }

        # 优先级 2：因果 / 比较
        if causal and (internal or external or marketplace):
            intent = Intent.HYBRID_ANALYSIS
            reason = "问题包含因果/比较语义，且涉及企业内部数据与外部因素，需交叉分析"
        elif external and internal:
            intent = Intent.HYBRID_ANALYSIS
            reason = "问题同时涉及外部信息与企业内部数据，需交叉分析"
        elif marketplace and internal:
            intent = Intent.HYBRID_ANALYSIS
            reason = "问题同时涉及跨境平台与企业内部数据，需交叉分析"
        elif external and not internal:
            intent = Intent.EXTERNAL_INFORMATION
            reason = "问题仅涉及外部公开信息，无需查询企业数据库"
        else:
            intent = Intent.INTERNAL_DATA
            reason = "问题仅涉及企业内部经营数据，走数据库分析链路"

        return {
            "intent": intent.value,
            "reason": reason,
            "confidence": 0.9,
            "signals": {
                "internal": internal,
                "external": external,
                "marketplace": marketplace,
                "causal": causal,
            },
        }


router = IntentRouter()
