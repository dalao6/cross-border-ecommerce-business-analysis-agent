"""ColumnMetric 映射器：在字段指标关联实体和 ORM 模型之间做双向转换。"""

from dataclasses import asdict

from backend.entities.column_metric import ColumnMetric
from backend.models.column_metric import ColumnMetricMySQL


class ColumnMetricMapper:
    """负责 `ColumnMetric` 与 `ColumnMetricMySQL` 之间的双向转换"""

    @staticmethod
    def to_entity(column_metric_mysql: ColumnMetricMySQL) -> ColumnMetric:
        return ColumnMetric(
            column_id=column_metric_mysql.column_id,
            metric_id=column_metric_mysql.metric_id,
        )

    @staticmethod
    def to_model(column_metric: ColumnMetric) -> ColumnMetricMySQL:
        return ColumnMetricMySQL(**asdict(column_metric))
