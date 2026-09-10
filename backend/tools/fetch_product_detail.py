"""商品详情抓取工具 —— 解析商品页提取尺码 / 价格 / 月销 / 评论等结构化字段。

输入：
    url:       商品链接
    platform:  amazon | temu | ebay | auto（自动识别）
    use_cache: 命中已抓取快照时直接返回，避免重复抓取

输出：{
    ok, url, platform, title, price, currency, sizes, colors,
    monthly_sales, monthly_sales_window, review_count, rating,
    fetched_at, fetch_backend, source_html_snippet, note
}

后端：
    mock        —— 从 aliyun_marketplace_search 的本地数据反查（默认；离线可用）
    scraperapi  —— 走 ScraperAPI 代理抓取（需 SCRAPER_API_KEY）
    direct      —— 直连 httpx（仅对小站点或测试有效，Amazon / Temu / eBay 直连基本会被拦截）
    auto        —— 按 (ScraperAPI 可用 → scraperapi) / (直连 → direct) / (兜底 mock) 顺序
"""

from __future__ import annotations

import re
import time
from typing import Any
from urllib.parse import urlparse

from backend.config import settings
from backend.tools.aliyun_marketplace_search import get_product_by_url


# 简易进程内缓存，避免同一 URL 在一次会话里被重复抓取
_CACHE: dict[str, dict[str, Any]] = {}


