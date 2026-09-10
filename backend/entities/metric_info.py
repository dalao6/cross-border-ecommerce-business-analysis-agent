"""指标元数据业务实体。"""

from dataclasses import dataclass


@dataclass
class MetricInfo:
    """系统内部统一使用的指标元数据表达"""

    id: str
    name: str
    description: str
    relevant_columns: list[str]
    alias: list[str]
