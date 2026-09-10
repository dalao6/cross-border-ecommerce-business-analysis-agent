"""NL2SQL 引擎。

基于「Table Recall + Schema Recall + Metric Recall」的召回结果，把自然语言问题
转成结构化 SQL。采用确定性规则引擎实现，保证离线可跑、结果可复现；同时预留
LLM 生成扩展点（当配置了 LLM 时优先走 LLM 生成，失败则回退规则引擎）。

支持的分析意图：时间趋势 / 排名 TOP N / 总量 / 同比 / 缺货预测 / 复购率 /
质检不合格率 / 生产延期 / 下降对比。
"""

import re
from datetime import date, timedelta

from backend.config import settings

# 中文数字 → 阿拉伯数字
CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
          "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}

TODAY = date.fromisoformat(settings.today)

# 品类 → 数据库取值
CATEGORY_MAP = {
    "性感内衣": "性感内衣", "情趣内衣": "情趣内衣", "COS": "COS服饰",
    "COS服饰": "COS服饰", "家居服": "家居服", "睡裙": "睡裙",
}

# 平台 → 数据库取值
PLATFORM_MAP = {
    "TikTok Shop": "TikTok Shop", "TikTok": "TikTok Shop", "tiktok": "TikTok Shop",
    "亚马逊": "Amazon", "Amazon": "Amazon", "amazon": "Amazon",
    "独立站": "独立站", "Shein": "Shein", "shein": "Shein",
}

COUNTRY_MAP = {"美国": "美国", "英国": "英国", "中东": "中东"}


# ---------------------------------------------------------------------------
# 解析辅助
# ---------------------------------------------------------------------------
def _parse_time(query: str) -> dict:
    """解析时间范围，返回 {start, end, granularity, label}。默认 2025 全年。"""
    # 具体月份：2025年8月 / 8月 / 8月份
    m = re.search(r"(20\d{2})年\s*(\d{1,2}|[一二三四五六七八九十]+)月", query)
    if m:
        year = int(m.group(1))
        month = _to_int(m.group(2))
        start = date(year, month, 1)
        end = date(year, month, 28)
        end = _month_end(start)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "granularity": "month", "label": f"{year}年{month}月"}
    m = re.search(r"(?<!年)(\d{1,2}|[一二三四五六七八九十]+)月(?:份|销量|销售额)?", query)
    if m:
        month = _to_int(m.group(1))
        year = TODAY.year
        start = date(year, month, 1)
        end = _month_end(start)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "granularity": "month", "label": f"{year}年{month}月"}

    # 最近 N 天
    m = re.search(r"(?:最近|近)\s*(\d{1,3})\s*天", query)
    if m:
        n = int(m.group(1))
        end = TODAY
        start = TODAY - timedelta(days=n - 1)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "granularity": "day", "label": f"最近{n}天"}

    # 最近/近 N 个月
    m = re.search(r"(?:最近|近)\s*(\d{1,2}|[一二三四五六七八九十]+)\s*个?月", query)
    if m:
        n = _to_int(m.group(1))
        end = TODAY
        start = (TODAY - timedelta(days=n * 30)).replace(day=1)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "granularity": "month", "label": f"最近{n}个月"}

    # 上个月 / 上月
    if "上月" in query or "上个月" in query:
        ym = TODAY.replace(day=1) - timedelta(days=1)
        start = ym.replace(day=1)
        end = _month_end(start)
        return {"start": start.isoformat(), "end": end.isoformat(),
                "granularity": "month", "label": f"{ym.year}年{ym.month}月"}

    # 具体年份
    m = re.search(r"(20\d{2})年", query)
    if m:
        year = int(m.group(1))
        return {"start": date(year, 1, 1).isoformat(), "end": date(year, 12, 31).isoformat(),
                "granularity": "month", "label": f"{year}年"}
    if "今年" in query:
        return {"start": date(TODAY.year, 1, 1).isoformat(), "end": TODAY.isoformat(),
                "granularity": "month", "label": f"{TODAY.year}年"}
    if "近一年" in query or "近1年" in query:
        return {"start": (TODAY - timedelta(days=365)).isoformat(), "end": TODAY.isoformat(),
                "granularity": "month", "label": "近一年"}

    # 默认 2025 全年
    return {"start": date(2025, 1, 1).isoformat(), "end": date(2025, 12, 31).isoformat(),
            "granularity": "month", "label": "2025年"}