def _detect_platform(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if "amazon" in host:
        return "amazon"
    if "temu" in host:
        return "temu"
    if "ebay" in host:
        return "ebay"
    return "unknown"


# ---------------------------------------------------------------------------
# HTML 字段解析（针对 Amazon / Temu / eBay 的典型结构做容错解析）
# ---------------------------------------------------------------------------
_PRICE_PATTERNS = [
    # Amazon
    r'"priceAmount"\s*:\s*([\d.]+)',
    r'class="a-price-whole">([\d,.]+)',
    r'priceblock_(?:ourprice|dealprice|saleprice)">\s*\$?([\d,.]+)',
    # Temu / eBay
    r'"price"\s*:\s*\$?([\d.]+)',
    r'class="[^"]*price[^"]*">\s*\$?([\d,.]+)',
]
_SIZES_PATTERNS = [
    # Amazon dropdown / list of size buttons
    r'"variationValues"\s*:\s*\{[^}]*"size_name"\s*:\s*\[([^\]]+)\]',
    r'data-default-value="Size_([A-Z0-9/]+)"',
    r'class="a-list-item"[^>]*>\s*Size\s*[:：]?\s*([A-Z0-9/\-\s,]+?)\s*<',
]
_REVIEW_PATTERNS = [
    # Amazon
    r'"totalReviews"\s*:\s*(\d+)',
    r'id="acrCustomerReviewText"[^>]*>\s*([\d,]+)\s*(?:ratings|reviews|customer rating)',
    r'(\d{1,3}(?:,\d{3})*)\s*(?:ratings|reviews)',
]
_RATING_PATTERNS = [
    r'"ratingValue"\s*:\s*([\d.]+)',
    r'class="a-icon-alt">\s*([\d.]+)\s*out of',
    r'aria-label="([\d.]+)\s*out of\s*5 stars"',
]
_MONTHLY_PATTERNS = [
    # Amazon "bought in past month"
    r'([\d,]+)\s*\+\s*bought in past month',
    r'"boughtInPastMonth"\s*:\s*(\d+)',
    # eBay "sold X"
    r'([\d,]+)\s*sold',
]


def _extract_field(html: str, patterns: list[str], cast=float, default=None):
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                return cast(raw)
            except (ValueError, TypeError):
                continue
    return default


def _extract_sizes(html: str) -> list[str]:
    for pat in _SIZES_PATTERNS:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            raw = m.group(1)
            # 可能是 JSON 数组字符串，也可能是 "S, M, L, XL" 形式
            if raw.startswith('"') and raw.endswith('"'):
                raw = raw.strip('"')
            parts = re.split(r'[\s,，/、]+', raw)
            sizes = [p for p in (s.strip() for s in parts) if p and len(p) <= 12]
            if sizes:
                return sizes[:20]
    return []


def _extract_title(html: str) -> str | None:
    # 通用 title 提取
    m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        return m.group(1).strip()[:200]
    # Amazon product title
    m = re.search(r'id="productTitle"[^>]*>\s*([^<]+?)\s*<', html)
    if m:
        return m.group(1).strip()[:200]
    return None


def _parse_html(html: str, url: str) -> dict[str, Any]:
    """从 HTML 提取结构化字段。"""
    platform = _detect_platform(url)
    return {
        "ok": True,
        "url": url,
        "platform": platform,
        "title": _extract_title(html),
        "price": _extract_field(html, _PRICE_PATTERNS, float),
        "currency": "USD",  # 默认值；可由解析到的页面 locale 进一步判断
        "sizes": _extract_sizes(html),
        "review_count": _extract_field(html, _REVIEW_PATTERNS, int),
        "rating": _extract_field(html, _RATING_PATTERNS, float),
        "monthly_sales": _extract_field(html, _MONTHLY_PATTERNS, int),
        "monthly_sales_window": "近 30 天",
        "raw_source": "html_parsed",
    }


# ---------------------------------------------------------------------------
# 后端实现
# ---------------------------------------------------------------------------
def _fetch_via_scraperapi(url: str) -> dict[str, Any]:
    """走 ScraperAPI 代理抓取（推荐用于 Amazon / Temu / eBay 真实抓取）。

    API：https://api.scraperapi.com/?api_key=KEY&url=URL&render=true
    """
    import httpx

    api_key = settings.scraper_api_key
    proxy = (
        f"https://api.scraperapi.com/?api_key={api_key}"
        f"&url={url}&render=false&country_code=us"
    )
    with httpx.Client(timeout=settings.fetch_timeout) as client:
        resp = client.get(proxy, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text

    parsed = _parse_html(html, url)
    parsed["fetch_backend"] = "scraperapi"
    parsed["fetched_at"] = int(time.time())
    return parsed


def _fetch_direct(url: str) -> dict[str, Any]:
    """直连抓取（受反爬限制，生产环境慎用）。"""
    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9,zh;q=0.8",
    }
    with httpx.Client(
        timeout=settings.fetch_timeout,
        follow_redirects=True,
        headers=headers,
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text

    parsed = _parse_html(html, url)
    parsed["fetch_backend"] = "direct"
    parsed["fetched_at"] = int(time.time())
    return parsed


def _fetch_mock(url: str) -> dict[str, Any]:
    """回退到 mock：从 aliyun_marketplace_search 的本地库反查，附加"抓取时间"。"""
    item = get_product_by_url(url)
    if not item:
        return {
            "ok": False,
            "url": url,
            "platform": _detect_platform(url),
            "error": "未在本地商品库中匹配到该 URL，请确认是否为 Amazon / Temu / eBay 上的标准商品页。",
            "fetch_backend": "mock",
            "fetched_at": int(time.time()),
        }
    return {
        "ok": True,
        "url": url,
        "platform": item["platform"],
        "title": item["title"],
        "price": item["price"],
        "currency": item.get("currency", "USD"),
        "sizes": item.get("sizes", []),
        "colors": item.get("colors", []),
        "review_count": item.get("review_count", 0),
        "rating": item.get("rating"),
        "monthly_sales": item.get("monthly_sales", 0),
        "monthly_sales_window": item.get("monthly_sales_window", "近 30 天"),
        "brand": item.get("brand", ""),
        "seller": item.get("seller", ""),
        "fetch_backend": "mock",
        "fetched_at": int(time.time()),
        "note": "演示数据（配置 PRODUCT_FETCH_BACKEND=scraperapi 可抓取真实页面）",
    }


# ---------------------------------------------------------------------------
# 对外主入口
# ---------------------------------------------------------------------------
def fetch_product_detail(
    url: str,
    platform: str | None = None,
    use_cache: bool = True,
    backend: str | None = None,
) -> dict[str, Any]:
    """抓取商品详情。"""
    url = (url or "").strip()
    if not url:
        return {"ok": False, "error": "url 不能为空"}

    # 缓存命中
    if use_cache and url in _CACHE:
        cached = dict(_CACHE[url])
        cached["from_cache"] = True
        return cached

    chosen = (backend or settings.product_fetch_backend or "mock").lower()
    if platform:
        chosen = "auto"  # 显式传了 platform 仍走 auto 决定后端
    result: dict[str, Any] | None = None

    # auto：按可用顺序尝试
    if chosen == "auto" or chosen == "scraperapi":
        if settings.use_scraper_api:
            try:
                result = _fetch_via_scraperapi(url)
            except Exception as e:  # noqa: BLE001
                result = {"ok": False, "url": url, "error": f"ScraperAPI 失败：{e}"}
        if result is not None and result.get("ok"):
            pass
        elif chosen == "scraperapi":
            # 显式要 scraperapi 但失败 → 报错，不静默回退
            return result or {"ok": False, "url": url, "error": "ScraperAPI 抓取失败"}
        # auto 失败则继续尝试 direct
        chosen = "direct"

    if chosen == "direct" and (result is None or not result.get("ok")):
        try:
            result = _fetch_direct(url)
        except Exception as e:  # noqa: BLE001
            result = {"ok": False, "url": url, "error": f"直连抓取失败：{e}"}

    if result is None or not result.get("ok"):
        # 兜底 mock
        result = _fetch_mock(url)
        if result.get("ok"):
            result["note"] = (
                (result.get("note", "") + "；" if result.get("note") else "")
                + "抓取失败，已回退演示数据。"
            )

    _CACHE[url] = result
    return result


def clear_cache() -> None:
    _CACHE.clear()