"""
召回信息合并步骤

把字段、字段取值、指标三路召回结果聚合成统一上下文，供前端展示与审计使用。
由于本项目的 NL2SQL 引擎是确定性规则实现（不依赖召回结果生成 SQL），
这里的合并主要服务于「三路召回 SSE 事件可见」与审计日志，不承担 SQL 上下文组装职责。
"""


def merge_retrieved_info(
    columns: list[dict], values: list[dict], metrics: list[dict]
) -> dict:
    """合并三路召回结果，返回结构化的展示摘要。"""
    table_names = sorted({c.get("table_name") for c in columns if c.get("table_name")})
    metric_names = [m.get("metric_name") for m in metrics if m.get("metric_name")]

    return {
        "table_names": table_names,
        "column_count": len(columns),
        "value_count": len(values),
        "metric_names": metric_names,
    }