def _month_end(d: date) -> date:
    nxt = d.replace(day=28) + timedelta(days=4)
    return nxt - timedelta(days=nxt.day)


def _to_int(s: str) -> int:
    s = s.strip()
    if s.isdigit():
        return int(s)
    return CN_NUM.get(s, 1)


def _extract_filters(query: str) -> dict:
    """提取维度过滤条件。"""
    filters = {}
    for cn, val in COUNTRY_MAP.items():
        if cn in query:
            filters["country"] = val
            break
    for kw, val in PLATFORM_MAP.items():
        if kw in query:
            filters["platform"] = val
            break
    for cn, val in CATEGORY_MAP.items():
        if cn in query:
            filters["category"] = val
            break
    if "B端" in query or "B端客户" in query:
        filters["customer_type"] = "B端"
    elif "C端" in query or "C端消费者" in query:
        filters["customer_type"] = "C端"
    return filters


def _detect_metric(query: str) -> str:
    """识别核心业务指标。"""
    if any(k in query for k in ["复购率", "回购率", "回头客"]):
        return "复购率"
    if any(k in query for k in ["质检不合格率", "不合格率", "次品率", "不良率", "退货率"]):
        return "质检不合格率"
    if any(k in query for k in ["延期", "交付", "交期"]):
        return "延期"
    if any(k in query for k in ["库存", "缺货", "缺货预测"]):
        return "库存"
    if any(k in query for k in ["毛利率", "毛利"]):
        return "毛利率"
    if any(k in query for k in ["利润", "毛利额"]):
        return "利润"
    if any(k in query for k in ["客单价"]):
        return "客单价"
    if any(k in query for k in ["销售额", "GMV", "成交额", "营收", "收入", "金额"]):
        return "销售额"
    return "销量"


def _detect_dimension(query: str) -> str:
    """识别分组维度。"""
    if any(k in query for k in ["各月", "每月", "按月", "每个月", "逐月", "趋势"]):
        return "month"
    if any(k in query for k in ["平台", "渠道"]):
        return "platform"
    if any(k in query for k in ["店铺", "哪家店", "哪个店"]):
        return "store"
    if any(k in query for k in ["品类", "类目", "分类"]):
        return "category"
    if any(k in query for k in ["客户", "采购商", "买家"]):
        return "customer"
    if any(k in query for k in ["SKU", "商品", "产品", "款式"]):
        return "product"
    if any(k in query for k in ["国家", "地区", "市场"]):
        return "country"
    return "month"


def _detect_ranking(query: str) -> dict | None:
    """识别排名诉求。"""
    m = re.search(r"(?:前|TOP|top)\s*(\d{1,2})", query)
    n = int(m.group(1)) if m else None
    desc = any(k in query for k in ["最高", "最多", "最大", "最好", "TOP", "top", "前"])
    asc = any(k in query for k in ["最低", "最少", "最小", "最慢", "下降", "下滑", "滞销"])
    if desc or asc or n:
        return {"n": n or 10, "order": "DESC" if desc or (n and not asc) else "ASC"}
    return None


# ---------------------------------------------------------------------------
# SQL 片段
# ---------------------------------------------------------------------------
def _metric_expr(metric: str) -> str:
    """返回 SELECT 中该指标的聚合表达式（基于 sales_order 别名 so）。"""
    if metric == "销售额":
        return "SUM(so.amount)"
    if metric == "利润":
        return "SUM(so.amount) - SUM(p.cost * so.quantity)"
    if metric == "毛利率":
        return "ROUND(100.0 * (SUM(so.amount) - SUM(p.cost * so.quantity)) / SUM(so.amount), 2)"
    if metric == "客单价":
        return "ROUND(SUM(so.amount) / COUNT(DISTINCT so.order_id), 2)"
    return "SUM(so.quantity)"  # 销量


