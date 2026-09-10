"""External Web Search 工具 —— 获取互联网公开信息。

输入：query
输出：结构化搜索结果（title / url / source / published_time / summary / content / relevance / credibility）。

本模块内置一个「模拟公开信息知识库」（mock 后端），用于离线演示，覆盖海外市场趋势、
TikTok Shop 规则、贸易政策等场景；同时预留 real 后端扩展点，可在有真实搜索 API 时接入。
所有外部信息在最终答案中都被严格标记为「外部公开信息」，绝不伪装成企业内部数据。
"""

from backend.config import settings
from backend.tools.scoring import score_candidates

# ---------------------------------------------------------------------------
# 模拟公开信息知识库（演示用，来源为示意性公开信源）
# ---------------------------------------------------------------------------
MOCK_KNOWLEDGE_BASE = [
    {
        "title": "2025 年美国内衣电商市场保持温和增长",
        "url": "https://www.statista.com/outlook/dmo/ecommerce/fashion/lingerie-nightwear/united-states",
        "source": "Statista 行业报告",
        "published_time": "2025-10-15",
        "credibility": "高",
        "summary": "美国内衣与睡衣电商市场 2025 年整体保持约 5% 的同比增长，线上渗透率继续提升。",
        "content": "据 Statista 数据，2025 年美国 lingerie & sleepwear 线上零售额同比增长约 5%，"
                  "其中 DTC 独立站与短视频电商渠道增长最快。消费者对舒适、无钢圈、多场景穿搭的需求上升。",
        "keywords": ["美国", "内衣", "市场", "趋势", "增长", "美国市场", "美国内衣"],
    },
    {
        "title": "TikTok Shop 美国站 2025 年佣金与物流政策调整公告",
        "url": "https://seller.tiktok.com/us/policy-update-2025",
        "source": "TikTok Shop 官方公告",
        "published_time": "2025-08-20",
        "credibility": "高",
        "summary": "TikTok Shop 美国站自 2025 年 9 月起调整部分类目佣金率与物流履约要求，服饰类佣金上调约 2 个百分点。",
        "content": "TikTok Shop 官方公告显示，2025 年 9 月 1 日起美国站服饰类目成交佣金上调约 2%"
                  "，同时加强物流履约时效考核，未达标店铺将面临流量权重下调。",
        "keywords": ["TikTok", "TikTok Shop", "规则", "政策", "佣金", "美国", "平台规则"],
    },
    {
        "title": "TikTok Shop 2025 年强化内容合规与达人分成机制",
        "url": "https://seller.tiktok.com/us/content-policy-2025",
        "source": "TikTok Shop 官方公告",
        "published_time": "2025-07-10",
        "credibility": "高",
        "summary": "TikTok Shop 2025 年加强对低质短视频与违规内容的治理，并调整达人带货分成比例，影响店铺流量获取成本。",
        "content": "2025 年起 TikTok Shop 对低质量、重复搬运内容加大治理力度，达人合作佣金分成机制调整，"
                  "部分中小店铺获客成本上升，流量向优质内容和头部达人倾斜。",
        "keywords": ["TikTok", "TikTok Shop", "规则", "达人", "内容", "流量", "分成"],
    },
    {
        "title": "中东 modest fashion 内衣市场高速增长",
        "url": "https://www.euromonitor.com/middle-east-modest-fashion",
        "source": "Euromonitor 行业报告",
        "published_time": "2025-11-02",
        "credibility": "高",
        "summary": "中东 modest fashion 及贴身衣物市场 2025 年增速超过 12%，跨境电商渗透率快速提升。",
        "content": "Euromonitor 报告显示，中东地区 modest fashion 与贴身衣物市场 2025 年同比增长超 12%，"
                  "年轻消费者对跨境电商接受度高，社交电商是主要增长引擎。",
        "keywords": ["中东", "市场", "趋势", "增长", "中东市场", "时尚"],
    },
    {
        "title": "美国消费者 2025 年服饰消费信心回落",
        "url": "https://www.census.gov/retail/apparel-2025",
        "source": "美国商务部零售抽样调查",
        "published_time": "2025-09-30",
        "credibility": "中",
        "summary": "2025 年三季度美国服饰零售增速放缓，消费者对可选消费支出趋于谨慎。",
        "content": "美国商务部零售数据显示，2025 年三季度服饰及配饰零售额同比增速放缓，"
                  "高通胀与借贷成本上升抑制了部分可选消费。",
        "keywords": ["美国", "消费", "零售", "服饰", "趋势", "市场"],
    },
    {
        "title": "跨境电商出口美国关税政策与小额豁免动态",
        "url": "https://www.cbp.gov/trade/de-minimis-2025",
        "source": "美国海关与边境保护局（CBP）",
        "published_time": "2025-06-15",
        "credibility": "高",
        "summary": "美国 2025 年就 de minimis 小额免税政策展开调整讨论，跨境电商直邮成本面临不确定性。",
        "content": "CBP 公开信息显示，2025 年美国对 800 美元以下 de minimis 包裹政策进行审查，"
                  "若收紧将提高跨境直邮小包的综合成本。",
        "keywords": ["关税", "海关", "政策", "贸易", "跨境电商", "美国", "出口"],
    },
    {
        "title": "2025 年美元兑人民币汇率中枢",
        "url": "https://www.safe.gov.cn/forex-2025",
        "source": "国家外汇管理局（示意）",
        "published_time": "2025-12-20",
        "credibility": "高",
        "summary": "2025 年美元兑人民币汇率整体在 7.0~7.3 区间波动，出口结汇收益相对稳定。",
        "content": "2025 年人民币兑美元汇率维持双向波动，全年中枢约 7.15，跨境出口企业结汇收益较为稳定。",
        "keywords": ["汇率", "人民币", "美元", "实时"],
    },
    {
        "title": "全球性感内衣/情趣内衣线上市场集中度提升",
        "url": "https://www.grandviewresearch.com/lingerie-2025",
        "source": "Grand View Research",
        "published_time": "2025-05-18",
        "credibility": "中",
        "summary": "全球线上情趣内衣市场集中度提升，头部品牌与有内容能力的卖家份额扩大，长尾卖家承压。",
        "content": "Grand View Research 指出，2025 年全球线上情趣内衣市场增长集中在具备内容营销与达人资源的卖家，"
                  "纯铺货型长尾卖家转化率下降。",
        "keywords": ["情趣内衣", "竞品", "竞争", "市场", "趋势", "卖家"],
    },
]


