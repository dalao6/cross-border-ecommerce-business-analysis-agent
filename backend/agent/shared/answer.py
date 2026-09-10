"""最终答案合成（shared 层）。

把企业内部数据、外部公开信息与综合分析组装成前端可渲染的结构化答案。
核心原则（capsule 第十九/三十二节）：

    - 内部数据与外部信息严格分区，绝不混为一谈。
    - 综合判断基于事实推导，无法确认的部分一律标记「推测」。
"""

GROWTH_WORDS = ["增长", "上升", "走高", "扩大", "提升", "回暖"]
DECLINE_WORDS = ["下降", "放缓", "回落", "收缩", "下滑", "走弱", "疲软"]


def _direction(text: str) -> int:
    """粗略判断文本表达的市场方向：1 增长 / -1 下降 / 0 中性。"""
    g = sum(1 for w in GROWTH_WORDS if w in text)
    d = sum(1 for w in DECLINE_WORDS if w in text)
    if g > d:
        return 1
    if d > g:
        return -1
    return 0


def _external_summary(external: dict) -> str:
    results = external.get("results", [])
    if not results:
        return external.get("note", "未检索到高度相关的公开信息。")
    parts = []
    for r in results[:3]:
        parts.append(f"· {r['title']}（来源：{r['source']}，可信度：{r['credibility']}）：{r['summary']}")
    return "\n".join(parts)


def _marketplace_summary(external: dict) -> str:
    products = external.get("results", [])
    details = external.get("details", []) or []
    if not products:
        return external.get("note", "未检索到跨境平台商品。")
    n_total = len(products)
    n_detail = sum(1 for d in details if d.get("detail", {}).get("ok"))
    platforms = sorted({p["platform"] for p in products})
    return (
        f"覆盖 {', '.join(platforms)} 共 {n_total} 个商品链接"
        + (f"，其中 {n_detail} 个已完成详情抓取" if n_detail else "")
        + "。"
    )


def _synthesize_hybrid(query: str, internal: dict, external: dict) -> dict:
    """基于内部 + 外部信息做交叉分析，返回综合判断文本与「推测」标记。"""
    uncertain = []
    analysis = internal.get("analysis", {})
    conclusion = analysis.get("conclusion", "")
    anomalies = analysis.get("anomalies", [])
    results = external.get("results", [])

    # 内部方向（看整体趋势措辞，而非异常点提及）
    internal_growing = "整体呈上升" in conclusion
    internal_declining = "整体呈下降" in conclusion

    # 外部方向
    ext_dir = 0
    for r in results:
        ext_dir += _direction(r["summary"] + r["content"])
    if results:
        ext_dir = 1 if ext_dir > 0 else (-1 if ext_dir < 0 else 0)

    # 外部规则/政策类信源
    rule_sources = [r for r in results if any(
        k in (r["title"] + r["summary"]) for k in ["规则", "政策", "佣金", "合规", "治理", "调整", "公告"])]

    sentences = []

    # ---- Case A：平台规则 / 政策变化对销量的影响 ----
    if any(k in query for k in ["规则", "政策", "会不会影响", "影响"]):
        if rule_sources:
            titles = "、".join(f"「{r['title']}」" for r in rule_sources[:2])
            sentences.append(f"外部公开信息显示存在平台规则/政策调整：{titles}。")
        if internal_growing:
            sentences.append("企业内部数据显示相关平台销量整体仍处上升通道，短期未出现明显负面冲击。")
            sentences.append("但规则/政策变化可能在中长期抬升获客成本或改变流量分配，需持续跟踪其影响。")
            uncertain.append("规则变化对销量的量化影响尚难精确测算，属推测。")
        elif internal_declining:
            sentences.append("企业内部数据显示相关平台销量已现回落，规则/政策变化可能是影响因素之一。")
            uncertain.append("销量回落与规则变化的因果关联尚未验证，属推测。")
        else:
            sentences.append("已结合平台规则变化与企业内部数据完成交叉分析（详见上方分区）。")
        return {"content": "\n".join(sentences), "uncertain": uncertain}

    # ---- Case B：为什么下降 ----
    if "下降" in query or "下滑" in query or internal_declining:
        worst = None
        for a in anomalies:
            if a["pct_change"] < 0 and (worst is None or a["pct_change"] < worst["pct_change"]):
                worst = a
        if worst:
            sentences.append(f"企业内部数据显示，{worst['label']} 出现明显下滑：{worst['reason']}。")
        if ext_dir >= 0:
            sentences.append(
                "同期外部公开信息显示，目标市场整体并未同步走弱，甚至保持增长。"
                "因此本次下滑更可能源于企业自身因素（平台流量、店铺运营、商品结构、价格或履约等），"
                "而非单纯的市场环境所致。"
            )
            uncertain.append("下滑的具体内因（平台/店铺/商品/客户）尚未定位，属推测，需进一步下钻验证。")
            sentences.append("建议继续下钻：平台 → 店铺 → 商品 → 客户，定位具体流失来源。")
        else:
            sentences.append("外部公开信息显示市场整体同期亦走弱，企业下滑与外部环境相关性较高，受宏观/行业因素影响较大。")

    # ---- Case C：增长 / 是否符合趋势 ----
    elif "增长" in query or "符合" in query:
        if ext_dir > 0:
            sentences.append("外部公开信息显示当地市场处于增长通道，企业内部增长与市场整体趋势方向一致，属顺势增长。")
        else:
            sentences.append("企业内部虽增长，但外部市场并无明显同步信号，需关注增长是否来自结构性/一次性因素。")
            uncertain.append("增长驱动因素尚未确认，属推测。")

    # ---- 兜底 ----
    else:
        sentences.append("已结合企业内部数据与外部公开信息完成交叉分析，二者可互相印证/存在差异（详见上方分区）。")

    return {
        "content": "\n".join(sentences),
        "uncertain": uncertain,
    }