def _needs_product_join(metric: str) -> bool:
    return metric in ("利润", "毛利率")


def _where(filters: dict, alias: str = "so") -> str:
    parts = []
    if filters.get("country"):
        parts.append(f"{alias}.country = '{filters['country']}'")
    if filters.get("platform"):
        parts.append(f"{alias}.platform = '{filters['platform']}'")
    if filters.get("category"):
        parts.append(f"p.category = '{filters['category']}'")
    return " AND ".join(parts)


def _trend_sql(metric: str, time: dict, filters: dict) -> str:
    expr = _metric_expr(metric)
    join = "JOIN product p ON p.product_id = so.product_id" if _needs_product_join(metric) else ""
    where = []
    where.append(f"so.order_date >= '{time['start']}' AND so.order_date <= '{time['end']}'")
    w = _where(filters)
    if w:
        where.append(w)
    where_sql = "WHERE " + " AND ".join(where)
    return (
        f"SELECT substr(so.order_date, 1, 7) AS month, {expr} AS value "
        f"FROM sales_order so {join} {where_sql} "
        f"GROUP BY month ORDER BY month"
    )


def _rank_sql(metric: str, dimension: str, time: dict, filters: dict, ranking: dict) -> str:
    expr = _metric_expr(metric)
    join = "JOIN product p ON p.product_id = so.product_id" if _needs_product_join(metric) else ""
    dim_map = {
        "platform": ("so.platform", "platform"),
        "country": ("so.country", "country"),
        "store": ("s.store_name", "store_name"),
        "product": ("p.product_name", "product_name"),
        "category": ("p.category", "category"),
        "customer": ("c.customer_name", "customer_name"),
    }
    dim_col, dim_alias = dim_map.get(dimension, ("so.platform", "platform"))
    joins = join
    if dimension == "store":
        joins += " JOIN store s ON s.store_id = so.store_id"
    if dimension == "product":
        joins += "" if _needs_product_join(metric) else " JOIN product p ON p.product_id = so.product_id"
    if dimension == "customer":
        joins += " JOIN customer c ON c.customer_id = so.customer_id"
    if dimension == "category":
        joins += "" if _needs_product_join(metric) else " JOIN product p ON p.product_id = so.product_id"

    where = [f"so.order_date >= '{time['start']}' AND so.order_date <= '{time['end']}'"]
    w = _where(filters)
    if w:
        where.append(w)
    where_sql = "WHERE " + " AND ".join(where)

    order = ranking["order"]
    n = ranking["n"]
    return (
        f"SELECT {dim_col} AS {dim_alias}, {expr} AS value "
        f"FROM sales_order so {joins} {where_sql} "
        f"GROUP BY {dim_col} ORDER BY value {order} LIMIT {n}"
    )


def _total_sql(metric: str, time: dict, filters: dict) -> str:
    expr = _metric_expr(metric)
    join = "JOIN product p ON p.product_id = so.product_id" if _needs_product_join(metric) else ""
    where = [f"so.order_date >= '{time['start']}' AND so.order_date <= '{time['end']}'"]
    w = _where(filters)
    if w:
        where.append(w)
    where_sql = "WHERE " + " AND ".join(where)
    return f"SELECT {expr} AS value FROM sales_order so {join} {where_sql}"


def _yoy_sql(metric: str, filters: dict) -> str:
    expr = _metric_expr(metric)
    join = "JOIN product p ON p.product_id = so.product_id" if _needs_product_join(metric) else ""
    where = []
    w = _where(filters)
    if w:
        where.append(w)
    where.append("so.order_date >= '2024-01-01' AND so.order_date <= '2025-12-31'")
    where_sql = "WHERE " + " AND ".join(where)
    return (
        f"SELECT substr(so.order_date, 1, 4) AS year, {expr} AS value "
        f"FROM sales_order so {join} {where_sql} GROUP BY year ORDER BY year"
    )


