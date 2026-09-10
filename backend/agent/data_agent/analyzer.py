"""Result Analyzer —— SQL 结果分析、图表配置与异常检测。

把 SQL 原始结果转成前端可直接消费的：
    - 图表配置（line/bar/pie/scalar）
    - 指标卡
    - 自然语言结论
    - 异常检测结果（供 HYBRID 链路自动触发外部搜索）

不把原始数据直接丢给 LLM，而是先做结构分析，再生成结论。
"""


def _num(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def _fmt(x) -> str:
    x = _num(x)
    if abs(x) >= 10000:
        return f"{x/10000:.1f}万"
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if x == int(x):
        return str(int(x))
    return f"{x:,.1f}"


def _detect_anomalies(series: list[tuple]) -> list[dict]:
    """基于环比变化率检测异常点。返回 [{label, value, pct_change, reason}]。"""
    anomalies = []
    for i in range(1, len(series)):
        label, val = series[i]
        prev_label, prev_val = series[i - 1]
        if prev_val == 0:
            continue
        pct = (val - prev_val) / prev_val * 100
        if abs(pct) >= 15:
            direction = "下降" if pct < 0 else "上升"
            anomalies.append({
                "label": label,
                "value": val,
                "prev_value": prev_val,
                "pct_change": round(pct, 1),
                "reason": f"{label} 环比{direction} {abs(pct):.1f}%（{_fmt(prev_val)} → {_fmt(val)}）",
            })
    return anomalies


def analyze(query: str, intent: str, metric: str, dimension: str, rows: list[dict]) -> dict:
    """分析 SQL 结果，返回图表配置、指标、结论与异常。"""
    result = {
        "chart_type": "scalar",
        "chart": {},
        "metrics": [],
        "conclusion": "",
        "insights": [],
        "anomalies": [],
    }

    if not rows:
        result["conclusion"] = "查询结果为空，未找到匹配的企业经营数据。"
        return result

    if intent == "trend":
        return _analyze_trend(rows, metric)
    if intent == "rank":
        return _analyze_rank(rows, dimension)
    if intent == "total":
        return _analyze_total(rows, metric)
    if intent == "yoy":
        return _analyze_yoy(rows, metric)
    if intent == "shortage":
        return _analyze_shortage(rows)
    if intent == "repurchase":
        return _analyze_repurchase(rows)
    if intent == "defect":
        return _analyze_defect(rows)
    if intent == "delay":
        return _analyze_delay(rows)
    if intent == "decline":
        return _analyze_decline(rows)

    # 兜底：单值
    result["conclusion"] = f"查询完成，共返回 {len(rows)} 条数据。"
    return result


# ---------------------------------------------------------------------------
# 各意图分析
# ---------------------------------------------------------------------------
def _analyze_trend(rows: list[dict], metric: str) -> dict:
    series = [(r.get("month", ""), _num(r.get("value", 0))) for r in rows]
    labels = [s[0] for s in series]
    values = [s[1] for s in series]
    total = sum(values)
    peak = max(series, key=lambda x: x[1])
    anomalies = _detect_anomalies(series)

    conclusion = f"{len(series)} 个月累计{metric}为 {_fmt(total)}；峰值出现在 {peak[0]}（{_fmt(peak[1])}）。"
    if len(series) >= 2:
        first, last = values[0], values[-1]
        pct = (last - first) / first * 100 if first else 0
        conclusion += f" 整体呈{('上升' if pct >= 0 else '下降')}态势，期末较期初{('+' if pct >= 0 else '')}{pct:.1f}%。"
    # 点出最明显的环比下滑，呼应「为什么下降」类问题
    drops = [a for a in anomalies if a["pct_change"] < 0]
    if drops:
        worst_drop = min(drops, key=lambda a: a["pct_change"])
        conclusion += f" 其中 {worst_drop['label']} 出现明显环比下滑 {worst_drop['pct_change']:.1f}%。"

    return {
        "chart_type": "line",
        "chart": {
            "x_axis": labels,
            "series": [{"name": metric, "data": values}],
        },
        "metrics": [{"label": f"累计{metric}", "value": _fmt(total)}],
        "conclusion": conclusion,
        "insights": [a["reason"] for a in anomalies],
        "anomalies": anomalies,
    }


def _analyze_rank(rows: list[dict], dimension: str) -> dict:
    # 维度列名因 SQL 而异，取第一个非数值列
    keys = list(rows[0].keys())
    dim_col = next((k for k in keys if k not in ("value", "change_pct", "current_value", "previous_value")), keys[0])
    items = [(r.get(dim_col, ""), _num(r.get("value", 0))) for r in rows]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]

    top = items[0]
    total = sum(values)
    top_share = (top[1] / total * 100) if total else 0
    conclusion = f"排名第一的是「{top[0]}」（{_fmt(top[1])}），占整体 {top_share:.1f}%。共统计 {len(items)} 项。"

    return {
        "chart_type": "bar",
        "chart": {
            "x_axis": labels,
            "series": [{"name": "数值", "data": values}],
        },
        "metrics": [{"label": f"TOP1 · {top[0]}", "value": _fmt(top[1])}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }


def _analyze_total(rows: list[dict], metric: str) -> dict:
    v = _num(rows[0].get("value", 0))
    return {
        "chart_type": "scalar",
        "chart": {},
        "metrics": [{"label": metric, "value": _fmt(v)}],
        "conclusion": f"查询结果：{metric}为 {_fmt(v)}。",
        "insights": [],
        "anomalies": [],
    }


def _analyze_yoy(rows: list[dict], metric: str) -> dict:
    by_year = {r.get("year", ""): _num(r.get("value", 0)) for r in rows}
    labels = list(by_year.keys())
    values = [by_year[k] for k in labels]
    conclusion = ""
    if len(labels) >= 2:
        prev, cur = values[0], values[-1]
        pct = (cur - prev) / prev * 100 if prev else 0
        conclusion = f"{labels[-1]} 年{metric}为 {_fmt(cur)}，同比{('+' if pct >= 0 else '')}{pct:.1f}%。"
    return {
        "chart_type": "bar",
        "chart": {"x_axis": labels, "series": [{"name": metric, "data": values}]},
        "metrics": [{"label": f"{labels[-1]}年{metric}", "value": _fmt(values[-1] if values else 0)}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }


def _analyze_shortage(rows: list[dict]) -> dict:
    items = [(r.get("sku", ""), _num(r.get("days_left", 0)), _num(r.get("stock", 0))) for r in rows]
    labels = [i[0] for i in items]
    days = [i[1] for i in items]
    conclusion = f"共发现 {len(items)} 个 SKU 未来 15 天内可能缺货。"
    detail = "、".join(f"{sku}（约剩 {int(d)} 天）" for sku, d, _ in items[:5])
    if detail:
        conclusion += f" 最紧迫：{detail}。"
    return {
        "chart_type": "bar",
        "chart": {"x_axis": labels, "series": [{"name": "可支撑天数", "data": days}]},
        "metrics": [{"label": "缺货风险 SKU", "value": str(len(items))}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }


def _analyze_repurchase(rows: list[dict]) -> dict:
    r = rows[0]
    rate = _num(r.get("repurchase_rate", 0))
    return {
        "chart_type": "scalar",
        "chart": {},
        "metrics": [{"label": "复购率", "value": f"{rate:.1f}%"}],
        "conclusion": f"统计周期内复购率为 {rate:.1f}%（{r.get('repurchase_customers')} 人复购 / {r.get('total_customers')} 人下单）。",
        "insights": [],
        "anomalies": [],
    }


def _analyze_defect(rows: list[dict]) -> dict:
    items = [(r.get("product_name", ""), _num(r.get("defect_rate", 0))) for r in rows]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    worst = items[0]
    conclusion = f"质检不合格率最高的商品是「{worst[0]}」，不合格率 {worst[1]:.1f}%。"
    return {
        "chart_type": "bar",
        "chart": {"x_axis": labels, "series": [{"name": "不合格率(%)", "data": values}]},
        "metrics": [{"label": "最高不合格率", "value": f"{worst[1]:.1f}%"}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }


def _analyze_delay(rows: list[dict]) -> dict:
    items = [(r.get("product_name", ""), _num(r.get("avg_delay_days", 0))) for r in rows]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    slowest = items[0]
    conclusion = f"交付最慢的商品是「{slowest[0]}」，平均延期 {slowest[1]:.1f} 天。"
    return {
        "chart_type": "bar",
        "chart": {"x_axis": labels, "series": [{"name": "平均延期天数", "data": values}]},
        "metrics": [{"label": "最高平均延期", "value": f"{slowest[1]:.1f}天"}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }


def _analyze_decline(rows: list[dict]) -> dict:
    items = [(r.get("name", ""), _num(r.get("change_pct", 0))) for r in rows if r.get("change_pct") is not None]
    labels = [i[0] for i in items]
    values = [i[1] for i in items]
    if not items:
        return {"chart_type": "scalar", "chart": {}, "metrics": [],
                "conclusion": "未发现明显下降的商品/维度。", "insights": [], "anomalies": []}
    worst = items[0]
    conclusion = f"下降最明显的是「{worst[0]}」，环比 {worst[1]:.1f}%。"
    return {
        "chart_type": "bar",
        "chart": {"x_axis": labels, "series": [{"name": "环比变化(%)", "data": values}]},
        "metrics": [{"label": "最大降幅", "value": f"{worst[1]:.1f}%"}],
        "conclusion": conclusion,
        "insights": [],
        "anomalies": [],
    }