def build_answer(intent: str, query: str, internal: dict | None = None,
                 external: dict | None = None, marketplace: dict | None = None) -> dict:
    """组装最终答案对象。

    三种执行结果可任意组合：
        internal    —— 企业数据库链路
        external    —— 互联网公开信息搜索
        marketplace —— 跨境平台商品搜索 + 详情抓取
    """
    sections = []

    # 企业内部数据分区
    if internal is not None:
        analysis = internal.get("analysis", {})
        sec = {
            "key": "internal",
            "title": "企业内部数据",
            "conclusion": analysis.get("conclusion", ""),
            "insights": analysis.get("insights", []),
            "metrics": analysis.get("metrics", []),
            "chart_type": analysis.get("chart_type", "scalar"),
            "chart": analysis.get("chart", {}),
            "sql": internal.get("sql", ""),
            "table": internal.get("table", {}),
            "source": "企业数据库（内部权威数据）",
        }
        sections.append(sec)

    # 跨境平台商品情报分区（marketplace 链路专属）
    if marketplace is not None:
        sec = {
            "key": "marketplace",
            "title": "跨境平台商品情报",
            "summary": _marketplace_summary(marketplace),
            "platforms": marketplace.get("platforms", []),
            "products": marketplace.get("results", []),
            "details": marketplace.get("details", []),
            "backend": marketplace.get("backend", "?"),
            "note": marketplace.get("note", ""),
            "source": "跨境平台公开商品数据（演示）",
        }
        sections.append(sec)
        external = None  # marketplace 已独立渲染，避免重复

    # 外部公开信息分区
    if external is not None:
        # 区分传统"网络公开信息"与"跨境平台商品"两种外部数据
        is_marketplace = bool(external.get("platforms")) or "details" in external
        if is_marketplace and marketplace is None:
            sec = {
                "key": "marketplace",
                "title": "跨境平台商品情报",
                "summary": _marketplace_summary(external),
                "platforms": external.get("platforms", []),
                "products": external.get("results", []),
                "details": external.get("details", []),
                "backend": external.get("backend", "?"),
                "note": external.get("note", ""),
                "source": "跨境平台公开商品数据（演示）",
            }
        else:
            results = external.get("results", [])
            sec = {
                "key": "external",
                "title": "外部公开信息",
                "summary": _external_summary(external),
                "sources": [
                    {
                        "title": r["title"],
                        "source": r["source"],
                        "url": r["url"],
                        "published_time": r["published_time"],
                        "credibility": r["credibility"],
                        "summary": r["summary"],
                    }
                    for r in results
                ],
            }
        sections.append(sec)

    # 综合判断分区（仅混合分析）
    summary = ""
    uncertain = []
    if intent == "HYBRID_ANALYSIS" and internal is not None and external is not None:
        syn = _synthesize_hybrid(query, internal, external)
        sections.append({
            "key": "conclusion",
            "title": "综合判断",
            "content": syn["content"],
            "uncertain": syn["uncertain"],
        })
        uncertain = syn["uncertain"]

    # 顶层摘要：取第一个分区的结论
    for s in sections:
        if s["key"] == "internal":
            summary = s["conclusion"]
            break
        if s["key"] == "marketplace":
            summary = s.get("summary", "")[:160]
            break
        if s["key"] == "external":
            summary = s.get("summary", "")[:120]
            break

    return {
        "intent": intent,
        "query": query,
        "summary": summary,
        "sections": sections,
        "uncertain": uncertain,
    }