def _shortage_sql(days_recent: int = 30, days_threshold: int = 15) -> str:
    start = (TODAY - timedelta(days=days_recent - 1)).isoformat()
    return (
        f"SELECT p.sku, p.product_name, p.category, i.quantity AS stock, i.safety_stock, "
        f"COALESCE(s.qty, 0) AS sales_recent, ROUND(COALESCE(s.qty, 0) / {days_recent}.0, 2) AS daily_avg, "
        f"CAST(i.quantity / MAX(COALESCE(s.qty, 0) / {days_recent}.0, 0.01) AS INTEGER) AS days_left "
        f"FROM inventory i "
        f"JOIN product p ON p.product_id = i.product_id "
        f"LEFT JOIN (SELECT product_id, SUM(quantity) AS qty FROM sales_order "
        f"WHERE order_date >= '{start}' GROUP BY product_id) s ON s.product_id = i.product_id "
        f"WHERE COALESCE(s.qty, 0) > 0 AND i.quantity / (COALESCE(s.qty, 0) / {days_recent}.0) < {days_threshold} "
        f"ORDER BY days_left ASC"
    )


def _repurchase_sql(time: dict, filters: dict) -> str:
    where = [f"so.order_date >= '{time['start']}' AND so.order_date <= '{time['end']}'"]
    if filters.get("customer_type"):
        where.append(f"c.customer_type = '{filters['customer_type']}'")
    where_sql = "WHERE " + " AND ".join(where)
    join = "JOIN customer c ON c.customer_id = so.customer_id" if filters.get("customer_type") else ""
    return (
        f"SELECT COUNT(DISTINCT CASE WHEN cnt >= 2 THEN customer_id END) AS repurchase_customers, "
        f"COUNT(DISTINCT customer_id) AS total_customers, "
        f"ROUND(100.0 * COUNT(DISTINCT CASE WHEN cnt >= 2 THEN customer_id END) / "
        f"COUNT(DISTINCT customer_id), 2) AS repurchase_rate "
        f"FROM (SELECT so.customer_id, COUNT(DISTINCT so.order_id) AS cnt "
        f"FROM sales_order so {join} {where_sql} GROUP BY so.customer_id)"
    )


def _defect_sql() -> str:
    return (
        "SELECT p.sku, p.product_name, SUM(qi.defect_qty) AS defect_qty, "
        "SUM(qi.total_qty) AS total_qty, "
        "ROUND(100.0 * SUM(qi.defect_qty) / SUM(qi.total_qty), 2) AS defect_rate "
        "FROM quality_inspection qi JOIN product p ON p.product_id = qi.product_id "
        "GROUP BY qi.product_id ORDER BY defect_rate DESC LIMIT 10"
    )


def _delay_sql(time: dict) -> str:
    return (
        "SELECT p.sku, p.product_name, COUNT(*) AS delay_count, "
        "ROUND(AVG(pd.delay_days), 1) AS avg_delay_days "
        "FROM production_delay pd JOIN product p ON p.product_id = pd.product_id "
        f"WHERE pd.planned_date >= '{time['start']}' "
        "GROUP BY pd.product_id ORDER BY avg_delay_days DESC LIMIT 10"
    )


