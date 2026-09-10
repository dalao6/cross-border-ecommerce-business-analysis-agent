"""字段与指标关联业务实体。"""

from dataclasses import dataclass


@dataclass
class ColumnMetric:
    """字段和指标之间的关联关系"""

    column_id: str
    metric_id: str
