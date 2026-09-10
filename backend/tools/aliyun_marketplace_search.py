"""商品平台搜索工具 —— 阿里云 OpenSearch 后端 + 离线 mock 后端。

输入：
    query:   搜索词，例如 "情趣内衣 性感蕾丝"
    platform: amazon | temu | ebay | all（默认 all，三平台一起搜）
    top_k:   返回条数

输出：商品链接列表，每条含
    platform, title, url, snippet, asin/sku（若有）, price_range, rating, monthly_sales

真实环境（marketplace_search_backend == "aliyun_opensearch"）：
    需要在阿里云 OpenSearch 控制台创建应用，把 Amazon / Temu / eBay 的商品文档
    （含 url / title / platform / tags 等字段）导入该应用，再由本工具以 OpenSearch v3 API
    调用 search 接口。鉴权采用阿里云 v3 签名（HMAC-SHA1 + Base64）。

离线环境（默认 mock）：
    使用内置的「Amazon / Temu / eBay 情趣内衣热销榜」模拟数据，覆盖跨境卖家调研
    所需的典型字段，保证整条链路可端到端跑通。
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from urllib.parse import quote

from backend.config import settings
from backend.tools.scoring import score_candidates


# ---------------------------------------------------------------------------
# 模拟数据：Amazon / Temu / eBay 情趣内衣热销榜（演示用，结构贴近真实页面）
# ---------------------------------------------------------------------------
MOCK_MARKETPLACE = [
    # ---------- Amazon ----------
    {
        "platform": "amazon", "marketplace": "Amazon US",
        "asin": "B0CSEN1234", "sku": "YL-LB-001",
        "title": "Women's Sexy Lace Lingerie Set - Bra & Panty with Garter Belt, Lingerie Underwear Set, Valentine's Day Gift",
        "brand": "Avidlove", "url": "https://www.amazon.com/dp/B0CSEN1234",
        "snippet": "Stretchy floral lace bralette and panty set with adjustable straps; one-size fits most S-XL.",
        "tags": ["情趣内衣", "性感", "蕾丝", "套装", "套装", "女士", "跨境", "Lingerie Set", "Lace"],
        "price": 19.99, "currency": "USD",
        "rating": 4.6, "review_count": 12830,
        "monthly_sales": 5400, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL"], "colors": ["Black", "Red", "Wine Red", "Purple"],
        "seller": "Avidlove US Official", "is_prime": True,
        "credibility": "高",
    },
    {
        "platform": "amazon", "marketplace": "Amazon US",
        "asin": "B0DKSN9821", "sku": "YL-CN-002",
        "title": "Women Teddy Lingerie Sheer Lace Babydoll Nightgown - V Neck Sleepwear",
        "brand": "Hankitrade", "url": "https://www.amazon.com/dp/B0DKSN9821",
        "snippet": "Sheer mesh babydoll with adjustable straps; romantic gift for her.",
        "tags": ["情趣内衣", "睡裙", "透视", "Babydoll", "Lingerie", "Hanky"],
        "price": 16.99, "currency": "USD",
        "rating": 4.4, "review_count": 7241,
        "monthly_sales": 3200, "monthly_sales_window": "近 30 天",
        "sizes": ["S/M", "L/XL", "XXL"], "colors": ["Black", "Burgundy", "Navy"],
        "seller": "Hankitrade Official", "is_prime": True,
        "credibility": "高",
    },
    {
        "platform": "amazon", "marketplace": "Amazon US",
        "asin": "B0CXRG2247", "sku": "YL-CN-003",
        "title": "Women's Plus Size Lingerie - Sexy Lace Bra Panty Set for Curvy Women 1X-4X",
        "brand": "Ekouaer", "url": "https://www.amazon.com/dp/B0CXRG2247",
        "snippet": "Inclusive sizing 1X-4X; floral eyelash lace; wire-free support.",
        "tags": ["情趣内衣", "大码", "Plus Size", "蕾丝", "女士", "Lingerie", "大码"],
        "price": 22.99, "currency": "USD",
        "rating": 4.5, "review_count": 4316,
        "monthly_sales": 2100, "monthly_sales_window": "近 30 天",
        "sizes": ["1X", "2X", "3X", "4X"], "colors": ["Black", "Red", "Rose Red", "White"],
        "seller": "Ekouaer Direct", "is_prime": True,
        "credibility": "高",
    },
    {
        "platform": "amazon", "marketplace": "Amazon US",
        "asin": "B0BSTN5523", "sku": "YL-CN-004",
        "title": "Women Costume Lingerie - Sexy Maid Outfit Lingerie Dress with Apron",
        "brand": "Avidlove", "url": "https://www.amazon.com/dp/B0BSTN5523",
        "snippet": "Role-play maid costume with apron and headband; Halloween & party.",
        "tags": ["情趣内衣", "角色扮演", "女仆", "COS", "Maid", "Costume"],
        "price": 18.99, "currency": "USD",
        "rating": 4.3, "review_count": 5882,
        "monthly_sales": 1800, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL"], "colors": ["Black", "Red"],
        "seller": "Avidlove US Official", "is_prime": True,
        "credibility": "高",
    },
    {
        "platform": "amazon", "marketplace": "Amazon UK",
        "asin": "B0FUKG7711", "sku": "YL-CN-005",
        "title": "Lace Bodystocking Lingerie for Women - Sheer Floral Pattern Full Body",
        "brand": "Hanky Panky", "url": "https://www.amazon.co.uk/dp/B0FUKG7711",
        "snippet": "Full-length sheer bodystocking with floral lace; one size.",
        "tags": ["情趣内衣", "Bodystocking", "全身", "透视", "Lingerie", "蕾丝"],
        "price": 14.99, "currency": "GBP",
        "rating": 4.2, "review_count": 1108,
        "monthly_sales": 760, "monthly_sales_window": "近 30 天",
        "sizes": ["One Size"], "colors": ["Black", "Red", "White"],
        "seller": "Hanky London", "is_prime": True,
        "credibility": "高",
    },
    # ---------- Temu ----------
    {
        "platform": "temu", "marketplace": "Temu Global",
        "sku": "TM-98765", "title": "Sexy Lace Bra Set Push Up Underwire Lingerie 2-Piece",
        "brand": "Yiyi Official Flagship", "url": "https://www.temu.com/goods.html?goods_id=98765",
        "snippet": "Push-up underwire with adjustable straps; 6 colors available.",
        "tags": ["情趣内衣", "性感", "蕾丝", "套装", "Push Up", "Temu"],
        "price": 8.99, "currency": "USD",
        "rating": 4.5, "review_count": 23300,
        "monthly_sales": 18000, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL", "XXL"], "colors": ["Black", "Red", "Pink", "Blue", "White", "Nude"],
        "seller": "Yiyi Official Flagship", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "temu", "marketplace": "Temu Global",
        "sku": "TM-98801", "title": "Women's Sleepwear Satin Nightgown Long Lace Trim",
        "brand": "Yiyi Silk Series", "url": "https://www.temu.com/goods.html?goods_id=98801",
        "snippet": "Satin nightgown with lace trim; floor length; 4 colors.",
        "tags": ["家居服", "睡裙", "缎面", "家居服", "Sleepwear", "Temu"],
        "price": 12.50, "currency": "USD",
        "rating": 4.4, "review_count": 8800,
        "monthly_sales": 6300, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL", "XXL"], "colors": ["Black", "Red", "Champagne", "Navy"],
        "seller": "Yiyi Silk Series", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "temu", "marketplace": "Temu Global",
        "sku": "TM-98822", "title": "Plus Size Lingerie 4XL Lace Underwear Set Stretchy Bra Panty",
        "brand": "Yiyi Plus", "url": "https://www.temu.com/goods.html?goods_id=98822",
        "snippet": "Stretchy 1X-5X lingerie set; wire-free; soft floral lace.",
        "tags": ["情趣内衣", "大码", "Plus", "蕾丝", "Temu", "大码"],
        "price": 10.99, "currency": "USD",
        "rating": 4.3, "review_count": 5612,
        "monthly_sales": 4200, "monthly_sales_window": "近 30 天",
        "sizes": ["1X", "2X", "3X", "4X", "5X"], "colors": ["Black", "Red", "Rose", "White"],
        "seller": "Yiyi Plus Store", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "temu", "marketplace": "Temu Global",
        "sku": "TM-98900", "title": "Sexy Cosplay Costume Maid Outfit Lingerie Set with Apron",
        "brand": "Yiyi Cosplay", "url": "https://www.temu.com/goods.html?goods_id=98900",
        "snippet": "Maid costume with apron and headband; 3 sizes.",
        "tags": ["COS服饰", "角色扮演", "COS", "Maid", "Temu"],
        "price": 9.99, "currency": "USD",
        "rating": 4.2, "review_count": 3400,
        "monthly_sales": 2100, "monthly_sales_window": "近 30 天",
        "sizes": ["S/M", "L/XL", "XXL"], "colors": ["Black", "Pink", "Purple"],
        "seller": "Yiyi Cosplay", "is_prime": False,
        "credibility": "中",
    },
    # ---------- eBay ----------
    {
        "platform": "ebay", "marketplace": "eBay US",
        "sku": "EB-556677", "title": "NEW Women Sexy Lace Teddy Lingerie Bodysuit Sheer Mesh Babydoll",
        "brand": "Unbranded", "url": "https://www.ebay.com/itm/334556677",
        "snippet": "Sheer mesh bodysuit teddy; one size; free shipping.",
        "tags": ["情趣内衣", "Bodysuit", "透视", "Teddy", "Lingerie", "eBay"],
        "price": 11.99, "currency": "USD",
        "rating": 4.4, "review_count": 1840,
        "monthly_sales": 1200, "monthly_sales_window": "近 30 天",
        "sizes": ["One Size", "Plus Size"], "colors": ["Black", "Red", "White"],
        "seller": "lingerie_outlet_us", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "ebay", "marketplace": "eBay US",
        "sku": "EB-556881", "title": "Women Lingerie Set Lace Bra Garter Belt Panty 4-Piece Lingerie",
        "brand": "Unbranded", "url": "https://www.ebay.com/itm/334556881",
        "snippet": "4-piece garter belt set with stockings; S-XL; 5 colors.",
        "tags": ["情趣内衣", "吊带", "Garter", "套装", "Lingerie", "eBay"],
        "price": 17.99, "currency": "USD",
        "rating": 4.5, "review_count": 2210,
        "monthly_sales": 900, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL"], "colors": ["Black", "Red", "Purple", "Burgundy", "Navy"],
        "seller": "best_lingerie_shop", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "ebay", "marketplace": "eBay UK",
        "sku": "EB-557120", "title": "Plus Size Lingerie 4XL Lingerie Set Floral Lace Bra Panty",
        "brand": "Unbranded", "url": "https://www.ebay.co.uk/itm/334557120",
        "snippet": "Plus size floral lace set 1X-4X; wire-free; 4 colors.",
        "tags": ["情趣内衣", "大码", "Plus", "蕾丝", "Lingerie", "eBay", "大码"],
        "price": 15.99, "currency": "GBP",
        "rating": 4.3, "review_count": 980,
        "monthly_sales": 540, "monthly_sales_window": "近 30 天",
        "sizes": ["1X", "2X", "3X", "4X"], "colors": ["Black", "Red", "Navy", "Burgundy"],
        "seller": "uk_lingerie_warehouse", "is_prime": False,
        "credibility": "中",
    },
    {
        "platform": "ebay", "marketplace": "eBay US",
        "sku": "EB-558800", "title": "Women's Sleepwear Silk Satin Nightgown Long Lace Trim Homewear",
        "brand": "Yiyi Silk eBay Store", "url": "https://www.ebay.com/itm/334558800",
        "snippet": "Long satin nightgown with lace trim; gift box packaging.",
        "tags": ["家居服", "睡裙", "缎面", "Sleepwear", "eBay"],
        "price": 19.99, "currency": "USD",
        "rating": 4.6, "review_count": 1450,
        "monthly_sales": 720, "monthly_sales_window": "近 30 天",
        "sizes": ["S", "M", "L", "XL", "XXL"], "colors": ["Black", "Red", "Champagne", "Navy", "Rose"],
        "seller": "yiyi_silk_ebay", "is_prime": False,
        "credibility": "中",
    },
]


# ---------------------------------------------------------------------------
# 平台识别 & 过滤
# ---------------------------------------------------------------------------
PLATFORM_KEYWORDS = {
    "amazon": ["amazon", "亚马逊", "amz"],
    "temu": ["temu", "拼多多跨境", "海外拼多多"],
    "ebay": ["ebay", "易贝", "e-bay"],
}


def detect_platforms(query: str) -> list[str]:
    """根据用户问题识别要搜索的平台列表。"""
    q = query.lower()
    hit = [p for p, kws in PLATFORM_KEYWORDS.items() if any(k in q for k in kws)]
    if not hit:
        return ["amazon", "temu", "ebay"]
    return hit


def filter_by_platform(items: list[dict], platforms: list[str]) -> list[dict]:
    return [it for it in items if it["platform"] in platforms]


# ---------------------------------------------------------------------------
# Mock 后端
# ---------------------------------------------------------------------------
def _mock_search(query: str, platforms: list[str], top_k: int) -> dict[str, Any]:
    """使用内置模拟数据检索。"""
    field_weights = {"title": 1.0, "tags": 1.5, "snippet": 0.6, "brand": 0.4}
    candidates = filter_by_platform(MOCK_MARKETPLACE, platforms)
    scored = score_candidates(query, candidates, field_weights)
    hits = [s for s in scored if s["score"] > 0][:top_k]

    if not hits:
        # 平台过滤后无命中，回退返回该平台销量 top 3
        candidates_sorted = sorted(candidates, key=lambda x: -x.get("monthly_sales", 0))
        hits = candidates_sorted[:top_k]
        note = "未按关键词精确匹配，已回退为该平台销量 Top 结果。"
    else:
        note = ""

    return {
        "ok": True,
        "query": query,
        "platforms": platforms,
        "results": hits,
        "note": note,
        "backend": "mock",
    }


# ---------------------------------------------------------------------------
# 阿里云 OpenSearch 真实后端（v3 签名）
# ---------------------------------------------------------------------------
def _aliyun_opensearch_search(query: str, platforms: list[str], top_k: int) -> dict[str, Any]:
    """调用阿里云 OpenSearch 应用 v3 search 接口。

    文档：https://help.aliyun.com/zh/open-search/developer-reference/sign
    """
    import httpx

    try:
        endpoint = settings.aliyun_opensearch_endpoint.rstrip("/")
        path = f"/v3/openapi/apps/{settings.aliyun_opensearch_app}/search"
        method = "POST"

        body = {
            "query": {
                "query": query,
                "config": {
                    "start": 0,
                    "hit": top_k,
                    "format": "json",
                    "rerank_size": top_k,
                },
            },
            "filter": " OR ".join([f'platform="{p}"' for p in platforms]) if platforms else "",
        }
        body_str = json.dumps(body, separators=(",", ":"))

        timestamp = str(int(time.time()))
        nonce = uuid.uuid4().hex
        # 阿里云 v3 签名：HMAC-SHA1(secret, METHOD + "\n" + path + "\n" + body + "\n" + timestamp)
        sign_str = f"{method}\n{path}\n{body_str}\n{timestamp}"
        digest = hmac.new(
            settings.aliyun_access_key_secret.encode("utf-8"),
            sign_str.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(digest).decode("utf-8")

        token = base64.b64encode(
            f"{settings.aliyun_access_key_id}:{signature}".encode("utf-8")
        ).decode("utf-8")

        headers = {
            "Authorization": f"OPENSEARCH {token}",
            "Content-Type": "application/json;charset=utf-8",
        }

        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{endpoint}{path}", content=body_str, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        items = []
        for hit in data.get("result", {}).get("items", []):
            # OpenSearch 返回字段是动态的，这里做轻量归一化
            fields = hit.get("fields", {})
            items.append({
                "platform": fields.get("platform", "unknown"),
                "marketplace": fields.get("marketplace", ""),
                "title": fields.get("title", ""),
                "url": fields.get("url", ""),
                "snippet": fields.get("snippet", ""),
                "asin": fields.get("asin", ""),
                "sku": fields.get("sku", ""),
                "brand": fields.get("brand", ""),
                "price": float(fields["price"]) if "price" in fields and fields["price"] else None,
                "currency": fields.get("currency", "USD"),
                "rating": float(fields["rating"]) if "rating" in fields and fields["rating"] else None,
                "review_count": int(fields.get("review_count", 0)),
                "monthly_sales": int(fields.get("monthly_sales", 0)),
                "monthly_sales_window": "近 30 天",
                "sizes": fields.get("sizes", "").split(",") if isinstance(fields.get("sizes"), str) and fields.get("sizes") else [],
                "colors": fields.get("colors", "").split(",") if isinstance(fields.get("colors"), str) and fields.get("colors") else [],
                "credibility": "中",
            })

        return {
            "ok": True,
            "query": query,
            "platforms": platforms,
            "results": items[:top_k],
            "note": "" if items else "未在 OpenSearch 应用中检索到结果，请检查应用索引与查询词。",
            "backend": "aliyun_opensearch",
        }
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "query": query,
            "platforms": platforms,
            "results": [],
            "note": f"阿里云 OpenSearch 调用失败：{e}（已回退到本地模拟数据）",
            "backend": "aliyun_opensearch",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def aliyun_marketplace_search(
    query: str,
    platform: str = "all",
    top_k: int = 8,
) -> dict[str, Any]:
    """商品平台搜索主入口。

    Args:
        query: 搜索词，例如 "情趣内衣 性感蕾丝" / "plus size lingerie"
        platform: amazon | temu | ebay | all
        top_k: 返回条数

    Returns:
        dict: {
            "ok": True,
            "query": ...,
            "platforms": [...],
            "results": [{platform, title, url, asin, price, rating, monthly_sales, ...}],
            "backend": "mock" | "aliyun_opensearch",
            "note": "...",
        }
    """
    query = (query or "").strip()
    platforms = (
        detect_platforms(query)
        if platform == "all" or not platform
        else [p.strip().lower() for p in platform.split(",") if p.strip()]
    )

    if settings.use_aliyun_opensearch and settings.marketplace_search_backend == "aliyun_opensearch":
        real_result = _aliyun_opensearch_search(query, platforms, top_k)
        if real_result["ok"]:
            return real_result
        # 真实后端失败 → 回退到 mock，避免阻断 Agent 链路
        mock = _mock_search(query, platforms, top_k)
        mock["note"] = real_result.get("note", "") + ("；" if mock.get("note") else "") + "已回退到本地模拟数据。"
        return mock

    return _mock_search(query, platforms, top_k)


def get_product_by_url(url: str) -> dict[str, Any] | None:
    """根据 url 查找 mock 库中对应的商品（用于 fetch 工具回退到本地数据时使用）。"""
    for it in MOCK_MARKETPLACE:
        if it["url"] == url:
            return it
    return None