def external_web_search(query: str, top_k: int = 5) -> dict:
    """搜索互联网公开信息，返回结构化结果列表。"""
    if settings.external_search_backend != "mock":
        return _real_search(query, top_k)

    scored = score_candidates(query, MOCK_KNOWLEDGE_BASE, {"title": 0.8, "summary": 1.0, "content": 0.5, "keywords": 1.6})
    # 只保留有命中的结果
    hits = [s for s in scored if s["score"] > 0]
    if not hits:
        return {
            "ok": True,
            "query": query,
            "results": [],
            "note": "未检索到高度相关的公开信息，请调整检索词。",
        }

    results = []
    for s in hits[:top_k]:
        results.append({
            "title": s["title"],
            "url": s["url"],
            "source": s["source"],
            "published_time": s["published_time"],
            "credibility": s["credibility"],
            "relevance": s["score"],
            "summary": s["summary"],
            "content": s["content"],
        })
    return {"ok": True, "query": query, "results": results, "note": ""}


def _real_search(query: str, top_k: int = 5) -> dict:
    """真实搜索后端：调用 DashScope Qwen 联网搜索 API 获取互联网公开信息。

    使用 DashScope 的 web_search 插件，让模型在生成回答前先联网检索，
    搜索结果会附带在响应的 search_info 字段中，确保信息来自真实互联网而非幻觉。
    """
    import json

    import httpx

    try:
        payload = {
            "model": settings.llm_model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个互联网信息检索助手。请根据搜索结果，整理并返回结构化的互联网公开信息。"
                        '请严格以JSON格式返回，格式为：{"results": [{"title": "标题", "url": "链接", '
                        '"source": "来源", "published_time": "发布时间", "credibility": "高/中/低", '
                        '"summary": "摘要", "content": "详细内容"}]}'
                        "不要添加任何多余文字，只返回JSON。"
                    ),
                },
                {"role": "user", "content": f"搜索关于以下主题的最新互联网公开信息：{query}"},
            ],
            "temperature": 0,
            "result_format": "message",
            "search_info": {"enable_search": True, "search_strategy": "auto"},
        }
        headers = {
            "Authorization": f"Bearer {settings.llm_api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{settings.llm_base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()

        message = data["choices"][0]["message"]
        content = message.get("content", "")

        search_results = []
        search_info = data.get("search_info", [])
        for item in search_info:
            search_results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("site_name", "互联网公开信息"),
                "published_time": item.get("date", ""),
                "credibility": "中",
                "summary": item.get("snippet", ""),
                "content": item.get("snippet", ""),
                "relevance": 1.0,
            })

        if search_results:
            results = search_results[:top_k]
            return {"ok": True, "query": query, "results": results, "note": ""}

        json_str = content.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        parsed = json.loads(json_str)
        results = parsed.get("results", [])[:top_k]

        for r in results:
            r.setdefault("url", "")
            r.setdefault("source", "互联网公开信息")
            r.setdefault("published_time", "")
            r.setdefault("credibility", "中")
            r.setdefault("summary", "")
            r.setdefault("content", "")
            r["relevance"] = 1.0

        return {"ok": True, "query": query, "results": results, "note": ""}
    except Exception as e:
        return {
            "ok": False,
            "query": query,
            "results": [],
            "note": f"真实搜索失败，请检查 API 配置：{e}",
        }