def _decline_sql(metric: str, dimension: str, filters: dict) -> str:
    """两期对比：近 3 个月 vs 前 3 个月，计算环比变化。"""
    expr = _metric_expr(metric)
    dim_map = {
        "platform": "so.platform", "country": "so.country", "store": "s.store_name",
        "product": "p.product_name", "category": "p.category", "customer": "c.customer_name",
    }
    dim_col = dim_map.get(dimension, "so.platform")
    joins = ""
    if dimension == "store":
        joins += " JOIN store s ON s.store_id = so.store_id"
    if dimension == "product" or dimension == "category":
        joins += " JOIN product p ON p.product_id = so.product_id"
    if dimension == "customer":
        joins += " JOIN customer c ON c.customer_id = so.customer_id"

    cur_start = (TODAY - timedelta(days=90)).isoformat()
    prev_start = (TODAY - timedelta(days=180)).isoformat()
    cur_end = TODAY.isoformat()
    prev_end = (TODAY - timedelta(days=91)).isoformat()

    w = _where(filters)
    cur_where = f"so.order_date >= '{cur_start}' AND so.order_date <= '{cur_end}'"
    prev_where = f"so.order_date >= '{prev_start}' AND so.order_date <= '{prev_end}'"
    if w:
        cur_where += f" AND {w}"
        prev_where += f" AND {w}"

    return (
        f"SELECT cur.{dim_col.split('.')[-1]} AS name, cur.v AS current_value, prev.v AS previous_value, "
        f"ROUND(100.0 * (cur.v - prev.v) / prev.v, 2) AS change_pct "
        f"FROM (SELECT {dim_col}, {expr} AS v FROM sales_order so {joins} WHERE {cur_where} GROUP BY {dim_col}) cur "
        f"LEFT JOIN (SELECT {dim_col}, {expr} AS v FROM sales_order so {joins} WHERE {prev_where} GROUP BY {dim_col}) prev "
        f"ON cur.{dim_col.split('.')[-1]} = prev.{dim_col.split('.')[-1]} "
        f"ORDER BY change_pct ASC LIMIT 10"
    )


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def generate_sql(query: str, context: dict | None = None) -> dict:
    """把自然语言问题转成 SQL。context 为召回结果（当前规则引擎按需取用）。"""
    metric = _detect_metric(query)
    time = _parse_time(query)
    filters = _extract_filters(query)
    dimension = _detect_dimension(query)
    ranking = _detect_ranking(query)

    # 缺货预测
    if any(k in query for k in ["缺货", "库存不足", "可能缺货"]):
        m = re.search(r"(?:未来|接下来)?\s*(\d{1,3})\s*天", query)
        threshold = int(m.group(1)) if m else 15
        m2 = re.search(r"(?:最近|近)\s*(\d{1,3})\s*天", query)
        recent = int(m2.group(1)) if m2 else 30
        return {"sql": _shortage_sql(recent, threshold), "intent": "shortage",
                "metric": "库存", "dimension": "product", "filters": filters, "time": time}

    # 复购率
    if metric == "复购率":
        return {"sql": _repurchase_sql(time, filters), "intent": "repurchase",
                "metric": metric, "dimension": "customer", "filters": filters, "time": time}

    # 质检不合格率
    if metric == "质检不合格率":
        return {"sql": _defect_sql(), "intent": "defect",
                "metric": metric, "dimension": "product", "filters": filters, "time": time}

    # 生产延期
    if metric == "延期":
        return {"sql": _delay_sql(time), "intent": "delay",
                "metric": metric, "dimension": "product", "filters": filters, "time": time}

    # 同比
    if any(k in query for k in ["同比"]):
        return {"sql": _yoy_sql(metric, filters), "intent": "yoy",
                "metric": metric, "dimension": "year", "filters": filters, "time": time}

    # 因果型问题（为什么…下降/增长）：给出时间趋势，配合异常检测定位拐点
    if "为什么" in query:
        return {"sql": _trend_sql(metric, time, filters), "intent": "trend",
                "metric": metric, "dimension": "month", "filters": filters, "time": time}

    # 下降/下滑对比（针对「哪些 X 下降」类，非「为什么下降」）
    if any(k in query for k in ["下降", "下滑", "流失", "连续"]):
        return {"sql": _decline_sql(metric, dimension, filters), "intent": "decline",
                "metric": metric, "dimension": dimension, "filters": filters, "time": time}

    # 时间趋势（各月/趋势）
    if dimension == "month" and (ranking is None) and any(k in query for k in ["各月", "每月", "按月", "每个月", "逐月", "趋势", "变化"]):
        return {"sql": _trend_sql(metric, time, filters), "intent": "trend",
                "metric": metric, "dimension": "month", "filters": filters, "time": time}

    # 排名 / TOP N
    if ranking is not None or any(k in query for k in ["最高", "最多", "最低", "最慢", "最好", "排名", "TOP", "top", "前"]):
        rk = ranking or {"n": 10, "order": "DESC"}
        return {"sql": _rank_sql(metric, dimension, time, filters, rk), "intent": "rank",
                "metric": metric, "dimension": dimension, "filters": filters, "time": time}

    # 默认：总量
    return {"sql": _total_sql(metric, time, filters), "intent": "total",
            "metric": metric, "dimension": dimension, "filters": filters, "time": time}
